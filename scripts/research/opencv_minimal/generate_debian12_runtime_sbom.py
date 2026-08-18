"""Generate the deterministic private SBOM for the Debian 12 M4 runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

RUNTIME_FILES = {
    "libmirror_opencv_remap.so": (
        "1fca403721b0ea2adb5a7529aa41d3a8f65813635378ea1a7c69973764f99e49"
    ),
    "libopencv_core.so.5.0.0": ("00f6f16794afeafd06fe6ed596c75e6173199a344242b0eb1d5bdb3197eda8eb"),
    "libopencv_flann.so.5.0.0": (
        "50f7b0d5883b49b6d114f58d1c74560f780603dedc7c876039db3991bb788f79"
    ),
    "libopencv_geometry.so.5.0.0": (
        "e021428b8080794899bb36c7be7d8bc3ea4187cda47c3cd8d989d5b3768f9d36"
    ),
    "libopencv_imgproc.so.5.0.0": (
        "d8ee4b5211369ffbe5f27b68587ae34c5bb75979c41b08b83495dd8869efd6c9"
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime.resolve(strict=True)
    for name, expected in RUNTIME_FILES.items():
        actual = hashlib.sha256((runtime / name).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"RUNTIME_HASH_MISMATCH:{name}")

    properties = [
        {"name": f"project-mirror:sha256:{name}", "value": digest}
        for name, digest in sorted(RUNTIME_FILES.items())
    ]
    document = {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "components": [
            {
                "bom-ref": "pkg:github/opencv/opencv@5.0.0",
                "hashes": [
                    {
                        "alg": "SHA-256",
                        "content": (
                            "b0528f5a1d379d59d4701cb28c36e22214cc51cf64594e5b56f2d3e6c0233095"
                        ),
                    }
                ],
                "licenses": [{"license": {"id": "Apache-2.0"}}],
                "name": "OpenCV",
                "properties": properties[1:],
                "purl": "pkg:github/opencv/opencv@5.0.0",
                "type": "library",
                "version": "5.0.0",
            },
            {
                "bom-ref": "pkg:generic/zlib@1.3.2",
                "licenses": [{"license": {"id": "Zlib"}}],
                "name": "zlib",
                "purl": "pkg:generic/zlib@1.3.2",
                "scope": "required",
                "type": "library",
                "version": "1.3.2",
            },
            {
                "bom-ref": "pkg:generic/project-mirror-opencv-remap@ctypes-c-v1",
                "licenses": [{"license": {"name": "Project Mirror private first-party code"}}],
                "name": "project-mirror-opencv-remap",
                "properties": properties[:1],
                "purl": "pkg:generic/project-mirror-opencv-remap@ctypes-c-v1",
                "type": "library",
                "version": "ctypes-c-v1",
            },
        ],
        "dependencies": [
            {
                "dependsOn": [
                    "pkg:github/opencv/opencv@5.0.0",
                    "pkg:generic/zlib@1.3.2",
                ],
                "ref": "pkg:generic/project-mirror-opencv-remap@ctypes-c-v1",
            },
            {
                "dependsOn": ["pkg:generic/zlib@1.3.2"],
                "ref": "pkg:github/opencv/opencv@5.0.0",
            },
            {"dependsOn": [], "ref": "pkg:generic/zlib@1.3.2"},
        ],
        "metadata": {
            "component": {
                "bom-ref": "project-mirror:p2-m4:opencv-debian12-v3",
                "name": "OPENCV_5_0_0_DEBIAN12_COMPAT_V3",
                "type": "application",
                "version": "cc-p2-m4-02",
            }
        },
        "specVersion": "1.6",
        "version": 1,
    }
    encoded = json.dumps(
        document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    args.output.write_bytes(encoded + b"\n")
    print(hashlib.sha256(encoded + b"\n").hexdigest())


if __name__ == "__main__":
    main()
