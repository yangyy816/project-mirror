from __future__ import annotations

import re

INTERNAL_SYNTHETIC_NAMESPACE = "internal-synthetic/v1"


def data_export_object_key(export_id: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{32}", export_id):
        raise ValueError("export id must use the opaque 32-character syntax")
    return f"exports/v1/{export_id}"


def internal_synthetic_generated_object_key(storage_id: str) -> str:
    """Adapter-only P2 key derivation, isolated from every user-asset namespace.

    Application/domain code must retain only the opaque storage reference, never this key.
    """
    if not re.fullmatch(r"[0-9a-f]{32}", storage_id):
        raise ValueError("synthetic storage id must use the opaque 32-character syntax")
    return f"{INTERNAL_SYNTHETIC_NAMESPACE}/{storage_id}"
