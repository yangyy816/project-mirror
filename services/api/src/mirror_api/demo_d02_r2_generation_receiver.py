"""Fail-closed local receiver for one ImageGen PNG data URL.

This module deliberately has no knowledge of evidence roots, prompts, provider
responses, registries, or output locators.  Its only write authority is the
Principal-created :class:`PreallocatedDestination` capability.
"""

from __future__ import annotations

import base64
import binascii
import ctypes
import hashlib
import os
import re
import stat
import warnings
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Final, NoReturn, cast

from PIL import Image

DATA_URL_PREFIX: Final = "data:image/png;base64,"
MAXIMUM_BYTES: Final = 20_971_520
MAXIMUM_CANONICAL_BASE64_PAYLOAD_BYTES: Final = 27_962_028
MAXIMUM_COMPLETE_DATA_URL_ASCII_BYTES: Final = 27_962_050
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


@dataclass(frozen=True, slots=True)
class ReceivedPng:
    """Non-sensitive validation facts; it intentionally exposes no URL or path."""

    byte_size: int
    sha256: str
    width: int
    height: int


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
        """Write exactly once and independently replay the resulting bytes."""

        path = self._path
        parent = path.parent
        _validate_ancestor_identities(
            self._ancestor_identities,
            code="DESTINATION_WRITE_FAILED",
        )
        _require_not_reparse_if_exists(path, code="DESTINATION_COLLISION")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError as error:
            raise D02R2PngReceiverError(
                "DESTINATION_COLLISION", "preallocated destination already exists"
            ) from error
        except OSError as error:
            raise D02R2PngReceiverError(
                "DESTINATION_WRITE_FAILED", "exclusive create failed"
            ) from error
        try:
            opened_identity = _descriptor_identity(descriptor, code="DESTINATION_WRITE_FAILED")
            _write_all(descriptor, data)
            os.fsync(descriptor)
            _require_opened_path_identity(path, opened_identity, code="DESTINATION_REPLAY_FAILED")
        except D02R2PngReceiverError:
            raise
        except OSError as error:
            raise D02R2PngReceiverError(
                "DESTINATION_DURABILITY_FAILED", "file durability sync failed"
            ) from error
        finally:
            try:
                os.close(descriptor)
            except OSError as error:
                raise D02R2PngReceiverError(
                    "DESTINATION_DURABILITY_FAILED", "file close failed"
                ) from error
        try:
            _sync_directory(parent)
        except OSError as error:
            raise D02R2PngReceiverError(
                "DESTINATION_DURABILITY_FAILED", "parent durability sync failed"
            ) from error
        _validate_ancestor_identities(
            self._ancestor_identities,
            code="DESTINATION_REPLAY_FAILED",
        )
        return _read_file_bytes_no_follow(path, maximum_bytes=len(data))


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


def _read_file_bytes_no_follow(path: Path, *, maximum_bytes: int) -> bytes:
    _require_not_reparse(path, code="DESTINATION_REPLAY_FAILED")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise D02R2PngReceiverError(
            "DESTINATION_REPLAY_FAILED", "no-follow replay open failed"
        ) from error
    try:
        opened_identity = _descriptor_identity(descriptor, code="DESTINATION_REPLAY_FAILED")
        chunks: list[bytes] = []
        total = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            total += len(chunk)
            if total > maximum_bytes:
                _fail("DESTINATION_REPLAY_FAILED", "replay exceeded validated byte size")
            chunks.append(chunk)
        _require_opened_path_identity(path, opened_identity, code="DESTINATION_REPLAY_FAILED")
        return b"".join(chunks)
    except D02R2PngReceiverError:
        raise
    except OSError as error:
        raise D02R2PngReceiverError("DESTINATION_REPLAY_FAILED", "replay read failed") from error
    finally:
        os.close(descriptor)


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
