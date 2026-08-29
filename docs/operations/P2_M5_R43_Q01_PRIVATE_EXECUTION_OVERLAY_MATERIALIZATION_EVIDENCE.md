# P2-M5-R43-Q01 — Private Execution Overlay Materialization Evidence

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R43-Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION`
- `PREDECESSOR_ACCEPTED_AUTHORITY: 7404be4d4ad807b5f3559b869fd02d0bd4c5948a`
- `CHANGE_CLASS: PRINCIPAL_PRIVATE_OVERLAY_MATERIALIZATION_ZERO_GENERATION`
- `STATUS: LOCAL_CANDIDATE_PENDING_TRACKED_GATES`

## Outcome

The accepted CC05-C exact task-scoped receipt was consumed through its fixed handoff only. Receipt-directed traversal
followed ten bounded UTF-8 text documents and matched all eight expected private control digests. It did not list a
directory, follow a reparse point, search another root, read an image or model, or call a Provider.

The Principal rendered the accepted four-field private Prompt contract for `CAL-REQ-002` in memory and immediately
discarded the rendered value. No Prompt text or rendered digest was printed, persisted in the overlay, included in
this evidence, placed in command output, or exposed to a reviewer.

## Recoverable project custody

The materialization tool, create-new intent, sequence-zero overlay and durable handle are retained together in the
project's dedicated Git-ignored private namespace. They are not left only in Agent memory, system Temp, a scratchpad
or invisible tool state. The tracked evidence contains no private locator or host path.

The create-new overlay has these allowlisted facts:

- opaque overlay output ID: `P2M5-R43-Q01-E4-b46b12fe2ebf421da1d8fc66f16ad530`;
- controller SHA-256: `2e0d3fd4c10535bae366273ac6775eb198d3490beac9bb89a4db3d1f5b388d7a`;
- materialization intent SHA-256: `116db6f61ec1da36d1e08ecf1b2e43d0653e20ebb8ad565b4e9963a12d7c2a4b`;
- durable private handle SHA-256: `224d41954db49da6ff3a19422a29a8fa93e3c2e8e6e54a980d1a2761afd9d80b`;
- sequence-zero receipt SHA-256: `8d7987beecb2b4491a2d15b395198dcb70d00c2fc909fd21feee579922830398`;
- sequence-zero state SHA-256: `7a1240721d997fa8d3d261c8b7b52ce300eca27e676eba9e6d2a89d183280af4`;
- phase: `READY`;
- sequence: `0`;
- `decode_authorized: false`;
- `hard_stop: false`; and
- fresh-process exact-handle recovery: `PASS`.

## Preserved resource authority

The initialized state exactly preserves:

- request calls / requested outputs / returned outputs / raw outputs: `1/1/1/1`;
- failed / rejected / admitted: `0/0/0`;
- remaining formal calls / formal raw capacity / global native output capacity: `31/31/62`;
- global native outputs consumed: `2`;
- active calls: `0`;
- `CAL-REQ-001: CONSUMED_FAILED_NO_RETRY`;
- next unused ordinal: `CAL-REQ-002`; and
- `CAL-REQ-002: NOT_CONSUMED`.

Q01 performed zero generation or Provider calls, consumed zero ordinals, created zero raw outputs, read zero image
bytes and performed zero decode, QA, screening or admission operations. It does not itself authorize dispatch.

## Tracked redaction and phase boundary

The machine-readable companion contains only opaque IDs, digests, counters, versioned statuses and allowlisted
outcomes. It contains no Prompt, private locator, host path, seed, image byte, object key, signed URL, Provider raw
payload or credential.

There is no public API, schema, migration, dependency, model artifact or workflow change. P2-M5 technical Gate and
P2-MVR-v1 remain `NOT_EVALUATED`; P2-M6, QuestionBank release, production geometry/Provider and real-user facial
processing remain closed.

## Acceptance conditions

1. The machine-readable evidence matches this record and its file SHA-256 is bound in both current-state mirrors.
2. Canonical Acceptance and Execution Protocol true-EOF blocks retain the complete CC05-C predecessor keyset and
   match in key order and values.
3. Focused tests, Ruff, strict mypy, changed-path and private-leak checks pass locally.
4. A normal non-force push is followed by exact-SHA three-job CI, all eight artifact-family content checks,
   independent Security/Privacy/License/Research review, Sol High final review and Principal acceptance.
5. Until every Gate passes, `CAL-REQ-002` remains unconsumed and no image generation is allowed.

After acceptance, the next bounded action is `EXECUTE_CAL_REQ_002`; it is not part of Q01.

`P2_M5_STATE: EXECUTING`

`P2_M5_TECHNICAL_GATE: NOT_EVALUATED`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED`
