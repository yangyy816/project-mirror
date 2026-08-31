# P2-M5-R60 — private post-registration resource diagnosis

## Bounded authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R60`
- `BASELINE_SHA: 817b51f3ed5d7f7255405b34b9578b64e01517c2`
- `CHANGE_CLASS: BOUNDED_RESOURCE_DIAGNOSIS`
- `TRIGGER: reproducible resource growth in test_success_chain_preserves_ledger_and_redacts_private_fixture`

## Objective

Determine the exact bounded cause of the resource growth in the deterministic,
synthetic-only post-registration success-chain test. Preserve every existing
durability, replay, failure-classification, lease, and evidence invariant.

## Allowed scope

- `services/api/tests/test_private_imagegen_post_registration.py`;
- `services/api/src/mirror_api/synthetic_dataset/private_imagegen_post_registration.py`;
- this diagnosis contract and one redacted evidence record.

## Forbidden scope

No schema, migration, public API, OpenAPI, Provider, dependency, Prompt,
policy, model/runtime, source-base, Docker, QuestionBank, resource ledger,
imagegen, decode, Vision/M3, CAL-REQ, or production change is authorized.

## Stop rule

If diagnosis requires changing the persisted evidence schema, external
capability authority, replay semantics, lease semantics, failure taxonomy, or
security boundary, R60 stops with `PRINCIPAL_DECISION_REQUIRED`; it does not
implement a speculative optimization.

## Acceptance

- a deterministic reproduction identifies the owning allocation/path class;
- a redacted result distinguishes fixture-only, controller-only, or combined
  cause without private bytes/locators;
- focused tests, Ruff, mypy, and diff check run;
- no external or sensitive operation occurs.
