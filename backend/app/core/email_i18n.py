"""Textes d’e-mails transactionnels (fr / en). La langue vient de l’utilisateur ou du défaut instance."""

from __future__ import annotations

from typing import Any, Optional

from app.core.config import settings

SUPPORTED = frozenset({"en", "fr"})


def normalize_locale(raw: Optional[str]) -> str:
    if not raw:
        return settings.DEFAULT_NOTIFICATION_LOCALE
    x = str(raw).strip().lower()[:8]
    if x.startswith("en"):
        return "en"
    if x.startswith("fr"):
        return "fr"
    return settings.DEFAULT_NOTIFICATION_LOCALE


def locale_for_user(user: Optional[Any]) -> str:
    if user is None:
        return normalize_locale(None)
    return normalize_locale(getattr(user, "preferred_locale", None))


def deadline_alert(locale: str, full_name: str, ref: str, title: str) -> tuple[str, str]:
    loc = normalize_locale(locale)
    if loc == "en":
        subj = f"Deadline alert: {ref}"
        body = (
            f"Dear {full_name},\n\n"
            f"This is an alert that document {ref} ({title}) has passed its response deadline.\n\n"
            f"Please review and take appropriate action.\n\n"
            f"Best regards,\n{settings.PROJECT_NAME}"
        )
    else:
        subj = f"Alerte échéance : {ref}"
        body = (
            f"Bonjour {full_name},\n\n"
            f"Le courrier {ref} ({title}) a dépassé la date limite de réponse.\n\n"
            f"Merci d’examiner le dossier et d’agir en conséquence.\n\n"
            f"Cordialement,\n{settings.PROJECT_NAME}"
        )
    return subj, body.strip()


def appointment_reminder(
    locale: str, visitor_name: str, title: str, when: str, location: str, organizer_name: str
) -> tuple[str, str]:
    loc = normalize_locale(locale)
    loc_hint = location or ("To be confirmed" if loc == "en" else "À confirmer")
    if loc == "en":
        subj = f"Appointment reminder: {title}"
        body = (
            f"Dear {visitor_name},\n\n"
            f"This is a reminder that you have an appointment scheduled for:\n"
            f"Date: {when}\n"
            f"Location: {loc_hint}\n"
            f"Host: {organizer_name}\n\n"
            f"Please arrive on time. If you need to reschedule, please contact us.\n\n"
            f"Best regards,\n{settings.PROJECT_NAME}"
        )
    else:
        subj = f"Rappel de rendez-vous : {title}"
        body = (
            f"Bonjour {visitor_name},\n\n"
            f"Nous vous rappelons votre rendez-vous :\n"
            f"Date : {when}\n"
            f"Lieu : {loc_hint}\n"
            f"Interlocuteur : {organizer_name}\n\n"
            f"Merci d’arriver à l’heure. Pour décaler le rendez-vous, contactez-nous.\n\n"
            f"Cordialement,\n{settings.PROJECT_NAME}"
        )
    return subj, body.strip()


def booking_confirmed_plain(
    locale: str,
    visitor_name: str,
    title: str,
    when: str,
    org_name: str,
    location: str,
    *,
    has_qr_inline: bool = False,
) -> str:
    loc = normalize_locale(locale)
    loc_disp = location or ("—" if loc == "fr" else "—")
    qr_note_en = (
        "\n\nThe HTML version of this message includes your check-in QR code as an inline image."
        if has_qr_inline
        else ""
    )
    qr_note_fr = (
        "\n\nLa version HTML de ce message inclut votre code QR d’accueil en image intégrée."
        if has_qr_inline
        else ""
    )
    if loc == "en":
        return (
            f"Dear {visitor_name},\n\n"
            f"Your appointment request has been confirmed.\n\n"
            f"Title: {title}\n"
            f"When: {when}\n"
            f"Host: {org_name}\n"
            f"Location: {loc_disp}\n\n"
            f"Please bring this email or your QR code when you arrive.{qr_note_en}\n\n"
            f"Best regards,\n{settings.PROJECT_NAME}"
        ).strip()
    return (
        f"Bonjour {visitor_name},\n\n"
        f"Votre demande de rendez-vous est confirmée.\n\n"
        f"Titre : {title}\n"
        f"Date : {when}\n"
        f"Interlocuteur : {org_name}\n"
        f"Lieu : {loc_disp}\n\n"
        f"Présentez cet e-mail ou votre QR code à votre arrivée.{qr_note_fr}\n\n"
        f"Cordialement,\n{settings.PROJECT_NAME}"
    ).strip()


def booking_confirmed_html(
    locale: str,
    visitor_name: str,
    title: str,
    when: str,
    org_name: str,
    location: str,
    qr_inline_cid: Optional[str],
) -> str:
    """qr_inline_cid : identifiant sans préfixe cid: (ex. booking_qr), image jointe multipart/related."""
    loc = normalize_locale(locale)
    loc_disp = location or "—"
    if loc == "en":
        parts = [
            f"<p>Dear {visitor_name},</p>",
            "<p>Your appointment request has been <strong>confirmed</strong>.</p>",
            "<ul>",
            f"<li><strong>Title:</strong> {title}</li>",
            f"<li><strong>When:</strong> {when}</li>",
            f"<li><strong>Host:</strong> {org_name}</li>",
            f"<li><strong>Location:</strong> {loc_disp}</li>",
            "</ul>",
        ]
        if qr_inline_cid:
            parts.append(
                f'<p><img src="cid:{qr_inline_cid}" alt="Check-in QR" style="max-width:220px;height:auto;" /></p>'
            )
        parts.append(f"<p>Best regards,<br/>{settings.PROJECT_NAME}</p>")
    else:
        parts = [
            f"<p>Bonjour {visitor_name},</p>",
            "<p>Votre demande de rendez-vous est <strong>confirmée</strong>.</p>",
            "<ul>",
            f"<li><strong>Titre :</strong> {title}</li>",
            f"<li><strong>Date :</strong> {when}</li>",
            f"<li><strong>Interlocuteur :</strong> {org_name}</li>",
            f"<li><strong>Lieu :</strong> {loc_disp}</li>",
            "</ul>",
        ]
        if qr_inline_cid:
            parts.append(
                f'<p><img src="cid:{qr_inline_cid}" alt="QR d’accueil" style="max-width:220px;height:auto;" /></p>'
            )
        parts.append(f"<p>Cordialement,<br/>{settings.PROJECT_NAME}</p>")
    return "".join(parts)


def booking_confirmed_subject(locale: str, title: str) -> str:
    loc = normalize_locale(locale)
    if loc == "en":
        return f"Appointment confirmed: {title}"
    return f"Rendez-vous confirmé : {title}"


def mail_validation_required(locale: str, ref: str, title: str) -> tuple[str, str]:
    loc = normalize_locale(locale)
    if loc == "en":
        return (
            f"Validation required — {ref}",
            f"A validation is required for mail item {ref} ({title}).",
        )
    return (
        f"Validation requise — {ref}",
        f"Une validation est requise pour le courrier {ref} ({title}).",
    )


def mail_workflow_hold(locale: str, ref: str, title: str) -> tuple[str, str]:
    loc = normalize_locale(locale)
    if loc == "en":
        return (
            f"On hold — {ref}",
            f"Mail item {ref} ({title}) has been put on hold. Please check the mail module for next steps.",
        )
    return (
        f"Mise en attente — {ref}",
        f"Le courrier {ref} ({title}) a été mis en attente. Consultez la GED pour la suite du traitement.",
    )


def mail_workflow_request_changes(locale: str, ref: str, title: str) -> tuple[str, str]:
    loc = normalize_locale(locale)
    if loc == "en":
        return (
            f"Further information requested — {ref}",
            f"Further information has been requested for mail item {ref} ({title}). Please update the case in the mail module.",
        )
    return (
        f"Compléments demandés — {ref}",
        f"Des compléments ont été demandés pour le courrier {ref} ({title}). Merci de mettre à jour le dossier dans la GED.",
    )


def mail_workflow_reject(locale: str, ref: str, title: str) -> tuple[str, str]:
    loc = normalize_locale(locale)
    if loc == "en":
        return (
            f"Mail item rejected — {ref}",
            f"Mail item {ref} ({title}) has been rejected. Check the mail module for history and next steps.",
        )
    return (
        f"Courrier rejeté — {ref}",
        f"Le courrier {ref} ({title}) a été rejeté. Consultez la GED pour l’historique et les prochaines étapes.",
    )
