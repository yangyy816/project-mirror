from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from mirror_api.demo_operation_graph import (
    GRAPH_ALGORITHM_VERSION,
    GRAPH_SCHEMA_VERSION,
    CapabilityState,
    DemoOperationGraphError,
    ImageVersionReference,
    OperationExecutionUnavailable,
    OperationLineageError,
    OperationSpec,
    OperationType,
    PreserveKey,
    build_operation_graph,
    canonical_json_bytes,
    capability_state,
    graph_canonical_json,
    graph_content_digest,
    hydrate_operation_graph,
    parse_operation_spec,
    plan_restore_transition,
    plan_rollback_transition,
    validate_for_execution,
    validate_result_asset_id,
)

INPUT_ID = "a" * 32
INPUT_DIGEST = "b" * 64
TARGET_ID = "c" * 32
TARGET_DIGEST = "d" * 64


def _effect(operation_type: str, parameters: dict[str, object]) -> dict[str, object]:
    target = {
        "CROP": "CANVAS",
        "ROTATE": "CANVAS",
        "EXPOSURE": "FULL_IMAGE",
        "CONTRAST": "FULL_IMAGE",
        "SATURATION": "FULL_IMAGE",
        "TEMPERATURE": "FULL_IMAGE",
        "GEOMETRY": "FACE_REGION",
        "RESTORE": "VERSION_CONTENT",
        "ROLLBACK": "VERSION_CONTENT",
    }
    if operation_type == "MAKEUP":
        return {
            "capability_state": "DEFERRED_WITH_EXPLICIT_REASON",
            "effect_type": "UNAVAILABLE",
            "reason_code": "MAKEUP_DEFERRED_NO_APPROVED_ENGINE",
            "target_region": "NONE",
        }
    if operation_type == "GENERATIVE":
        return {
            "capability_state": "CAPABILITY_UNAVAILABLE",
            "effect_type": "UNAVAILABLE",
            "reason_code": "GENERATIVE_PROVIDER_UNAVAILABLE",
            "target_region": "NONE",
        }
    result: dict[str, object] = {
        "effect_type": operation_type,
        "target_region": target[operation_type],
    }
    for key in (
        "bottom_inset_ppm",
        "left_inset_ppm",
        "right_inset_ppm",
        "top_inset_ppm",
        "angle_mdeg",
        "expand_canvas",
        "delta_ppm",
        "dimension_key",
    ):
        if key in parameters:
            result[key] = parameters[key]
    for key in (
        "exposure_ev_milli",
        "contrast_delta_ppm",
        "saturation_delta_ppm",
        "temperature_delta_mired",
    ):
        if key in parameters:
            result[key] = parameters[key]
    if operation_type in {"RESTORE", "ROLLBACK"}:
        result["target_image_version_digest"] = parameters["target_image_version_digest"]
    return result


def _spec(
    operation_type: str = "EXPOSURE",
    parameters: dict[str, object] | None = None,
    preserve: list[str] | None = None,
    engine: str | None = None,
    expected_effect: dict[str, object] | None = None,
) -> dict[str, object]:
    defaults: dict[str, tuple[str, dict[str, object], list[str]]] = {
        "CROP": (
            "RASTER",
            {"left_inset_ppm": 1, "right_inset_ppm": 0, "top_inset_ppm": 0, "bottom_inset_ppm": 0},
            ["IDENTITY_REFERENCE_FRAME"],
        ),
        "ROTATE": (
            "RASTER",
            {"angle_mdeg": 1, "expand_canvas": False},
            ["IDENTITY_REFERENCE_FRAME"],
        ),
        "EXPOSURE": ("RASTER", {"exposure_ev_milli": 1}, ["IDENTITY_REFERENCE_FRAME"]),
        "CONTRAST": ("RASTER", {"contrast_delta_ppm": 1}, ["IDENTITY_REFERENCE_FRAME"]),
        "SATURATION": ("RASTER", {"saturation_delta_ppm": 1}, ["IDENTITY_REFERENCE_FRAME"]),
        "TEMPERATURE": ("RASTER", {"temperature_delta_mired": 1}, ["IDENTITY_REFERENCE_FRAME"]),
        "GEOMETRY": (
            "GEOMETRY",
            {"dimension_key": "jaw_width", "delta_ppm": 1},
            ["IDENTITY_REFERENCE_FRAME", "NON_TARGET_GEOMETRY"],
        ),
        "RESTORE": (
            "RASTER",
            {"target_image_version_id": TARGET_ID, "target_image_version_digest": TARGET_DIGEST},
            ["TARGET_VERSION_BYTES"],
        ),
        "ROLLBACK": (
            "RASTER",
            {"target_image_version_id": TARGET_ID, "target_image_version_digest": TARGET_DIGEST},
            ["TARGET_VERSION_BYTES"],
        ),
        "MAKEUP": ("MAKEUP", {"reason_code": "MAKEUP_DEFERRED_NO_APPROVED_ENGINE"}, []),
        "GENERATIVE": ("GENERATIVE", {"reason_code": "GENERATIVE_PROVIDER_UNAVAILABLE"}, []),
    }
    default_engine, default_parameters, default_preserve = defaults[operation_type]
    actual_parameters = deepcopy(default_parameters) if parameters is None else parameters
    return {
        "engine": default_engine if engine is None else engine,
        "operation_type": operation_type,
        "parameters": actual_parameters,
        "preserve": default_preserve if preserve is None else preserve,
        "expected_effect": _effect(operation_type, actual_parameters)
        if expected_effect is None
        else expected_effect,
    }


def _assert_code(code: str, action: object) -> None:
    with pytest.raises(DemoOperationGraphError) as error:
        assert callable(action)
        action()
    assert error.value.code == code


def test_frozen_golden_digest_and_replay_are_byte_identical() -> None:
    spec = _spec("EXPOSURE", {"exposure_ev_milli": 250})
    digests = {
        graph_content_digest(build_operation_graph(INPUT_ID, INPUT_DIGEST, [spec]))
        for _ in range(100)
    }
    graph = build_operation_graph(INPUT_ID, INPUT_DIGEST, [spec])
    assert GRAPH_SCHEMA_VERSION == "mirror.demo/OperationGraph/v2"
    assert GRAPH_ALGORITHM_VERSION == "demo-operation-graph-linear-v1"
    assert digests == {"22e06819de362dac62ffc244b2945ced614858331102a70902c8fa74a22cacb5"}
    assert graph_canonical_json(graph) == (
        b'{"algorithm_version":"demo-operation-graph-linear-v1","input_image_version_digest":"'
        + b"b" * 64
        + b'","input_image_version_id":"'
        + b"a" * 32
        + b'","nodes":[{"depends_on":[],"node_id":"op-00000000","operation_index":0,'
        + b'"spec":{"engine":"RASTER","expected_effect":{"effect_type":"EXPOSURE",'
        + b'"exposure_ev_milli":250,"target_region":"FULL_IMAGE"},"operation_type":"EXPOSURE",'
        + b'"parameters":{"exposure_ev_milli":250},"preserve":["IDENTITY_REFERENCE_FRAME"]}}],'
        + b'"schema_version":"mirror.demo/OperationGraph/v2"}'
    )


def test_tracked_v2_golden_vector_matches_python_authority() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "demo_operation_graph_v2_golden.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert set(fixture) == {
        "canonical_json_utf8_hex",
        "digest_algorithm",
        "digest_domain",
        "graph_digest_sha256",
        "graph_schema_version",
        "input_image_version_digest",
        "input_image_version_id",
        "operation_specs",
        "vector_schema_version",
    }
    assert fixture["vector_schema_version"] == "mirror.demo/OperationGraphGoldenVector/v1"
    assert fixture["graph_schema_version"] == GRAPH_SCHEMA_VERSION
    assert fixture["digest_algorithm"] == "SHA-256"
    assert fixture["digest_domain"] == f"{GRAPH_SCHEMA_VERSION}\n"
    graph = build_operation_graph(
        fixture["input_image_version_id"],
        fixture["input_image_version_digest"],
        fixture["operation_specs"],
    )
    canonical = graph_canonical_json(graph)
    assert canonical.hex() == fixture["canonical_json_utf8_hex"]
    assert graph_content_digest(graph) == fixture["graph_digest_sha256"]


def test_key_and_preserve_order_canonicalize_but_operation_order_remains_semantic() -> None:
    left = _spec("CONTRAST", {"contrast_delta_ppm": 10}, ["POSE", "IDENTITY_REFERENCE_FRAME"])
    right = {
        "expected_effect": {
            "target_region": "FULL_IMAGE",
            "effect_type": "CONTRAST",
            "contrast_delta_ppm": 10,
        },
        "preserve": ["IDENTITY_REFERENCE_FRAME", "POSE"],
        "parameters": {"contrast_delta_ppm": 10},
        "operation_type": "CONTRAST",
        "engine": "RASTER",
    }
    first = build_operation_graph(INPUT_ID, INPUT_DIGEST, [left, _spec("EXPOSURE")])
    second = build_operation_graph(INPUT_ID, INPUT_DIGEST, [right, _spec("EXPOSURE")])
    assert graph_content_digest(first) == graph_content_digest(second)
    reordered = build_operation_graph(
        INPUT_ID,
        INPUT_DIGEST,
        [_spec("EXPOSURE"), left],
    )
    assert graph_content_digest(first) != graph_content_digest(reordered)
    noncanonical_nodes = type(first)(
        first.algorithm_version,
        first.input_image_version_digest,
        first.input_image_version_id,
        tuple(reversed(first.nodes)),
    )
    _assert_code(
        "NON_CANONICAL_NODE_ORDER",
        lambda: graph_content_digest(noncanonical_nodes),
    )


def test_node_id_is_graph_local_and_not_a_global_execution_identity() -> None:
    first = build_operation_graph(INPUT_ID, INPUT_DIGEST, [_spec("EXPOSURE")])
    second = build_operation_graph("c" * 32, "d" * 64, [_spec("EXPOSURE")])
    assert first.nodes[0].node_id == second.nodes[0].node_id == "op-00000000"
    assert graph_content_digest(first) != graph_content_digest(second)


@pytest.mark.parametrize(
    ("operation_type", "parameters"),
    [
        (
            "CROP",
            {
                "left_inset_ppm": 250000,
                "right_inset_ppm": 250000,
                "top_inset_ppm": 0,
                "bottom_inset_ppm": 0,
            },
        ),
        ("ROTATE", {"angle_mdeg": -15000, "expand_canvas": True}),
        ("EXPOSURE", {"exposure_ev_milli": 2000}),
        ("CONTRAST", {"contrast_delta_ppm": -500000}),
        ("SATURATION", {"saturation_delta_ppm": 1000000}),
        ("TEMPERATURE", {"temperature_delta_mired": -100}),
        ("GEOMETRY", {"dimension_key": "x" * 48, "delta_ppm": 100000}),
        (
            "RESTORE",
            {"target_image_version_id": TARGET_ID, "target_image_version_digest": TARGET_DIGEST},
        ),
        (
            "ROLLBACK",
            {"target_image_version_id": TARGET_ID, "target_image_version_digest": TARGET_DIGEST},
        ),
        ("MAKEUP", {"reason_code": "MAKEUP_DEFERRED_NO_APPROVED_ENGINE"}),
        ("GENERATIVE", {"reason_code": "GENERATIVE_PROVIDER_UNAVAILABLE"}),
    ],
)
def test_every_frozen_operation_parses(operation_type: str, parameters: dict[str, object]) -> None:
    parsed = parse_operation_spec(_spec(operation_type, parameters))
    assert parsed.operation_type.value == operation_type


@pytest.mark.parametrize(
    ("operation_type", "key", "minimum", "maximum"),
    [
        ("EXPOSURE", "exposure_ev_milli", -2000, 2000),
        ("CONTRAST", "contrast_delta_ppm", -500000, 500000),
        ("SATURATION", "saturation_delta_ppm", -1000000, 1000000),
        ("TEMPERATURE", "temperature_delta_mired", -100, 100),
        ("GEOMETRY", "delta_ppm", -100000, 100000),
    ],
)
def test_scalar_boundaries_zero_and_one_unit_outside_fail_closed(
    operation_type: str, key: str, minimum: int, maximum: int
) -> None:
    for value in (minimum, maximum):
        parameters = _spec(operation_type)["parameters"]
        assert isinstance(parameters, dict)
        parameters[key] = value
        raw = _spec(operation_type, parameters)
        raw["expected_effect"] = _effect(operation_type, parameters)
        assert parse_operation_spec(raw).parameters[key] == value
    for value in (minimum - 1, maximum + 1, 0, True, 1.0, "1"):
        parameters = _spec(operation_type)["parameters"]
        assert isinstance(parameters, dict)
        parameters[key] = value
        raw = _spec(operation_type, parameters)
        raw["expected_effect"] = _effect(operation_type, parameters)
        _assert_invalid_scalar(lambda raw=raw: parse_operation_spec(raw))


def test_crop_rotate_geometry_and_transition_parameter_edge_cases() -> None:
    assert parse_operation_spec(
        _spec(
            "CROP",
            {
                "left_inset_ppm": 0,
                "right_inset_ppm": 0,
                "top_inset_ppm": 0,
                "bottom_inset_ppm": 250000,
            },
        )
    )
    for parameters in (
        {"left_inset_ppm": 0, "right_inset_ppm": 0, "top_inset_ppm": 0, "bottom_inset_ppm": 0},
        {"left_inset_ppm": -1, "right_inset_ppm": 0, "top_inset_ppm": 0, "bottom_inset_ppm": 0},
        {"left_inset_ppm": 250001, "right_inset_ppm": 0, "top_inset_ppm": 0, "bottom_inset_ppm": 0},
    ):
        _assert_code(
            "INVALID_PARAMETERS",
            lambda parameters=parameters: parse_operation_spec(_spec("CROP", parameters)),
        )
    for parameters in (
        {"angle_mdeg": -15001, "expand_canvas": False},
        {"angle_mdeg": 0, "expand_canvas": False},
        {"angle_mdeg": 15001, "expand_canvas": False},
        {"angle_mdeg": 1, "expand_canvas": 1},
    ):
        _assert_code(
            "INVALID_PARAMETERS",
            lambda parameters=parameters: parse_operation_spec(_spec("ROTATE", parameters)),
        )
    for parameters in (
        {"dimension_key": "Bad", "delta_ppm": 1},
        {"dimension_key": "x" * 49, "delta_ppm": 1},
        {"dimension_key": "jaw", "delta_ppm": 0},
    ):
        _assert_code(
            "INVALID_PARAMETERS",
            lambda parameters=parameters: parse_operation_spec(_spec("GEOMETRY", parameters)),
        )
    _assert_code(
        "INVALID_ID",
        lambda: parse_operation_spec(
            _spec(
                "RESTORE",
                {"target_image_version_id": "A" * 32, "target_image_version_digest": TARGET_DIGEST},
            )
        ),
    )
    _assert_code(
        "INVALID_DIGEST",
        lambda: parse_operation_spec(
            _spec(
                "ROLLBACK",
                {"target_image_version_id": TARGET_ID, "target_image_version_digest": "0" * 63},
            )
        ),
    )


def test_spec_shape_effect_engine_and_preserve_fail_closed() -> None:
    raw = _spec()
    raw["extra"] = None
    _assert_code("INVALID_PARAMETERS", lambda: parse_operation_spec(raw))
    _assert_code(
        "ENGINE_OPERATION_MISMATCH",
        lambda: parse_operation_spec(_spec("EXPOSURE", engine="GEOMETRY")),
    )
    _assert_code(
        "EXPECTED_EFFECT_MISMATCH",
        lambda: parse_operation_spec(
            _spec(
                "EXPOSURE",
                expected_effect={"effect_type": "EXPOSURE", "target_region": "FULL_IMAGE"},
            )
        ),
    )
    _assert_code("INVALID_PRESERVE", lambda: parse_operation_spec(_spec("EXPOSURE", preserve=[])))
    _assert_code(
        "INVALID_PRESERVE",
        lambda: parse_operation_spec(_spec("GEOMETRY", preserve=["IDENTITY_REFERENCE_FRAME"])),
    )
    _assert_code(
        "INVALID_PRESERVE",
        lambda: parse_operation_spec(_spec("RESTORE", preserve=["TARGET_VERSION_BYTES", "POSE"])),
    )
    _assert_code(
        "INVALID_PRESERVE", lambda: parse_operation_spec(_spec("MAKEUP", preserve=["POSE"]))
    )
    _assert_code(
        "INVALID_PRESERVE",
        lambda: parse_operation_spec(
            _spec("EXPOSURE", preserve=["POSE", "POSE", "IDENTITY_REFERENCE_FRAME"])
        ),
    )
    _assert_code(
        "INVALID_PARAMETERS",
        lambda: parse_operation_spec(_spec("MAKEUP", {"reason_code": "wrong"})),
    )


@pytest.mark.parametrize("operation_type", ["CROP", "ROTATE", "GEOMETRY"])
def test_structural_effect_snapshots_are_exact(operation_type: str) -> None:
    raw = _spec(operation_type)
    effect = raw["expected_effect"]
    assert isinstance(effect, dict)
    structural_keys = {
        "CROP": {
            "bottom_inset_ppm",
            "left_inset_ppm",
            "right_inset_ppm",
            "top_inset_ppm",
        },
        "ROTATE": {"angle_mdeg", "expand_canvas"},
        "GEOMETRY": {"delta_ppm", "dimension_key"},
    }[operation_type]
    for key in structural_keys:
        missing = deepcopy(raw)
        missing_effect = missing["expected_effect"]
        assert isinstance(missing_effect, dict)
        missing_effect.pop(key)
        _assert_code(
            "EXPECTED_EFFECT_MISMATCH", lambda missing=missing: parse_operation_spec(missing)
        )
        wrong = deepcopy(raw)
        wrong_effect = wrong["expected_effect"]
        assert isinstance(wrong_effect, dict)
        value = wrong_effect[key]
        wrong_effect[key] = value + 1 if isinstance(value, int) else "other"
        _assert_code("EXPECTED_EFFECT_MISMATCH", lambda wrong=wrong: parse_operation_spec(wrong))
    extra = deepcopy(raw)
    extra_effect = extra["expected_effect"]
    assert isinstance(extra_effect, dict)
    extra_effect["unexpected"] = True
    _assert_code("EXPECTED_EFFECT_MISMATCH", lambda: parse_operation_spec(extra))


def test_operation_spec_is_deeply_immutable_and_payload_is_defensively_copied() -> None:
    raw = _spec("CROP")
    parsed = parse_operation_spec(raw)
    raw_parameters = raw["parameters"]
    assert isinstance(raw_parameters, dict)
    raw_parameters["left_inset_ppm"] = 99
    assert parsed.parameters["left_inset_ppm"] == 1
    graph = build_operation_graph(INPUT_ID, INPUT_DIGEST, [parsed])
    digest = graph_content_digest(graph)
    with pytest.raises(TypeError):
        parsed.parameters["left_inset_ppm"] = 2  # type: ignore[index]
    first = parsed.canonical_payload()
    first_parameters = first["parameters"]
    assert isinstance(first_parameters, dict)
    first_parameters["left_inset_ppm"] = 77
    first_effect = first["expected_effect"]
    assert isinstance(first_effect, dict)
    first_effect["effect_type"] = "CHANGED"
    second = parsed.canonical_payload()
    assert second["parameters"]["left_inset_ppm"] == 1
    assert second["expected_effect"]["effect_type"] == "CROP"
    assert graph_content_digest(graph) == digest


def test_manual_spec_rejects_non_json_and_preserve_mutation_at_construction() -> None:
    valid = parse_operation_spec(_spec("EXPOSURE"))
    for parameters in (
        {"exposure_ev_milli": {"set": {1}}},
        {"exposure_ev_milli": (1,)},
        {"exposure_ev_milli": object()},
        {1: "not-json-key"},
    ):
        with pytest.raises(DemoOperationGraphError):
            OperationSpec(
                valid.engine,
                valid.operation_type,
                parameters,
                valid.preserve,
                valid.expected_effect,
            )
    external_preserve = [PreserveKey.IDENTITY_REFERENCE_FRAME]
    constructed = OperationSpec(
        valid.engine,
        valid.operation_type,
        {"exposure_ev_milli": 1},
        external_preserve,
        {"effect_type": "EXPOSURE", "exposure_ev_milli": 1, "target_region": "FULL_IMAGE"},
    )
    external_preserve.clear()
    assert constructed.preserve == (PreserveKey.IDENTITY_REFERENCE_FRAME,)
    for preserve in (
        ["IDENTITY_REFERENCE_FRAME"],
        [PreserveKey.POSE, PreserveKey.IDENTITY_REFERENCE_FRAME],
        [PreserveKey.IDENTITY_REFERENCE_FRAME, PreserveKey.IDENTITY_REFERENCE_FRAME],
        [],
    ):
        with pytest.raises(DemoOperationGraphError):
            OperationSpec(
                valid.engine,
                valid.operation_type,
                {"exposure_ev_milli": 1},
                preserve,
                {"effect_type": "EXPOSURE", "exposure_ev_milli": 1, "target_region": "FULL_IMAGE"},
            )
    _assert_code(
        "INVALID_PARAMETERS",
        lambda: parse_operation_spec(
            _spec("MAKEUP", {"reason": "MAKEUP_DEFERRED_NO_APPROVED_ENGINE"})
        ),
    )


def test_canonical_json_rejects_non_interoperable_values() -> None:
    for value in (
        {"float": 1.0},
        {"set": {"x"}},
        {"time": object()},
        {1: "key"},
        {"null": None},
        {"large": 9_007_199_254_740_992},
        {"small": -9_007_199_254_740_992},
        {"non_nfc": "e\u0301"},
        {"surrogate": "\ud800"},
        {"nested": {"items": [None]}},
        {"nested": {"large": 9_007_199_254_740_992}},
        {"nested": {"non_nfc": "e\u0301"}},
    ):
        _assert_code("NON_CANONICAL_JSON", lambda value=value: canonical_json_bytes(value))


def test_canonical_json_uses_utf8_key_order_and_preserves_bool_int_distinction() -> None:
    assert canonical_json_bytes({"中": True, "é": 1, "a": False}) == (
        '{"a":false,"é":1,"中":true}'.encode()
    )
    assert canonical_json_bytes({"maximum": 9_007_199_254_740_991})
    assert canonical_json_bytes({"minimum": -9_007_199_254_740_991})


def test_graph_limits_and_hydrated_topology_reason_codes() -> None:
    _assert_code("INVALID_GRAPH", lambda: build_operation_graph(INPUT_ID, INPUT_DIGEST, []))
    _assert_code(
        "INVALID_GRAPH", lambda: build_operation_graph(INPUT_ID, INPUT_DIGEST, [_spec()] * 65)
    )
    graph = build_operation_graph(
        INPUT_ID, INPUT_DIGEST, [_spec(), _spec("CONTRAST"), _spec("SATURATION")]
    )
    payload = graph.canonical_payload()
    cases: list[tuple[str, dict[str, object]]] = []
    duplicate_id = deepcopy(payload)
    duplicate_id["nodes"][1]["node_id"] = "op-00000000"
    cases.append(("DUPLICATE_NODE_ID", duplicate_id))
    duplicate_index = deepcopy(payload)
    duplicate_index["nodes"][1]["operation_index"] = 0
    cases.append(("DUPLICATE_OPERATION_INDEX", duplicate_index))
    orphan = deepcopy(payload)
    orphan["nodes"][1]["depends_on"] = ["op-99999999"]
    cases.append(("ORPHAN_DEPENDENCY", orphan))
    duplicate_edge = deepcopy(payload)
    duplicate_edge["nodes"][1]["depends_on"] = ["op-00000000", "op-00000000"]
    cases.append(("DUPLICATE_EDGE", duplicate_edge))
    cycle = deepcopy(payload)
    cycle["nodes"][0]["depends_on"] = ["op-00000001"]
    cycle["nodes"][1]["depends_on"] = ["op-00000000"]
    cases.append(("GRAPH_CYCLE", cycle))
    disconnected = deepcopy(payload)
    disconnected["nodes"][1]["depends_on"] = []
    cases.append(("DISCONNECTED_GRAPH", disconnected))
    branch = deepcopy(payload)
    branch["nodes"][2]["depends_on"] = ["op-00000000"]
    cases.append(("NON_LINEAR_GRAPH_UNSUPPORTED", branch))
    join = deepcopy(payload)
    join["nodes"][2]["depends_on"] = ["op-00000000", "op-00000001"]
    cases.append(("NON_LINEAR_GRAPH_UNSUPPORTED", join))
    jump = deepcopy(payload)
    jump["nodes"][1]["depends_on"] = ["op-00000002"]
    jump["nodes"][2]["depends_on"] = ["op-00000000"]
    cases.append(("NON_LINEAR_GRAPH_UNSUPPORTED", jump))
    gap = deepcopy(payload)
    gap["nodes"][2]["operation_index"] = 3
    cases.append(("INVALID_GRAPH", gap))
    for code, invalid in cases:
        _assert_code(code, lambda invalid=invalid: hydrate_operation_graph(invalid))


def test_hydration_validates_explicit_metadata_and_keeps_duplicate_specs_distinct() -> None:
    graph = build_operation_graph(INPUT_ID, INPUT_DIGEST, [_spec(), _spec()])
    assert graph.nodes[0].spec == graph.nodes[1].spec
    assert graph.nodes[0].node_id != graph.nodes[1].node_id
    assert hydrate_operation_graph(graph.canonical_payload()) == graph
    bad = graph.canonical_payload()
    bad["algorithm_version"] = "other"
    _assert_code("UNSUPPORTED_ALGORITHM_VERSION", lambda: hydrate_operation_graph(bad))
    wrong_schema = graph.canonical_payload()
    wrong_schema["schema_version"] = "mirror.demo/OperationGraph/v1"
    _assert_code("UNSUPPORTED_SCHEMA_VERSION", lambda: hydrate_operation_graph(wrong_schema))


def test_unavailable_nodes_parse_but_execution_fails_before_any_callback() -> None:
    graph = build_operation_graph(
        INPUT_ID, INPUT_DIGEST, [_spec(), _spec("MAKEUP"), _spec("GENERATIVE")]
    )
    callback_calls = 0

    def callback() -> None:
        nonlocal callback_calls
        callback_calls += 1

    with pytest.raises(OperationExecutionUnavailable) as error:
        validate_for_execution(graph)
        callback()
    assert error.value.code == CapabilityState.DEFERRED_WITH_EXPLICIT_REASON.value
    assert str(error.value) == "MAKEUP_DEFERRED_NO_APPROVED_ENGINE"
    assert callback_calls == 0


@pytest.mark.parametrize("dimension_key", ["not_screened", "jaw_width"])
def test_geometry_is_structurally_parseable_but_execution_registry_gated(
    dimension_key: str,
) -> None:
    spec = parse_operation_spec(_spec("GEOMETRY", {"dimension_key": dimension_key, "delta_ppm": 1}))
    assert capability_state(spec) is CapabilityState.CAPABILITY_GATED
    graph = build_operation_graph(INPUT_ID, INPUT_DIGEST, [spec])
    with pytest.raises(OperationExecutionUnavailable) as error:
        validate_for_execution(graph)
    assert error.value.code == CapabilityState.CAPABILITY_GATED.value
    assert str(error.value) == "GEOMETRY_EXECUTION_REGISTRY_REQUIRED"


def _version(
    marker: str,
    sequence: int,
    parent: str | None,
    *,
    actor: str = "e" * 32,
    demo_session: str = "4" * 32,
    session: str = "f" * 32,
    quarantined: bool = False,
) -> ImageVersionReference:
    asset_marker = {"a": "1", "b": "2", "c": "3", "d": "4"}.get(marker, "5")
    return ImageVersionReference(
        image_version_id=marker * 32,
        image_version_digest=marker * 64,
        actor_id=actor,
        demo_session_id=demo_session,
        editing_session_id=session,
        result_asset_id=asset_marker * 32,
        result_asset_sha256=asset_marker * 64,
        sequence=sequence,
        parent_image_version_id=parent,
        quarantined=quarantined,
    )


def test_restore_and_rollback_transition_intents_are_append_only_and_bound() -> None:
    original = _version("a", 0, None)
    parent = _version("b", 1, original.image_version_id)
    current = _version("c", 2, parent.image_version_id)
    history = [original, parent, current]
    restore = plan_restore_transition(
        current, history, original.image_version_id, original.image_version_digest
    )
    rollback = plan_rollback_transition(
        current, history, parent.image_version_id, parent.image_version_digest
    )
    assert (
        restore.kind,
        restore.parent_image_version_id,
        restore.parent_image_version_digest,
        restore.result_sequence,
        restore.source_image_version_id,
        restore.source_image_version_digest,
        restore.source_asset_id,
        restore.source_asset_sha256,
        restore.target_image_version_id,
        restore.target_image_version_digest,
        restore.target_result_asset_id,
        restore.target_result_asset_sha256,
        restore.expected_result_asset_sha256,
    ) == (
        "RESTORED",
        current.image_version_id,
        current.image_version_digest,
        3,
        current.image_version_id,
        current.image_version_digest,
        current.result_asset_id,
        current.result_asset_sha256,
        original.image_version_id,
        original.image_version_digest,
        original.result_asset_id,
        original.result_asset_sha256,
        original.result_asset_sha256,
    )
    assert (rollback.kind, rollback.target_image_version_id) == (
        "ROLLED_BACK",
        parent.image_version_id,
    )
    assert restore.requires_distinct_result_asset_id is True
    _assert_lineage(
        "RESULT_ASSET_NOT_DISTINCT",
        lambda: validate_result_asset_id(restore, current.result_asset_id),
    )
    _assert_lineage(
        "RESULT_ASSET_NOT_DISTINCT",
        lambda: validate_result_asset_id(restore, original.result_asset_id),
    )
    validate_result_asset_id(restore, "9" * 32)


def test_transition_lineage_fail_closed_boundaries() -> None:
    original = _version("a", 0, None)
    parent = _version("b", 1, original.image_version_id)
    current = _version("c", 2, parent.image_version_id)
    history = [original, parent, current]
    _assert_lineage(
        "CURRENT_TARGET_UNSUPPORTED",
        lambda: plan_restore_transition(
            current, history, current.image_version_id, current.image_version_digest
        ),
    )
    _assert_lineage(
        "TARGET_DIGEST_MISMATCH",
        lambda: plan_restore_transition(current, history, original.image_version_id, "0" * 64),
    )
    _assert_lineage(
        "ROLLBACK_NOT_IMMEDIATE_PARENT",
        lambda: plan_rollback_transition(
            current, history, original.image_version_id, original.image_version_digest
        ),
    )
    _assert_lineage(
        "ROLLBACK_NOT_IMMEDIATE_PARENT",
        lambda: plan_rollback_transition(
            original, history, parent.image_version_id, parent.image_version_digest
        ),
    )
    foreign = _version("d", 1, original.image_version_id, session="9" * 32)
    foreign_current = _version("c", 2, foreign.image_version_id)
    _assert_lineage(
        "CROSS_SESSION_HISTORY",
        lambda: plan_restore_transition(
            foreign_current,
            [original, foreign, foreign_current],
            foreign.image_version_id,
            foreign.image_version_digest,
        ),
    )
    quarantined = _version("b", 1, original.image_version_id, quarantined=True)
    _assert_lineage(
        "QUARANTINED_HISTORY",
        lambda: plan_restore_transition(
            current,
            [original, quarantined, current],
            quarantined.image_version_id,
            quarantined.image_version_digest,
        ),
    )
    outsider = _version("d", 3, original.image_version_id)
    _assert_lineage(
        "TARGET_NOT_ANCESTOR",
        lambda: plan_restore_transition(
            current,
            [original, parent, current, outsider],
            outsider.image_version_id,
            outsider.image_version_digest,
        ),
    )
    _assert_lineage(
        "TARGET_NOT_FOUND", lambda: plan_restore_transition(current, history, "9" * 32, "9" * 64)
    )


def test_current_ancestor_chain_validates_authority_sequence_and_quarantine() -> None:
    original = _version("a", 0, None)
    parent = _version("b", 1, original.image_version_id)
    current = _version("c", 2, parent.image_version_id)
    foreign_actor = _version("b", 1, original.image_version_id, actor="9" * 32)
    _assert_lineage(
        "CROSS_SESSION_HISTORY",
        lambda: plan_restore_transition(
            current,
            [original, foreign_actor, current],
            original.image_version_id,
            original.image_version_digest,
        ),
    )
    foreign_demo = _version("b", 1, original.image_version_id, demo_session="9" * 32)
    _assert_lineage(
        "CROSS_SESSION_HISTORY",
        lambda: plan_restore_transition(
            current,
            [original, foreign_demo, current],
            original.image_version_id,
            original.image_version_digest,
        ),
    )
    foreign_editing = _version("b", 1, original.image_version_id, session="9" * 32)
    _assert_lineage(
        "CROSS_SESSION_HISTORY",
        lambda: plan_restore_transition(
            current,
            [original, foreign_editing, current],
            original.image_version_id,
            original.image_version_digest,
        ),
    )
    gap_current = _version("c", 3, parent.image_version_id)
    _assert_lineage(
        "SEQUENCE_GAP",
        lambda: plan_restore_transition(
            gap_current,
            [original, parent, gap_current],
            original.image_version_id,
            original.image_version_digest,
        ),
    )
    quarantined_current = _version("c", 2, parent.image_version_id, quarantined=True)
    _assert_lineage(
        "QUARANTINED_HISTORY",
        lambda: plan_restore_transition(
            quarantined_current,
            [original, parent, quarantined_current],
            original.image_version_id,
            original.image_version_digest,
        ),
    )
    quarantined_parent = _version("b", 1, original.image_version_id, quarantined=True)
    _assert_lineage(
        "QUARANTINED_HISTORY",
        lambda: plan_restore_transition(
            current,
            [original, quarantined_parent, current],
            original.image_version_id,
            original.image_version_digest,
        ),
    )


def _assert_lineage(code: str, action: object) -> None:
    with pytest.raises(OperationLineageError) as error:
        assert callable(action)
        action()
    assert error.value.code == code


def _assert_invalid_scalar(action: object) -> None:
    with pytest.raises(DemoOperationGraphError) as error:
        assert callable(action)
        action()
    assert error.value.code in {"INVALID_PARAMETERS", "NON_CANONICAL_JSON"}


def test_hand_constructed_spec_cannot_bypass_derived_effect() -> None:
    _assert_code(
        "EXPECTED_EFFECT_MISMATCH",
        lambda: OperationSpec(
            engine=parse_operation_spec(_spec()).engine,
            operation_type=OperationType.EXPOSURE,
            parameters={"exposure_ev_milli": 1},
            preserve=(PreserveKey.IDENTITY_REFERENCE_FRAME,),
            expected_effect={"effect_type": "EXPOSURE", "target_region": "FULL_IMAGE"},
        ),
    )
