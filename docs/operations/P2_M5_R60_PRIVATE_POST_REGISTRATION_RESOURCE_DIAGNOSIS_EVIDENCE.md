# P2-M5-R60 resource diagnosis evidence

`STATUS: DIAGNOSIS_COMPLETE_PRINCIPAL_DECISION_REQUIRED`

## Reproduction

The deterministic synthetic-only success-chain fixture was profiled in a
Git-ignored task-owned custody root. It executes no Provider, imagegen,
decode, Vision/M3, runtime, model, database, or production operation.

## Observation

After completed operation results 1 through 5, traced current allocation grew
from approximately 25 MB to 58 MB, with a monotonic per-operation increase.
The full suite independently showed unbounded process growth in the same
success-chain path.

The diagnostic intentionally raised after operation 5. The resulting
create-once conflict is a consequence of interrupting after the result record
but before the surrounding transition completes; it is not a product result.

## Disposition

The owning path is the CC06 post-registration controller's repeated durable
operation/transition lifecycle, not P2-M5-R59 builder-lock code or the
synthetic image fixture. A repair would need to alter or reframe persistence,
replay, and historical-evidence verification behavior. Those are security
and contract authority boundaries, so R60 does not implement a speculative
memory optimization.

`NEXT_ACTION: PRINCIPAL_DECISION_REQUIRED_FOR_CC06_DURABILITY_AND_REPLAY_REPAIR`
