"""Django config package.

Loads Celery app so that @shared_task decorator works.
"""

from config.celery import app as celery_app

__all__ = ("celery_app",)
