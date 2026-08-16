from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Literal

from mirror_api.image_sanitizer import SANITIZER_VERSION, ImageSanitizerConfig


def normalizer_config_digest(config: ImageSanitizerConfig) -> str:
    canonical = json.dumps(
        asdict(config), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return sha256(canonical).hexdigest()


@dataclass(frozen=True)
class NormalizationAuthority:
    normalizer_version: str
    normalizer_config_digest: str

    def __post_init__(self) -> None:
        if self.normalizer_version != SANITIZER_VERSION:
            raise ValueError("normalizer version is not supported")
        if not re.fullmatch(r"[0-9a-f]{64}", self.normalizer_config_digest):
            raise ValueError("normalizer config digest must be lowercase SHA-256")


@dataclass(frozen=True)
class NormalizationResult:
    record_id: str
    status: Literal["NORMALIZED", "NORMALIZATION_FAILED"]
    normalized_asset_id: str | None
    result_code: str | None
    sha256: str | None


class NormalizationRejected(Exception):
    def __init__(self, code: str) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", code):
            code = "normalization_rejected"
        self.code = code
        super().__init__(code)


class NormalizationRetryableError(Exception):
    def __init__(self, code: str = "normalization_storage_unavailable") -> None:
        self.code = code
        super().__init__(code)
