# P2-M5-R61 — streamed post-registration verification

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R61`
- `BASELINE_SHA: 790f71445ed8563e25799be4a2b60cbc1626a749`
- `AUTHORITY: ADR-054 + ADR-056`

## Objective

Replace retained historical post-state mappings with a bounded, streamed
anchor index while preserving the exact verified receipt, plan, result,
normalization, attempt, failure and checkpoint relationships.

## Allowed files

- `services/api/src/mirror_api/synthetic_dataset/private_imagegen_post_registration.py`;
- `services/api/tests/test_private_imagegen_post_registration.py`;
- this contract and redacted evidence.

## Non-negotiable rules

No external operation may run without the same chain/tip preflight. Terminal,
recovery and successor verification remain complete. No schema, migration,
public API, Provider, model/runtime, source, ledger, CAL-REQ, policy, Prompt,
dependency, imagegen, decode, Vision/M3 or production behavior changes.

## Acceptance

- all existing tamper/replay/fresh-process tests retain their semantics;
- a success chain no longer retains whole historical post mappings;
- resource evidence is bounded and redacted;
- focused tests, Ruff, mypy, complete Linux CI and independent review pass.
