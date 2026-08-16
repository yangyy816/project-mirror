from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from mirror_api.providers.base import SyntheticOutputSpecification
from mirror_api.providers.synthetic_local import LocalSyntheticRawStorageProvider
from mirror_api.synthetic_dataset.codex_native_source import (
    CodexNativeAdmissionEvidence,
    CodexNativeAdmissionRejected,
    CodexNativeGenerationSpecification,
    CodexNativeSourceAdmissionService,
)

_MANIFEST_SCHEMA = "mirror.synthetic-dataset/CodexNativeAdmissionManifest/v1"
_EVIDENCE_SCHEMA = "mirror.synthetic-dataset/CodexNativeValidationEvidence/v1"
_MAX_MANIFEST_BYTES = 128 * 1024
_MAX_SOURCE_BYTES = 20 * 1024 * 1024


class ManifestError(ValueError):
    """A safe manifest rejection that never includes prompt text or paths."""


def _object(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ManifestError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{label} must be non-empty text")
    return value


def _integer(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise ManifestError(f"{label} must be an integer")
    return value


def _optional_text(value: object, *, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label=label)


def _exact_keys(document: dict[str, object], expected: set[str], *, label: str) -> None:
    if set(document) != expected:
        raise ManifestError(f"{label} fields are invalid")


def _read_manifest(path: Path) -> dict[str, object]:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ManifestError("admission manifest is unavailable") from exc
    if not content or len(content) > _MAX_MANIFEST_BYTES:
        raise ManifestError("admission manifest size is invalid")
    try:
        return _object(json.loads(content), label="admission manifest")
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError("admission manifest is invalid JSON") from exc


def _parse_specification(document: dict[str, object]) -> CodexNativeGenerationSpecification:
    _exact_keys(
        document,
        {
            "schema_version",
            "specification_reference",
            "specification_version",
            "generation_policy_reference",
            "prompt_template_reference",
            "prompt_digest",
            "requested_pose_reference",
            "requested_expression_reference",
            "styling_constraints_reference",
            "output_specification",
            "requested_quantity",
            "max_attempts",
            "retry_ceiling",
            "concurrency_ceiling",
            "stop_condition_reference",
            "coverage_pack_reference",
            "coverage_cell_reference",
            "synthetic_only",
            "real_person_reference_used",
        },
        label="generation specification",
    )
    output = _object(document["output_specification"], label="output specification")
    _exact_keys(output, {"media_type", "width", "height", "max_byte_size"}, label="output")
    media_type = _text(output["media_type"], label="output media type")
    if media_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ManifestError("output media type is invalid")
    return CodexNativeGenerationSpecification(
        schema_version=cast(
            Literal["mirror.synthetic-dataset/CodexNativeGenerationSpecification/v1"],
            _text(document["schema_version"], label="specification schema version"),
        ),
        specification_reference=_text(
            document["specification_reference"], label="specification reference"
        ),
        specification_version=_text(
            document["specification_version"], label="specification version"
        ),
        generation_policy_reference=_text(
            document["generation_policy_reference"], label="generation policy reference"
        ),
        prompt_template_reference=_text(
            document["prompt_template_reference"], label="prompt template reference"
        ),
        prompt_digest=_text(document["prompt_digest"], label="prompt digest"),
        requested_pose_reference=_text(
            document["requested_pose_reference"], label="requested pose reference"
        ),
        requested_expression_reference=_text(
            document["requested_expression_reference"], label="requested expression reference"
        ),
        styling_constraints_reference=_text(
            document["styling_constraints_reference"], label="styling constraints reference"
        ),
        output_specification=SyntheticOutputSpecification(
            media_type=cast(Literal["image/jpeg", "image/png", "image/webp"], media_type),
            width=_integer(output["width"], label="output width"),
            height=_integer(output["height"], label="output height"),
            max_byte_size=_integer(output["max_byte_size"], label="output maximum bytes"),
        ),
        requested_quantity=_integer(document["requested_quantity"], label="requested quantity"),
        max_attempts=_integer(document["max_attempts"], label="maximum attempts"),
        retry_ceiling=_integer(document["retry_ceiling"], label="retry ceiling"),
        concurrency_ceiling=_integer(document["concurrency_ceiling"], label="concurrency ceiling"),
        stop_condition_reference=_text(
            document["stop_condition_reference"], label="stop condition reference"
        ),
        coverage_pack_reference=_optional_text(
            document["coverage_pack_reference"], label="coverage pack reference"
        ),
        coverage_cell_reference=_optional_text(
            document["coverage_cell_reference"], label="coverage cell reference"
        ),
        synthetic_only=cast(Literal[True], document["synthetic_only"]),
        real_person_reference_used=cast(Literal[False], document["real_person_reference_used"]),
    )


def _read_source(path: Path, *, expected_sha256: str) -> bytes:
    if len(expected_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in expected_sha256
    ):
        raise ManifestError("generated source checksum is invalid")
    try:
        with path.open("rb") as handle:
            content = handle.read(_MAX_SOURCE_BYTES + 1)
    except OSError as exc:
        raise ManifestError("generated source is unavailable") from exc
    if not content or len(content) > _MAX_SOURCE_BYTES:
        raise ManifestError("generated source size is invalid")
    if not hmac.compare_digest(hashlib.sha256(content).hexdigest(), expected_sha256):
        raise ManifestError("generated source checksum does not match")
    return content


def _source_within_root(*, source_root: Path, manifest_path: str) -> Path:
    if manifest_path.startswith(("\\\\", "//")):
        raise ManifestError("generated source is outside the approved source root")
    untrusted_source = Path(manifest_path)
    if ".." in untrusted_source.parts:
        raise ManifestError("generated source is outside the approved source root")
    try:
        root_candidate = source_root.absolute()
        root_metadata = root_candidate.lstat()
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if stat.S_ISLNK(root_metadata.st_mode) or (
            getattr(root_metadata, "st_file_attributes", 0) & reparse_flag
        ):
            raise ManifestError("approved source root must not be a link or reparse point")
        root = root_candidate.resolve(strict=True)
        source_candidate = (
            untrusted_source if untrusted_source.is_absolute() else root / untrusted_source
        )
        source_candidate.relative_to(root)
        current = root
        for component in source_candidate.relative_to(root).parts:
            current /= component
            metadata = current.lstat()
            if stat.S_ISLNK(metadata.st_mode) or (
                getattr(metadata, "st_file_attributes", 0) & reparse_flag
            ):
                raise ManifestError("generated source is outside the approved source root")
        source = source_candidate.resolve(strict=True)
        source.relative_to(root)
    except ManifestError:
        raise
    except (OSError, ValueError) as exc:
        raise ManifestError("generated source is outside the approved source root") from exc
    if not root.is_dir() or not source.is_file():
        raise ManifestError("generated source is outside the approved source root")
    return source


async def admit_manifest(
    *, manifest_path: Path, source_root: Path, storage_root: Path, evidence_output: Path
) -> dict[str, object]:
    manifest = _read_manifest(manifest_path)
    _exact_keys(
        manifest,
        {"schema_version", "validation_reference", "specifications"},
        label="admission manifest",
    )
    if manifest["schema_version"] != _MANIFEST_SCHEMA:
        raise ManifestError("admission manifest schema version is not supported")
    validation_reference = _text(manifest["validation_reference"], label="validation reference")
    specifications = manifest["specifications"]
    if not isinstance(specifications, list) or not specifications:
        raise ManifestError("admission manifest specifications are invalid")
    service = CodexNativeSourceAdmissionService(
        storage=LocalSyntheticRawStorageProvider(root=storage_root),
        now=lambda: datetime.now().astimezone(),
    )
    evidence: list[CodexNativeAdmissionEvidence] = []
    requested_count = 0
    attempt_budget = 0
    attempts_used = 0
    observed_items: set[str] = set()
    for raw_entry in specifications:
        entry = _object(raw_entry, label="specification entry")
        _exact_keys(entry, {"specification", "items"}, label="specification entry")
        specification = _parse_specification(
            _object(entry["specification"], label="generation specification")
        )
        items = entry["items"]
        if not isinstance(items, list) or len(items) != specification.requested_quantity:
            raise ManifestError("specification item count does not match requested quantity")
        requested_count += specification.requested_quantity
        attempt_budget += specification.max_attempts
        item_documents = [_object(raw_item, label="generation item") for raw_item in items]
        item_attempts = [
            _integer(item.get("attempt"), label="item attempt") for item in item_documents
        ]
        if any(
            attempt < 1 or attempt > 1 + specification.retry_ceiling for attempt in item_attempts
        ):
            raise ManifestError("generation item exceeds its retry ceiling")
        if sum(item_attempts) > specification.max_attempts:
            raise ManifestError("generation specification exceeds its attempt budget")
        for item, attempt in zip(item_documents, item_attempts, strict=True):
            _exact_keys(
                item,
                {
                    "item_reference",
                    "attempt",
                    "generated_at",
                    "source_path",
                    "expected_sha256",
                },
                label="generation item",
            )
            item_reference = _text(item["item_reference"], label="item reference")
            if item_reference in observed_items:
                raise ManifestError("generation item reference is duplicated")
            observed_items.add(item_reference)
            try:
                generated_at = datetime.fromisoformat(
                    _text(item["generated_at"], label="generation timestamp")
                )
            except ValueError as exc:
                raise ManifestError("generation timestamp is invalid") from exc
            evidence.append(
                await service.admit(
                    specification=specification,
                    item_reference=item_reference,
                    attempt=attempt,
                    generated_at=generated_at,
                    content=_read_source(
                        _source_within_root(
                            source_root=source_root,
                            manifest_path=_text(item["source_path"], label="generated source path"),
                        ),
                        expected_sha256=_text(
                            item["expected_sha256"], label="generated source checksum"
                        ),
                    ),
                    media_type=specification.output_specification.media_type,
                )
            )
        attempts_used += sum(item_attempts)
    if validation_reference == "p2-m2-v01":
        if requested_count != 8 or attempt_budget != 12:
            raise ManifestError("P2-M2-V01 must use the approved 8-image and 12-attempt budget")
    elif requested_count > 24:
        raise ManifestError("native generation cohort exceeds the Principal-approved boundary")
    document: dict[str, object] = {
        "schema_version": _EVIDENCE_SCHEMA,
        "validation_reference": validation_reference,
        "status": "passed",
        "images_requested": requested_count,
        "images_admitted": len(evidence),
        "attempt_budget": attempt_budget,
        "attempts_used": attempts_used,
        "source_kind": "CODEX_NATIVE_IMAGEGEN",
        "provenance_level": "PROVENANCE_ONLY",
        "cost_accounting_mode": "REQUEST_COUNT_ONLY",
        "production_provider_approved": False,
        "production_generation_enabled": False,
        "items": [item.to_document() for item in evidence],
    }
    evidence_output.parent.mkdir(parents=True, exist_ok=True)
    evidence_output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return document


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Admit operator-generated Codex native images into private synthetic raw storage"
        )
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        document = asyncio.run(
            admit_manifest(
                manifest_path=cast(Path, args.manifest),
                source_root=cast(Path, args.source_root),
                storage_root=cast(Path, args.storage_root),
                evidence_output=cast(Path, args.evidence_output),
            )
        )
    except OSError:
        reason = "offline_source_io_failed"
        print(f"Codex native admission failed: {reason}", file=sys.stderr)
        return 1
    except (ManifestError, CodexNativeAdmissionRejected, ValueError) as exc:
        reason = exc.code if isinstance(exc, CodexNativeAdmissionRejected) else str(exc)
        print(f"Codex native admission failed: {reason}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": document["status"],
                "images_requested": document["images_requested"],
                "images_admitted": document["images_admitted"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
