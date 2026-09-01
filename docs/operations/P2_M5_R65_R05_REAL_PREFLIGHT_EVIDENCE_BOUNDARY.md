# P2-M5-R65-R05 — real durable-preflight evidence boundary

`STATUS: EXECUTION_READY`

## Trigger

The existing R65 transport test creates an isolated temporary project and
intentionally advances only synthetic counters. It validates orchestration and
fresh-process verification, but cannot prove the required zero-impact
end-to-end preflight against the formal CAL-REQ-005 durable chain.

## Repair

R65 now explicitly distinguishes that non-authoritative harness from the
formal preflight. The formal preflight remains required before dispatch and
must resolve exact task-scoped staging, registry, receipt, runtime, model,
zero-egress, real M3 executor and terminal-recovery authorities while leaving
the formal call, raw-capacity and ordinal ledger unchanged.

## Scope boundary

This repair changes only governance and test naming. It does not read private
inputs, discover private roots, alter the legacy overlay, mutate a ledger,
call image generation, decode, M3, QA, Provider, runtime or model, or change
schema, migration, OpenAPI, policy, resources, QuestionBank or M6 state.

## Exit condition

Only a real, zero-image and zero-ordinal preflight with every exact authority
proven may close this repair and permit the separately authorized one-call
CAL-REQ-005 dispatch. Missing authority remains fail closed.
