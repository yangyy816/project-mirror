from __future__ import annotations

import secrets

from celery import Celery

from mirror_api.data_rights.task_contract import (
    AccountDeletionTaskMessage,
    DataExportTaskMessage,
)


class CeleryDataRightsDispatcher:
    def __init__(self, *, redis_url: str) -> None:
        self._celery = Celery(
            "mirror-api-data-rights-dispatch", broker=redis_url, backend=redis_url
        )
        self._celery.conf.update(
            task_serializer="json", accept_content=["json"], result_serializer="json"
        )

    def dispatch_data_export(self, message: DataExportTaskMessage) -> str:
        return self._send("mirror.data_export.process", message.to_message())

    def dispatch_account_deletion(self, message: AccountDeletionTaskMessage) -> str:
        return self._send("mirror.account_deletion.process", message.to_message())

    def _send(self, name: str, message: dict[str, str]) -> str:
        self._celery.send_task(
            name,
            args=[message],
            task_id=secrets.token_hex(16),
            headers={"request_id": message["request_id"], "job_id": message["job_id"]},
            queue="mirror.maintenance",
        )
        return message["job_id"]


class RecoverableDataRightsDispatcher:
    def dispatch_data_export(self, message: DataExportTaskMessage) -> str:
        message.validate()
        return message.job_id

    def dispatch_account_deletion(self, message: AccountDeletionTaskMessage) -> str:
        message.validate()
        return message.job_id
