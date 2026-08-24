# P2-M5-R29 Pre-registration Order Repair

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R29`
- `PREDECESSOR_ACCEPTED_AUTHORITY: f88ccddd9ad182046f52dbf42298d4f8702537ba`
- `FAILURE_EVENT: CAL-REQ-001_OUTPUT_DECODE_BEFORE_OUTPUT_REGISTRATION`
- `R29_AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`

## Bounded repair packet

- `OBJECTIVE`: preserve the consumed rejected `CAL-REQ-001` and its completed exact-target cleanup, then freeze a corrected future-output sequence: exact native handle → create-new staging copy → SHA-256/type/byte-size registration in the private registry → decode/dimension/QA use.
- `SCOPE`: this repair record and canonical/mirror true-EOF status tails only.
- `ALLOWED_FILES_OR_MODULES`: this file, `docs/operations/P2_M5_ACCEPTANCE.md`, and `docs/operations/P2_M5_EXECUTION_PROTOCOL.md` only.
- `FORBIDDEN_SCOPE`: no history rewrite, retry, replacement, ordinal reuse, private path/locator/Prompt/image byte publication, image generation, QA, screening, identity, cohort, holdout, transform, MVR, M6, schema, migration, API, CI, dependency, model, resource-envelope, MEMORY, shared-summary, or P2-M7 change.
- `PRESERVED_EXECUTION_FACTS`: one `CAL-REQ-001` call and one raw output; the output was rejected before admission for `OUTPUT_DECODE_BEFORE_OUTPUT_REGISTRATION`; its exact SHA-256, byte count, opaque ID, request/output facts, and completed cleanup remain in the Git-external Principal registry. No retry occurred.
- `CORRECTED_FUTURE_SEQUENCE`: no decode, image library load, dimension read, vision, QA, or reviewer input may occur until the exact returned bytes have been create-new staged, SHA-256 hashed, magic-typed, byte-sized, and durably registered with the ordinal/source/specification/assignment binding.
- `ACCEPTANCE_CRITERIA`: exactly three documentation paths; full canonical/mirror key/value/order equality; all governed-key final occurrences in the R29 true-EOF tails; no private leakage; strict MR01 history preserved; counts accurately reflect one consumed rejected raw output; future execution remains disabled until all R29 gates and Principal acceptance.

R29 changes no policy or ceiling. After acceptance, it may authorize only the next never-used ordinal, `CAL-REQ-002`, under the corrected sequence and existing serial/no-retry envelope. It does not restore or re-use `CAL-REQ-001`.
