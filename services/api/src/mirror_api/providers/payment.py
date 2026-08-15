from __future__ import annotations

from typing import NoReturn

from mirror_api.providers.base import PaymentCommand


class DisabledPaymentProvider:
    """Phase 0 boundary: never simulates a successful payment."""

    async def execute(self, command: PaymentCommand) -> NoReturn:
        del command
        raise NotImplementedError("real payment is TODO_PHASE_7 and cannot be simulated as success")
