import asyncio
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Literal, Optional, Tuple
import uuid as uuid_lib
from sqlalchemy.orm import Session
import logging

from app.core.config import settings
from app.core.email_i18n import (
    appointment_reminder,
    booking_confirmed_html,
    booking_confirmed_plain,
    booking_confirmed_subject,
    deadline_alert,
    locale_for_user,
    mail_validation_required,
    mail_workflow_hold,
    mail_workflow_reject,
    mail_workflow_request_changes,
    normalize_locale,
)
from app.services.storage_service import storage_service
from app.services.qr_service import build_appointment_qr_png_bytes
from app.models.notification import Notification, NotificationType, NotificationStatus
from app.models.appointment import Appointment
from app.models.mail import MailDocument
from app.models.user import User

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications via email and SMS"""

    def __init__(self) -> None:
        # Une seule connexion SMTP à la fois (Gmail et autres limitent les sessions parallèles).
        self._smtp_send_lock: Optional[asyncio.Lock] = None
        self._smtp_lock_loop: Optional[asyncio.AbstractEventLoop] = None

    def _smtp_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if self._smtp_send_lock is None or self._smtp_lock_loop is not loop:
            self._smtp_lock_loop = loop
            self._smtp_send_lock = asyncio.Lock()
        return self._smtp_send_lock

    async def send_email(
        self,
        to_email: str,
        subject: str,
        message: str,
        html_message: Optional[str] = None,
        inline_png_cid_parts: Optional[List[Tuple[str, bytes]]] = None,
    ) -> bool:
        """Send email via SMTP.

        inline_png_cid_parts: liste (content_id_sans_crochets, png_bytes) pour <img src="cid:...">.
        Utilisé pour le QR : les data: URLs sont souvent bloquées par les webmails.
        """
        # Check if SMTP is configured
        host = (settings.SMTP_HOST or "").strip()
        if not host:
            logger.warning("SMTP not configured, email sending skipped")
            return False

        try:
            if inline_png_cid_parts:
                message_obj = MIMEMultipart("related")
                message_obj["From"] = settings.SMTP_FROM or "noreply@fpi-connect.local"
                message_obj["To"] = to_email
                message_obj["Subject"] = subject
                msg_alt = MIMEMultipart("alternative")
                msg_alt.attach(MIMEText(message, "plain", "utf-8"))
                if html_message:
                    msg_alt.attach(MIMEText(html_message, "html", "utf-8"))
                message_obj.attach(msg_alt)
                for cid, raw_png in inline_png_cid_parts:
                    img = MIMEImage(raw_png, _subtype="png")
                    img.add_header("Content-ID", f"<{cid}>")
                    img.add_header("Content-Disposition", "inline", filename=f"{cid}.png")
                    message_obj.attach(img)
            else:
                message_obj = MIMEMultipart("alternative")
                message_obj["From"] = settings.SMTP_FROM or "noreply@fpi-connect.local"
                message_obj["To"] = to_email
                message_obj["Subject"] = subject
                message_obj.attach(MIMEText(message, "plain", "utf-8"))
                if html_message:
                    message_obj.attach(MIMEText(html_message, "html", "utf-8"))

            # Coercion explicite : si le port arrive en str depuis l’env, "465" == 465 est faux et casse TLS.
            port = int(settings.SMTP_PORT)
            use_tls = bool(settings.SMTP_USE_TLS)
            # Port 465 : TLS implicite. Sinon (ex. 587) : STARTTLS si SMTP_USE_TLS.
            use_implicit = use_tls and port == 465
            start_tls = (use_tls and port != 465) if use_tls else False

            async with self._smtp_lock():
                await aiosmtplib.send(
                    message_obj,
                    hostname=host,
                    port=port,
                    username=settings.SMTP_USER if settings.SMTP_USER else None,
                    password=settings.SMTP_PASSWORD if settings.SMTP_PASSWORD else None,
                    use_tls=use_implicit,
                    start_tls=start_tls,
                    timeout=90.0,
                )
            logger.info(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            logger.error(
                "Failed to send email to %s: %s: %s",
                to_email,
                type(e).__name__,
                e,
                exc_info=False,
            )
            return False
    
    async def create_notification(
        self,
        db: Session,
        notification_type: NotificationType,
        message: str,
        recipient_id: Optional[uuid_lib.UUID] = None,
        recipient_email: Optional[str] = None,
        recipient_phone: Optional[str] = None,
        subject: Optional[str] = None,
        template_name: Optional[str] = None,
        related_document_id: Optional[uuid_lib.UUID] = None,
        related_appointment_id: Optional[uuid_lib.UUID] = None,
    ) -> Notification:
        """Create notification record"""
        notification = Notification(
            recipient_id=recipient_id,
            recipient_email=recipient_email,
            recipient_phone=recipient_phone,
            notification_type=notification_type,
            status=NotificationStatus.PENDING,
            subject=subject,
            message=message,
            template_name=template_name,
            related_document_id=related_document_id,
            related_appointment_id=related_appointment_id
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification
    
    async def send_notification(
        self,
        db: Session,
        notification: Notification,
        html_message: Optional[str] = None,
        inline_png_cid_parts: Optional[List[Tuple[str, bytes]]] = None,
    ) -> bool:
        """Send notification and update status"""
        try:
            if notification.notification_type == NotificationType.EMAIL:
                if not notification.recipient_email:
                    raise ValueError("Email address required for email notification")
                
                success = await self.send_email(
                    notification.recipient_email,
                    notification.subject or "Notification",
                    notification.message,
                    html_message=html_message,
                    inline_png_cid_parts=inline_png_cid_parts,
                )
                
                if success:
                    notification.status = NotificationStatus.SENT
                    notification.sent_at = datetime.utcnow()
                else:
                    notification.status = NotificationStatus.FAILED
                    notification.error_message = "Failed to send email"
            
            elif notification.notification_type == NotificationType.SMS:
                # Placeholder for SMS implementation
                notification.status = NotificationStatus.FAILED
                notification.error_message = "SMS not yet implemented"
            
            db.commit()
            return notification.status == NotificationStatus.SENT
        
        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.error_message = str(e)
            notification.retry_count += 1
            db.commit()
            return False
    
    async def send_appointment_reminder(
        self,
        db: Session,
        appointment: Appointment
    ) -> bool:
        """Send appointment reminder email"""
        if not appointment.visitor_email:
            return False

        reminder_time = appointment.start_time.strftime("%Y-%m-%d %H:%M")
        loc = normalize_locale(settings.DEFAULT_NOTIFICATION_LOCALE)
        subj, message = appointment_reminder(
            loc,
            appointment.visitor_name,
            appointment.title,
            reminder_time,
            appointment.location or "",
            appointment.organizer.full_name,
        )

        notification = await self.create_notification(
            db,
            NotificationType.EMAIL,
            message,
            recipient_email=appointment.visitor_email,
            subject=subj,
            related_appointment_id=appointment.id
        )

        return await self.send_notification(db, notification)
    
    async def send_deadline_alert(
        self,
        db: Session,
        document: MailDocument
    ) -> bool:
        """Send deadline alert for overdue document"""
        # Get assigned user email
        if not document.assigned_to_user or not document.assigned_to_user.email:
            return False

        loc = locale_for_user(document.assigned_to_user)
        subj, message = deadline_alert(
            loc,
            document.assigned_to_user.full_name,
            document.reference_number,
            document.title,
        )

        notification = await self.create_notification(
            db,
            NotificationType.EMAIL,
            message,
            recipient_id=document.assigned_to_user.id,
            recipient_email=document.assigned_to_user.email,
            subject=subj,
            related_document_id=document.id
        )

        return await self.send_notification(db, notification)

    async def send_public_booking_confirmation(
        self,
        db: Session,
        appointment: Appointment,
    ) -> bool:
        """Email visitor after reception finalizes the appointment (public or internal; includes QR if present)."""
        if not appointment.visitor_email:
            return False

        from sqlalchemy.orm import joinedload

        apt = (
            db.query(Appointment)
            .options(joinedload(Appointment.visitor), joinedload(Appointment.organizer))
            .filter(Appointment.id == appointment.id)
            .first()
        )
        if not apt:
            return False

        when = apt.start_time.strftime("%Y-%m-%d %H:%M")
        org_name = apt.organizer.full_name if apt.organizer else ""
        loc = normalize_locale(settings.DEFAULT_NOTIFICATION_LOCALE)
        qr_png: Optional[bytes] = None
        if apt.visitor and getattr(apt.visitor, "qr_code_path", None):
            try:
                qr_png = await storage_service.get_file(apt.visitor.qr_code_path)
            except Exception:
                qr_png = None
        if qr_png is None:
            try:
                qr_png = build_appointment_qr_png_bytes(apt.id)
            except Exception:
                qr_png = None

        qr_cid = "booking_qr" if qr_png else None
        loc_disp = apt.location or ""
        plain = booking_confirmed_plain(
            loc,
            apt.visitor_name,
            apt.title,
            when,
            org_name,
            loc_disp,
            has_qr_inline=bool(qr_png),
        )
        html_message = booking_confirmed_html(
            loc, apt.visitor_name, apt.title, when, org_name, loc_disp, qr_cid
        )
        subj = booking_confirmed_subject(loc, apt.title)

        notification = await self.create_notification(
            db,
            NotificationType.EMAIL,
            plain,
            recipient_email=str(apt.visitor_email),
            subject=subj,
            related_appointment_id=apt.id,
        )
        inline = [("booking_qr", qr_png)] if qr_png else None
        return await self.send_notification(
            db, notification, html_message=html_message, inline_png_cid_parts=inline
        )

    async def send_mail_validation_required_emails(
        self,
        db: Session,
        document: MailDocument,
        recipient_user_ids: List[uuid_lib.UUID],
    ) -> int:
        """E-mail aux utilisateurs devant valider un courrier (soumission validation)."""
        if not recipient_user_ids:
            return 0
        users = db.query(User).filter(User.id.in_(recipient_user_ids), User.email.isnot(None)).all()
        sent = 0
        for u in users:
            loc = locale_for_user(u)
            subj, msg = mail_validation_required(
                loc, document.reference_number, document.title
            )
            n = await self.create_notification(
                db,
                NotificationType.EMAIL,
                msg,
                recipient_id=u.id,
                recipient_email=u.email,
                subject=subj,
                related_document_id=document.id,
            )
            if await self.send_notification(db, n):
                sent += 1
        return sent

    async def send_mail_workflow_event_emails(
        self,
        db: Session,
        document: MailDocument,
        recipient_user_ids: List[uuid_lib.UUID],
        event: Literal["hold", "request_changes", "reject"],
    ) -> int:
        """E-mails workflow courrier (attente, compléments, rejet), langue par destinataire."""
        if not recipient_user_ids:
            return 0
        fn = {
            "hold": mail_workflow_hold,
            "request_changes": mail_workflow_request_changes,
            "reject": mail_workflow_reject,
        }[event]
        users = (
            db.query(User)
            .filter(User.id.in_(recipient_user_ids), User.email.isnot(None))
            .all()
        )
        sent = 0
        ref, title = document.reference_number, document.title
        for u in users:
            loc = locale_for_user(u)
            subj, body = fn(loc, ref, title)
            n = await self.create_notification(
                db,
                NotificationType.EMAIL,
                body,
                recipient_id=u.id,
                recipient_email=u.email,
                subject=subj,
                related_document_id=document.id,
            )
            if await self.send_notification(db, n):
                sent += 1
        return sent


notification_service = NotificationService()

