"""Background task package."""

from app.worker.tasks.resume_tasks import process_resume

__all__ = ["process_resume"]
