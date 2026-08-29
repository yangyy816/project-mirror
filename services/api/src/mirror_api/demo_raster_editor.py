"""Pure, local, deterministic raster materialization for the D07-B demo scope."""

from __future__ import annotations

import hashlib
import io
import warnings
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Final, cast

from PIL import Image, UnidentifiedImageError

from mirror_api.demo_operation_graph import OperationEngine, OperationSpec, OperationType

RASTER_ALGORITHM_VERSION: Final = "demo-raster-editor-pillow12-fixedpoint-v1"
OUTPUT_MIME_TYPE: Final = "image/png"
MAX_INPUT_BYTES: Final = 32 * 1024 * 1024
MAX_INPUT_PIXELS: Final = 40_000_000
_SCALE: Final = 1_000_000
_MIDPOINT: Final = 128
_SUPPORTED_SOURCE_FORMATS: Final = frozenset({"PNG", "JPEG", "WEBP"})
_EXECUTABLE_TYPES: Final = frozenset(
    {
        OperationType.CROP,
        OperationType.ROTATE,
        OperationType.EXPOSURE,
        OperationType.CONTRAST,
        OperationType.SATURATION,
        OperationType.TEMPERATURE,
    }
)


class RasterEditError(ValueError):
    """Fail-closed raster execution error with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RasterEditResult:
    """Deterministic, metadata-free PNG materialization and its binding facts."""

    algorithm_version: str
    input_sha256: str
    mime_type: str
    output_sha256: str
    png_bytes: bytes
    height: int
    width: int


def execute_raster_operation(input_bytes: bytes, spec: OperationSpec) -> RasterEditResult:
    """Apply one frozen D07-A raster operation without mutating the input bytes."""

    normalized_spec = _validate_spec(spec)
    source = _decode_source(input_bytes)
    rendered: Image.Image | None = None
    try:
        rendered = _render(source, normalized_spec)
        if rendered.width <= 0 or rendered.height <= 0:
            raise RasterEditError("INVALID_RENDER", "rendered image dimensions must be positive")
        width = rendered.width
        height = rendered.height
        png_bytes = _encode_png(rendered)
    finally:
        if rendered is not None:
            rendered.close()
        source.close()
    return RasterEditResult(
        algorithm_version=RASTER_ALGORITHM_VERSION,
        input_sha256=hashlib.sha256(input_bytes).hexdigest(),
        mime_type=OUTPUT_MIME_TYPE,
        output_sha256=hashlib.sha256(png_bytes).hexdigest(),
        png_bytes=png_bytes,
        height=height,
        width=width,
    )


def _validate_spec(spec: OperationSpec) -> OperationSpec:
    if not isinstance(spec, OperationSpec):
        raise RasterEditError("INVALID_SPEC", "raster execution requires a frozen OperationSpec")
    if spec.engine is not OperationEngine.RASTER:
        raise RasterEditError("UNSUPPORTED_ENGINE", "only the raster engine can be materialized")
    if spec.operation_type not in _EXECUTABLE_TYPES:
        raise RasterEditError(
            "UNSUPPORTED_OPERATION",
            "operation type is not executable by the deterministic raster editor",
        )
    try:
        return OperationSpec(
            engine=spec.engine,
            operation_type=spec.operation_type,
            parameters=spec.parameters,
            preserve=spec.preserve,
            expected_effect=spec.expected_effect,
        )
    except (TypeError, ValueError) as exc:
        raise RasterEditError("INVALID_SPEC", "operation spec is not canonical") from exc


def _decode_source(input_bytes: bytes) -> Image.Image:
    if not isinstance(input_bytes, bytes) or not input_bytes:
        raise RasterEditError("INVALID_INPUT", "input must be non-empty immutable image bytes")
    if len(input_bytes) > MAX_INPUT_BYTES:
        raise RasterEditError("INPUT_TOO_LARGE", "input image bytes exceed the configured limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(input_bytes)) as decoded:
                if decoded.format not in _SUPPORTED_SOURCE_FORMATS:
                    raise RasterEditError(
                        "UNSUPPORTED_IMAGE", "input image format is not supported"
                    )
                if decoded.width <= 0 or decoded.height <= 0:
                    raise RasterEditError(
                        "INVALID_IMAGE", "input image dimensions must be positive"
                    )
                if decoded.width * decoded.height > MAX_INPUT_PIXELS:
                    raise RasterEditError(
                        "DECOMPRESSION_BOMB", "input image exceeds the pixel limit"
                    )
                decoded.load()
                return decoded.convert("RGB")
    except RasterEditError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise RasterEditError("INVALID_IMAGE", "input image cannot be safely decoded") from exc


def _render(image: Image.Image, spec: OperationSpec) -> Image.Image:
    operation_type = spec.operation_type
    if operation_type is OperationType.CROP:
        return _crop(image, spec)
    if operation_type is OperationType.ROTATE:
        return _rotate(image, spec)
    if operation_type is OperationType.EXPOSURE:
        return _map_pixels(image, _exposure_transform(int(spec.parameters["exposure_ev_milli"])))
    if operation_type is OperationType.CONTRAST:
        return _map_pixels(image, _contrast_transform(int(spec.parameters["contrast_delta_ppm"])))
    if operation_type is OperationType.SATURATION:
        return _saturation(image, int(spec.parameters["saturation_delta_ppm"]))
    if operation_type is OperationType.TEMPERATURE:
        return _temperature(image, int(spec.parameters["temperature_delta_mired"]))
    raise RasterEditError("UNSUPPORTED_OPERATION", "operation type is not executable")


def _crop(image: Image.Image, spec: OperationSpec) -> Image.Image:
    parameters = spec.parameters
    left = _ppm_pixels(image.width, int(parameters["left_inset_ppm"]))
    right = _ppm_pixels(image.width, int(parameters["right_inset_ppm"]))
    top = _ppm_pixels(image.height, int(parameters["top_inset_ppm"]))
    bottom = _ppm_pixels(image.height, int(parameters["bottom_inset_ppm"]))
    if left + right >= image.width or top + bottom >= image.height:
        raise RasterEditError("ZERO_SIZE_CROP", "crop insets leave no pixels")
    return image.crop((left, top, image.width - right, image.height - bottom))


def _rotate(image: Image.Image, spec: OperationSpec) -> Image.Image:
    parameters = spec.parameters
    angle_degrees = Decimal(int(parameters["angle_mdeg"])) / Decimal(1000)
    return image.rotate(
        float(angle_degrees),
        resample=Image.Resampling.BICUBIC,
        expand=bool(parameters["expand_canvas"]),
        fillcolor=(0, 0, 0),
    )


def _ppm_pixels(size: int, inset_ppm: int) -> int:
    inset = Decimal(size) * Decimal(inset_ppm) / Decimal(_SCALE)
    return int(inset.to_integral_value(ROUND_HALF_EVEN))


def _exposure_transform(exposure_ev_milli: int) -> tuple[int, ...]:
    with localcontext() as context:
        context.prec = 50
        factor = (Decimal(2).ln() * Decimal(exposure_ev_milli) / Decimal(1000)).exp()
        factor_scaled = int((factor * Decimal(_SCALE)).to_integral_value(ROUND_HALF_EVEN))
    return tuple(_clamp(_round_div(value * factor_scaled, _SCALE)) for value in range(256))


def _contrast_transform(delta_ppm: int) -> tuple[int, ...]:
    factor_scaled = _SCALE + delta_ppm
    return tuple(
        _clamp(_MIDPOINT + _round_div((value - _MIDPOINT) * factor_scaled, _SCALE))
        for value in range(256)
    )


def _map_pixels(image: Image.Image, transform: tuple[int, ...]) -> Image.Image:
    return image.point(transform * 3)


def _saturation(image: Image.Image, delta_ppm: int) -> Image.Image:
    factor_scaled = _SCALE + delta_ppm
    output = Image.new("RGB", image.size)
    pixels = cast(Iterable[tuple[int, int, int]], image.getdata())
    output.putdata([_saturate_pixel(pixel, factor_scaled) for pixel in pixels])
    return output


def _saturate_pixel(pixel: tuple[int, int, int], factor_scaled: int) -> tuple[int, int, int]:
    red, green, blue = pixel
    luma = _round_div(299 * red + 587 * green + 114 * blue, 1000)
    return (
        _clamp(luma + _round_div((red - luma) * factor_scaled, _SCALE)),
        _clamp(luma + _round_div((green - luma) * factor_scaled, _SCALE)),
        _clamp(luma + _round_div((blue - luma) * factor_scaled, _SCALE)),
    )


def _temperature(image: Image.Image, delta_mired: int) -> Image.Image:
    """Use fixed-point opposing red/blue channel shifts for a bounded temperature intent."""

    shift = _round_div(delta_mired * 255, 1000)
    output = Image.new("RGB", image.size)
    pixels = cast(Iterable[tuple[int, int, int]], image.getdata())
    output.putdata(
        [(_clamp(red + shift), green, _clamp(blue - shift)) for red, green, blue in pixels]
    )
    return output


def _round_div(numerator: int, denominator: int) -> int:
    return int((Decimal(numerator) / Decimal(denominator)).to_integral_value(ROUND_HALF_EVEN))


def _clamp(value: int) -> int:
    return max(0, min(255, value))


def _encode_png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=9, optimize=False)
    return output.getvalue()
