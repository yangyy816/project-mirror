# P2-M5-R63 — Windows native FFI binding repair

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R63`
- `BASELINE_SHA: 307147f5395a3746c5976ffce8d9fcfac12c1f4d`
- `STATUS: EXECUTING_LOCAL_ONLY`

## Objective

Remove per-call Windows ctypes type construction, DLL loading and function
signature assignment from the private overlay's descriptor-bound filesystem
helpers. In the same bounded resource repair, use ADR-056's already-permitted
per-verification receipt-tip index so terminal evidence does not repeatedly
rescan an already chain-verified immutable prefix. Both changes preserve the
existing no-follow, reparse, handle, lease, receipt and controller behavior.

## Allowed scope

- `private_execution_overlay.py` Windows-native type/binding initialization
  and its direct call sites;
- `private_imagegen_post_registration.py` only for an invocation-local index
  of receipts already verified from the current immutable chain;
- deterministic binding-identity and Windows resource tests; and
- this redacted contract and evidence.

## Forbidden scope

- post-registration controller state/recovery semantics or persisted payloads;
- receipt, ledger, replay, capability, Provider, policy, model, schema,
  migration, OpenAPI, CI, imagegen, decode, M3, admission and release work;
- private locators, bytes, Prompts, credentials or runtime/model artifacts.

## Acceptance

- all Windows native ctypes structures and signature assignments used by the
  affected filesystem and lease helpers are module-level and singleton-bound;
- initialization is thread-safe, initializes once per process and fails before
  caching a partial binding;
- no affected hot path loads a DLL or mutates `argtypes`/`restype`;
- descriptor-bound behavior and existing rejection reasons remain unchanged;
- the 20-operation / 478-landmark chain and complete focused controller
  regression complete naturally with bounded resources; and
- the indexed verifier rejects the same missing, substituted, stale, duplicate
  and non-canonical records as the unindexed verifier;
- normal local, canonical-LF and remote gates pass before any commit.

## Current disposition

R63 has no candidate, commit or acceptance claim until both deterministic
native-binding and terminal-evidence equivalence/resource gates pass.
