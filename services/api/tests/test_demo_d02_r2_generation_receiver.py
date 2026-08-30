from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
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


def test_provider_result_file_handoff_is_consumed_before_publish(tmp_path: Path) -> None:
    image_url = _png_url()
    expected = base64.b64decode(image_url[len(receiver.DATA_URL_PREFIX) :])
    result_file = tmp_path / "provider-result.json"
    result_file.write_text(
        json.dumps({"image_url": image_url}, separators=(",", ":")),
        encoding="utf-8",
    )

    facts = receiver.receive_imagegen_result_file(
        result_file=result_file.resolve(),
        destination=_destination(tmp_path),
    )

    assert facts.sha256 == hashlib.sha256(expected).hexdigest()
    assert (tmp_path / "source.png").read_bytes() == expected
    assert not result_file.exists()
    assert not (tmp_path / ".source.png.incoming").exists()


def test_builtin_imagegen_png_file_handoff_uses_same_durable_writer(tmp_path: Path) -> None:
    image_url = _png_url(size=(96, 80))
    expected = base64.b64decode(image_url[len(receiver.DATA_URL_PREFIX) :])
    source_parent = tmp_path / "provider"
    destination_parent = tmp_path / "evidence"
    source_parent.mkdir()
    destination_parent.mkdir()
    source = source_parent / "generated.png"
    source.write_bytes(expected)

    facts = receiver.receive_imagegen_png_file(
        source_file=source.resolve(),
        destination=_destination(destination_parent),
    )

    assert facts.sha256 == hashlib.sha256(expected).hexdigest()
    assert (destination_parent / "source.png").read_bytes() == expected
    assert source.read_bytes() == expected
    assert not (destination_parent / ".source.png.incoming").exists()


def test_materializer_consumes_structured_extension_result_without_saved_path(
    tmp_path: Path,
) -> None:
    image_url = _png_url(size=(96, 80))
    expected = base64.b64decode(image_url[len(receiver.DATA_URL_PREFIX) :])
    private_prompt = "PRIVATE_PROMPT_MUST_NOT_BE_INTERPRETED_OR_LOGGED"
    result_metadata = {
        "type": "Extension",
        "kind": "image_gen.generation",
        "status": "completed",
        "failure": None,
        "result": image_url[len(receiver.DATA_URL_PREFIX) :],
        "savedPath": "",
        "revisedPrompt": private_prompt,
    }

    facts = receiver.ImageGenResultMaterializer().receive(
        result_metadata=result_metadata,
        destination=_destination(tmp_path),
    )

    assert facts.sha256 == hashlib.sha256(expected).hexdigest()
    assert (tmp_path / "source.png").read_bytes() == expected
    assert private_prompt not in repr(facts)


def test_materializer_uses_exact_saved_path_fallback(tmp_path: Path) -> None:
    image_url = _png_url(size=(80, 96))
    expected = base64.b64decode(image_url[len(receiver.DATA_URL_PREFIX) :])
    source_parent = tmp_path / "provider"
    destination_parent = tmp_path / "evidence"
    source_parent.mkdir()
    destination_parent.mkdir()
    source = source_parent / "generated.png"
    source.write_bytes(expected)

    facts = receiver.ImageGenResultMaterializer().receive(
        result_metadata={
            "type": "Extension",
            "kind": "image_gen.generation",
            "status": "completed",
            "failure": None,
            "result": None,
            "savedPath": str(source.resolve()),
            "revisedPrompt": "PRIVATE",
        },
        destination=_destination(destination_parent),
        allowed_saved_file=source.resolve(),
    )

    assert facts.sha256 == hashlib.sha256(expected).hexdigest()
    assert (destination_parent / "source.png").read_bytes() == expected
    assert source.read_bytes() == expected


def test_materializer_rejects_free_form_output_hint_without_parsing_paths(
    tmp_path: Path,
) -> None:
    output_hint = r"generated file C:\private\first.png and preview C:\private\second.png"

    assert (
        _error_code(
            receiver.ImageGenResultMaterializer().receive,
            result_metadata={"output_hint": output_hint},
            destination=_destination(tmp_path),
        )
        == "TOOL_RESULT_NOT_PROGRAMMATICALLY_MATERIALIZABLE"
    )
    assert not (tmp_path / "source.png").exists()


def test_materializer_reports_missing_saved_file_before_receiver(tmp_path: Path) -> None:
    missing = (tmp_path / "missing.png").resolve()
    assert (
        _error_code(
            receiver.ImageGenResultMaterializer().receive,
            result_metadata={
                "type": "Extension",
                "kind": "image_gen.generation",
                "status": "completed",
                "failure": None,
                "result": None,
                "savedPath": str(missing),
            },
            destination=_destination(tmp_path),
            allowed_saved_file=missing,
        )
        == "GENERATED_FILE_NOT_FOUND"
    )
    assert not (tmp_path / "source.png").exists()


def test_invalid_provider_result_is_consumed_with_zero_output(tmp_path: Path) -> None:
    result_file = tmp_path / "provider-result.json"
    result_file.write_text('{"image_url":42}', encoding="utf-8")

    assert (
        _error_code(
            receiver.receive_imagegen_result_file,
            result_file=result_file.resolve(),
            destination=_destination(tmp_path),
        )
        == "INVALID_PROVIDER_RESULT"
    )
    assert not result_file.exists()
    assert not (tmp_path / "source.png").exists()
    assert not (tmp_path / ".source.png.incoming").exists()


def test_cli_file_handoff_never_echoes_provider_payload(tmp_path: Path) -> None:
    image_url = _png_url()
    result_file = tmp_path / "provider-result.json"
    result_file.write_text(
        json.dumps({"image_url": image_url}, separators=(",", ":")),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    source_root = str(Path(receiver.__file__).resolve().parents[1])
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (source_root, environment.get("PYTHONPATH", "")) if value
    )

    completed = subprocess.run(  # noqa: S603 - fixed current interpreter and literal argv
        [
            sys.executable,
            "-m",
            "mirror_api.demo_d02_r2_generation_receiver",
            "--result-leaf",
            result_file.name,
            "--destination-leaf",
            "source.png",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert image_url not in completed.stdout
    assert image_url not in completed.stderr
    assert image_url[len(receiver.DATA_URL_PREFIX) :][:32] not in completed.stdout
    assert image_url[len(receiver.DATA_URL_PREFIX) :][:32] not in completed.stderr
    assert json.loads(completed.stdout)["status"] == "PERSISTED"
    assert completed.stderr == ""
    assert not result_file.exists()
    assert (tmp_path / "source.png").is_file()
    assert not (tmp_path / ".source.png.incoming").exists()


def test_cli_collision_consumes_payload_and_preserves_existing_output(tmp_path: Path) -> None:
    image_url = _png_url()
    result_file = tmp_path / "provider-result.json"
    result_file.write_text(
        json.dumps({"image_url": image_url}, separators=(",", ":")),
        encoding="utf-8",
    )
    target = tmp_path / "source.png"
    target.write_bytes(b"existing")
    environment = os.environ.copy()
    source_root = str(Path(receiver.__file__).resolve().parents[1])
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (source_root, environment.get("PYTHONPATH", "")) if value
    )

    completed = subprocess.run(  # noqa: S603 - fixed current interpreter and literal argv
        [
            sys.executable,
            "-m",
            "mirror_api.demo_d02_r2_generation_receiver",
            "--result-leaf",
            result_file.name,
            "--destination-leaf",
            target.name,
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert json.loads(completed.stderr)["code"] == "DESTINATION_COLLISION"
    assert image_url not in completed.stdout
    assert image_url not in completed.stderr
    assert not result_file.exists()
    assert target.read_bytes() == b"existing"
    assert not (tmp_path / ".source.png.incoming").exists()


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


@pytest.mark.parametrize("failure", ["short_write", "fsync", "parent_sync", "publish", "replay"])
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
    elif failure == "publish":
        monkeypatch.setattr(
            "mirror_api.demo_d02_r2_generation_receiver.os.link",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("no")),
        )
        expected = "DESTINATION_PUBLISH_FAILED"
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
    assert not target.exists()
    assert not (tmp_path / ".source.png.incoming").exists()


def test_windows_parent_sync_branch_uses_platform_primitive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    called: list[Path] = []
    monkeypatch.setattr("mirror_api.demo_d02_r2_generation_receiver.os.name", "nt")
    monkeypatch.setattr(receiver, "_sync_directory_windows", lambda path: called.append(path))
    receiver._sync_directory(tmp_path)
    assert called == [tmp_path]
