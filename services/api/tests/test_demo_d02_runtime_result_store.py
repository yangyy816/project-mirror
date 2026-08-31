from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest
from PIL import Image

from mirror_api.demo_d02_r2_runtime_forward import M4ExecutionOutput
from mirror_api.demo_d02_runtime_result_store import (
    D02RuntimeResultStore,
    D02RuntimeResultStoreError,
)
from mirror_api.demo_measurement_quality import mirror_demo_digest


def _output(marker: int) -> M4ExecutionOutput:
    image = Image.new("RGB", (96, 96), (marker, 80, 160))
    stream = io.BytesIO()
    image.save(stream, format="JPEG", quality=95, subsampling=0)
    content = stream.getvalue()
    payload = {
        "schema_version": "mirror.demo/D02R2M4ExecutionOutput/v1",
        "case_id": f"{marker:032x}",
        "replay_index": 1,
        "result_output_id": f"output-{marker:032x}",
        "result_sha256": hashlib.sha256(content).hexdigest(),
        "result_byte_size": len(content),
        "result_mime_type": "image/jpeg",
        "result_width": 96,
        "result_height": 96,
        "changed_pixel_count": 1,
        "execution_receipt_digest": hashlib.sha256(f"receipt-{marker}".encode()).hexdigest(),
        "execution_succeeded": True,
    }
    output_digest = mirror_demo_digest(payload["schema_version"], payload)
    return M4ExecutionOutput(content=content, output_digest=output_digest, **payload)


def _store(tmp_path: Path) -> D02RuntimeResultStore:
    (tmp_path / ".private-handoff").mkdir()
    return D02RuntimeResultStore(
        workspace_root=tmp_path,
        availability_binding_digest="a" * 64,
    )


def test_persist_load_and_finalize_48_first_replay_outputs(tmp_path: Path) -> None:
    store = _store(tmp_path)
    outputs = tuple(_output(ordinal) for ordinal in range(1, 49))
    for ordinal, output in enumerate(outputs, 1):
        assert store.persist(output, ordinal).output == output
    assert store.load(case_ordinal=1) == outputs[0]
    assert store.finalize() == outputs


def test_tampered_copy_is_rejected_without_locator_or_bytes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.persist(_output(1), 1)
    path = (
        tmp_path
        / ".private-handoff"
        / "d02-acquisition"
        / "objects"
        / "runtime-results"
        / "d02-runtime-result-o01-backup.jpg"
    )
    path.write_bytes(b"tampered")
    with pytest.raises(D02RuntimeResultStoreError) as raised:
        store.load(case_ordinal=1)
    assert raised.value.code == "RUNTIME_RESULT_FILE_TAMPERED"
    assert str(path) not in repr(raised.value)


def test_ordinal_collision_is_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.persist(_output(1), 1)
    with pytest.raises(D02RuntimeResultStoreError, match="RUNTIME_RESULT_ORDINAL_COLLISION"):
        store.persist(_output(2), 1)


def test_partial_primary_recovers_exactly_then_persists_index(tmp_path: Path) -> None:
    store = _store(tmp_path)
    output = _output(1)
    store._ensure_layout()
    store._materialize(1, "primary", output)
    assert store.persist(output, 1).output == output
    assert store.load(case_ordinal=1) == output


def test_index_duplicate_json_key_is_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store._ensure_layout()
    index = tmp_path / ".private-handoff" / "D02_RUNTIME_RESULT_INDEX.json"
    index.write_text('{"schema_version":"x","schema_version":"x"}', encoding="utf-8")
    with pytest.raises(D02RuntimeResultStoreError, match="RUNTIME_RESULT_INDEX_UNREADABLE"):
        store.verify(case_ordinal=1)


def test_availability_index_rejects_another_runtime_binding(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.persist(_output(1), 1)
    substituted = D02RuntimeResultStore(
        workspace_root=tmp_path,
        availability_binding_digest="b" * 64,
    )
    with pytest.raises(D02RuntimeResultStoreError, match="RUNTIME_RESULT_INDEX_SCHEMA_INVALID"):
        substituted.load(case_ordinal=1)
