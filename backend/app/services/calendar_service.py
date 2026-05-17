from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from datetime import datetime, timedelta
from typing import List, Optional
import uuid
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import User


class CalendarService:
    """Service for managing calendar and appointments"""
    
    def check_conflicts(
        self,
        db: Session,
        organizer_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        exclude_appointment_id: Optional[uuid.UUID] = None
    ) -> List[Appointment]:
        """Check for conflicting appointments"""
        # Build conflict conditions using SQLAlchemy or_() and and_()
        # A conflict occurs when:
        # 1. New appointment starts during an existing appointment
        #    (existing.start <= new.start < existing.end)
        # 2. New appointment ends during an existing appointment
        #    (existing.start < new.end <= existing.end)
        # 3. New appointment completely contains an existing appointment
        #    (new.start <= existing.start < new.end)
        conflict_condition = or_(
            and_(
                Appointment.start_time <= start_time,
                start_time < Appointment.end_time
            ),
            and_(
                Appointment.start_time < end_time,
                end_time <= Appointment.end_time
            ),
            and_(
                start_time <= Appointment.start_time,
                Appointment.start_time < end_time
            )
        )
        
        query = db.query(Appointment).filter(
            Appointment.organizer_id == organizer_id,
            Appointment.archived_at.is_(None),
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.status != AppointmentStatus.COMPLETED,
            Appointment.status != AppointmentStatus.NO_SHOW,
            conflict_condition
        )
        
        if exclude_appointment_id:
            query = query.filter(Appointment.id != exclude_appointment_id)
        
        return query.all()
    
    def get_available_slots(
        self,
        db: Session,
        organizer_id: int,
        date: datetime,
        duration_minutes: int = 30,
        work_start: int = 9,
        work_end: int = 17
    ) -> List[dict]:
        """Get available time slots for a given date"""
        # Get all appointments for the day
        day_start = datetime.combine(date.date(), datetime.min.time()).replace(hour=work_start)
        day_end = datetime.combine(date.date(), datetime.min.time()).replace(hour=work_end)
        
        appointments = db.query(Appointment).filter(
            Appointment.organizer_id == organizer_id,
            Appointment.archived_at.is_(None),
            Appointment.start_time >= day_start,
            Appointment.start_time < day_end,
            Appointment.status != AppointmentStatus.CANCELLED
        ).order_by(Appointment.start_time).all()
        
        # Generate available slots
        available_slots = []
        current_time = day_start
        
        for appointment in appointments:
            if current_time < appointment.start_time:
                # There's a gap before this appointment
                slot_end = min(appointment.start_time, current_time + timedelta(minutes=duration_minutes))
                if (slot_end - current_time).total_seconds() >= duration_minutes * 60:
                    available_slots.append({
                        "start": current_time,
                        "end": slot_end
                    })
            current_time = max(current_time, appointment.end_time)
        
        # Add remaining time after last appointment
        if current_time < day_end:
            slot_end = min(day_end, current_time + timedelta(minutes=duration_minutes))
            if (slot_end - current_time).total_seconds() >= duration_minutes * 60:
                available_slots.append({
                    "start": current_time,
                    "end": slot_end
                })
        
        return available_slots
    
    def get_appointments_by_date_range(
        self,
        db: Session,
        organizer_id: Optional[uuid.UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Appointment]:
        """Get appointments within a date range"""
        query = db.query(Appointment)
        
        if organizer_id:
            query = query.filter(Appointment.organizer_id == organizer_id)
        
        if start_date:
            query = query.filter(Appointment.start_time >= start_date)
        
        if end_date:
            query = query.filter(Appointment.start_time <= end_date)

        query = query.filter(Appointment.archived_at.is_(None))
        return query.order_by(Appointment.start_time).all()


calendar_service = CalendarService()

