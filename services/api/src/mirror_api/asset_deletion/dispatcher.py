from __future__ import annotations

import secrets

from celery import Celery

from mirror_api.asset_deletion.task_contract import AssetDeletionTaskMessage


class CeleryAssetDeletionDispatcher:
    def __init__(self, *, redis_url: str) -> None:
        self._celery = Celery("mirror-api-deletion-dispatch", broker=redis_url, backend=redis_url)
        self._celery.conf.update(
            task_serializer="json", accept_content=["json"], result_serializer="json"
        )

    def dispatch_asset_deletion(self, message: AssetDeletionTaskMessage) -> str:
        message.validate()
        self._celery.send_task(
            "mirror.asset_deletion.process",
            args=[message.to_message()],
            task_id=secrets.token_hex(16),
            headers={"request_id": message.request_id, "job_id": message.job_id},
            queue="mirror.maintenance",
        )
        return message.job_id


class RecoverableAssetDeletionDispatcher:
    def dispatch_asset_deletion(self, message: AssetDeletionTaskMessage) -> str:
        message.validate()
        return message.job_id
