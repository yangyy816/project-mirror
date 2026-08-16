# P2-M2-V01 Codex Native Synthetic Source Validation

## Result

`P2_M2_V01: PASS`

On 2026-08-16, the Principal executed the owner-authorized, operator-assisted offline source path
defined by ADR-026. Four versioned PromptTemplate categories produced two clearly adult,
synthetic-only images each. All eight outputs passed bounded admission into the private synthetic
raw namespace. This result validates source-to-raw admission only; it is not M3 normalization or
QA evidence and does not establish QuestionBank coverage.

## Bounded execution evidence

| Fact                    | Result                   |
| ----------------------- | ------------------------ |
| Requested images        | 8                        |
| Images admitted         | 8                        |
| Attempts used / maximum | 8 / 12                   |
| Per-item retry ceiling  | 1; no retry used         |
| Concurrency ceiling     | 1; generation was serial |
| Source kind             | `CODEX_NATIVE_IMAGEGEN`  |
| Provenance level        | `PROVENANCE_ONLY`        |
| Cost mode               | `REQUEST_COUNT_ONLY`     |
| Production Provider     | `NOT_CONFIGURED`         |
| Production generation   | `FAIL_CLOSED`            |

The requested output was `1024×1024 PNG`. The native tool returned `1254×1254 PNG` for every
item. Admission did not resample or normalize the files. It accepted the bounded single-frame PNGs
because their aspect ratio matched the specification and explicitly recorded
`dimensions_match_requested=false`, preserving both requested and observed facts.

The source SHA-256 values were recomputed from all eight private staging files and matched the
admission evidence. Model identifier, model snapshot/version, Provider request identifier, seed,
usage and Provider cost were unavailable and remain `NULL`; none was inferred or fabricated.

## Privacy and artifact boundary

- No named identity, real-person reference, scraped/social-media image, celebrity reference, user
  data or production credential was used.
- Source images, Prompt text, generation plan, private paths and raw-storage objects remain under
  ignored local private storage and are not committed.
- Admission required an explicit private staging source root and rejects resolved paths or symlinks
  outside it.
- The committed redacted manifest is `P2_M2_V01_REDACTED_MANIFEST.json`. It contains only bounded
  aggregate facts, item references, checksums and byte sizes; it excludes Prompt text, paths,
  storage references/object keys and image bytes.
- Codex native generation remains an offline operator workflow. No
  `CodexImageGenerationProvider`, runtime config option, browser automation or unofficial endpoint
  was added.

## Gate interpretation

`P2_M2_CODEX_NATIVE_SOURCE_GATE: PASS`

`P2_M2_PROGRAMMATIC_PROVIDER_GATE: DEFERRED_EXTERNAL_PRODUCTION_DEPENDENCY`

`P2_M2_PRODUCTION_PROVIDER_APPROVAL: NOT_GRANTED`

V01 removes the development/research source blocker under the Project Owner change control. It
does not close `PRODUCTION-BLOCKER-IMAGEGEN-PROVIDER`; the final M2 Gate still requires the complete
deterministic core and same-SHA CI evidence.
