"""Fail-closed ImageGen result materializer and local PNG receiver.

This module deliberately has no knowledge of evidence roots, prompts, registries,
or persistent output locators.  It accepts only typed programmatic result fields;
human ``output_hint`` text is never parsed.  Its only write authority is the
Principal-created :class:`PreallocatedDestination` capability.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import ctypes
import hashlib
import json
import os
import re
import stat
import sys
import warnings
import zlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Final, NoReturn, cast

from PIL import Image

DATA_URL_PREFIX: Final = "data:image/png;base64,"
MAXIMUM_BYTES: Final = 20_971_520
MAXIMUM_CANONICAL_BASE64_PAYLOAD_BYTES: Final = 27_962_028
MAXIMUM_COMPLETE_DATA_URL_ASCII_BYTES: Final = 27_962_050
MAXIMUM_PROVIDER_RESULT_FILE_BYTES: Final = MAXIMUM_COMPLETE_DATA_URL_ASCII_BYTES + 1_048_576
MINIMUM_EDGE_PIXELS: Final = 64
MAXIMUM_EDGE_PIXELS: Final = 8192
MAXIMUM_PIXEL_COUNT: Final = 40_000_000
_DESTINATION_FACTORY_TOKEN: Final = object()
_SAFE_LEAF_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,255}\Z")


class D02R2PngReceiverError(Exception):
    """An allowlisted, fail-closed receiver failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


_RECEIVED_PNG_FACTORY_TOKEN = object()
_BOUND_PNG_FILE_FACTORY_TOKEN = object()


@dataclass(frozen=True, slots=True, init=False)
class ReceivedPng:
    """Non-sensitive validation facts; it intentionally exposes no URL or path."""

    byte_size: int
    sha256: str
    width: int
    height: int

    def __init__(
        self,
        *,
        byte_size: int,
        sha256: str,
        width: int,
        height: int,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _RECEIVED_PNG_FACTORY_TOKEN:
            raise TypeError("ReceivedPng facts must be issued by the PNG receiver")
        object.__setattr__(self, "byte_size", byte_size)
        object.__setattr__(self, "sha256", sha256)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)


@dataclass(frozen=True, slots=True, init=False)
class PreallocatedDestination:
    """Principal-owned, one-name write capability.

    The receiver never resolves an evidence root.  The Principal must create
    this capability only after its own allocation and containment checks.
    """

    _path: Path
    _ancestor_identities: tuple[tuple[Path, tuple[int, int]], ...]

    def __init__(
        self,
        *,
        path: Path,
        ancestor_identities: tuple[tuple[Path, tuple[int, int]], ...],
        _factory_token: object,
    ) -> None:
        if _factory_token is not _DESTINATION_FACTORY_TOKEN:
            _fail(
                "DESTINATION_CAPABILITY_INVALID",
                "destination capability must be created by the Principal binding factory",
            )
        object.__setattr__(self, "_path", path)
        object.__setattr__(self, "_ancestor_identities", ancestor_identities)

    def write_create_new_durable(self, data: bytes) -> bytes:
        """Stage completely, publish create-new, and independently replay bytes."""

        path = self._path
        parent = path.parent
        temporary = parent / f".{path.name}.incoming"
        _validate_ancestor_identities(
            self._ancestor_identities,
            code="DESTINATION_WRITE_FAILED",
        )
        _require_not_reparse_if_exists(path, code="DESTINATION_COLLISION")
        _require_not_reparse_if_exists(temporary, code="DESTINATION_TEMP_COLLISION")
        temporary_identity: tuple[int, int] | None = None
        published = False
        try:
            temporary_identity = _write_staged_file(temporary, data)
            try:
                _sync_directory(parent)
            except OSError as error:
                raise D02R2PngReceiverError(
                    "DESTINATION_DURABILITY_FAILED", "staging durability sync failed"
                ) from error
            try:
                os.link(temporary, path, follow_symlinks=False)
            except FileExistsError as error:
                raise D02R2PngReceiverError(
                    "DESTINATION_COLLISION", "preallocated destination already exists"
                ) from error
            except OSError as error:
                raise D02R2PngReceiverError(
                    "DESTINATION_PUBLISH_FAILED", "atomic create-new publish failed"
                ) from error
            published = True
            _require_opened_path_identity(
                path,
                temporary_identity,
                code="DESTINATION_PUBLISH_FAILED",
            )
            try:
                _sync_directory(parent)
            except OSError as error:
                raise D02R2PngReceiverError(
                    "DESTINATION_DURABILITY_FAILED", "published destination sync failed"
                ) from error
            replayed = _read_file_bytes_no_follow(path, maximum_bytes=len(data))
            if replayed != data:
                _fail("DESTINATION_REPLAY_FAILED", "published bytes differ from staged bytes")
            try:
                os.unlink(temporary)
            except OSError as error:
                raise D02R2PngReceiverError(
                    "DESTINATION_TEMP_CLEANUP_FAILED", "staging cleanup failed"
                ) from error
            try:
                _sync_directory(parent)
            except OSError as error:
                raise D02R2PngReceiverError(
                    "DESTINATION_DURABILITY_FAILED", "cleanup durability sync failed"
                ) from error
            _validate_ancestor_identities(
                self._ancestor_identities,
                code="DESTINATION_REPLAY_FAILED",
            )
            return replayed
        except BaseException:
            if published:
                _best_effort_unlink_owned(path, temporary_identity)
            _best_effort_unlink_owned(temporary, temporary_identity)
            _best_effort_sync_directory(parent)
            raise

    def bind_published_png(self, *, expected: ReceivedPng) -> BoundPngFile:
        """Bind the exact file published through this one-name capability."""

        bound = bind_principal_existing_png_file(path=self._path)
        if bound.validate() != expected:
            _fail("DESTINATION_REPLAY_FAILED", "published PNG facts changed after materialization")
        return bound


@dataclass(frozen=True, slots=True, init=False)
class BoundPngFile:
    """No-follow capability for one exact existing PNG file identity.

    The path remains encapsulated.  A recovery caller may reconstruct the
    capability only from the exact private checkpoint locator and recorded
    file identity; the receiver never searches for a replacement file.
    """

    _path: Path
    _identity: tuple[int, int]
    _ancestor_identities: tuple[tuple[Path, tuple[int, int]], ...]

    def __init__(
        self,
        *,
        path: Path,
        identity: tuple[int, int],
        ancestor_identities: tuple[tuple[Path, tuple[int, int]], ...],
        _factory_token: object,
    ) -> None:
        if _factory_token is not _BOUND_PNG_FILE_FACTORY_TOKEN:
            _fail("INVALID_PROVIDER_FILE", "existing PNG capability was not issued by its binder")
        object.__setattr__(self, "_path", path)
        object.__setattr__(self, "_identity", identity)
        object.__setattr__(self, "_ancestor_identities", ancestor_identities)

    @property
    def file_identity(self) -> tuple[int, int]:
        """Return non-locator identity facts suitable for the private index."""

        return self._identity

    def validate(self) -> ReceivedPng:
        """Re-read the bound file and replay its PNG facts without copying it."""

        data = self.read_png_bytes()
        return _validate_png_bytes(data)

    def read_png_bytes(self) -> bytes:
        """Return exact validated bytes to an in-process D02 runtime consumer.

        The file locator remains encapsulated.  Callers receive only the bytes
        of this already-bound identity after the same no-follow and ancestor
        replay used by :meth:`validate`.
        """

        _validate_ancestor_identities(self._ancestor_identities, code="INVALID_PROVIDER_FILE")
        data = _read_file_bytes_no_follow(
            self._path,
            maximum_bytes=MAXIMUM_BYTES,
            code="INVALID_PROVIDER_FILE",
            expected_identity=self._identity,
        )
        _require_opened_path_identity(
            self._path,
            self._identity,
            code="INVALID_PROVIDER_FILE",
        )
        _validate_png_bytes(data)
        _validate_ancestor_identities(self._ancestor_identities, code="INVALID_PROVIDER_FILE")
        return data

    def copy_create_new(self, *, destination: PreallocatedDestination) -> ReceivedPng:
        """Copy only this bound identity into a create-new durable destination."""

        _validate_ancestor_identities(self._ancestor_identities, code="INVALID_PROVIDER_FILE")
        data = _read_file_bytes_no_follow(
            self._path,
            maximum_bytes=MAXIMUM_BYTES,
            code="INVALID_PROVIDER_FILE",
            expected_identity=self._identity,
        )
        facts = _validate_png_bytes(data)
        replayed = destination.write_create_new_durable(data)
        if replayed != data or hashlib.sha256(replayed).hexdigest() != facts.sha256:
            _fail("DESTINATION_REPLAY_FAILED", "published PNG differs from bound source file")
        _validate_ancestor_identities(self._ancestor_identities, code="INVALID_PROVIDER_FILE")
        return facts


def bind_principal_preallocated_destination(
    *,
    parent: Path,
    leaf_name: str,
) -> PreallocatedDestination:
    """Bind one already allocated leaf without learning the evidence-root locator."""

    if not isinstance(parent, Path) or not parent.is_absolute():
        _fail("DESTINATION_CAPABILITY_INVALID", "destination parent must be an absolute Path")
    if (
        not isinstance(leaf_name, str)
        or _SAFE_LEAF_RE.fullmatch(leaf_name) is None
        or Path(leaf_name).name != leaf_name
        or leaf_name in {".", ".."}
    ):
        _fail("DESTINATION_CAPABILITY_INVALID", "destination leaf is not an exact safe name")
    try:
        resolved_parent = parent.resolve(strict=True)
    except OSError as error:
        raise D02R2PngReceiverError(
            "DESTINATION_CAPABILITY_INVALID",
            "destination parent cannot be resolved",
        ) from error
    if resolved_parent != parent or not parent.is_dir():
        _fail(
            "DESTINATION_CAPABILITY_INVALID",
            "destination parent is not an exact existing directory",
        )
    ancestor_identities = _capture_ancestor_identities(parent)
    path = parent / leaf_name
    _require_not_reparse_if_exists(path, code="DESTINATION_COLLISION")
    return PreallocatedDestination(
        path=path,
        ancestor_identities=ancestor_identities,
        _factory_token=_DESTINATION_FACTORY_TOKEN,
    )


def bind_principal_existing_png_file(
    *,
    path: Path,
    expected_identity: tuple[int, int] | None = None,
) -> BoundPngFile:
    """Bind one exact existing PNG; never discover or substitute another file."""

    if not isinstance(path, Path) or not path.is_absolute():
        _fail("INVALID_PROVIDER_FILE", "existing PNG path must be an absolute Path")
    original = path
    _require_not_reparse(original, code="INVALID_PROVIDER_FILE")
    try:
        resolved = original.resolve(strict=True)
        parent = original.parent.resolve(strict=True)
        info = os.lstat(original)
    except OSError as error:
        raise D02R2PngReceiverError(
            "INVALID_PROVIDER_FILE", "existing PNG file is unavailable"
        ) from error
    if resolved != original or parent != original.parent or not stat.S_ISREG(info.st_mode):
        _fail("INVALID_PROVIDER_FILE", "existing PNG is not an exact regular file")
    identity = info.st_dev, info.st_ino
    if expected_identity is not None and identity != expected_identity:
        _fail("INVALID_PROVIDER_FILE", "existing PNG identity differs from private checkpoint")
    return BoundPngFile(
        path=original,
        identity=identity,
        ancestor_identities=_capture_ancestor_identities(parent),
        _factory_token=_BOUND_PNG_FILE_FACTORY_TOKEN,
    )


class ImageGenResultMaterializer:
    """Convert one structured ImageGen result into the existing PNG receiver.

    The materializer intentionally ignores prompts, revised prompts, and free-form
    output hints.  It supports canonical MCP image fields and the exact structured
    Codex ``image_gen.generation`` extension event.  It never logs or returns the
    private bytes or locator.
    """

    def receive(
        self,
        *,
        result_metadata: object,
        destination: PreallocatedDestination,
        allowed_saved_file: Path | None = None,
    ) -> ReceivedPng:
        kind, reference = _extract_programmatic_imagegen_reference(
            result_metadata,
            allowed_saved_file=allowed_saved_file,
        )
        if kind == "DATA_URL":
            return receive_imagegen_png(image_url=reference, destination=destination)
        if kind == "LOCAL_FILE":
            return receive_imagegen_png_file(
                source_file=Path(reference),
                destination=destination,
            )
        _fail(
            "TOOL_RESULT_NOT_PROGRAMMATICALLY_MATERIALIZABLE",
            "ImageGen result reference kind is unsupported",
        )


def _extract_programmatic_imagegen_reference(
    value: object,
    *,
    allowed_saved_file: Path | None,
) -> tuple[str, str]:
    if not isinstance(value, Mapping):
        _fail("RESULT_REFERENCE_NOT_RETURNED", "ImageGen result must be an object")

    payload = value.get("payload")
    if isinstance(payload, Mapping):
        item = payload.get("item")
        if isinstance(item, Mapping) and item.get("kind") == "image_gen.generation":
            if _has_inline_image_reference_field(value):
                _fail(
                    "TOOL_RESULT_NOT_PROGRAMMATICALLY_MATERIALIZABLE",
                    "ImageGen wrapper and nested item both contain image references",
                )
            value = item

    if value.get("kind") == "image_gen.generation":
        if (
            value.get("type") != "Extension"
            or value.get("status") != "completed"
            or value.get("failure") is not None
        ):
            _fail(
                "TOOL_RESULT_NOT_PROGRAMMATICALLY_MATERIALIZABLE",
                "ImageGen extension result is not a completed success",
            )
        if _has_inline_image_reference_field(value):
            _fail(
                "TOOL_RESULT_NOT_PROGRAMMATICALLY_MATERIALIZABLE",
                "ImageGen extension mixes result fields with inline image references",
            )
        raw_result = value.get("result")
        saved_path = value.get("savedPath")
        raw_result_present = isinstance(raw_result, str) and bool(raw_result)
        saved_path_present = isinstance(saved_path, str) and bool(saved_path)
        if raw_result is not None and raw_result != "" and not isinstance(raw_result, str):
            _fail(
                "TOOL_RESULT_NOT_PROGRAMMATICALLY_MATERIALIZABLE",
                "ImageGen extension result bytes have an unsupported type",
            )
        if saved_path is not None and saved_path != "" and not isinstance(saved_path, str):
            _fail(
                "TOOL_RESULT_NOT_PROGRAMMATICALLY_MATERIALIZABLE",
                "ImageGen extension saved path has an unsupported type",
            )
        if raw_result_present and saved_path_present:
            _fail(
                "TOOL_RESULT_NOT_PROGRAMMATICALLY_MATERIALIZABLE",
                "ImageGen extension returned multiple image references",
            )
        if raw_result_present:
            assert isinstance(raw_result, str)
            if raw_result.startswith(DATA_URL_PREFIX):
                return "DATA_URL", raw_result
            return "DATA_URL", DATA_URL_PREFIX + raw_result
        if not saved_path_present:
            _fail(
                "RESULT_REFERENCE_NOT_RETURNED",
                "ImageGen extension returned neither result bytes nor a saved path",
            )
        assert isinstance(saved_path, str)
        source = Path(saved_path)
        if not source.is_absolute():
            if os.name != "nt" and re.fullmatch(r"[A-Za-z]:[\\/].+", saved_path):
                _fail(
                    "HOST_CONTAINER_PATH_MISMATCH",
                    "ImageGen returned a host path that is not mapped in this process",
                )
            _fail(
                "TOOL_RESULT_NOT_PROGRAMMATICALLY_MATERIALIZABLE",
                "ImageGen saved path is not absolute",
            )
        if allowed_saved_file is None:
            _fail(
                "TOOL_RESULT_NOT_PROGRAMMATICALLY_MATERIALIZABLE",
                "ImageGen saved path lacks a Principal-bound file capability",
            )
        try:
            resolved_source = source.resolve(strict=True)
            resolved_allowed = allowed_saved_file.resolve(strict=True)
        except OSError:
            _fail("GENERATED_FILE_NOT_FOUND", "ImageGen saved file is unavailable")
        if resolved_source != source or resolved_allowed != allowed_saved_file:
            _fail(
                "TOOL_RESULT_NOT_PROGRAMMATICALLY_MATERIALIZABLE",
                "ImageGen saved path changed identity before materialization",
            )
        if resolved_source != resolved_allowed or not resolved_source.is_file():
            _fail(
                "TOOL_RESULT_NOT_PROGRAMMATICALLY_MATERIALIZABLE",
                "ImageGen saved path differs from the Principal-bound file",
            )
        return "LOCAL_FILE", str(resolved_source)

    return "DATA_URL", _extract_unique_inline_png_reference(
        value,
        missing_code="RESULT_REFERENCE_NOT_RETURNED",
        invalid_code="TOOL_RESULT_NOT_PROGRAMMATICALLY_MATERIALIZABLE",
    )


def _has_inline_image_reference_field(value: Mapping[object, object]) -> bool:
    return any(key in value for key in ("image_url", "structuredContent", "content"))


def _extract_unique_inline_png_reference(
    value: Mapping[object, object],
    *,
    missing_code: str,
    invalid_code: str,
) -> str:
    candidates: list[str] = []
    unsupported = False

    if "image_url" in value:
        direct = value.get("image_url")
        if isinstance(direct, str) and direct:
            candidates.append(direct)
        else:
            unsupported = True

    structured = value.get("structuredContent")
    if isinstance(structured, Mapping) and "image_url" in structured:
        structured_url = structured.get("image_url")
        if isinstance(structured_url, str) and structured_url:
            candidates.append(structured_url)
        else:
            unsupported = True
    elif (
        "structuredContent" in value
        and structured is not None
        and not isinstance(structured, Mapping)
    ):
        unsupported = True

    content = value.get("content")
    if isinstance(content, list):
        image_items = [
            item for item in content if isinstance(item, Mapping) and item.get("type") == "image"
        ]
        if len(image_items) > 1:
            _fail(invalid_code, "ImageGen result contains multiple image payloads")
        if len(image_items) == 1:
            image_item = image_items[0]
            data = image_item.get("data")
            if image_item.get("mimeType") == "image/png" and isinstance(data, str) and data:
                candidates.append(DATA_URL_PREFIX + data)
            else:
                unsupported = True
    elif "content" in value and content is not None:
        unsupported = True

    if unsupported or len(candidates) > 1:
        _fail(invalid_code, "ImageGen result does not contain one unique supported PNG reference")
    if len(candidates) == 1:
        return candidates[0]
    if "output_hint" in value:
        _fail(invalid_code, "free-form output_hint is not a programmatic image reference")
    _fail(missing_code, "ImageGen result has no supported reference")


def receive_imagegen_png(*, image_url: str, destination: PreallocatedDestination) -> ReceivedPng:
    """Validate a canonical PNG data URL fully in memory, then persist it once."""

    data = _decode_canonical_png_data_url(image_url)
    facts = _validate_png_bytes(data)
    replayed = destination.write_create_new_durable(data)
    if replayed != data:
        _fail("DESTINATION_REPLAY_FAILED", "durable replay bytes differ from validated PNG")
    if hashlib.sha256(replayed).digest() != hashlib.sha256(data).digest():
        _fail("DESTINATION_REPLAY_FAILED", "durable replay digest differs from validated PNG")
    replayed_facts = _validate_png_bytes(replayed)
    if replayed_facts != facts:
        _fail("DESTINATION_REPLAY_FAILED", "durable replay metadata differs from validated PNG")
    return facts


def receive_imagegen_result_file(
    *,
    result_file: Path,
    destination: PreallocatedDestination,
) -> ReceivedPng:
    """Consume one private provider-result file before publishing its PNG."""

    return receive_imagegen_png(
        image_url=consume_imagegen_result_file(result_file),
        destination=destination,
    )


def receive_imagegen_png_file(
    *, source_file: Path, destination: PreallocatedDestination
) -> ReceivedPng:
    """Consume a built-in ImageGen local-file handoff through the same writer."""

    return bind_principal_existing_png_file(path=source_file).copy_create_new(
        destination=destination
    )


def consume_imagegen_result_file(result_file: Path) -> str:
    """Read, remove, and decode the provider envelope without publishing bytes."""

    result_bytes = _consume_provider_result_file(result_file)
    try:
        value: object = json.loads(result_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise D02R2PngReceiverError(
            "INVALID_PROVIDER_RESULT", "provider result is not canonical JSON"
        ) from error
    return _extract_image_url(value)


def _extract_image_url(value: object) -> str:
    if not isinstance(value, dict):
        _fail("INVALID_PROVIDER_RESULT", "provider result must be an object")
    return _extract_unique_inline_png_reference(
        value,
        missing_code="INVALID_PROVIDER_RESULT",
        invalid_code="INVALID_PROVIDER_RESULT",
    )


def _decode_canonical_png_data_url(image_url: str) -> bytes:
    if not isinstance(image_url, str):
        _fail("INVALID_IMAGE_URL_TYPE", "image_url must be a string")
    try:
        ascii_url = image_url.encode("ascii")
    except UnicodeEncodeError as error:
        raise D02R2PngReceiverError("INVALID_DATA_URL", "image_url must be ASCII") from error
    if len(ascii_url) > MAXIMUM_COMPLETE_DATA_URL_ASCII_BYTES:
        _fail("DATA_URL_TOO_LARGE", "complete image data URL exceeds the frozen maximum")
    if not image_url.startswith(DATA_URL_PREFIX):
        _fail("INVALID_DATA_URL", "only the exact PNG data URL prefix is accepted")
    payload = image_url[len(DATA_URL_PREFIX) :]
    if not payload or len(payload) > MAXIMUM_CANONICAL_BASE64_PAYLOAD_BYTES:
        _fail("INVALID_BASE64", "base64 payload is empty or exceeds the frozen maximum")
    try:
        decoded = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as error:
        raise D02R2PngReceiverError("INVALID_BASE64", "payload is not strict base64") from error
    if base64.b64encode(decoded).decode("ascii") != payload:
        _fail("INVALID_BASE64", "payload is not canonical base64")
    if len(decoded) > MAXIMUM_BYTES:
        _fail("PNG_TOO_LARGE", "decoded PNG exceeds the frozen maximum")
    return decoded


def _validate_png_bytes(data: bytes) -> ReceivedPng:
    width, height = _validate_png_container(data)
    _validate_png_dimensions(width, height)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as checked:
                if checked.format != "PNG":
                    _fail("PNG_DECODE_FAILED", "Pillow did not identify a PNG")
                checked.verify()
            with Image.open(BytesIO(data)) as loaded:
                if loaded.format != "PNG":
                    _fail("PNG_DECODE_FAILED", "Pillow reopen did not identify a PNG")
                frame_count = getattr(loaded, "n_frames", 1)
                if frame_count != 1 or bool(getattr(loaded, "is_animated", False)):
                    _fail("PNG_ANIMATION_FORBIDDEN", "animated PNGs are forbidden")
                if loaded.size != (width, height):
                    _fail("PNG_DECODE_FAILED", "Pillow dimensions differ from the PNG header")
                loaded.seek(0)
                loaded.load()
    except D02R2PngReceiverError:
        raise
    except (
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
        OSError,
        ValueError,
    ) as error:
        raise D02R2PngReceiverError(
            "PNG_DECODE_FAILED", "Pillow PNG verification failed"
        ) from error
    return ReceivedPng(
        byte_size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        width=width,
        height=height,
        _factory_token=_RECEIVED_PNG_FACTORY_TOKEN,
    )


def _validate_png_dimensions(width: int, height: int) -> None:
    if (
        width < MINIMUM_EDGE_PIXELS
        or height < MINIMUM_EDGE_PIXELS
        or width > MAXIMUM_EDGE_PIXELS
        or height > MAXIMUM_EDGE_PIXELS
    ):
        _fail("PNG_DIMENSIONS_INVALID", "PNG edge dimensions are outside frozen bounds")
    if width * height > MAXIMUM_PIXEL_COUNT:
        _fail("PNG_DIMENSIONS_INVALID", "PNG pixel count exceeds the frozen maximum")


def _validate_png_container(data: bytes) -> tuple[int, int]:
    signature = b"\x89PNG\r\n\x1a\n"
    if not data.startswith(signature):
        _fail("INVALID_PNG_SIGNATURE", "PNG signature is missing")
    position = len(signature)
    seen_ihdr = False
    seen_plte = False
    seen_idat = False
    idat_closed = False
    seen_iend = False
    width = 0
    height = 0
    color_type = -1
    while position < len(data):
        if len(data) - position < 12:
            _fail("INVALID_PNG_CONTAINER", "PNG chunk header is truncated")
        length = int.from_bytes(data[position : position + 4], "big")
        if length > MAXIMUM_BYTES or length > len(data) - position - 12:
            _fail("INVALID_PNG_CONTAINER", "PNG chunk length is out of bounds")
        chunk_type = data[position + 4 : position + 8]
        if not all(65 <= value <= 90 or 97 <= value <= 122 for value in chunk_type):
            _fail("INVALID_PNG_CONTAINER", "PNG chunk type is invalid")
        if 97 <= chunk_type[2] <= 122:
            _fail("INVALID_PNG_CONTAINER", "PNG reserved chunk-type bit is invalid")
        chunk_end = position + 12 + length
        chunk_data = data[position + 8 : position + 8 + length]
        expected_crc = int.from_bytes(data[position + 8 + length : chunk_end], "big")
        if zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF != expected_crc:
            _fail("INVALID_PNG_CONTAINER", "PNG chunk CRC is invalid")
        if not seen_ihdr:
            if chunk_type != b"IHDR" or length != 13:
                _fail("INVALID_PNG_CONTAINER", "IHDR must be the first 13-byte PNG chunk")
            seen_ihdr = True
            width = int.from_bytes(chunk_data[0:4], "big")
            height = int.from_bytes(chunk_data[4:8], "big")
            bit_depth = chunk_data[8]
            color_type = chunk_data[9]
            valid_depths = {
                0: {1, 2, 4, 8, 16},
                2: {8, 16},
                3: {1, 2, 4, 8},
                4: {8, 16},
                6: {8, 16},
            }
            if (
                color_type not in valid_depths
                or bit_depth not in valid_depths[color_type]
                or chunk_data[10] != 0
                or chunk_data[11] != 0
                or chunk_data[12] not in {0, 1}
            ):
                _fail("INVALID_PNG_CONTAINER", "IHDR fields are invalid")
        elif chunk_type == b"IHDR":
            _fail("INVALID_PNG_CONTAINER", "IHDR must occur exactly once")
        elif chunk_type == b"PLTE":
            if (
                seen_plte
                or seen_idat
                or color_type in {0, 4}
                or length == 0
                or length > 768
                or length % 3 != 0
            ):
                _fail("INVALID_PNG_CONTAINER", "PLTE order or length is invalid")
            seen_plte = True
        elif chunk_type == b"IDAT":
            if idat_closed or (color_type == 3 and not seen_plte):
                _fail("INVALID_PNG_CONTAINER", "IDAT order is invalid")
            seen_idat = True
        elif chunk_type == b"IEND":
            if length != 0 or seen_iend or not seen_idat or chunk_end != len(data):
                _fail("INVALID_PNG_CONTAINER", "IEND must occur exactly once at the end")
            seen_iend = True
            position = chunk_end
            break
        else:
            if 65 <= chunk_type[0] <= 90:
                _fail("INVALID_PNG_CONTAINER", "unknown critical PNG chunk is forbidden")
            if seen_idat:
                idat_closed = True
        position = chunk_end
    if not seen_ihdr or not seen_iend or position != len(data):
        _fail("INVALID_PNG_CONTAINER", "PNG is missing its final IEND")
    return width, height


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        try:
            written = os.write(descriptor, view[offset:])
        except OSError as error:
            raise D02R2PngReceiverError("DESTINATION_WRITE_FAILED", "file write failed") from error
        if written <= 0 or written > len(view) - offset:
            _fail("DESTINATION_WRITE_FAILED", "short file write failed closed")
        offset += written


def _write_staged_file(path: Path, data: bytes) -> tuple[int, int]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as error:
        raise D02R2PngReceiverError(
            "DESTINATION_TEMP_COLLISION", "staging destination already exists"
        ) from error
    except OSError as error:
        raise D02R2PngReceiverError(
            "DESTINATION_WRITE_FAILED", "exclusive staging create failed"
        ) from error
    identity: tuple[int, int] | None = None
    try:
        identity = _descriptor_identity(descriptor, code="DESTINATION_WRITE_FAILED")
        _write_all(descriptor, data)
        try:
            os.fsync(descriptor)
        except OSError as error:
            raise D02R2PngReceiverError(
                "DESTINATION_DURABILITY_FAILED", "staging file sync failed"
            ) from error
        _require_opened_path_identity(path, identity, code="DESTINATION_WRITE_FAILED")
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        _best_effort_unlink_owned(path, identity)
        raise
    try:
        os.close(descriptor)
    except OSError as error:
        _best_effort_unlink_owned(path, identity)
        raise D02R2PngReceiverError(
            "DESTINATION_DURABILITY_FAILED", "staging file close failed"
        ) from error
    return identity


def _consume_provider_result_file(path: Path) -> bytes:
    if not isinstance(path, Path) or not path.is_absolute():
        _fail("INVALID_PROVIDER_RESULT", "provider result path must be absolute")
    if _SAFE_LEAF_RE.fullmatch(path.name) is None or path.name in {".", ".."}:
        _fail("INVALID_PROVIDER_RESULT", "provider result leaf is invalid")
    try:
        parent = path.parent.resolve(strict=True)
    except OSError as error:
        raise D02R2PngReceiverError(
            "INVALID_PROVIDER_RESULT", "provider result parent is unavailable"
        ) from error
    if parent != path.parent:
        _fail("INVALID_PROVIDER_RESULT", "provider result parent changed identity")
    ancestors = _capture_ancestor_identities(parent)
    _require_not_reparse(path, code="INVALID_PROVIDER_RESULT")
    identity = _path_identity(path, code="INVALID_PROVIDER_RESULT")
    result = _read_file_bytes_no_follow(
        path,
        maximum_bytes=MAXIMUM_PROVIDER_RESULT_FILE_BYTES,
        code="INVALID_PROVIDER_RESULT",
        expected_identity=identity,
    )
    _require_opened_path_identity(path, identity, code="INVALID_PROVIDER_RESULT")
    try:
        os.unlink(path)
        _sync_directory(parent)
    except OSError as error:
        raise D02R2PngReceiverError(
            "PROVIDER_RESULT_CLEANUP_FAILED", "provider result cleanup failed"
        ) from error
    _validate_ancestor_identities(ancestors, code="INVALID_PROVIDER_RESULT")
    return result


def _read_file_bytes_no_follow(
    path: Path,
    *,
    maximum_bytes: int,
    code: str = "DESTINATION_REPLAY_FAILED",
    expected_identity: tuple[int, int] | None = None,
) -> bytes:
    _require_not_reparse(path, code=code)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise D02R2PngReceiverError(code, "no-follow file open failed") from error
    try:
        try:
            opened_info = os.fstat(descriptor)
        except OSError as error:
            raise D02R2PngReceiverError(code, "descriptor identity lookup failed") from error
        opened_identity = opened_info.st_dev, opened_info.st_ino
        if not stat.S_ISREG(opened_info.st_mode):
            _fail(code, "opened path is not a regular file")
        if expected_identity is not None and opened_identity != expected_identity:
            _fail(code, "opened file identity differs from the bound file")
        chunks: list[bytes] = []
        total = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            total += len(chunk)
            if total > maximum_bytes:
                _fail(code, "file read exceeded its maximum byte size")
            chunks.append(chunk)
        _require_opened_path_identity(path, opened_identity, code=code)
        return b"".join(chunks)
    except D02R2PngReceiverError:
        raise
    except OSError as error:
        raise D02R2PngReceiverError(code, "no-follow file read failed") from error
    finally:
        try:
            os.close(descriptor)
        except OSError as error:
            raise D02R2PngReceiverError(code, "no-follow file close failed") from error


def _best_effort_unlink_owned(path: Path, identity: tuple[int, int] | None) -> None:
    if identity is None:
        return
    try:
        _require_not_reparse(path, code="DESTINATION_TEMP_CLEANUP_FAILED")
        if _path_identity(path, code="DESTINATION_TEMP_CLEANUP_FAILED") == identity:
            os.unlink(path)
    except (D02R2PngReceiverError, OSError):
        return


def _best_effort_sync_directory(path: Path) -> None:
    try:
        _sync_directory(path)
    except OSError:
        return


def _capture_ancestor_identities(
    parent: Path,
) -> tuple[tuple[Path, tuple[int, int]], ...]:
    paths = (parent, *parent.parents)
    identities: list[tuple[Path, tuple[int, int]]] = []
    for path in paths:
        _require_not_reparse(path, code="DESTINATION_CAPABILITY_INVALID")
        identities.append((path, _path_identity(path, code="DESTINATION_CAPABILITY_INVALID")))
    return tuple(identities)


def _validate_ancestor_identities(
    identities: tuple[tuple[Path, tuple[int, int]], ...],
    *,
    code: str,
) -> None:
    if not identities:
        _fail(code, "destination ancestor identity set is empty")
    for path, expected_identity in identities:
        _require_not_reparse(path, code=code)
        if _path_identity(path, code=code) != expected_identity:
            _fail(code, "destination ancestor identity changed")


def _descriptor_identity(descriptor: int, *, code: str) -> tuple[int, int]:
    try:
        info = os.fstat(descriptor)
    except OSError as error:
        raise D02R2PngReceiverError(code, "descriptor identity lookup failed") from error
    return info.st_dev, info.st_ino


def _path_identity(path: Path, *, code: str) -> tuple[int, int]:
    try:
        info = os.stat(path, follow_symlinks=False)
    except OSError as error:
        raise D02R2PngReceiverError(code, "path identity lookup failed") from error
    return info.st_dev, info.st_ino


def _require_opened_path_identity(path: Path, identity: tuple[int, int], *, code: str) -> None:
    _require_not_reparse(path, code=code)
    if _path_identity(path, code=code) != identity:
        _fail(code, "opened file identity changed before validation")


def _require_not_reparse_if_exists(path: Path, *, code: str) -> None:
    try:
        _require_not_reparse(path, code=code)
    except D02R2PngReceiverError as error:
        if isinstance(error.__cause__, FileNotFoundError):
            return
        raise


def _require_not_reparse(path: Path, *, code: str) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError as error:
        raise D02R2PngReceiverError(code, "required path does not exist") from error
    except OSError as error:
        raise D02R2PngReceiverError(code, "path lstat failed") from error
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if stat.S_ISLNK(info.st_mode) or (reparse_flag and attributes & reparse_flag):
        _fail(code, "symlink, junction, or reparse point is forbidden")


def _sync_directory(path: Path) -> None:
    if os.name != "nt":
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return
    _sync_directory_windows(path)


def _sync_directory_windows(path: Path) -> None:
    from ctypes import wintypes

    win_dll = getattr(ctypes, "WinDLL", None)
    if not callable(win_dll):
        raise OSError("Windows DLL loader is unavailable")
    kernel32 = win_dll("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    flush_file_buffers = kernel32.FlushFileBuffers
    flush_file_buffers.argtypes = [wintypes.HANDLE]
    flush_file_buffers.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    handle = create_file(
        str(path),
        0x80000000 | 0x40000000,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        raise OSError(_windows_last_error(), "CreateFileW failed for directory durability")
    try:
        if not flush_file_buffers(handle):
            raise OSError(_windows_last_error(), "FlushFileBuffers failed for directory")
    finally:
        if not close_handle(handle):
            raise OSError(_windows_last_error(), "CloseHandle failed for directory")


def _windows_last_error() -> int:
    get_last_error = getattr(ctypes, "get_last_error", None)
    if not callable(get_last_error):
        _fail("DESTINATION_DURABILITY_FAILED", "Windows last-error API is unavailable")
    value = cast(Callable[[], object], get_last_error)()
    if not isinstance(value, int) or isinstance(value, bool):
        _fail("DESTINATION_DURABILITY_FAILED", "Windows last-error API returned invalid data")
    return value


def _fail(code: str, message: str) -> NoReturn:
    raise D02R2PngReceiverError(code, message)


class _FailClosedArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> NoReturn:
        _fail("INVALID_PROVIDER_RESULT", "receiver CLI arguments are invalid")


def _run_cli(argv: list[str] | None = None) -> int:
    try:
        parser = _FailClosedArgumentParser()
        parser.add_argument("--tool-result-stdin", action="store_true")
        parser.add_argument("--destination-leaf", required=True)
        args = parser.parse_args(argv)
        if not bool(args.tool_result_stdin):
            _fail("INVALID_PROVIDER_RESULT", "typed tool result stdin is required")
        if sys.stdin.isatty():
            _fail("INVALID_PROVIDER_RESULT", "typed tool result stdin must be non-TTY")
        parent = Path.cwd().resolve(strict=True)
        destination = bind_principal_preallocated_destination(
            parent=parent,
            leaf_name=cast(str, args.destination_leaf),
        )
        raw_result = sys.stdin.buffer.read(MAXIMUM_PROVIDER_RESULT_FILE_BYTES + 1)
        if len(raw_result) > MAXIMUM_PROVIDER_RESULT_FILE_BYTES:
            _fail("INVALID_PROVIDER_RESULT", "tool result exceeds the frozen maximum")
        try:
            result_metadata: object = json.loads(raw_result.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise D02R2PngReceiverError(
                "INVALID_PROVIDER_RESULT", "tool result stdin is not JSON"
            ) from error
        result = ImageGenResultMaterializer().receive(
            result_metadata=result_metadata,
            destination=destination,
        )
    except D02R2PngReceiverError as error:
        print(
            json.dumps(
                {"status": "FAILED", "code": error.code},
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    except Exception:
        print(
            json.dumps(
                {"status": "FAILED", "code": "INTERNAL_RECEIVER_FAILURE"},
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "status": "PERSISTED",
                "media_type": "image/png",
                "byte_size": result.byte_size,
                "sha256": result.sha256,
                "width": result.width,
                "height": result.height,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_cli())
