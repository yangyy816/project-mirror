from __future__ import annotations

import hashlib
import io

import pytest
from PIL import Image

from mirror_api.demo_operation_graph import (
    OperationEngine,
    OperationSpec,
    OperationType,
    PreserveKey,
)
from mirror_api.demo_raster_editor import (
    OUTPUT_MIME_TYPE,
    RASTER_ALGORITHM_VERSION,
    RasterEditError,
    execute_raster_operation,
)


def _image_bytes(*, size: tuple[int, int] = (12, 10), exif: bytes | None = None) -> bytes:
    output = io.BytesIO()
    with Image.new("RGB", size) as image:
        image.putdata(
            [
                ((index * 31) % 256, (index * 73) % 256, (index * 113) % 256)
                for index in range(size[0] * size[1])
            ]
        )
        if exif is None:
            image.save(output, format="JPEG", quality=93)
        else:
            image.save(output, format="JPEG", quality=93, exif=exif)
    return output.getvalue()


def _spec(operation_type: OperationType, parameters: dict[str, int | bool]) -> OperationSpec:
    effect = {"effect_type": operation_type.value, "target_region": "FULL_IMAGE", **parameters}
    if operation_type in {OperationType.CROP, OperationType.ROTATE}:
        effect["target_region"] = "CANVAS"
    return OperationSpec(
        engine=OperationEngine.RASTER,
        operation_type=operation_type,
        parameters=parameters,
        preserve=(PreserveKey.IDENTITY_REFERENCE_FRAME,),
        expected_effect=effect,
    )


@pytest.mark.parametrize(
    ("operation_type", "parameters", "expected_sha256"),
    [
        (
            OperationType.CROP,
            {
                "left_inset_ppm": 100_000,
                "right_inset_ppm": 0,
                "top_inset_ppm": 0,
                "bottom_inset_ppm": 0,
            },
            "9e58aa2f44529de3e1e713f45335cccf901c725bcb102085735ef8fd8f067cc5",
        ),
        (
            OperationType.ROTATE,
            {"angle_mdeg": 5_000, "expand_canvas": True},
            "c54664d5d4f7f8a770d90860a9f4c697238b859554ffe8f063e88d3396d61aa4",
        ),
        (
            OperationType.EXPOSURE,
            {"exposure_ev_milli": 500},
            "e56c9db5de38ad641eb5bd4b3df9f26789040ef7844b5fb1c68fccf9da6a4f57",
        ),
        (
            OperationType.CONTRAST,
            {"contrast_delta_ppm": 200_000},
            "6cafa55c4ff62bb6d8ac00b22c33aa3dd193886dd0c68a1dd787e681303c6279",
        ),
        (
            OperationType.SATURATION,
            {"saturation_delta_ppm": -500_000},
            "5b9331db7e6e139571c4249500140305bc442c3a3cbcec96e010a7ca3f9013d3",
        ),
        (
            OperationType.TEMPERATURE,
            {"temperature_delta_mired": 100},
            "af3f58eb490f2cbd3737122dd6ebb76c179f565fd4c0428053d6cd8334cbe9de",
        ),
    ],
)
def test_each_supported_operation_materializes_deterministic_changed_png(
    operation_type: OperationType,
    parameters: dict[str, int | bool],
    expected_sha256: str,
) -> None:
    source = _image_bytes()
    spec = _spec(operation_type, parameters)

    first = execute_raster_operation(source, spec)
    second = execute_raster_operation(source, spec)

    assert first == second
    assert first.input_sha256 == hashlib.sha256(source).hexdigest()
    assert first.output_sha256 == hashlib.sha256(first.png_bytes).hexdigest()
    assert first.output_sha256 == expected_sha256
    assert first.algorithm_version == RASTER_ALGORITHM_VERSION
    assert first.mime_type == OUTPUT_MIME_TYPE
    assert first.png_bytes != source
    with Image.open(io.BytesIO(source)) as source_decoded:
        source_pixels = source_decoded.convert("RGB").tobytes()
    with Image.open(io.BytesIO(first.png_bytes)) as decoded:
        assert decoded.format == "PNG"
        assert decoded.mode == "RGB"
        assert decoded.size == (first.width, first.height)
        assert decoded.info.get("exif") in (None, b"")
        assert decoded.info.get("icc_profile") is None
        if operation_type not in {OperationType.CROP, OperationType.ROTATE}:
            assert decoded.tobytes() != source_pixels


def test_input_bytes_are_immutable_and_exif_is_not_propagated() -> None:
    source = _image_bytes(exif=b"Exif\x00\x00demo-private-metadata")
    original = bytes(source)

    result = execute_raster_operation(
        source, _spec(OperationType.EXPOSURE, {"exposure_ev_milli": 250})
    )

    assert source == original
    with Image.open(io.BytesIO(result.png_bytes)) as decoded:
        assert decoded.getexif() == {}
        assert decoded.info == {}


def test_invalid_images_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _spec(OperationType.CONTRAST, {"contrast_delta_ppm": 100_000})
    with pytest.raises(RasterEditError, match="cannot be safely decoded") as invalid:
        execute_raster_operation(b"not an image", spec)
    assert invalid.value.code == "INVALID_IMAGE"

    monkeypatch.setattr("mirror_api.demo_raster_editor.MAX_INPUT_PIXELS", 10)
    with pytest.raises(RasterEditError, match="pixel limit") as oversized:
        execute_raster_operation(_image_bytes(), spec)
    assert oversized.value.code == "DECOMPRESSION_BOMB"


def test_unsupported_engine_and_non_materializable_raster_type_fail_closed() -> None:
    geometry = OperationSpec(
        engine=OperationEngine.GEOMETRY,
        operation_type=OperationType.GEOMETRY,
        parameters={"dimension_key": "jaw_width", "delta_ppm": 1},
        preserve=(PreserveKey.IDENTITY_REFERENCE_FRAME, PreserveKey.NON_TARGET_GEOMETRY),
        expected_effect={
            "effect_type": "GEOMETRY",
            "target_region": "FACE_REGION",
            "dimension_key": "jaw_width",
            "delta_ppm": 1,
        },
    )
    with pytest.raises(RasterEditError, match="only the raster engine") as engine_error:
        execute_raster_operation(_image_bytes(), geometry)
    assert engine_error.value.code == "UNSUPPORTED_ENGINE"

    restore = OperationSpec(
        engine=OperationEngine.RASTER,
        operation_type=OperationType.RESTORE,
        parameters={"target_image_version_id": "a" * 32, "target_image_version_digest": "b" * 64},
        preserve=(PreserveKey.TARGET_VERSION_BYTES,),
        expected_effect={
            "effect_type": "RESTORE",
            "target_region": "VERSION_CONTENT",
            "target_image_version_digest": "b" * 64,
        },
    )
    with pytest.raises(RasterEditError, match="not executable") as operation_error:
        execute_raster_operation(_image_bytes(), restore)
    assert operation_error.value.code == "UNSUPPORTED_OPERATION"
