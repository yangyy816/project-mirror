from __future__ import annotations

import struct
import zlib
from collections.abc import AsyncIterator
from io import BytesIO

import pytest
from PIL import Image, PngImagePlugin  # type: ignore[import-not-found]

from mirror_api.image_sanitizer import (
    ImageSanitizationError,
    ImageSanitizerConfig,
    sanitize_async_image_stream,
    sanitize_image,
    sanitize_image_stream,
)


def _image_bytes(
    image_format: str,
    *,
    size: tuple[int, int] = (64, 80),
    mode: str = "RGB",
    **save_kwargs: object,
) -> bytes:
    image = Image.new(mode, size, (12, 34, 56, 128) if mode == "RGBA" else (12, 34, 56))
    try:
        output = BytesIO()
        image.save(output, format=image_format, **save_kwargs)
        return output.getvalue()
    finally:
        image.close()


@pytest.mark.parametrize(
    ("image_format", "mime_type"),
    (("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")),
)
def test_sanitizer_canonicalizes_supported_synthetic_formats(
    tmp_path, image_format: str, mime_type: str
) -> None:
    result = sanitize_image(
        _image_bytes(image_format), declared_mime_type=mime_type, spool_root=tmp_path
    )
    assert result.content_type == "image/jpeg"
    assert result.width == 64
    assert result.height == 80
    assert result.byte_size == len(result.bytes_value)
    with Image.open(BytesIO(result.bytes_value)) as output:
        assert output.format == "JPEG"
        assert output.size == (64, 80)
        assert not output.getexif()
        assert not {"exif", "icc_profile", "xmp", "comment"}.intersection(output.info)


def test_sanitizer_applies_exif_orientation_and_removes_metadata(tmp_path) -> None:
    exif = Image.Exif()
    exif[274] = 6
    raw = _image_bytes("JPEG", size=(64, 96), exif=exif, comment=b"synthetic-metadata")
    result = sanitize_image(raw, declared_mime_type="image/jpeg", spool_root=tmp_path)
    assert (result.width, result.height) == (96, 64)
    assert b"synthetic-metadata" not in result.bytes_value


def test_sanitizer_flattens_alpha_against_white(tmp_path) -> None:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    try:
        raw = BytesIO()
        image.save(raw, format="PNG")
    finally:
        image.close()
    result = sanitize_image(raw.getvalue(), declared_mime_type="image/png", spool_root=tmp_path)
    with Image.open(BytesIO(result.bytes_value)) as output:
        pixel = output.convert("RGB").getpixel((32, 32))
    assert min(pixel) >= 245


def test_sanitizer_removes_png_metadata_and_polyglot_trailer(tmp_path) -> None:
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("comment", "synthetic-non-face-metadata")
    raw = _image_bytes("PNG", pnginfo=png_info) + b"polyglot-sentinel-payload"
    result = sanitize_image(raw, declared_mime_type="image/png", spool_root=tmp_path)
    assert b"synthetic-non-face-metadata" not in result.bytes_value
    assert b"polyglot-sentinel-payload" not in result.bytes_value


def test_sanitizer_rejects_mismatch_truncation_animation_and_bomb(tmp_path) -> None:
    png = _image_bytes("PNG")
    with pytest.raises(ImageSanitizationError, match="image_type_mismatch"):
        sanitize_image(png, declared_mime_type="image/jpeg", spool_root=tmp_path)
    with pytest.raises(ImageSanitizationError) as truncated:
        sanitize_image(png[:-8], declared_mime_type="image/png", spool_root=tmp_path)
    assert truncated.value.code in {"image_decode_failed", "image_magic_mismatch"}

    first = Image.new("RGB", (64, 64), "red")
    second = Image.new("RGB", (64, 64), "blue")
    try:
        animated = BytesIO()
        first.save(animated, format="WEBP", save_all=True, append_images=[second], duration=10)
    finally:
        first.close()
        second.close()
    with pytest.raises(ImageSanitizationError, match="image_animated"):
        sanitize_image(animated.getvalue(), declared_mime_type="image/webp", spool_root=tmp_path)

    ihdr = struct.pack(">IIBBBBB", 9000, 64, 8, 2, 0, 0, 0)
    bomb = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr
    bomb += struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    compressed = zlib.compress(b"\x00")
    bomb += struct.pack(">I", len(compressed)) + b"IDAT" + compressed
    bomb += struct.pack(">I", zlib.crc32(b"IDAT" + compressed))
    bomb += b"\x00\x00\x00\x00IEND\xaeB`\x82"
    with pytest.raises(ImageSanitizationError, match="image_dimensions_exceeded"):
        sanitize_image(bomb, declared_mime_type="image/png", spool_root=tmp_path)


def test_sanitizer_enforces_byte_and_output_limits_and_is_repeatable(tmp_path) -> None:
    raw = _image_bytes("PNG")
    too_small_input = ImageSanitizerConfig(max_input_bytes=len(raw) - 1)
    with pytest.raises(ImageSanitizationError, match="image_too_large"):
        sanitize_image(
            raw,
            declared_mime_type="image/png",
            config=too_small_input,
            spool_root=tmp_path,
        )

    output_limited = ImageSanitizerConfig(max_output_bytes=100)
    with pytest.raises(ImageSanitizationError, match="sanitized_output_too_large"):
        sanitize_image(
            raw,
            declared_mime_type="image/png",
            config=output_limited,
            spool_root=tmp_path,
        )

    first = sanitize_image_stream(
        (raw[:17], raw[17:]), declared_mime_type="image/png", spool_root=tmp_path
    )
    second = sanitize_image(raw, declared_mime_type="image/png", spool_root=tmp_path)
    assert first.bytes_value == second.bytes_value
    assert first.sha256 == second.sha256


def test_sanitizer_only_exposes_allowlisted_error_codes(tmp_path) -> None:
    with pytest.raises(ImageSanitizationError) as error:
        sanitize_image(b"not an image", declared_mime_type="image/png", spool_root=tmp_path)
    assert error.value.code == "image_magic_mismatch"
    assert str(error.value) == error.value.code


@pytest.mark.asyncio
async def test_sanitizer_accepts_bounded_async_storage_stream(tmp_path) -> None:
    raw = _image_bytes("PNG")

    async def stream() -> AsyncIterator[bytes]:
        yield raw[:13]
        yield raw[13:]

    sanitized = await sanitize_async_image_stream(
        stream(), declared_mime_type="image/png", spool_root=tmp_path
    )
    assert sanitized.content_type == "image/jpeg"
