from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mirror_api.providers.base import PrivateDownloadGrant


@dataclass(frozen=True)
class AssetView:
    id: str
    asset_role: str
    mime_type: str
    byte_size: int
    width: int
    height: int
    created_at: datetime


@dataclass(frozen=True)
class AssetDownloadGrantResult:
    asset: AssetView
    grant: PrivateDownloadGrant
