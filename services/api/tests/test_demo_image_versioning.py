from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from mirror_api.demo_image_versioning import (
    IMPLEMENTATION_STATUS,
    REAL_ASSET_INTEGRATION_STATUS,
    DemoImageVersion,
    DemoImageVersionError,
    ImageVersionKind,
    InMemoryImageVersionAuthority,
    PublishEditRequest,
    PublishTransitionRequest,
)
from mirror_api.demo_operation_graph import build_operation_graph, parse_operation_spec


def _original() -> DemoImageVersion:
    return DemoImageVersion(
        image_version_id="a" * 32,
        image_version_digest="a" * 64,
        actor_id="b" * 32,
        demo_session_id="c" * 32,
        editing_session_id="d" * 32,
        sequence=0,
        parent_image_version_id=None,
        source_image_version_id=None,
        source_image_version_digest=None,
        target_image_version_id=None,
        target_image_version_digest=None,
        result_asset_id="e" * 32,
        result_asset_sha256="e" * 64,
        operation_graph_digest=None,
        kind=ImageVersionKind.ORIGINAL,
    )


def _spec(operation_type: str, parameters: dict[str, str | int] | None = None) -> dict[str, object]:
    if operation_type == "EXPOSURE":
        params: dict[str, str | int] = {"exposure_ev_milli": 1}
        preserve = ["IDENTITY_REFERENCE_FRAME"]
        effect: dict[str, str | int] = {
            "effect_type": "EXPOSURE",
            "exposure_ev_milli": 1,
            "target_region": "FULL_IMAGE",
        }
    else:
        assert parameters is not None
        params = parameters
        preserve = ["TARGET_VERSION_BYTES"]
        effect = {
            "effect_type": operation_type,
            "target_image_version_digest": parameters["target_image_version_digest"],
            "target_region": "VERSION_CONTENT",
        }
    return {
        "engine": "RASTER",
        "operation_type": operation_type,
        "parameters": params,
        "preserve": preserve,
        "expected_effect": effect,
    }


def _edit_request(source: DemoImageVersion, key: str = "edit-1") -> PublishEditRequest:
    return PublishEditRequest(
        idempotency_key=key,
        source_image_version_id=source.image_version_id,
        source_image_version_digest=source.image_version_digest,
        operation_graph=build_operation_graph(
            source.image_version_id,
            source.image_version_digest,
            [parse_operation_spec(_spec("EXPOSURE"))],
        ),
        result_asset_id="f" * 32,
        result_asset_sha256="f" * 64,
    )


def _transition_request(
    source: DemoImageVersion, target: DemoImageVersion, operation: str, key: str
) -> PublishTransitionRequest:
    return PublishTransitionRequest(
        idempotency_key=key,
        source_image_version_id=source.image_version_id,
        source_image_version_digest=source.image_version_digest,
        target_image_version_id=target.image_version_id,
        target_image_version_digest=target.image_version_digest,
        operation_graph=build_operation_graph(
            source.image_version_id,
            source.image_version_digest,
            [
                parse_operation_spec(
                    _spec(
                        operation,
                        {
                            "target_image_version_id": target.image_version_id,
                            "target_image_version_digest": target.image_version_digest,
                        },
                    )
                )
            ],
        ),
        result_asset_id="1" * 32 if operation == "RESTORE" else "2" * 32,
        result_asset_sha256=target.result_asset_sha256,
    )


def _error(code: str, callable_object: object) -> None:
    with pytest.raises(DemoImageVersionError) as error:
        assert callable(callable_object)
        callable_object()
    assert error.value.code == code


def test_edit_is_append_only_and_replay_is_canonical() -> None:
    authority = InMemoryImageVersionAuthority(_original())
    original = authority.history()[0]
    first = authority.publish_edit(_edit_request(original))
    replay = authority.publish_edit(_edit_request(original))
    assert first is replay
    assert first.kind is ImageVersionKind.EDIT
    assert first.parent_image_version_id == original.image_version_id
    assert first.source_image_version_digest == original.image_version_digest
    assert first.operation_graph_digest is not None
    assert len(authority.history()) == 2
    assert IMPLEMENTATION_STATUS == "IMPLEMENTATION_READY"
    assert authority.integration_status == REAL_ASSET_INTEGRATION_STATUS


def test_same_key_with_different_semantics_conflicts_without_partial_publication() -> None:
    authority = InMemoryImageVersionAuthority(_original())
    source = authority.history()[0]
    authority.publish_edit(_edit_request(source, "same"))
    changed = _edit_request(source, "same")
    changed = PublishEditRequest(
        **{**changed.__dict__, "result_asset_id": "9" * 32, "result_asset_sha256": "9" * 64}
    )
    _error("IDEMPOTENCY_CONFLICT", lambda: authority.publish_edit(changed))
    assert len(authority.history()) == 2


def test_concurrent_same_request_has_one_canonical_winner() -> None:
    authority = InMemoryImageVersionAuthority(_original())
    request = _edit_request(authority.history()[0], "parallel")
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _index: authority.publish_edit(request), range(32)))
    assert len({item.image_version_id for item in results}) == 1
    assert len(authority.history()) == 2


def test_restore_and_rollback_each_publish_new_bound_versions() -> None:
    authority = InMemoryImageVersionAuthority(_original())
    original = authority.history()[0]
    edited = authority.publish_edit(_edit_request(original))
    restored = authority.restore(_transition_request(edited, original, "RESTORE", "restore"))
    rolled_back = authority.rollback(_transition_request(restored, edited, "ROLLBACK", "rollback"))
    assert restored.kind is ImageVersionKind.RESTORED
    assert restored.target_image_version_id == original.image_version_id
    assert restored.result_asset_sha256 == original.result_asset_sha256
    assert rolled_back.kind is ImageVersionKind.ROLLED_BACK
    assert rolled_back.target_image_version_id == edited.image_version_id
    assert len(authority.history()) == 4


def test_branch_publications_keep_session_sequence_strictly_monotonic() -> None:
    authority = InMemoryImageVersionAuthority(_original())
    original = authority.history()[0]
    first = authority.publish_edit(_edit_request(original, "first"))
    second_request = _edit_request(original, "second")
    second_request = PublishEditRequest(
        **{
            **second_request.__dict__,
            "result_asset_id": "8" * 32,
            "result_asset_sha256": "8" * 64,
        }
    )
    second = authority.publish_edit(second_request)
    assert (first.sequence, second.sequence) == (1, 2)
    assert [item.sequence for item in authority.history()] == [0, 1, 2]


def test_fail_closed_graph_lineage_and_result_mismatches_leave_no_partial_version() -> None:
    authority = InMemoryImageVersionAuthority(_original())
    original = authority.history()[0]
    bad_graph = build_operation_graph("f" * 32, "f" * 64, [parse_operation_spec(_spec("EXPOSURE"))])
    bad_edit = PublishEditRequest(
        "bad-graph",
        original.image_version_id,
        original.image_version_digest,
        bad_graph,
        "f" * 32,
        "f" * 64,
    )
    _error("OPERATION_GRAPH_SOURCE_MISMATCH", lambda: authority.publish_edit(bad_edit))
    edited = authority.publish_edit(_edit_request(original))
    transition = _transition_request(edited, original, "RESTORE", "restore-bad")
    wrong_digest = PublishTransitionRequest(
        **{**transition.__dict__, "result_asset_sha256": "0" * 64}
    )
    _error("RESULT_DIGEST_MISMATCH", lambda: authority.restore(wrong_digest))
    assert len(authority.history()) == 2
    restored = authority.restore(_transition_request(edited, original, "RESTORE", "restore-ok"))
    illegal_rollback = _transition_request(restored, original, "ROLLBACK", "rollback-illegal")
    _error("ROLLBACK_NOT_IMMEDIATE_PARENT", lambda: authority.rollback(illegal_rollback))
    assert len(authority.history()) == 3
