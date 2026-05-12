"""Background task package."""

from app.worker.tasks.resume import process_resume

__all__ = ["process_resume"]
