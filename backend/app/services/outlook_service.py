from typing import List, Optional
from datetime import datetime
from urllib.parse import quote

from app.core.config import settings
from app.models.appointment import Appointment


class OutlookService:
    """Service for integrating with Outlook/Exchange calendars"""
    
    def __init__(self):
        self.use_graph_api = bool(
            settings.MICROSOFT_GRAPH_CLIENT_ID and
            settings.MICROSOFT_GRAPH_CLIENT_SECRET
        )
        self.use_ews = bool(
            settings.EXCHANGE_SERVER_URL and
            settings.EXCHANGE_USERNAME
        )

    def _graph_access_token(self) -> Optional[str]:
        try:
            from msal import ConfidentialClientApplication
        except Exception:
            return None

        app = ConfidentialClientApplication(
            settings.MICROSOFT_GRAPH_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{settings.MICROSOFT_GRAPH_TENANT_ID}",
            client_credential=settings.MICROSOFT_GRAPH_CLIENT_SECRET,
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        return result.get("access_token")

    def _graph_user_identifier(self, appointment: Appointment) -> Optional[str]:
        organizer = getattr(appointment, "organizer", None)
        if organizer and organizer.email:
            return organizer.email
        return None
    
    async def sync_appointment_to_outlook(
        self,
        appointment: Appointment
    ) -> Optional[str]:
        """Sync appointment to Outlook and return event ID"""
        if self.use_graph_api:
            return await self._sync_to_graph_api(appointment)
        elif self.use_ews:
            return await self._sync_to_ews(appointment)
        else:
            return None
    
    async def _sync_to_graph_api(
        self,
        appointment: Appointment
    ) -> Optional[str]:
        """Sync using Microsoft Graph API"""
        try:
            access_token = self._graph_access_token()
            if not access_token:
                return None

            user_identifier = self._graph_user_identifier(appointment)
            if not user_identifier:
                return None

            import aiohttp
            event_data = {
                "subject": appointment.title,
                "body": {
                    "contentType": "HTML",
                    "content": appointment.description or ""
                },
                "start": {
                    "dateTime": appointment.start_time.isoformat(),
                    "timeZone": "UTC"
                },
                "end": {
                    "dateTime": appointment.end_time.isoformat(),
                    "timeZone": "UTC"
                },
                "location": {
                    "displayName": appointment.location or ""
                },
                "attendees": [
                    {
                        "emailAddress": {
                            "address": appointment.visitor_email,
                            "name": appointment.visitor_name
                        },
                        "type": "required"
                    }
                ] if appointment.visitor_email else []
            }

            async with aiohttp.ClientSession() as session:
                url = f"https://graph.microsoft.com/v1.0/users/{quote(user_identifier)}/calendar/events"
                headers = {"Authorization": f"Bearer {access_token}"}

                async with session.post(url, json=event_data, headers=headers) as response:
                    if response.status == 201:
                        event = await response.json()
                        return event.get("id")

            return None

        except Exception as e:
            print(f"Failed to sync to Graph API: {str(e)}")
            return None

    async def delete_graph_calendar_event(self, appointment: Appointment) -> bool:
        """Supprime l’événement du calendrier via Microsoft Graph (application permissions)."""
        if not self.use_graph_api or not appointment.outlook_event_id:
            return False
        try:
            access_token = self._graph_access_token()
            if not access_token:
                return False
            user_identifier = self._graph_user_identifier(appointment)
            if not user_identifier:
                return False
            import aiohttp

            eid = quote(str(appointment.outlook_event_id), safe="")
            url = f"https://graph.microsoft.com/v1.0/users/{quote(user_identifier)}/calendar/events/{eid}"
            headers = {"Authorization": f"Bearer {access_token}"}
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, headers=headers) as response:
                    return response.status in (200, 204)
        except Exception as e:
            print(f"Failed to delete Graph calendar event: {str(e)}")
            return False

    async def _sync_to_ews(
        self,
        appointment: Appointment
    ) -> Optional[str]:
        """Sync using Exchange Web Services (EWS)"""
        try:
            from exchangelib import Credentials, Account, CalendarItem, EWSDateTime, EWSTimeZone
            
            credentials = Credentials(
                settings.EXCHANGE_USERNAME,
                settings.EXCHANGE_PASSWORD
            )
            
            account = Account(
                settings.EXCHANGE_USERNAME,
                credentials=credentials,
                autodiscover=True
            )
            
            # Create calendar item
            item = CalendarItem(
                account=account,
                folder=account.calendar,
                subject=appointment.title,
                body=appointment.description or "",
                start=EWSDateTime.from_datetime(appointment.start_time.replace(tzinfo=EWSTimeZone.UTC)),
                end=EWSDateTime.from_datetime(appointment.end_time.replace(tzinfo=EWSTimeZone.UTC)),
                location=appointment.location or ""
            )
            
            item.save()
            return item.id
            
        except Exception as e:
            print(f"Failed to sync to EWS: {str(e)}")
            return None
    
    async def get_outlook_events(
        self,
        user_email: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[dict]:
        """Get events from Outlook calendar"""
        if self.use_graph_api:
            return await self._get_from_graph_api(user_email, start_date, end_date)
        elif self.use_ews:
            return await self._get_from_ews(user_email, start_date, end_date)
        else:
            return []
    
    async def _get_from_graph_api(
        self,
        user_email: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[dict]:
        """Get events from Graph API"""
        access_token = self._graph_access_token()
        if not access_token:
            return []
        if not user_email:
            return []

        import aiohttp

        url = (
            f"https://graph.microsoft.com/v1.0/users/{quote(user_email)}/calendarView"
            f"?startDateTime={quote(start_date.isoformat())}&endDateTime={quote(end_date.isoformat())}"
        )
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Prefer": 'outlook.timezone="UTC"',
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return []
                payload = await response.json()

        events: List[dict] = []
        for item in payload.get("value", []):
            events.append(
                {
                    "id": item.get("id"),
                    "subject": item.get("subject"),
                    "start": item.get("start", {}).get("dateTime"),
                    "end": item.get("end", {}).get("dateTime"),
                    "location": (item.get("location") or {}).get("displayName"),
                }
            )
        return events
    
    async def _get_from_ews(
        self,
        user_email: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[dict]:
        """Get events from EWS"""
        # Implementation using exchangelib
        return []


outlook_service = OutlookService()

