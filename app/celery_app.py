"""
Celery application configuration with Beat scheduler.

This module configures Celery for background task processing and
scheduled tasks (like RSS feed refresh every 24 hours).

Usage:
    # Start worker (processes tasks):
    celery -A app.celery_app worker --loglevel=info
    
    # Start beat scheduler (triggers scheduled tasks):
    celery -A app.celery_app beat --loglevel=info
    
    # Production (worker + beat together):
    celery -A app.celery_app worker --beat --loglevel=info
"""
from __future__ import annotations

import os
from celery import Celery
from celery.schedules import crontab

# Redis URL for broker and result backend
# Falls back to memory if REDIS_URL not set (for local dev without Redis)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def make_celery() -> Celery:
    """
    Create and configure the Celery application.
    
    Returns:
        Configured Celery instance
    """
    celery = Celery(
        "linkerhero",
        broker=REDIS_URL,
        backend=REDIS_URL,
        include=["app.tasks.rss_tasks"],
    )
    
    # Celery configuration
    celery.conf.update(
        # Task settings
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        
        # Task execution settings
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        
        # Result backend settings
        result_expires=3600,  # Results expire after 1 hour
        
        # Beat scheduler settings
        beat_schedule={
            "refresh-rss-feeds-daily": {
                "task": "app.tasks.rss_tasks.refresh_all_rss_feeds",
                "schedule": crontab(hour=6, minute=0),  # Run at 6:00 AM UTC daily
                "options": {"expires": 3600},  # Task expires if not run within 1 hour
            },
        },
        
        # Retry settings
        broker_connection_retry_on_startup=True,
    )
    
    return celery


# Create the Celery app instance
celery = make_celery()


class ContextTask(celery.Task):
    """
    Custom task class that ensures Flask app context is available.
    
    This allows tasks to access Flask extensions like SQLAlchemy.
    """
    
    def __call__(self, *args, **kwargs):
        from app import create_app
        
        flask_app = create_app()
        with flask_app.app_context():
            return self.run(*args, **kwargs)


# Set the custom task class as default
celery.Task = ContextTask


# Allow importing celery directly from this module
__all__ = ["celery", "make_celery"]

