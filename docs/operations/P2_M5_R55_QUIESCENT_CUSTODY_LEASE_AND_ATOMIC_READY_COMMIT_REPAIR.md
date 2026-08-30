# P2-M5-R55 — quiescent custody lease and atomic READY commit repair

## Status and scope

`P2-M5-R55` is the minimum forward repair authorized by Owner decision
`OD-P2-M5-R55-QUIESCENT-CUSTODY-001` for the mandatory Sol High finding on the
R54 candidate. R54's sequential directory probes cannot make a two-directory
snapshot atomic with the READY commit or function return. R55 therefore does
not add another probe. It makes every Project Mirror legal writer cooperate on
one cross-process lease, holds that lease through the final zero-work checks
and durable READY commit, and rejects stale READY handles at dispatch.

R55 is limited to the non-user, synthetic-only P2-M5 first-wave private
custody path. It creates no generation call, consumes no ordinal, reads no
image bytes, performs no decode or QA, and changes no policy, epoch, Provider,
model, schema, migration, OpenAPI, dependency, workflow, QuestionBank or M6
state.

## Frozen threat model

The trusted computing base is the current Owner Windows account plus the
Project-controlled Principal runtime. Project-controlled processes and
accidental concurrent writers are in scope and must use the shared lease.
An arbitrary hostile process running under the same OS credential and a
same-credential host compromise are out of scope for this first-wave
synthetic-only task.

The lease is cooperative concurrency control, not an authorization boundary.
It must never be described as defeating the active same-credential writer
counterexample preserved by Accepted ADR-048. This boundary does not apply to
real-user images, User Assets, uploads, SelfState, DesiredDelta, production,
public release, credentials or other sensitive data; those future surfaces
continue to require stronger account, ACL, service or object-storage
isolation.

## Quiescence lease

The frozen lease version is
`p2-m5-private-overlay-quiescence-lease-v1`.

- The persistent lease file is a fixed regular, non-reparse control file in
  the v2 successor root, never in `staging` or `records`.
- The successor root remains inside the project-local Git-ignored private
  namespace, and the lease path is containment checked without entering
  tracked evidence, errors or logs.
- Windows uses an OS-level exclusive byte-range lock on an active handle;
  POSIX uses `fcntl.flock` on an active file descriptor. No dependency,
  service, SDK or network call is introduced.
- Acquisition is nonblocking with a bounded monotonic timeout. Contention
  fails closed as `QUIESCENCE_LEASE_BUSY`.
- The file may persist, but ownership exists only while the descriptor or
  handle is active. Process exit releases the OS lock. No caller deletes a
  lock owned by another process.
- Same-thread nested Project Mirror operations reuse the already-held lease;
  other threads and processes remain excluded.

## Legal mutator coverage

All Project Mirror entry points which can mutate a v2 successor must acquire
the same lease before reading the transition tip and hold it until their
durable mutation and immediate verification finish. Coverage includes:

- READY preparation, ordinal consumption, dispatch failure and output-return
  transitions;
- output-registration attempt, staging write, capture sidecar, output record,
  registration receipt, registration failure and registration commit;
- capture-session handle and completion evidence written by the no-echo
  runner; and
- v2 successor creation/recovery and verification.

The capture module is included because it is a proved legal writer of overlay
control state, `staging`, `records` and completion evidence. Lower-level v2
mutation without a held lease is rejected or is reachable only through one of
the guarded entry points. V1 rollover bytes and semantics remain unchanged.

## Atomic READY commit

`rollover_terminal_overlay_v2()` performs one cooperative verify-and-commit
operation:

1. validate the exact CAL-REQ-003 predecessor receipt, state, event and
   controller pins;
2. deterministically establish or exact-verify the parent-level rollover
   intent, then create or exact-recover its one bound successor control root;
   this preparatory step creates no READY authority and writes no payload;
3. validate that root and create/open its fixed lease file without following a
   reparse node, then acquire the exclusive lease;
4. revalidate the predecessor, intent and private-parent binding under the
   lease;
5. create or exact-recover the plain work directories;
6. verify both `staging` and `records` are zero-work;
7. build the canonical READY event/state/receipt bound to the predecessor
   digests, controller, CAL-REQ-004, unchanged counters, lease version and
   deterministic successor generation;
8. create-new or exact-recover the control chain, flush/close/reread it and
   bind the returned handle to the exact receipt and state digests;
9. while still holding the same lease, revalidate the predecessor, intent,
   work-directory postconditions and durable READY receipt; and
10. release the lease only after the verified handle is fully constructed.

The authoritative control receipt remains in the successor control root and
is not a business payload record. `records` therefore remains a true zero-work
directory at READY.

## Stale-handle protection

Every returned `OverlayHandle` binds the exact receipt and state digests.
CAL-REQ-004 preparation must present the exact READY state digest. Under the
lease, the controller re-reads that receipt, proves it is the current tip and
performs the next append-only transition against the exact predecessor digest.
If another legal process has already advanced the state, the old handle is
stale and fails closed; it cannot prepare, consume or replay the ordinal.

The no-echo capture session similarly binds the exact consumed receipt/state
and holds the same lease from session validation through registration or
immutable failure completion. A completion receipt cannot make a stale
session current.

## Required tests and acceptance

R55 must preserve existing v1 and v2 pinning, recovery, reparse, tamper and
zero-work tests, and add deterministic coverage for:

- prefilled `staging` and `records`;
- cooperative writes attempted at each final-probe/commit/return boundary;
- verifier/writer and verifier/verifier concurrency without a fork;
- lease busy, release and crashed-holder recovery;
- lock path escape, reparse and invalid-node rejection;
- stale READY handles, exact digest mismatch, concurrent prepare and replay;
- all legal v2 mutators refusing to bypass the lease;
- fixed errors which expose neither a directory entry name nor a private
  locator; and
- at least one live subprocess lease contender on Windows and one on Linux.

The direct same-credential writer counterexample remains valid
`OUTSIDE_GUARANTEE_REQUIRES_EXCLUSIVE_CUSTODY` evidence and is not an
implementation PASS.

Acceptance requires Ruff format/check, strict mypy, all R52-R55 focused tests,
Windows live multi-process evidence, canonical-LF Linux focused and complete
API/Worker regression, scoped Prettier, diff/allowlist/leak/authority/resource
checks, new same-SHA three-job CI, all eight artifact-family content checks,
independent Security/Privacy/License/Research review, Sol High final review and
Principal acceptance.

## Local validation evidence

- Windows R52-R55 focused suite: `144 passed`, `3` expected POSIX-only skips,
  `0` failure/error in `770.41s`; live thread/process contention, crashed-holder
  release and stale-handle probes passed.
- Canonical-LF Linux focused suite: `147 passed`, `1 warning`, `0` skip/failure
  in `44.93s`; the live subprocess lease contender ran on Linux.
- Canonical-LF Linux complete API/Worker regression: `719 passed`, `160 skipped`,
  `34 warnings`, `0` failure/error in `61.54s`; the isolated PostgreSQL schema
  reached `0014_m5_eval_authority` and Redis/Celery remained available.
- The first two Linux attempts exposed missing read-only repository mounts in
  the disposable validation container, not assertion or product failures. The
  complete repository view was then mounted read-only and the exact suites
  above passed. The task-owned Docker project and canonical-LF validation
  checkout were retired after evidence capture; no private payload was created.

Until every Gate passes, R52-R55 remain unaccepted, CAL-REQ-003 remains
terminal and no-retry, and CAL-REQ-004 remains unconsumed and unauthorized.
After Principal acceptance the unique successor is one exact
`EXECUTE_CAL_REQ_004` call; no post-acceptance status commit or R56 state-sync
repair is required.
