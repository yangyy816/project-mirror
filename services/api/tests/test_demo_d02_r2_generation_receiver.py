from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
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


def _cli_environment() -> dict[str, str]:
    environment = os.environ.copy()
    source_root = str(Path(receiver.__file__).resolve().parents[1])
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (source_root, environment.get("PYTHONPATH", "")) if value
    )
    return environment


class _FakeStdin:
    def __init__(self, payload: bytes, *, tty: bool = False) -> None:
        self.buffer = BytesIO(payload)
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


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


def test_builtin_imagegen_png_file_rejects_symlink_without_deleting_source(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.png"
    target.write_bytes(base64.b64decode(_png_url()[len(receiver.DATA_URL_PREFIX) :]))
    linked = tmp_path / "linked.png"
    try:
        linked.symlink_to(target)
    except OSError:
        pytest.skip("file symlinks are unavailable on this host")
    destination_parent = tmp_path / "evidence"
    destination_parent.mkdir()

    assert (
        _error_code(
            receiver.receive_imagegen_png_file,
            source_file=linked,
            destination=_destination(destination_parent),
        )
        == "INVALID_PROVIDER_FILE"
    )
    assert target.is_file()
    assert linked.is_symlink()
    assert not (destination_parent / "source.png").exists()
    assert not (destination_parent / ".source.png.incoming").exists()


def test_builtin_imagegen_png_file_rejects_nonregular_source(tmp_path: Path) -> None:
    source_directory = tmp_path / "provider-directory"
    source_directory.mkdir()
    destination_parent = tmp_path / "evidence"
    destination_parent.mkdir()

    assert (
        _error_code(
            receiver.receive_imagegen_png_file,
            source_file=source_directory,
            destination=_destination(destination_parent),
        )
        == "INVALID_PROVIDER_FILE"
    )
    assert source_directory.is_dir()
    assert not (destination_parent / "source.png").exists()


def test_builtin_imagegen_png_file_rejects_junction_reparse_attribute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "generated.png"
    source.write_bytes(base64.b64decode(_png_url()[len(receiver.DATA_URL_PREFIX) :]))
    destination_parent = tmp_path / "evidence"
    destination_parent.mkdir()
    destination = _destination(destination_parent)

    class ReparseInfo:
        st_mode = stat.S_IFREG
        st_file_attributes = 1

    with monkeypatch.context() as scoped:
        scoped.setattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1, raising=False)
        scoped.setattr(os, "lstat", lambda _path: ReparseInfo())
        code = _error_code(
            receiver.receive_imagegen_png_file,
            source_file=source,
            destination=destination,
        )

    assert code == "INVALID_PROVIDER_FILE"
    assert source.is_file()
    assert not (destination_parent / "source.png").exists()


def test_builtin_imagegen_png_file_rejects_preopen_identity_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_bytes = base64.b64decode(_png_url()[len(receiver.DATA_URL_PREFIX) :])
    replacement_bytes = base64.b64decode(_png_url(size=(80, 80))[len(receiver.DATA_URL_PREFIX) :])
    source = tmp_path / "generated.png"
    replacement = tmp_path / "replacement.png"
    preserved_original = tmp_path / "preserved-original.png"
    source.write_bytes(original_bytes)
    replacement.write_bytes(replacement_bytes)
    destination_parent = tmp_path / "evidence"
    destination_parent.mkdir()
    original_reader = receiver._read_file_bytes_no_follow

    def replace_before_open(
        path: Path,
        *,
        maximum_bytes: int,
        code: str = "DESTINATION_REPLAY_FAILED",
        expected_identity: tuple[int, int] | None = None,
    ) -> bytes:
        source.replace(preserved_original)
        replacement.replace(source)
        return original_reader(
            path,
            maximum_bytes=maximum_bytes,
            code=code,
            expected_identity=expected_identity,
        )

    monkeypatch.setattr(receiver, "_read_file_bytes_no_follow", replace_before_open)

    assert (
        _error_code(
            receiver.receive_imagegen_png_file,
            source_file=source.resolve(),
            destination=_destination(destination_parent),
        )
        == "INVALID_PROVIDER_FILE"
    )
    assert preserved_original.read_bytes() == original_bytes
    assert source.read_bytes() == replacement_bytes
    assert not (destination_parent / "source.png").exists()


def test_no_follow_reader_maps_close_failure_to_callers_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "generated.png"
    source.write_bytes(base64.b64decode(_png_url()[len(receiver.DATA_URL_PREFIX) :]))
    original_close = os.close

    def close_then_fail(descriptor: int) -> None:
        original_close(descriptor)
        raise OSError("PRIVATE_CLOSE_FAILURE_MUST_NOT_ESCAPE")

    with monkeypatch.context() as scoped:
        scoped.setattr(os, "close", close_then_fail)
        code = _error_code(
            receiver._read_file_bytes_no_follow,
            source,
            maximum_bytes=receiver.MAXIMUM_BYTES,
            code="INVALID_PROVIDER_FILE",
        )

    assert code == "INVALID_PROVIDER_FILE"
    assert source.is_file()


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


def test_materializer_accepts_one_structured_or_content_png_reference(tmp_path: Path) -> None:
    image_url = _png_url(size=(80, 96))
    expected = base64.b64decode(image_url[len(receiver.DATA_URL_PREFIX) :])
    cases = [
        {"structuredContent": {"image_url": image_url}},
        {
            "content": [
                {
                    "type": "image",
                    "mimeType": "image/png",
                    "data": image_url[len(receiver.DATA_URL_PREFIX) :],
                }
            ]
        },
    ]

    for index, result_metadata in enumerate(cases):
        leaf_name = f"source-{index}.png"
        facts = receiver.ImageGenResultMaterializer().receive(
            result_metadata=result_metadata,
            destination=_destination(tmp_path, leaf_name),
        )
        assert facts.sha256 == hashlib.sha256(expected).hexdigest()
        assert (tmp_path / leaf_name).read_bytes() == expected


def test_materializer_rejects_missing_reference(tmp_path: Path) -> None:
    assert (
        _error_code(
            receiver.ImageGenResultMaterializer().receive,
            result_metadata={},
            destination=_destination(tmp_path),
        )
        == "RESULT_REFERENCE_NOT_RETURNED"
    )
    assert not (tmp_path / "source.png").exists()


@pytest.mark.parametrize(
    "result_metadata",
    [
        {
            "image_url": "data:image/png;base64,AAAA",
            "structuredContent": {"image_url": "data:image/png;base64,BBBB"},
        },
        {
            "content": [
                {"type": "image", "mimeType": "image/png", "data": "AAAA"},
                {"type": "image", "mimeType": "image/jpeg", "data": "BBBB"},
            ]
        },
        {
            "type": "Extension",
            "kind": "image_gen.generation",
            "status": "completed",
            "failure": None,
            "result": "AAAA",
            "savedPath": "C:\\private\\generated.png",
        },
        {
            "image_url": "data:image/png;base64,AAAA",
            "payload": {
                "item": {
                    "type": "Extension",
                    "kind": "image_gen.generation",
                    "status": "completed",
                    "failure": None,
                    "result": "BBBB",
                    "savedPath": "",
                }
            },
        },
        {"image_url": 42},
    ],
)
def test_materializer_rejects_conflicting_or_unsupported_typed_references(
    result_metadata: object,
    tmp_path: Path,
) -> None:
    assert (
        _error_code(
            receiver.ImageGenResultMaterializer().receive,
            result_metadata=result_metadata,
            destination=_destination(tmp_path),
        )
        == "TOOL_RESULT_NOT_PROGRAMMATICALLY_MATERIALIZABLE"
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


def test_cli_stdin_handoff_never_echoes_provider_payload(tmp_path: Path) -> None:
    image_url = _png_url()
    expected = base64.b64decode(image_url[len(receiver.DATA_URL_PREFIX) :])

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "mirror_api.demo_d02_r2_generation_receiver",
            "--tool-result-stdin",
            "--destination-leaf",
            "source.png",
        ],
        cwd=tmp_path,
        env=_cli_environment(),
        input=json.dumps({"image_url": image_url}, separators=(",", ":")),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert image_url not in completed.stdout
    assert image_url not in completed.stderr
    assert image_url[len(receiver.DATA_URL_PREFIX) :][:32] not in completed.stdout
    assert image_url[len(receiver.DATA_URL_PREFIX) :][:32] not in completed.stderr
    assert (
        completed.stdout
        == json.dumps(
            {
                "status": "PERSISTED",
                "media_type": "image/png",
                "byte_size": len(expected),
                "sha256": hashlib.sha256(expected).hexdigest(),
                "width": 64,
                "height": 64,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    assert completed.stderr == ""
    assert (tmp_path / "source.png").read_bytes() == expected
    assert not (tmp_path / ".source.png.incoming").exists()


def test_cli_stdin_collision_preserves_existing_output(tmp_path: Path) -> None:
    image_url = _png_url()
    target = tmp_path / "source.png"
    target.write_bytes(b"existing")

    completed = subprocess.run(  # noqa: S603 - fixed current interpreter and literal argv
        [
            sys.executable,
            "-m",
            "mirror_api.demo_d02_r2_generation_receiver",
            "--tool-result-stdin",
            "--destination-leaf",
            target.name,
        ],
        cwd=tmp_path,
        env=_cli_environment(),
        input=json.dumps({"image_url": image_url}, separators=(",", ":")),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == '{"code":"DESTINATION_COLLISION","status":"FAILED"}\n'
    assert image_url not in completed.stdout
    assert image_url not in completed.stderr
    assert target.read_bytes() == b"existing"
    assert not (tmp_path / ".source.png.incoming").exists()


def test_cli_rejects_legacy_or_path_arguments_without_echo_or_file_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("unchanged", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    forbidden_arguments = [
        str(outside.resolve()),
        r"C:\private\generated.png",
        "nested/generated.png",
        "../generated.png",
    ]

    for forbidden in forbidden_arguments:
        assert (
            receiver._run_cli(
                [
                    "--result-leaf",
                    forbidden,
                    "--destination-leaf",
                    "source.png",
                ]
            )
            == 2
        )
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == '{"code":"INVALID_PROVIDER_RESULT","status":"FAILED"}\n'
        assert forbidden not in captured.err
        assert outside.read_text(encoding="utf-8") == "unchanged"
        assert not (tmp_path / "source.png").exists()


def test_cli_rejects_tty_before_reading_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", _FakeStdin(b"PRIVATE_PAYLOAD", tty=True))

    assert receiver._run_cli(["--tool-result-stdin", "--destination-leaf", "source.png"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == '{"code":"INVALID_PROVIDER_RESULT","status":"FAILED"}\n'
    assert "PRIVATE_PAYLOAD" not in captured.err
    assert not (tmp_path / "source.png").exists()


def test_cli_unknown_exception_is_fixed_and_never_leaks_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    private_sentinel = "PRIVATE_LOCATOR_AND_PAYLOAD_MUST_NOT_LEAK"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "stdin",
        _FakeStdin(json.dumps({"image_url": _png_url()}).encode("utf-8")),
    )
    monkeypatch.setattr(
        receiver.ImageGenResultMaterializer,
        "receive",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError(private_sentinel)),
    )

    assert receiver._run_cli(["--tool-result-stdin", "--destination-leaf", "source.png"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == '{"code":"INTERNAL_RECEIVER_FAILURE","status":"FAILED"}\n'
    assert private_sentinel not in captured.err
    assert "Traceback" not in captured.err
    assert not (tmp_path / "source.png").exists()


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
