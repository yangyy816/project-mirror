# P2-M5-R53 — CAL-REQ-004 READY rollover contract

## Status and scope

`P2-M5-R53` is a bounded, tracked repair for a private, terminal receipt rollover.
It adds a parallel v2 authority path only. The v1 terminal rollover constants,
functions, receipt semantics and callers remain unchanged.

`TERMINAL_ROLLOVER_CONTRACT_V2` is exactly
`p2-m5-cal-req-003-to-004-ready-rollover/v2`.

The v2 path may create or recover exactly one project-local, ignored successor
overlay after the strictly pinned terminal `CAL-REQ-003` failure. It performs no
generation, retry, output creation, image-byte read, decode, dimension read, QA,
screening, admission, preparation or consumption of `CAL-REQ-004`.

## V2 predecessor authority

The caller supplies only the predecessor receipt path, four digest/controller
pins, the project-local parent/root/output identifiers and one timestamp. It
cannot supply counters, ordinals, phase, reason, status or intent identifiers.

Before any intent or successor root is created, v2 requires all of the
following: receipt sequence six; terminal phase/event
`OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE`; reason
`IMAGEGEN_DATA_URL_HEADER_INVALID`; `CAL-REQ-003` current and `CAL-REQ-004`
next ordinal; hard stop; no decode; no output registration; native ImageGen
data-URL attempt binding; matching action/ordinal/output receipt bindings; and
the frozen 3/3/3/3 request/requested/returned/raw ledger with zero failed,
rejected and admitted identities, 29/29 formal capacity, 60/4 global capacity,
and no active call. The actual pin values remain private and are never tracked.

## Successor and recovery rules

`TERMINAL_ROLLOVER_CONTRACT_V2` and `ROLLOVER_INTENT_SCHEMA_V2` are distinct
from v1. The deterministic `ROLLOVER-V2-` intent identity derives from the v2
contract and pinned predecessor receipt digest. The exact intent binds all
predecessor authority, the derived ledger, controller, successor root/output,
project-local parent and timestamp. Its create mode is create-new or recover
exact partial root; conflicting replay, changed root/output/timestamp or second
fork fails closed.

The only valid successor is sequence zero, `READY`, `CAL-REQ-004`, unprepared
and unconsumed. It inherits the frozen counters and binding, emits the explicit
v2 zero-work rollover event, has all action/output/registration fields null,
has no `receipt-000001.json`, and has empty staging and records directories.
Verification re-pins predecessor, intent, parent, successor event/state/receipt,
plain staging/records directories and no-follow/reparse boundaries. Fresh
creation and recovery tests prove those directories begin empty; the controller
never enumerates them, and later exact-name writes fail closed on conflicts.

## Required evidence

The implementation has focused synthetic coverage for happy path, four external
pins, exact replay, root fork rejection, five partial-crash recovery points,
predecessor/intent/successor tamper rejection, a POSIX parent-reparse race,
zero-work preservation and public signature restrictions. Those tests remain
candidate evidence until the Principal runs the canonical-LF suite.
The Principal alone may run a private smoke with the withheld receipt chain.
This contract grants neither generation nor dispatch authority.
