from __future__ import annotations

from mirror_api.config import Settings, get_settings

from mirror_worker.application import FoundationProbeService, TaskEnvelope


class LocalTaskRunner:
    """Synchronous DEVELOPMENT ONLY task runner."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if self.settings.app_env not in {"development", "test"}:
            raise RuntimeError("LocalTaskRunner is DEVELOPMENT ONLY")
        self.service = FoundationProbeService()

    def dispatch(self, envelope: TaskEnvelope) -> str:
        self.service.execute(envelope)
        return envelope.job_id
