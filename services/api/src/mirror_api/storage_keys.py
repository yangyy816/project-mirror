from __future__ import annotations

import hashlib
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


def synthetic_raw_storage_reference(item_id: str, attempt_id: str) -> str:
    """Derive a stable opaque reference without exposing either authority identifier."""
    if not re.fullmatch(r"[0-9a-f]{32}", item_id) or not re.fullmatch(r"[0-9a-f]{32}", attempt_id):
        raise ValueError("synthetic raw authority must use opaque identifiers")
    digest = hashlib.sha256(
        f"mirror-synthetic-raw-v1\n{item_id}\n{attempt_id}".encode()
    ).hexdigest()
    return f"raw-{digest[:60]}"


def internal_synthetic_raw_object_key(storage_reference: str) -> str:
    """Map an opaque application reference to an adapter-only private object key."""
    if not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", storage_reference):
        raise ValueError("synthetic storage reference must use the opaque syntax")
    digest = hashlib.sha256(storage_reference.encode()).hexdigest()
    return f"{INTERNAL_SYNTHETIC_NAMESPACE}/raw/{digest}"
