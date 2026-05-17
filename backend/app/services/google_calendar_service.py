from datetime import datetime, timedelta
from typing import Optional, List
from urllib.parse import quote

import aiohttp

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.user import User


class GoogleCalendarService:
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

    def is_configured(self) -> bool:
        return bool(
            settings.GOOGLE_CLIENT_ID
            and settings.GOOGLE_CLIENT_SECRET
            and settings.GOOGLE_REDIRECT_URI
        )

    async def exchange_code(self, code: str) -> Optional[dict]:
        if not self.is_configured():
            return None
        payload = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.TOKEN_URL, data=payload) as response:
                if response.status != 200:
                    return None
                return await response.json()

    async def refresh_access_token(self, user: User) -> Optional[str]:
        if not self.is_configured() or not user.google_refresh_token:
            return None
        if (
            user.google_access_token
            and user.google_access_token_expires_at
            and user.google_access_token_expires_at > datetime.utcnow() + timedelta(minutes=1)
        ):
            return user.google_access_token

        payload = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": user.google_refresh_token,
            "grant_type": "refresh_token",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.TOKEN_URL, data=payload) as response:
                if response.status != 200:
                    return None
                token_data = await response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return None
        expires_in = int(token_data.get("expires_in", 3600))
        user.google_access_token = access_token
        user.google_access_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        return access_token

    async def fetch_google_account_email(self, access_token: str) -> Optional[str]:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(self.USERINFO_URL, headers=headers) as response:
                if response.status != 200:
                    return None
                payload = await response.json()
        return payload.get("email")

    async def sync_appointment_to_google(
        self,
        appointment: Appointment,
        organizer: User,
        existing_event_id: Optional[str] = None,
    ) -> Optional[str]:
        access_token = await self.refresh_access_token(organizer)
        if not access_token:
            return None
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        event_payload = {
            "summary": appointment.title,
            "description": appointment.description or "",
            "location": appointment.location or "",
            "start": {"dateTime": appointment.start_time.isoformat() + "Z"},
            "end": {"dateTime": appointment.end_time.isoformat() + "Z"},
            "attendees": (
                [{"email": appointment.visitor_email, "displayName": appointment.visitor_name}]
                if appointment.visitor_email
                else []
            ),
        }
        async with aiohttp.ClientSession() as session:
            if existing_event_id:
                url = f"{self.EVENTS_URL}/{existing_event_id}"
                async with session.patch(url, json=event_payload, headers=headers) as response:
                    if response.status != 200:
                        return None
                    payload = await response.json()
                    return payload.get("id")
            async with session.post(self.EVENTS_URL, json=event_payload, headers=headers) as response:
                if response.status != 200:
                    return None
                payload = await response.json()
                return payload.get("id")

    async def delete_appointment_event(self, appointment: Appointment, organizer: User) -> bool:
        """Supprime l’événement Google Calendar lié au RDV (si id connu)."""
        if not appointment.google_event_id:
            return False
        access_token = await self.refresh_access_token(organizer)
        if not access_token:
            return False
        headers = {"Authorization": f"Bearer {access_token}"}
        eid = quote(str(appointment.google_event_id), safe="")
        url = f"{self.EVENTS_URL}/{eid}"
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as response:
                return response.status in (200, 204)

    async def get_google_events(self, organizer: User, start_date: datetime, end_date: datetime) -> List[dict]:
        access_token = await self.refresh_access_token(organizer)
        if not access_token:
            return []
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "timeMin": start_date.isoformat() + "Z",
            "timeMax": end_date.isoformat() + "Z",
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(self.EVENTS_URL, params=params, headers=headers) as response:
                if response.status != 200:
                    return []
                payload = await response.json()
        return payload.get("items", [])


google_calendar_service = GoogleCalendarService()
