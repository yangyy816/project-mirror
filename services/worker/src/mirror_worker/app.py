"""Celery CLI compatibility module. Production target: Linux + Redis only."""

from mirror_worker.celery_adapter import celery_app

__all__ = ["celery_app"]
