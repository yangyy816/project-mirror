# Pillow Decoder Adoption Record

## Status

`THIRD_PARTY_APPROVED_FOR_P1_M4_RUNTIME` — 2026-08-16

## Scope and purpose

Pillow is approved only as the in-process decoder/encoder used by P1-M4 `image-sanitizer-v1` for strict, single-frame JPEG/PNG/WebP input and canonical JPEG output. It is not a Vision Provider, face analyzer, image editor, arbitrary-format conversion service, URL fetcher or authority for Asset/Job state.

Application code must pass an explicit Pillow format allowlist and independently enforce magic/MIME, byte, edge, pixel, frame, decompression-bomb and output checks. Other plugins reported by the wheel are not approved capabilities.

## Upstream and package evidence

- Package: `pillow==12.3.0`
- Registry: `https://pypi.org/project/pillow/12.3.0/`
- Source: `https://github.com/python-pillow/Pillow`
- Documentation: `https://pillow.readthedocs.io`
- Release upload time reported by PyPI: 2026-07-01
- Requires Python: `>=3.10`; Project Mirror uses CPython 3.13
- Core `Requires-Dist`: none. All reported Python dependencies are gated by optional extras and are not installed.
- Top-level license expression in PyPI and both wheel METADATA files: `MIT-CMU`
- Package status: not yanked

Reviewed wheels and exact PyPI-matching SHA-256:

- `pillow-12.3.0-cp313-cp313-win_amd64.whl`: `1cca606cd25738df4ed873d5ad46bbdb3d83b5cbca291f6b4ff13a4df6b0bbe8`
- `pillow-12.3.0-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`: `0847a763afefb695bc912d7c131e7e0632d4edc1d8698f58ddabec8e46b8b6d3`

Both wheels contain `pillow-12.3.0.dist-info/licenses/LICENSE`. The full bundled notice was inspected rather than relying only on the top-level classifier. It contains Pillow/PIL terms and notices for the native libraries bundled by each wheel. The Linux notice includes AOM, Brotli, Bzip2, Dav1d, FreeType, HarfBuzz, LCMS2, libavif, libjpeg, liblzma, libpng, libtiff, libwebp, libyuv, OpenJPEG, Raqm, Tcl/Tk, XAU/XCB/XDMCP, zlib and zstd. The Windows notice includes the corresponding compiled dependency versions, including FreeType 2.14.3, LCMS2 2.19.1, libavif 1.4.2, libjpeg-turbo 3.1.4.1, libpng 1.6.58, libwebp 1.6.0, OpenJPEG 2.5.4, libtiff 4.7.1, XZ 5.8.3 and zlib-ng 2.3.3.

The reviewed terms are permissive for the intended commercial runtime. Redistribution must retain the complete wheel license/notices and required acknowledgements; Project Mirror's license inventory must not collapse these bundled notices to the single `MIT-CMU` label. Names of upstream authors/projects may not be used for endorsement. This engineering approval is not a substitute for later distribution-channel legal review.

## Platform and feature evidence

The Windows wheel was installed with `--no-index --no-deps` into a clean Python 3.13 venv. The manylinux wheel was installed with the same flags into an ephemeral `python:3.13.1-slim` container with `--network none`.

Both environments loaded Pillow core 12.3.0 and the required JPEG, PNG/ZLIB and WebP support. Reported native versions included libjpeg-turbo 3.1.4.1, WebP 1.6.0 and zlib-ng 2.3.3; Linux was compatible with the current slim runtime. The wheel also exposes many unapproved decoders, so the sanitizer must invoke `Image.open(..., formats=["JPEG", "PNG", "WEBP"])` and reject any decoder-reported format outside that set.

The Windows wheel exposes compiled `.pyd` modules and the Linux wheel exposes compiled `.so` modules; this is a native parser attack surface. Worker resource limits, bounded input, single-frame enforcement, decompression-bomb handling, re-encoding and post-encode validation remain mandatory even though package installation succeeds.

## Vulnerability and network evidence

- Isolated path audit after upgrading only the temporary venv's bootstrap pip to `26.2.1`: `No known vulnerabilities found`.
- The initial audit findings were six advisories against venv bootstrap `pip 24.3.1`, not Pillow; they disappeared after the isolated tooling upgrade.
- The updated complete `requirements.lock` installed successfully from scratch in `python:3.13.1-slim`; `pip check` reported no broken requirements and the locked Linux Pillow feature smoke passed.
- Full pinned-lock `pip-audit --requirement requirements.lock --no-deps --strict` completed without a vulnerability finding.
- No core Python dependency or runtime network/telemetry requirement is declared by Pillow.
- Native bundled library advisories may not always be attributed to the Python package by `pip-audit`; exact wheel hashes, decoder allowlisting, container/SBOM evidence and recurring dependency review remain required.

## Controls and approval boundary

- Pin `pillow==12.3.0` in the reviewed lock; a version change requires a new hash/license/vulnerability/feature review.
- Import only the modules required for decode, EXIF orientation and encode. Do not call ImageShow, external viewers, shell tools, arbitrary plugins or URL handlers.
- Do not parse or trust input ICC profiles in `image-sanitizer-v1`; strip them and apply the ADR-019 assumed-sRGB policy.
- Never enable `LOAD_TRUNCATED_IMAGES`; truncated input fails closed.
- Convert Pillow warnings and exceptions to a stable allowlisted rejection taxonomy; never log raw exception text or image metadata.
- Keep production real-image ingestion disabled until the independent Legal/Security/Provider Gate passes.
- Preserve the package's complete LICENSE/notices in distribution evidence.

## Principal decision

`THIRD_PARTY_APPROVED`: Pillow 12.3.0 may be added as a pinned P1-M4 runtime dependency under the controls above. This approval does not authorize other image libraries, real user images, AI/face analysis or general-purpose image conversion.

## Phase 2 scope addendum

`APPROVE_FOR_P2` — 2026-08-16

The already pinned and reviewed Pillow 12.3.0 runtime may later be reused for P2 synthetic normalization without a version change. This expands purpose only; it does not authorize P2-M1 image processing or any new dependency. Future P2 normalization must explicitly enforce bounded decode, pixel/decompression-bomb defenses, orientation and colorspace normalization, format allowlisting, explicit ICC/EXIF/XMP/IPTC/comment sanitation, canonical re-encoding, a second decode and checksum verification. Re-saving alone is not evidence that all metadata was removed.

### P2-M4-T05 bounded transform extension

`APPROVED_FOR_PRIVATE_SYNTHETIC_M4` — 2026-08-18

The same pinned Pillow 12.3.0 runtime may decode an already checksum-bound canonical synthetic JPEG
to bounded RGB pixels and encode the bounded RGB result of the approved M4 geometry adapter with the
unchanged `image-sanitizer-v1` JPEG policy. The adapter must verify declared dimensions, byte/pixel
limits, single-frame JPEG shape, second decode and output checksum. Pillow does not perform the warp,
select landmarks, infer age/identity, accept arbitrary formats or become transform authority.

This is a purpose-only extension: no version, wheel, lockfile, native closure or distribution decision
changes. It remains private synthetic M4 research and does not authorize User Assets, real-user facial
processing, production editing, QuestionBank release or a general image-manipulation surface.
