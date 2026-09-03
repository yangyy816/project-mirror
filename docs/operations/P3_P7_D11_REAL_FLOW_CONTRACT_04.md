# P3–P7 Demo D11 Real Flow Contract 04

## Decision status

```text
CONTRACT_ID: P3_P7_D11_REAL_FLOW_CONTRACT_04
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_ACCEPTED_FOR_ISOLATED_IMPLEMENTATION
BASE_SHA: f49104254e93ce1f83f4590f0e6cd4ff738d5599
INTEGRATION_GATE: D11_CONTRACT_02_AND_03_TASK_ACCEPTED
MIGRATION_CHANGE: NONE
PUBLIC_API_CHANGE: ADDITIVE_ANALYSIS_SCOPED_QUESTIONNAIRE_AND_PRESENTATION_MEDIA
PRODUCTION_AUTHORIZATION: NONE
REAL_USER_AUTHORIZATION: NONE
```

## Product slice

```text
COMPLETED_D03_ANALYSIS
-> SERVER_RESOLVED_SELF_STATE_AND_ADMITTED_QUESTION_BANK
-> D04_QUESTION_LOOP
-> SAME_ORIGIN_SYNTHETIC_PAIR_MEDIA
```

The browser continues to hold only the opaque D11 Session cookie and opaque
presentation tokens. It cannot select a SelfState, QuestionBank, run, pair,
identity, source or result Asset.

## Analysis-scoped questionnaire creation

Keep the existing D04 routes unchanged. Add:

```text
POST /api/v1/demo/analyses/{analysis_id}/questionnaire
Idempotency-Key: required
request body: none
response: existing DemoJobAcceptedResponse (202)
```

The application service must:

1. revalidate an actor-owned completed D03 run and its exact
   Observation/Baseline/SelfState graph;
2. require the Job result to be `SUPPORTED` or `UNSUPPORTED`;
3. resolve exactly one completed `D02GenericAdmission/v1` QuestionBank and
   replay the complete D04-B bank projection;
4. freeze `max_questions = 16`; and
5. call the existing D04 create transaction, which independently revalidates
   Session, SelfState and bank authority before writing Job/Run/Binding.

Zero or multiple completed generic admissions fail closed. No timestamp,
lexicographic ordering or "latest" heuristic may select a bank. Supporting
multiple concurrently admitted banks requires a future explicit active-bank
authority and is outside this slice.

## Presentation media

Add a Demo-Bearer-protected binary route:

```text
GET /api/v1/demo/questionnaires/runs/{run_id}/presentation-media/{side}
side = LEFT | RIGHT
response media type = image/jpeg
```

This route is read-only. It must:

- revalidate actor ownership and an active Session;
- require the run's current final step to be one unanswered `PRESENTED` step;
- replay the admitted bank and exact QuestionPair presentation;
- select only that step's requested LEFT or RIGHT result Asset;
- require a live `synthetic_dataset` synthetic result Asset at the exact
  `internal-synthetic/v1/d02/result/{asset_id}` key;
- load bytes only through the existing local synthetic Asset byte-loader;
- recheck byte length, SHA-256, JPEG decoding and exact dimensions; and
- return the unchanged canonical JPEG with `Cache-Control: private, no-store`
  and `X-Content-Type-Options: nosniff`.

Missing bytes, non-local/non-Demo runtime, malformed media, stale step, answered
step, owner mismatch or authority drift returns only a redacted unavailable
response. The route never returns an object key, locator, path, signed URL,
Prompt, receipt or credential. It does not reuse user-owned Asset download
grants and is not production-authorized.

## Browser questionnaire bridge

Add same-origin BFF routes:

```text
POST /api/demo/questionnaire
GET  /api/demo/questionnaire
POST /api/demo/questionnaire/response
GET  /api/demo/questionnaire/media/{presentation_token}/{side}
```

Start and read requests have no body or query. Response accepts exactly:

```json
{
  "presentation_token": "<opaque 64-hex>",
  "choice": "LEFT | RIGHT | INDISTINGUISHABLE | SKIP",
  "response_latency_ms": 0
}
```

with latency in `[0, 3600000]`. The BFF registry stores upstream run/Job,
current step/run versions, pair binding, a random presentation token and
preallocated idempotency keys. Same-handle start is single-flight. Same token
and response payload reuses one in-flight promise/key; another payload or a
stale token returns conflict. After a response succeeds the BFF calls `next`
and rotates the presentation token.

Browser QUESTION projection is exactly:

```json
{
  "status": "QUESTION",
  "presentation_token": "<opaque>",
  "left_image_url": "/api/demo/questionnaire/media/<opaque>/LEFT",
  "right_image_url": "/api/demo/questionnaire/media/<opaque>/RIGHT"
}
```

Completion is `{ "status": "COMPLETED" }`. No upstream ID, digest, dimension,
magnitude, routing score/component, object key, bearer or private value reaches
browser JSON, URL, DOM or logs. The media BFF validates cookie plus exact current
presentation token, forwards the server-held run ID and bearer upstream, and
streams only a successful JPEG response with no-store/nosniff headers.

Every upstream await uses the same compare-and-set rule as D11 analysis:
logout, expiry, config rotation or presentation change cannot revive a stale
entry or publish an old question/image.

## No-migration boundary

Existing D03, D04, D02 bank, Job and Asset authority is sufficient. New state
is an application resolver plus short-lived server registry state; no database
column, table, trigger or migration is added.

## Acceptance

- original D03/D04 routes remain compatible;
- unique-bank resolution and completed-analysis graph replay fail closed;
- source/SelfState/bank cannot be browser controlled;
- start/respond replay, collision and concurrency have one logical winner;
- current presentation replay and token rotation are deterministic;
- media ownership/current-step/side/Asset/bytes/digest/decode checks pass;
- browser and media responses contain no forbidden identifiers or secrets;
- logout/expiry/config/step races cannot revive or overwrite registry state;
- OpenAPI/generated client, Ruff, strict mypy, PostgreSQL, Web tests, build,
  Playwright, Gitleaks and one integrated-SHA CI pass before acceptance.
