# P3–P7 Demo D11 Real Flow Contract 08

## Decision status

```text
CONTRACT_ID: P3_P7_D11_REAL_FLOW_CONTRACT_08
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_ACCEPTED_FOR_ISOLATED_IMPLEMENTATION
BASE_SHA: c9b9f65cea9eb757b76489ae2a180270ad883cb2
INTEGRATION_GATE: CONTRACT_07_INTEGRATED_EXACT_SHA_CI_PASS
PUBLIC_API_SHAPE_CHANGE: ADDITIVE_SESSION_CANONICAL_SOURCE_SELECTOR
PUBLIC_API_BEHAVIOR_CHANGE: PRESENT
MIGRATION_CHANGE: NONE
BROWSER_AUTHORITY_CHANGE: NONE
PRODUCTION_AUTHORIZATION: NONE
REAL_USER_AUTHORIZATION: NONE
```

## Product slice

This slice lets the server start the first D08 editing Session from the exact
synthetic Asset already frozen into the current owner-bound Demo Session. It
removes the need for a browser, environment variable or shadow registry to
provide an Asset or identity ID.

It does not execute an edit, select an operation, return image bytes, invoke a
Provider, read D02 private state, or authorize real-user processing.

## Additive request contract

Extend the existing `DemoEditingSessionCreateRequest` with:

```json
{
  "session_id": "<DemoId>",
  "source_selector": "SESSION_CANONICAL_ASSET"
}
```

The three legal source forms are exactly:

1. existing `source_asset_id` with no image-version ID or selector;
2. existing `source_image_version_id` with no Asset ID or selector; or
3. `source_selector=SESSION_CANONICAL_ASSET` with both IDs omitted.

All other combinations fail validation. The two existing forms and their
semantic-idempotency digests remain byte-compatible: an absent selector must
not add a new `null` key to their canonical request payload.

The selector is Demo-only server resolution. The D11 BFF may submit it while
holding the opaque Session handle and upstream bearer. Browser JSON, DOM, URL,
storage and logs never receive or submit the resolved identity/Asset ID or
digest.

## Authority chain

Resolution occurs inside the existing editing admission transaction:

```text
authenticated DemoActor
-> exact active DemoSession
-> immutable DemoSession.config.synthetic_identity_id
-> current admitted DemoSyntheticIdentity
-> formal_canonical_asset_id + formal_canonical_asset_sha256
-> PRINCIPAL_ACCEPTED D02 source authority
-> FINALIZED four-source manifest
-> ADMITTED acquisition run
-> exact synthetic non-deleted Asset
```

The service must replay the Session schema/canonical payload/digest, actor
ownership, active lifecycle and the existing D02 identity/source/manifest/run
authority before selecting bytes. A superseded identity, mismatched Asset
ID/SHA, non-synthetic Asset or missing admission graph fails closed.

The resolved Asset ID/SHA is persisted only through the existing immutable
`DemoEditingSession` authority. No new table, mapping, cache or environment
configuration is permitted.

## Idempotency and errors

The existing `(actor, editing_session.create, idempotency-key-hash)` authority
remains the only winner. The new selector is part of the semantic request, so
replay returns the same Job/Binding/EditingSession and reuse with an explicit
source form is a payload conflict.

Errors use the existing editing envelope:

- missing/foreign/closed/expired Session or non-current identity: `404
DEMO_EDITING_AUTHORITY_UNAVAILABLE`;
- invalid selector combination: `422 DEMO_EDITING_REQUEST_INVALID`;
- malformed same-owner Session/identity/source graph: `503
DEMO_EDITING_AUTHORITY_CORRUPT`;
- same key with a different selector: `409
IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD`.

## Change boundary

Allowed changes are limited to the Session canonical-source resolver, editing
request/command/source resolution, route wiring, focused PostgreSQL/API tests,
generated OpenAPI client and this contract.

Explicitly forbidden:

- migration or ORM changes;
- D02 private checkpoint, Prompt, image or locator access;
- environment-provided identity/Asset source;
- active/latest identity or arbitrary synthetic-Asset fallback;
- Worker/execution/verifier/publication changes;
- browser/BFF/UI changes;
- Provider calls.

## Acceptance

Acceptance requires:

- schema tests for exactly the three legal source forms and every mixed/empty
  rejection;
- real PostgreSQL Session→identity→D02 authority→Asset resolution;
- same-key replay and cross-selector payload collision;
- owner, expiry, closed, tombstone, successor and source-drift fail-closed
  coverage;
- unchanged digests/replay for both existing explicit source forms;
- OpenAPI/generated-client validation;
- proof of no migration, ORM, Worker, BFF or private-state change;
- Ruff, strict mypy, diff check and changed-range Gitleaks;
- one integrated-SHA CI after preceding D11 Gates are accepted.
