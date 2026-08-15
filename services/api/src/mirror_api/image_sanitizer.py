"""Strict, dependency-local canonicalization for untrusted image bytes.

This module deliberately has no database, HTTP, task-runner, provider, or logging
dependency.  Callers receive only allowlisted error codes and never decoder text.
"""

from __future__ import annotations

import warnings
from collections.abc import AsyncIterable, Iterable
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import BinaryIO, Literal, cast

from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError

SanitizerErrorCode = Literal[
    "unsupported_image_type",
    "image_too_large",
    "image_magic_mismatch",
    "image_type_mismatch",
    "image_decode_failed",
    "image_decompression_bomb",
    "image_animated",
    "image_dimensions_invalid",
    "image_dimensions_exceeded",
    "image_pixels_exceeded",
    "sanitized_output_too_large",
    "sanitized_output_invalid",
]

CANONICAL_MIME_TYPE: Literal["image/jpeg"] = "image/jpeg"
SANITIZER_VERSION: Literal["image-sanitizer-v1"] = "image-sanitizer-v1"
_FORMAT_TO_MIME: dict[str, str] = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
_MAGIC_BY_FORMAT: dict[str, tuple[bytes, ...]] = {
    "JPEG": (b"\xff\xd8\xff",),
    "PNG": (b"\x89PNG\r\n\x1a\n",),
    "WEBP": (),
}
_REDACTED_INFO_KEYS = frozenset({"exif", "icc_profile", "xmp", "comment", "xml"})


class ImageSanitizationError(ValueError):
    """A stable, non-diagnostic rejection suitable for an ingestion record."""

    def __init__(self, code: SanitizerErrorCode) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ImageSanitizerConfig:
    version: Literal["image-sanitizer-v1"] = SANITIZER_VERSION
    max_input_bytes: int = 20 * 1024 * 1024
    max_output_bytes: int = 20 * 1024 * 1024
    min_edge_pixels: int = 64
    max_edge_pixels: int = 8192
    max_pixel_count: int = 40_000_000
    spool_memory_bytes: int = 1024 * 1024
    jpeg_quality_ladder: tuple[int, ...] = (95, 90, 85, 80, 75)

    def __post_init__(self) -> None:
        if self.max_input_bytes < 1 or self.max_output_bytes < 1:
            raise ValueError("sanitizer byte limits must be positive")
        if self.min_edge_pixels < 1 or self.max_edge_pixels < self.min_edge_pixels:
            raise ValueError("sanitizer edge limits are invalid")
        if self.max_pixel_count < self.min_edge_pixels * self.min_edge_pixels:
            raise ValueError("sanitizer pixel limit is invalid")
        if self.spool_memory_bytes < 1:
            raise ValueError("sanitizer spool limit must be positive")
        if not self.jpeg_quality_ladder or any(
            quality < 1 or quality > 100 for quality in self.jpeg_quality_ladder
        ):
            raise ValueError("sanitizer JPEG quality ladder is invalid")


@dataclass(frozen=True)
class SanitizedImage:
    version: Literal["image-sanitizer-v1"]
    content_type: Literal["image/jpeg"]
    bytes_value: bytes
    sha256: str
    byte_size: int
    width: int
    height: int


DEFAULT_IMAGE_SANITIZER_CONFIG = ImageSanitizerConfig()


def sanitize_image(
    raw_bytes: bytes,
    *,
    declared_mime_type: str,
    config: ImageSanitizerConfig = DEFAULT_IMAGE_SANITIZER_CONFIG,
    spool_root: Path | None = None,
) -> SanitizedImage:
    """Sanitize one already-bounded byte value without inspecting its metadata."""
    return sanitize_image_stream(
        (raw_bytes,),
        declared_mime_type=declared_mime_type,
        config=config,
        spool_root=spool_root,
    )


def sanitize_image_stream(
    chunks: Iterable[bytes],
    *,
    declared_mime_type: str,
    config: ImageSanitizerConfig = DEFAULT_IMAGE_SANITIZER_CONFIG,
    spool_root: Path | None = None,
) -> SanitizedImage:
    """Boundedly spool and canonicalize a JPEG, PNG, or WebP stream.

    The output is always a freshly encoded, metadata-free JPEG; input container
    bytes (including trailing/polyglot data) are never copied to output.
    """
    if declared_mime_type not in _FORMAT_TO_MIME.values():
        raise ImageSanitizationError("unsupported_image_type")
    directory = _validated_spool_root(spool_root) if spool_root is not None else None
    try:
        with SpooledTemporaryFile(
            max_size=config.spool_memory_bytes,
            mode="w+b",
            dir=directory,
        ) as opened_source:
            source = cast(BinaryIO, opened_source)
            _write_bounded(chunks, source, max_bytes=config.max_input_bytes)
            return _sanitize_spooled_source(
                source, declared_mime_type=declared_mime_type, config=config
            )
    except ImageSanitizationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageSanitizationError("image_decompression_bomb") from None
    except (OSError, SyntaxError, UnidentifiedImageError, ValueError):
        raise ImageSanitizationError("image_decode_failed") from None


async def sanitize_async_image_stream(
    chunks: AsyncIterable[bytes],
    *,
    declared_mime_type: str,
    config: ImageSanitizerConfig = DEFAULT_IMAGE_SANITIZER_CONFIG,
    spool_root: Path | None = None,
) -> SanitizedImage:
    """Boundedly sanitize an async storage stream without materializing raw bytes."""
    if declared_mime_type not in _FORMAT_TO_MIME.values():
        raise ImageSanitizationError("unsupported_image_type")
    directory = _validated_spool_root(spool_root) if spool_root is not None else None
    try:
        with SpooledTemporaryFile(
            max_size=config.spool_memory_bytes,
            mode="w+b",
            dir=directory,
        ) as opened_source:
            source = cast(BinaryIO, opened_source)
            received = 0
            async for chunk in chunks:
                if not isinstance(chunk, bytes):
                    raise ImageSanitizationError("image_decode_failed")
                received += len(chunk)
                if received > config.max_input_bytes:
                    raise ImageSanitizationError("image_too_large")
                source.write(chunk)
            return _sanitize_spooled_source(
                source, declared_mime_type=declared_mime_type, config=config
            )
    except ImageSanitizationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageSanitizationError("image_decompression_bomb") from None
    except (OSError, SyntaxError, UnidentifiedImageError, ValueError):
        raise ImageSanitizationError("image_decode_failed") from None


def _sanitize_spooled_source(
    source: BinaryIO, *, declared_mime_type: str, config: ImageSanitizerConfig
) -> SanitizedImage:
    source.seek(0)
    expected_format = _expected_format(source, declared_mime_type)
    source.seek(0)
    _decode_and_validate(source, expected_format, config)
    source.seek(0)
    encoded, width, height = _canonical_encode(source, expected_format, config)
    _validate_output(
        encoded,
        width=width,
        height=height,
        pixels=width * height,
        config=config,
    )
    return SanitizedImage(
        version=config.version,
        content_type=CANONICAL_MIME_TYPE,
        bytes_value=encoded,
        sha256=sha256(encoded).hexdigest(),
        byte_size=len(encoded),
        width=width,
        height=height,
    )


def _validated_spool_root(root: Path) -> str:
    candidate = root.absolute()
    if candidate.is_symlink():
        raise ImageSanitizationError("sanitized_output_invalid")
    candidate.mkdir(parents=True, exist_ok=True)
    resolved = candidate.resolve(strict=True)
    if resolved.is_symlink():
        raise ImageSanitizationError("sanitized_output_invalid")
    return str(resolved)


def _write_bounded(chunks: Iterable[bytes], destination: BinaryIO, *, max_bytes: int) -> int:
    received = 0
    for chunk in chunks:
        if not isinstance(chunk, bytes):
            raise ImageSanitizationError("image_decode_failed")
        received += len(chunk)
        if received > max_bytes:
            raise ImageSanitizationError("image_too_large")
        destination.write(chunk)
    return received


def _expected_format(source: BinaryIO, declared_mime_type: str) -> str:
    header = source.read(16)
    detected_format: str | None = None
    for image_format, magics in _MAGIC_BY_FORMAT.items():
        if any(header.startswith(magic) for magic in magics):
            detected_format = image_format
            break
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        detected_format = "WEBP"
    if detected_format is None:
        raise ImageSanitizationError("image_magic_mismatch")
    if _FORMAT_TO_MIME[detected_format] != declared_mime_type:
        raise ImageSanitizationError("image_type_mismatch")
    return detected_format


def _decode_and_validate(
    source: BinaryIO,
    expected_format: str,
    config: ImageSanitizerConfig,
) -> tuple[int, int, int]:
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(source, formats=("JPEG", "PNG", "WEBP")) as image:
            if image.format != expected_format:
                raise ImageSanitizationError("image_type_mismatch")
            if bool(getattr(image, "is_animated", False)) or getattr(image, "n_frames", 1) != 1:
                raise ImageSanitizationError("image_animated")
            width, height = image.size
            pixels = width * height
            _validate_dimensions(width, height, pixels, config)
            image.verify()
    return width, height, pixels


def _canonical_encode(
    source: BinaryIO,
    expected_format: str,
    config: ImageSanitizerConfig,
) -> tuple[bytes, int, int]:
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(source, formats=("JPEG", "PNG", "WEBP")) as image:
            if image.format != expected_format or bool(getattr(image, "is_animated", False)):
                raise ImageSanitizationError("image_type_mismatch")
            if getattr(image, "n_frames", 1) != 1:
                raise ImageSanitizationError("image_animated")
            image.load()
            oriented = ImageOps.exif_transpose(image)
            try:
                rgb = _assumed_srgb_rgb(oriented)
                try:
                    rgb.info.clear()
                    for quality in config.jpeg_quality_ladder:
                        output = BytesIO()
                        rgb.save(
                            output,
                            format="JPEG",
                            quality=quality,
                            subsampling="4:2:0",
                            optimize=False,
                            progressive=False,
                        )
                        encoded = output.getvalue()
                        if len(encoded) <= config.max_output_bytes:
                            return encoded, rgb.width, rgb.height
                finally:
                    rgb.close()
            finally:
                if oriented is not image:
                    oriented.close()
    raise ImageSanitizationError("sanitized_output_too_large")


def _assumed_srgb_rgb(image: Image.Image) -> Image.Image:
    """Discard profiles/metadata and composite alpha onto the fixed white background."""
    if "A" in image.getbands():
        rgba = image.convert("RGBA")
        try:
            canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
            try:
                canvas.alpha_composite(rgba)
                return canvas.convert("RGB")
            finally:
                canvas.close()
        finally:
            rgba.close()
    return image.convert("RGB")


def _validate_dimensions(
    width: int, height: int, pixels: int, config: ImageSanitizerConfig
) -> None:
    if width < 1 or height < 1:
        raise ImageSanitizationError("image_dimensions_invalid")
    if min(width, height) < config.min_edge_pixels:
        raise ImageSanitizationError("image_dimensions_invalid")
    if max(width, height) > config.max_edge_pixels:
        raise ImageSanitizationError("image_dimensions_exceeded")
    if pixels > config.max_pixel_count:
        raise ImageSanitizationError("image_pixels_exceeded")


def _validate_output(
    encoded: bytes,
    *,
    width: int,
    height: int,
    pixels: int,
    config: ImageSanitizerConfig,
) -> None:
    if not encoded or len(encoded) > config.max_output_bytes:
        raise ImageSanitizationError("sanitized_output_too_large")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(encoded), formats=("JPEG",)) as image:
                if (
                    image.format != "JPEG"
                    or getattr(image, "n_frames", 1) != 1
                    or image.size != (width, height)
                ):
                    raise ImageSanitizationError("sanitized_output_invalid")
                _validate_dimensions(width, height, pixels, config)
                image.load()
                if image.getexif() or _REDACTED_INFO_KEYS.intersection(image.info):
                    raise ImageSanitizationError("sanitized_output_invalid")
    except ImageSanitizationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageSanitizationError("sanitized_output_invalid") from None
    except (OSError, SyntaxError, UnidentifiedImageError, ValueError):
        raise ImageSanitizationError("sanitized_output_invalid") from None
