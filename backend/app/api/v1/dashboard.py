"""Indicateurs agrégés pour le tableau de bord."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.effective_permissions import user_has_permission
from app.core.security import get_current_user
from app.models.appointment import Appointment
from app.models.appointment_task import AppointmentTask, AppointmentTaskStatus
from app.models.mail import MailDocument, MailStatus
from app.models.user import User
from app.services.mail_kpi_delays import compute_mail_delay_kpis

router = APIRouter()


@router.get("/kpi", response_model=Dict[str, Any])
async def dashboard_kpi(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_has_permission(current_user, "dashboard.kpi"):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    show_org = user_has_permission(current_user, "dashboard.kpi.org")

    mine_mail_filter = or_(
        MailDocument.assigned_to == current_user.id,
        MailDocument.created_by == current_user.id,
    )
    mine_mail_rows = (
        db.query(MailDocument.status, func.count(MailDocument.id))
        .filter(mine_mail_filter)
        .group_by(MailDocument.status)
        .all()
    )
    mine_mail_by_status: Dict[str, int] = {}
    for s, c in mine_mail_rows:
        key = str(s.value if hasattr(s, "value") else s)
        mine_mail_by_status[key] = mine_mail_by_status.get(key, 0) + int(c)
    mine_overdue = (
        db.query(func.count(MailDocument.id))
        .filter(MailDocument.is_overdue.is_(True))
        .filter(mine_mail_filter)
        .scalar()
        or 0
    )
    mine_pending_validation = (
        db.query(func.count(MailDocument.id))
        .filter(MailDocument.status == MailStatus.PENDING_VALIDATION)
        .filter(mine_mail_filter)
        .scalar()
        or 0
    )
    mine_on_hold = (
        db.query(func.count(MailDocument.id))
        .filter(MailDocument.status == MailStatus.ON_HOLD)
        .filter(mine_mail_filter)
        .scalar()
        or 0
    )
    mine_mail_total_all = db.query(func.count(MailDocument.id)).filter(mine_mail_filter).scalar() or 0

    mine_appt_rows = (
        db.query(Appointment.status, func.count(Appointment.id))
        .filter(
            Appointment.organizer_id == current_user.id,
            Appointment.archived_at.is_(None),
        )
        .group_by(Appointment.status)
        .all()
    )
    mine_appt_by_status: Dict[str, int] = {}
    for st, c in mine_appt_rows:
        key = str(st.value if hasattr(st, "value") else st)
        mine_appt_by_status[key] = mine_appt_by_status.get(key, 0) + int(c)
    mine_appt_total_all = (
        db.query(func.count(Appointment.id))
        .filter(
            Appointment.organizer_id == current_user.id,
            Appointment.archived_at.is_(None),
        )
        .scalar()
        or 0
    )

    mail_by_status: Dict[str, int] = {}
    appt_by_status: Dict[str, int] = {}
    mail_total_all = 0
    overdue = 0
    appointments_total_all = 0
    pending_validation = 0
    on_hold = 0
    mail_delays: Optional[Dict[str, Any]] = None

    if show_org:
        mail_rows = db.query(MailDocument.status, func.count(MailDocument.id)).group_by(MailDocument.status).all()
        for s, c in mail_rows:
            key = str(s.value if hasattr(s, "value") else s)
            mail_by_status[key] = mail_by_status.get(key, 0) + int(c)
        mail_total_all = db.query(func.count(MailDocument.id)).scalar() or 0
        overdue = db.query(func.count(MailDocument.id)).filter(MailDocument.is_overdue.is_(True)).scalar() or 0

        appt_active = Appointment.archived_at.is_(None)
        appt_rows = (
            db.query(Appointment.status, func.count(Appointment.id))
            .filter(appt_active)
            .group_by(Appointment.status)
            .all()
        )
        for st, c in appt_rows:
            key = st.value if hasattr(st, "value") else str(st)
            key = str(key)
            appt_by_status[key] = appt_by_status.get(key, 0) + int(c)
        appointments_total_all = db.query(func.count(Appointment.id)).filter(appt_active).scalar() or 0

        pending_validation = (
            db.query(func.count(MailDocument.id))
            .filter(MailDocument.status == MailStatus.PENDING_VALIDATION)
            .scalar()
            or 0
        )
        on_hold = (
            db.query(func.count(MailDocument.id))
            .filter(MailDocument.status == MailStatus.ON_HOLD)
            .scalar()
            or 0
        )
        mail_delays = compute_mail_delay_kpis(db)

    if show_org:
        open_tasks = (
            db.query(func.count(AppointmentTask.id))
            .join(Appointment, AppointmentTask.appointment_id == Appointment.id)
            .filter(
                AppointmentTask.status == AppointmentTaskStatus.OPEN,
                Appointment.archived_at.is_(None),
            )
            .scalar()
            or 0
        )
    else:
        open_tasks = (
            db.query(func.count(AppointmentTask.id))
            .join(Appointment, AppointmentTask.appointment_id == Appointment.id)
            .filter(
                AppointmentTask.status == AppointmentTaskStatus.OPEN,
                Appointment.archived_at.is_(None),
                Appointment.organizer_id == current_user.id,
            )
            .scalar()
            or 0
        )

    return {
        "organization_metrics": show_org,
        "mail": {
            "by_status": mail_by_status,
            "overdue": int(overdue),
            "total": int(mail_total_all),
            "pending_validation": int(pending_validation),
            "on_hold": int(on_hold),
            "delays": mail_delays,
            "mine_by_status": mine_mail_by_status,
            "mine_total": int(mine_mail_total_all),
            "mine_overdue": int(mine_overdue),
            "mine_pending_validation": int(mine_pending_validation),
            "mine_on_hold": int(mine_on_hold),
        },
        "appointments": {
            "by_status": appt_by_status,
            "total": int(appointments_total_all),
            "mine_by_status": mine_appt_by_status,
            "mine_total": int(mine_appt_total_all),
        },
        "appointment_open_tasks": int(open_tasks),
    }
