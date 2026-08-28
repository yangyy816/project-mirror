from __future__ import annotations

import base64
import zlib
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from mirror_api import demo_d02_r2_generation_receiver as receiver


def _png_url(*, size: tuple[int, int] = (64, 64)) -> str:
    image = Image.new("RGB", size, "purple")
    stream = BytesIO()
    image.save(stream, format="PNG")
    return receiver.DATA_URL_PREFIX + base64.b64encode(stream.getvalue()).decode("ascii")


def _destination(parent: Path, leaf_name: str = "source.png") -> receiver.PreallocatedDestination:
    return receiver.bind_principal_preallocated_destination(
        parent=parent,
        leaf_name=leaf_name,
    )


def _png_chunk(chunk_type: bytes, payload: bytes = b"") -> bytes:
    crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
    return len(payload).to_bytes(4, "big") + chunk_type + payload + crc.to_bytes(4, "big")


def _error_code(callable_object: Callable[..., object], *args: object, **kwargs: object) -> str:
    with pytest.raises(receiver.D02R2PngReceiverError) as raised:
        callable_object(*args, **kwargs)
    return raised.value.code


def test_receives_valid_png_before_and_after_durable_replay(tmp_path: Path) -> None:
    result = receiver.receive_imagegen_png(image_url=_png_url(), destination=_destination(tmp_path))
    assert result.width == 64
    assert result.height == 64
    assert result.byte_size > 0
    assert len(result.sha256) == 64


@pytest.mark.parametrize(
    ("image_url", "expected"),
    [
        ("https://example.invalid/a.png", "INVALID_DATA_URL"),
        ("file:///tmp/a.png", "INVALID_DATA_URL"),
        ("data:image/jpeg;base64,AAAA", "INVALID_DATA_URL"),
        ("data:image/png;base64;foo,AAAA", "INVALID_DATA_URL"),
        (receiver.DATA_URL_PREFIX, "INVALID_BASE64"),
        (receiver.DATA_URL_PREFIX + "YWJj\n", "INVALID_BASE64"),
        (receiver.DATA_URL_PREFIX + "YWJj=", "INVALID_BASE64"),
    ],
)
def test_rejects_noncanonical_envelopes(image_url: str, expected: str, tmp_path: Path) -> None:
    assert (
        _error_code(
            receiver.receive_imagegen_png,
            image_url=image_url,
            destination=_destination(tmp_path, "no-write.png"),
        )
        == expected
    )
    assert not (tmp_path / "no-write.png").exists()


def test_rejects_non_string_and_oversize_before_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = _destination(tmp_path, "no-write.png")
    assert (
        _error_code(receiver.receive_imagegen_png, image_url=object(), destination=destination)
        == "INVALID_IMAGE_URL_TYPE"
    )
    monkeypatch.setattr(
        receiver, "MAXIMUM_COMPLETE_DATA_URL_ASCII_BYTES", len(receiver.DATA_URL_PREFIX)
    )
    assert (
        _error_code(receiver.receive_imagegen_png, image_url=_png_url(), destination=destination)
        == "DATA_URL_TOO_LARGE"
    )
    assert not (tmp_path / "no-write.png").exists()


@pytest.mark.parametrize("mutation", ["magic", "chunk", "crc", "ihdr", "iend", "trailing"])
def test_rejects_invalid_png_containers_before_write(mutation: str, tmp_path: Path) -> None:
    raw = base64.b64decode(_png_url()[len(receiver.DATA_URL_PREFIX) :])
    if mutation == "magic":
        raw = b"not-a-png" + raw[9:]
    elif mutation == "chunk":
        raw = raw[:8] + (len(raw) + 1).to_bytes(4, "big") + raw[12:]
    elif mutation == "crc":
        raw = raw[:-1] + bytes([raw[-1] ^ 1])
    elif mutation == "ihdr":
        raw = raw[:12] + b"IDAT" + raw[16:]
    elif mutation == "iend":
        raw = raw[:-12]
    else:
        raw += b"x"
    url = receiver.DATA_URL_PREFIX + base64.b64encode(raw).decode("ascii")
    target = tmp_path / "no-write.png"
    assert _error_code(
        receiver.receive_imagegen_png,
        image_url=url,
        destination=_destination(tmp_path, target.name),
    ) in {"INVALID_PNG_SIGNATURE", "INVALID_PNG_CONTAINER"}
    assert not target.exists()


@pytest.mark.parametrize("mutation", ["duplicate_ihdr", "unknown_critical", "split_idat"])
def test_rejects_critical_png_chunk_order_drift_before_write(
    mutation: str,
    tmp_path: Path,
) -> None:
    raw = base64.b64decode(_png_url()[len(receiver.DATA_URL_PREFIX) :])
    first_chunk_end = 8 + 12 + 13
    if mutation == "duplicate_ihdr":
        raw = raw[:first_chunk_end] + raw[8:first_chunk_end] + raw[first_chunk_end:]
    elif mutation == "unknown_critical":
        raw = raw[:first_chunk_end] + _png_chunk(b"ABCD") + raw[first_chunk_end:]
    else:
        raw = (
            raw[:first_chunk_end]
            + _png_chunk(b"IDAT")
            + _png_chunk(b"tEXt", b"k\x00v")
            + raw[first_chunk_end:]
        )
    target = tmp_path / "no-write.png"
    assert (
        _error_code(
            receiver.receive_imagegen_png,
            image_url=receiver.DATA_URL_PREFIX + base64.b64encode(raw).decode("ascii"),
            destination=_destination(tmp_path, target.name),
        )
        == "INVALID_PNG_CONTAINER"
    )
    assert not target.exists()


@pytest.mark.parametrize("size", [(63, 64), (8193, 64)])
def test_rejects_dimension_limits_before_write(size: tuple[int, int], tmp_path: Path) -> None:
    target = tmp_path / "no-write.png"
    assert (
        _error_code(
            receiver.receive_imagegen_png,
            image_url=_png_url(size=size),
            destination=_destination(tmp_path, target.name),
        )
        == "PNG_DIMENSIONS_INVALID"
    )
    assert not target.exists()


def test_rejects_pixel_limit_before_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image_url = _png_url()
    load_calls = 0
    original_load = Image.Image.load

    def tracked_load(image: Image.Image, *args: object, **kwargs: object) -> object:
        nonlocal load_calls
        load_calls += 1
        return original_load(image, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "load", tracked_load)
    monkeypatch.setattr(receiver, "MAXIMUM_PIXEL_COUNT", 1)
    target = tmp_path / "no-write.png"
    assert (
        _error_code(
            receiver.receive_imagegen_png,
            image_url=image_url,
            destination=_destination(tmp_path, target.name),
        )
        == "PNG_DIMENSIONS_INVALID"
    )
    assert load_calls == 0
    assert not target.exists()


def test_rejects_apng_before_write(tmp_path: Path) -> None:
    first = Image.new("RGB", (64, 64), "purple")
    second = Image.new("RGB", (64, 64), "orange")
    stream = BytesIO()
    first.save(stream, format="PNG", save_all=True, append_images=[second], duration=20)
    target = tmp_path / "no-write.png"
    assert (
        _error_code(
            receiver.receive_imagegen_png,
            image_url=receiver.DATA_URL_PREFIX
            + base64.b64encode(stream.getvalue()).decode("ascii"),
            destination=_destination(tmp_path, target.name),
        )
        == "PNG_ANIMATION_FORBIDDEN"
    )
    assert not target.exists()


def test_collision_is_fail_closed(tmp_path: Path) -> None:
    target = tmp_path / "source.png"
    target.write_bytes(b"unchanged")
    assert (
        _error_code(
            receiver.receive_imagegen_png,
            image_url=_png_url(),
            destination=_destination(tmp_path, target.name),
        )
        == "DESTINATION_COLLISION"
    )
    assert target.read_bytes() == b"unchanged"


def test_destination_capability_rejects_direct_construction_and_unsafe_names(
    tmp_path: Path,
) -> None:
    with pytest.raises(receiver.D02R2PngReceiverError, match="binding factory"):
        receiver.PreallocatedDestination(
            path=tmp_path / "forged.png",
            ancestor_identities=(),
            _factory_token=object(),
        )
    for leaf_name in ("../escape.png", "nested/escape.png", "..", ""):
        with pytest.raises(receiver.D02R2PngReceiverError) as raised:
            receiver.bind_principal_preallocated_destination(
                parent=tmp_path,
                leaf_name=leaf_name,
            )
        assert raised.value.code == "DESTINATION_CAPABILITY_INVALID"
    with pytest.raises(receiver.D02R2PngReceiverError) as raised:
        receiver.bind_principal_preallocated_destination(
            parent=Path("relative"),
            leaf_name="source.png",
        )
    assert raised.value.code == "DESTINATION_CAPABILITY_INVALID"


def test_destination_capability_rejects_symlinked_parent(tmp_path: Path) -> None:
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked"
    try:
        linked_parent.symlink_to(real_parent, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable on this host")

    with pytest.raises(receiver.D02R2PngReceiverError) as raised:
        receiver.bind_principal_preallocated_destination(
            parent=linked_parent,
            leaf_name="source.png",
        )
    assert raised.value.code == "DESTINATION_CAPABILITY_INVALID"


@pytest.mark.parametrize("failure", ["short_write", "fsync", "parent_sync", "replay"])
def test_destination_failures_are_fail_closed(
    failure: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "source.png"
    if failure == "short_write":
        monkeypatch.setattr(
            "mirror_api.demo_d02_r2_generation_receiver.os.write",
            lambda _fd, _data: 0,
        )
        expected = "DESTINATION_WRITE_FAILED"
    elif failure == "fsync":
        monkeypatch.setattr(
            "mirror_api.demo_d02_r2_generation_receiver.os.fsync",
            lambda _fd: (_ for _ in ()).throw(OSError("no")),
        )
        expected = "DESTINATION_DURABILITY_FAILED"
    elif failure == "parent_sync":
        monkeypatch.setattr(
            receiver, "_sync_directory", lambda _path: (_ for _ in ()).throw(OSError("no"))
        )
        expected = "DESTINATION_DURABILITY_FAILED"
    else:
        monkeypatch.setattr(
            receiver,
            "_read_file_bytes_no_follow",
            lambda _path, *, maximum_bytes: b"wrong",
        )
        expected = "DESTINATION_REPLAY_FAILED"
    assert (
        _error_code(
            receiver.receive_imagegen_png,
            image_url=_png_url(),
            destination=_destination(tmp_path, target.name),
        )
        == expected
    )


def test_windows_parent_sync_branch_uses_platform_primitive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    called: list[Path] = []
    monkeypatch.setattr("mirror_api.demo_d02_r2_generation_receiver.os.name", "nt")
    monkeypatch.setattr(receiver, "_sync_directory_windows", lambda path: called.append(path))
    receiver._sync_directory(tmp_path)
    assert called == [tmp_path]
