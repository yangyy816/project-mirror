# P2-M5-R64-R01 — CI platform-type repair

`STATUS: EXECUTING`

## Trigger

R64 candidate `887fcc08b85fc34bc6bb612986af90e509b0e83e` failed the
same-SHA `quality-and-integration` Python quality step. Linux mypy evaluated
the Windows-only `msvcrt` branch and reported missing `locking`, `LK_NBLCK` and
`LK_UNLCK` attributes.

## Bounded repair

The two Windows-only imports use the existing `importlib` plus `Any` pattern
already applied to the POSIX-only `fcntl` branch. This is a static typing repair
only: it changes no runtime lease protocol, receipt, bridge, provider, policy,
schema, OpenAPI, image, decode or M3 behavior.

## Required evidence

- full CI-range Ruff and mypy pass locally;
- R64 focused tests remain green;
- legacy overlay byte SHA remains exact; and
- a new same-SHA remote run passes before any R64 acceptance consideration.
