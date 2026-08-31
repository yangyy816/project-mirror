# P2-M5-R63 Windows native FFI binding repair evidence

`STATUS: LOCAL_PASS_PENDING_CANDIDATE_PREFLIGHT`

## Verified local evidence

- Module-level Windows native ctypes types and one lock-protected binding are
  used by the affected descriptor, file-I/O and lease helpers.
- A fresh-process binding test proves fail-closed initialization, one binding
  initialization, stable function identities and concurrent getter reuse.
- The complete 22-test post-registration focused suite completed with exit
  code zero. Its prior CPU concern is classified as
  `LONG_RUNNING_BUT_TERMINATING`; the slowest terminal-evidence test completed
  in approximately 399 seconds without an OOM or resource kill.
- A detached canonical-LF API and Worker regression completed with exit code
  zero. The only observed output was the pre-existing Starlette/httpx
  deprecation warning; no test failure or error was reported.

## Boundaries retained

- Controller state, ledger, receipt, replay, Provider, schema, migration,
  OpenAPI, imagegen, decode, M3 and admission semantics are unchanged.
- No private locator, Prompt, image/model bytes or credentials are recorded
  here.
