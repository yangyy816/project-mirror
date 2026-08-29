# P2-M5-R50 — ImageGen data-URL custody bridge

## Task contract

```text
BOOTSTRAP_STATUS: OK
TASK_ID: P2-M5-R50
OBJECTIVE: Implement ADR-053's strict built-in imagegen data-URL capture and terminal-overlay rollover without generation.
WHY_DELEGATED: NOT_DELEGATED; Principal executes after D0 acceptance because private custody and failure recovery are integrated.
SCOPE: One overlay module, one focused test module, and append-only R50 acceptance evidence.
ALLOWED_FILES_OR_MODULES: services/api/src/mirror_api/synthetic_dataset/private_execution_overlay.py; services/api/tests/test_private_execution_overlay.py; P2-M5 R50/D0 acceptance tails.
FORBIDDEN_SCOPE: imagegen/Provider/Vision calls; lost-output search; decode/QA/admission; schema/migration/OpenAPI/dependency/model/workflow/M6 changes; private bytes in Git.
DEPENDENCIES: ADR-053 and CC-P2-M5-05-D0 Principal acceptance.
INPUTS_AND_ASSUMPTIONS: Existing R49 controller and synthetic byte fixtures; no private input is required for implementation tests.
ACCEPTANCE_CRITERIA: Direct-path behavior preserved; strict data URL capture, mandatory sidecar, crash recovery and cross-root rollover pass; exact 30/30/61/3 and CAL-REQ-003 preserved; zero generation/decode/private leakage.
VALIDATION_COMMANDS: Ruff format/check; strict mypy; focused overlay pytest; full API/Worker pytest; pnpm check; contract drift; git diff/source/private scans; same-SHA three-job CI and eight artifact inspection.
RECOMMENDED_AGENT: Principal or pm_terra_high_worker only after frozen D0 contract.
RECOMMENDED_MODEL_TIER: Terra High for implementation; Sol High for final review.
OUTPUT_FORMAT: Standard bounded-task report plus exact SHA/CI/artifact/security/final-review evidence.
ESCALATION_CONDITION: Any architecture/schema/public-contract/security-boundary change, unbounded data URL, missing project-local custody, counter rewrite, CAL-REQ-002 retry/refund, or image generation requirement.
```

## Mandatory implementation assertions

- No plaintext `data:image/` value is written to event, state, receipt, record, exception or log.
- Encoded length is rejected before Base64 decoding when it cannot fit the frozen decoded-byte ceiling.
- Base64 uses strict validation and accepts no whitespace, alternate alphabet, URL encoding or extra MIME parameters.
- PNG/JPEG/WebP declared MIME and magic must agree.
- Predetermined `staging/<opaque-output-id>.raw` and capture sidecar use create-new-or-verify-exact semantics.
- Capture sidecar is verified by the final registration Gate; missing/tampered sidecar keeps decode closed.
- `record_output_returned`, attempt binding and final commit can resume from exact partial writes with no duplicate counters.
- New rollover root is project-local, create-new, cross-root bound, and derived only from a verified terminal predecessor.
- The predecessor remains terminal; `CAL-REQ-002` cannot be prepared in the new root.
- Tests use only inline synthetic non-face bytes and must not call an image decoder or imagegen.

## Required negative cases

- invalid scheme/MIME/parameters/whitespace/newline/padding/alphabet/empty payload;
- encoded and decoded byte overflow;
- MIME/magic mismatch and unknown magic;
- existing different staging bytes or sidecar, symlink/reparse and root escape;
- crash after returned counter, binding, attempt, staging, capture, record, registration and transition partial writes;
- wrong action/controller/data-URL digest, tampered predecessor and non-terminal rollover;
- caller-supplied counter/ordinal substitution and retry of `CAL-REQ-002`.

## Gate boundary

R50 PASS is only implementation evidence. It does not authorize `CAL-REQ-003`, generation, M5 technical/MVR Gate, M6,
QuestionBank release, production Provider/geometry or real-user processing. Principal acceptance after exact-SHA Gates is
mandatory.
