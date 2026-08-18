# P2-M4-T04 OpenCV 5 wheel PoC report

## Disposition

- Candidate: `OPENCV_PYTHON_HEADLESS_5_0_0_93_V1`
- Result: `FURTHER_RESEARCH`
- Approved for T05 adapter: **no**
- Scope: private synthetic/non-human PoC only

The candidate passed deterministic transform behavior, cross-platform parity, performance and
footprint gates. It is not approved because the general-purpose wheel brings a materially broader
native codec/network-capable closure than the bounded M4 adapter needs, and the native vulnerability
database Gate could not be completed. Thresholds were not changed.

## Artifact admission

All artifacts stayed under ignored `work/p2m4-opencv5` storage. Recomputed hashes matched the
preregistered official PyPI values:

| Artifact                 |      Bytes | SHA-256                                                            |
| ------------------------ | ---------: | ------------------------------------------------------------------ |
| Windows OpenCV wheel     | 43,825,962 | `829717b6a95554f273e49e357cee3b3a2a26b6f4842fbc1bed2b45bdd8f87e0e` |
| Linux OpenCV wheel       | 56,563,598 | `09a872a157c1376ab922a69bbf22f9a95bcc7b658a9d8b436a60212b02b2eeb4` |
| Python packaging source  | 81,817,738 | `b82f9831daab90b725c7c1ee1b36cb5732c367096ac76d119e64e14eb70d5f3c` |
| OpenCV 5.0.0 tag archive | 81,594,270 | `b0528f5a1d379d59d4701cb28c36e22214cc51cf64594e5b56f2d3e6c0233095` |
| Windows NumPy wheel      | 12,460,532 | `85aaccb24182c25df891ad0ec333585967e115269d5f1b17f2c9ae005bc96657` |
| Linux NumPy wheel        | 16,709,995 | `29b86ff8a6cc556b47ec6b64b194815cc80e6bf5eedcc6cddfd65318cb0b4eee` |

Wheel metadata requires only `numpy>=2` for Python 3.13; the pre-import lock used `numpy==2.5.2`.
No project manifest or lockfile changed.

## Execution evidence

- Windows: Python 3.13.1, two independent successful roots after two preserved R02 harness-failure
  roots.
- Linux: exact local image `python@sha256:031ebf3cde9f3719d2db385233bcb18df5162038e9cda20e64e08f49f4b47a2f`,
  two successful `--network none` containers after four preserved R03 import-stage attempts caused by
  a non-executable tmpfs.
- All four valid runs produced deterministic digest
  `5833e2cfa47036005aa10ebd57ea4f7c1cf95b7800dc7057c489c4cb0791bda1`.
- Windows-to-Linux decoded pixel comparison at 256x256 and 1024x1024: maximum delta `0`, mean delta
  `0.0`, changed-pixel fraction `0.0`.
- All nine preregistered numeric/bounds/foldover/malformed negative controls passed.
- Worst observed 1024x1024 p95 was `7.2457 ms`, below the `100 ms` Gate.
- Linux wheel uncompressed size was `150,297,995` bytes; isolated Windows NumPy/OpenCV runtime was
  `171,089,541` bytes, below the `350 MiB` Gate.

The observed evidence supports `BIT_EXACT_CROSS_PLATFORM` for this bounded non-human fixture, which
is stronger than the preregistered cross-platform measurement-equivalence claim. It does not prove
identity preservation or M5 variable isolation.

## Supply-chain findings

- Top-level OpenCV/Python package license is Apache-2.0. The wheel retains bundled third-party notices;
  the Linux third-party notice digest is
  `2537f5653345db7231ff12f307bcfa4c89807d45ed1c4bb8ebfb6f26f61b160a`.
- The Linux wheel includes FFmpeg, OpenSSL 1.1, libaom, libavif, libvpx, OpenBLAS/Fortran and codec
  libraries that are unnecessary for the M4 `remap` surface. The Windows wheel includes
  `opencv_videoio_ffmpeg500_64.dll`; import inspection found `WS2_32.dll`, `socket`, `connect` and
  `ioctlsocket` in that bundled DLL. `cv2.pyd` itself had no direct network DLL dependency.
- Exact Python-package audit for only NumPy 2.5.2 and opencv-python-headless 5.0.0.93 reported no
  known vulnerability. A CycloneDX Windows environment SBOM was generated with SHA-256
  `0f072d948946ea513e3cf9a986a88b54b86c0b97afde84ab1a4af48ca4950515`; the extracted Linux-wheel
  SBOM SHA-256 is `44a57a39346ca61cc47c56bacaa196f927b9d5f3a144f1848e0be24f7cba20ff`.
- Grype 0.117.0 was acquired at image digest
  `sha256:ddf9e9f204049f3a4a0955ef70873cabab6a31432125ad4f20a490b54950a253`, but two bounded database
  update attempts ended in TLS handshake timeout. Native-library vulnerability disposition is
  therefore `NOT_VERIFIED`, not PASS.
- Linux successful execution under `--network none` proves the harness did not require egress.
  Windows native scanning proves the distributed wheel contains network-capable code even though the
  bounded remap harness did not call it. A full process-level Windows egress capture was not used to
  erase this closure finding.

## Repairs and next candidate

- `P2-M4-R02`: replace NumPy 2.5-incompatible two-dimensional `np.cross` in the negative-control
  helper with the equivalent explicit determinant. No threshold or fixture changed.
- `P2-M4-R03`: stop placing native Python extensions on a Docker Desktop non-executable tmpfs. New
  ephemeral writable container layers retained `--network none` and read-only inputs.

The next bounded candidate should source-build OpenCV 5.0.0 with only the minimum `core/imgproc`
closure and a narrow first-party binding. It requires a new preregistered candidate ID, exact build
toolchain, reproducibility, license/SBOM/vulnerability and Windows/Linux zero-egress evidence. M3's
OpenCV 3.4.11 artifact remains unavailable to M4, and T05 stays blocked.
