# P3–P7 Demo D11 Real Flow Contract 05

## Decision status

```text
CONTRACT_ID: P3_P7_D11_REAL_FLOW_CONTRACT_05
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_ACCEPTED_FOR_ISOLATED_IMPLEMENTATION
BASE_SHA: 6a1564313f4a07bd4efbda24467f5361c145833f
INTEGRATION_GATE: CONTRACT_04_INTEGRATED_EXACT_SHA_CI_PASS
PUBLIC_API_SHAPE_CHANGE: NONE
PUBLIC_API_BEHAVIOR_CHANGE: MARK_ACCEPTED_P3_P4_CAPABILITIES_AVAILABLE
MIGRATION_CHANGE: NONE
PRODUCTION_AUTHORIZATION: NONE
REAL_USER_AUTHORIZATION: NONE
```

## Product slice

This slice turns the accepted server-only D11 bridge into the first truthful,
interactive synthetic Demo page:

```text
START_DEMO
-> OWNER_BOUND_SESSION
-> D03_ANALYSIS
-> D04_QUESTIONNAIRE
-> SAME_ORIGIN_LEFT_RIGHT_MEDIA
-> COMPLETED
```

It does not upload a user image, invoke a Provider, infer a sensitive trait,
show a beauty score, expose D02 private state, or authorize production or
real-user facial processing.

## Browser state machine

Add one client-side `DemoRealFlowWorkspace` with the exact visible states:

```text
IDLE
SESSION_CREATING
ANALYSIS_STARTING
ANALYSIS_PENDING
ANALYSIS_COMPLETED
QUESTIONNAIRE_STARTING
QUESTIONNAIRE_PENDING
QUESTION
RESPONSE_SUBMITTING
COMPLETED
ERROR
```

The component may call only the existing same-origin BFF routes. It must not
set an Authorization header, construct an upstream URL, select an identity,
Session, analysis, SelfState, QuestionBank, run, pair or Asset, or read the
HttpOnly cookie.

`POST /api/demo/session` followed by `POST /api/demo/analysis` starts the flow.
Pending analysis is polled through `GET /api/demo/analysis`. After analysis is
complete, the user explicitly starts the questionnaire. Pending questionnaire
state is polled through `GET /api/demo/questionnaire` until a question or
terminal result is returned.

Automatic polling uses a fixed one-second interval and a maximum of 120 polls
per phase. A timeout enters a recoverable `ERROR` state and never creates a new
Session, analysis or questionnaire implicitly. The user may retry the exact
current phase through the same BFF authority or end the Demo. Component unmount,
logout and a newer action generation invalidate all older asynchronous results.

## Question presentation

A question renders only:

- the two relative same-origin JPEG URLs returned by the BFF;
- neutral labels `左侧方案` and `右侧方案`; and
- four choices: `更偏好左侧`, `更偏好右侧`, `难以区分`, `跳过此题`.

The component records presentation time locally and submits an integer latency
clamped to `[0, 3600000]`. All four controls are disabled while one response is
in flight. A successful response replaces the whole question projection and
therefore rotates the opaque presentation token. No previous token or media URL
is retained in component state after the transition.

The completed view says only that the preference questionnaire is complete. It
must not display a score, rank, percentile, demographic label, hidden model
state or inferred aesthetic conclusion.

## Error and lifecycle behavior

Safe browser error classes are `DENIED`, `NOT_FOUND`, `CONFLICT`, `UNAVAILABLE`,
`UNSUPPORTED`, `STALE_RESPONSE`, `FAILED`, `REJECTED`, `CANCELLED` and local
`POLL_TIMEOUT`. Each maps to concise Chinese UI text without upstream IDs,
digests or exception content.

Retry never changes a submitted choice or generates client idempotency keys;
the BFF retains that authority. `DELETE /api/demo/session` is the only End Demo
action. It invalidates the browser cookie and the complete server registry;
the UI then discards all in-memory state and returns to `IDLE`, regardless of a
redacted network failure response.

The component must not use localStorage, sessionStorage, IndexedDB, service
worker caches or analytics. All status regions use `aria-live="polite"`;
buttons and images have accessible names and remain keyboard operable.

## Page projection

The `/demo` page mounts `DemoRealFlowWorkspace`. It removes the old read-only
claim, `REAL_D02_INTEGRATION_PENDING`, and `UI_CONTRACT_ONLY` fixture panels from
the rendered page. Existing historical component source may remain tracked but
must not be presented as real execution.

The capability summary remains server-rendered and cannot gate or fake the BFF
flow. Because D03 and D04 are accepted and exercised by this flow, their
existing capability rows are changed from `NOT_IMPLEMENTED` to `AVAILABLE`.
This changes no schema, route, credential or execution authority.

## Test boundary

The deterministic Playwright fake API may emulate the accepted public
Session/D03/D04/media responses. It is test infrastructure only and cannot be
used by production code.

Acceptance requires:

- Vitest coverage for start, pending polls, questionnaire start, all four
  choices, token rotation, terminal/error/retry/logout and stale async results;
- Playwright coverage of the complete visible flow and error recovery;
- browser requests contain no Authorization header;
- DOM, URL and Web storage contain no upstream ID, digest, bearer or private
  locator;
- pair images use only same-origin BFF URLs;
- Web lint, strict TypeScript, formatting, unit tests, production build,
  Playwright, Gitleaks and one integrated-SHA CI pass before acceptance.
