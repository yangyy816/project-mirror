# P2-M5-R46 — R45 CI Platform Typing Repair

## Task contract

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R46`
- `OBJECTIVE`: close the deterministic Linux strict-mypy failure from R45 without changing its runtime behavior,
  accepted CC05-A fallback, state machine, resource counters, public contract, private state or `CAL-REQ-002`.
- `DEPENDENCIES`: rejected R45 candidate `2ed324237dec074b9bd3412b4458fb715da95899`, same-SHA run
  `33249622650`, and its exact `quality-and-integration` failure log.
- `FORBIDDEN_SCOPE`: image generation, private input discovery or access, Prompt export, ordinal consumption,
  decode, QA, screening, admission, schema, migration, API, dependency, model, workflow, MEMORY and Gate changes.

## Deterministic failure evidence

The R45 run passed Ruff, secret scan and Docker validation, then failed before PostgreSQL/tests at Linux strict mypy.
The eleven diagnostics were platform-stub differences only: Linux regards POSIX flags as native integers while its
`ctypes`, `msvcrt` and `os` stubs do not expose Windows-only members. Rerunning that attempt cannot change the result,
so R45 remains rejected and no downstream artifact or review Gate is inferred from the partial run.

## Frozen repair behavior

- POSIX `O_DIRECTORY` and `O_NOFOLLOW` are obtained with runtime lookup plus exact integer type guards. Missing
  capability still returns `GENERATED_ARTIFACT_SAFE_OPEN_UNAVAILABLE` before source access.
- Windows `WinDLL`, `open_osfhandle` and `O_BINARY` are likewise obtained through runtime capability lookup and
  validated before use. The existing `CreateFileW`, no-reparse, no-write/delete-sharing and handle ownership
  semantics are unchanged.
- Both the native Windows mypy target and an explicit Linux mypy target must pass on the same source.
- The R45 source/root TOCTOU repair, exact four-field Prompt parser, automatic registration failure terminal,
  descriptor/handle cleanup, retry `0`, concurrency `1` and zero private/resource effects remain unchanged.

## Required evidence before acceptance

R46 requires focused tests, Windows and Linux strict mypy, the complete local quality matrix, a new same-SHA
three-job CI run, all eight artifact-content checks, independent Security/Privacy/License/Research review,
independent final review and Principal acceptance. Until then accepted CC05-A remains current, R43-Q01 remains
closed and `CAL-REQ-002` is not dispatched.

## Candidate status

- `P2_M5_R46_STATUS: READY_FOR_TRACKED_EVIDENCE`
- `P2_M5_R46_IMAGEGEN_CALLS: 0`
- `P2_M5_R46_ORDINALS_CONSUMED: 0`
- `P2_M5_R46_PRIVATE_ROOTS_CREATED: 0`
- `P2_M5_R46_PRIVATE_IMAGE_BYTES_READ_OR_WRITTEN: 0`
