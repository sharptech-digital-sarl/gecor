from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "fpi_connect",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    beat_schedule={
        'send-appointment-reminders': {
            'task': 'send_appointment_reminders',
            'schedule': crontab(hour=9, minute=0),  # Run daily at 9 AM
        },
        'check-deadlines': {
            'task': 'check_deadlines',
            'schedule': crontab(hour='*/2', minute=0),  # Run every 2 hours
        },
        'remind-password-reset-requests': {
            'task': 'remind_password_reset_requests',
            'schedule': crontab(minute=0),  # Chaque heure à :00 UTC
        },
    },
)

# Import tasks
from app.tasks import ocr_tasks, notification_tasks
