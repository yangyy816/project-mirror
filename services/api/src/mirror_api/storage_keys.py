from __future__ import annotations

import re


def data_export_object_key(export_id: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{32}", export_id):
        raise ValueError("export id must use the opaque 32-character syntax")
    return f"exports/v1/{export_id}"
