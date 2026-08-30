# P2-M5-R54 — rollover empty-directory integrity repair

## Status and scope

`P2-M5-R54` is the minimum forward repair for the mandatory independent
security finding on the R53 candidate. R53 proved that `staging` and `records`
were plain directories, but its verifier did not prove that they contained
zero entries. Passing that verifier with an added entry would contradict the
R53 zero-work, exact-partial-recovery and tamper-fail-closed contract.

R54 changes only the existing v2 CAL-REQ-003 terminal-to-CAL-REQ-004 READY
rollover implementation, its synthetic tests, this contract and the matching
conditional true-EOF authority. The v1 rollover remains byte-for-byte
unchanged. R54 creates no generation call, raw output, image read, decode,
dimension read, QA, screening, admission, dispatch preparation or ordinal
consumption.

## Frozen empty-directory rule

Fresh creation, exact partial recovery and every successful
`verify_rollover_successor_v2()` call must prove that both successor work
directories contain zero entries. A file, directory, symlink, reparse point or
any other returned directory entry is a mandatory fail-closed result.

The historical R53 phrase "the controller never enumerates them" forbids a
directory inventory and exposure of private entry metadata; it does not forbid
the zero-entry proof required by the same contract. R54 permits exactly one
bounded first-entry existence probe per check. The probe:

- opens and revalidates the same plain directory through the existing
  no-follow/handle-binding boundary;
- stops after determining whether a first entry exists;
- never reads entry bytes;
- application code never reads `DirEntry.name`, returns, logs or includes the
  entry name in an error;
- returns only pass-for-zero or the fixed
  `V2_ROLLOVER_SUCCESSOR_DIRECTORY_NOT_EMPTY` failure;
- converts an operating-system inspection failure to the fixed
  `V2_ROLLOVER_SUCCESSOR_DIRECTORY_INSPECTION_FAILED` failure.

The rollover checks both directories before committing sequence zero. The
verifier checks both once before reading the intent and again immediately
before returning, so prepopulation and an entry introduced during verification
cannot receive a passing result while it remains present. This is an integrity
check, not permission to discover or clean unknown private data.

## Recovery and tamper behavior

- A fresh successor begins with two empty work directories.
- An exact partial root is recoverable only while both directories are empty.
- A prepopulated partial root fails before event, state or receipt sequence zero
  is created or verified as successful.
- An already materialized successor with an added work entry fails fresh
  verification.
- An entry introduced between directory creation and the first probe fails
  before sequence-zero commit.
- An entry introduced after the verifier's first probe but before its final
  return fails the final probe.
- The controller does not delete, quarantine, rename or inspect the added
  entry. Custody and cleanup remain Principal responsibilities outside R54.

## Validation and acceptance

R54 must pass focused rollover/transport/authority tests, Ruff format and
lint, strict mypy, the canonical-LF complete API/worker regression and the
standard same-SHA CI and eight-artifact content checks. Independent
Security/Privacy and Sol High review plus Principal inspection are mandatory.

Before all R54 gates and Principal acceptance, R53 remains unaccepted,
`CAL-REQ-003` remains terminal and no-retry, and `CAL-REQ-004` remains
unprepared, unconsumed and unauthorized. After all gates and Principal
acceptance, the unique successor remains one exact `EXECUTE_CAL_REQ_004` call;
no post-acceptance status commit is required.
