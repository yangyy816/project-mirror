# ADR-020: User Data Rights and Asset Lifecycle

- Status: Accepted
- Date: 2026-08-16
- Decision owners: Principal Agent / Project Mirror
- Scope: P1-M5 — Asset Access, User Data Rights and Lifecycle UI

## Context

P1-M4 can promote a safe canonical object into an immutable Original Asset, but it intentionally exposes no download, deletion, export or account-deletion path. `Asset.deleted_at` alone cannot prove request admission, immediate access revocation, asynchronous object deletion, retry, completion or account-wide propagation. P1-M5 must close those rights without processing real faces, weakening Original immutability or inventing future Profile/Questionnaire deletion semantics.

## Decision

### Authority and state

- PostgreSQL remains authoritative. Object storage is a private blob executor and never decides ownership or lifecycle state.
- `0005_data_rights_lifecycle` is forward-only and adds append-only request/evidence records for Asset deletion, user export and account deletion. It does not modify `0001`–`0004`.
- Original Asset identity, storage key, digest, MIME, size and dimensions remain immutable. Deletion changes lifecycle state and later records physical object deletion; it never rewrites Original metadata.
- A deletion request immediately denies new download grants, ingestion/promotion and downstream processing. Physical deletion is asynchronous, idempotent and retryable.
- `AssetAccessAudit`, lifecycle events and physical-deletion evidence are append-only. Logs and API responses contain opaque IDs and stable result codes only.

### Private access

- Only an active owner can list or inspect their nondeleted Assets and request a download grant. Ownership is part of the SQL predicate, not a post-query comparison.
- `ObjectStorageProvider` gains a provider-neutral, one-time/short-lived private download grant for an exact server-selected key. It never accepts a user URL or path.
- Local development may expose a loopback-only tokenized GET Adapter for synthetic/non-face fixtures. It is hidden from OpenAPI, has no directory listing, stores only HMAC proof and remains rejected in production.
- Download grant creation and successful grant redemption are audited without storing the URL, token, object key or bytes.

### Asset deletion

- `DELETE /api/v1/assets/{asset_id}` returns `202` with an opaque `job_id`, accepts `Idempotency-Key`, and creates one owner-bound Asset deletion request.
- Request admission atomically tombstones access, blocks new work and enqueues a reference-only task. Repeated delivery or callback can create at most one physical-deletion completion evidence.
- Once object deletion has started, the API never promises recovery. Before physical deletion, only a future explicitly authorized recovery operation may cancel; P1-M5 exposes no self-service restore endpoint.

### Export

- `POST /api/v1/users/me/data-exports` returns `202`; status is owner-bound. A Worker creates a deterministic manifest plus the user's currently authorized data and Asset bytes in a private archive.
- Exports exclude secrets, token/hash material, internal risk signals, raw quarantine objects, system prompts, other users and legally isolated records. Every included category and schema version is explicit.
- Export packages have a configured short retention deadline, one-time/short-lived download grants and idempotent cleanup. Production values require reviewed retention configuration.

### Account deletion

- `POST /api/v1/users/me/deletion-requests` returns `202` and atomically moves the user to `deletion_requested`, revokes every session family, blocks all new access/signing/processing and schedules propagation.
- The Worker tombstones pending upload/ingestion work, withdraws active purpose grants through append-only evidence, deletes owned objects/exports and irreversibly disconnects direct account lookup material. Minimal legally required audit/financial/security facts may remain only in isolated, de-identified form.
- Physical deletion follows dependency order and writes append-only completion evidence. No API may report completion until storage and database propagation evidence agree.
- P1-M5 covers only Phase 1 entities that exist now. Future Questionnaire/Profile/Edit/Visual Memory phases must extend the propagation graph before their own Gate.

### Public API boundary

- `GET /api/v1/assets`
- `GET /api/v1/assets/{asset_id}`
- `POST /api/v1/assets/{asset_id}/download-grants`
- `DELETE /api/v1/assets/{asset_id}`
- `POST /api/v1/users/me/data-exports`
- `GET /api/v1/users/me/data-exports/{export_id}`
- `POST /api/v1/users/me/data-exports/{export_id}/download-grants`
- `POST /api/v1/users/me/deletion-requests`
- `GET /api/v1/users/me/deletion-requests/current`

All creating operations accept `Idempotency-Key`. Asynchronous operations return unguessable `job_id`; errors retain `code/message/request_id/details`. No endpoint reveals storage keys, hashes, provider payloads or internal audit content.

## Alternatives considered

- **Public or stable object URLs:** rejected because revocation, ownership and audit cannot be enforced.
- **Synchronous object deletion:** rejected because storage/database failures would create false success or partial deletion.
- **Hard-delete all PostgreSQL rows:** rejected because it conflicts with append-only evidence, foreign-key integrity and lawful minimal retention.
- **Keep account active during a recovery window:** rejected because deletion must immediately stop new processing and signing.
- **One generic mutable rights-request table:** rejected because export, Asset deletion and account deletion have different authority, retention and completion evidence.

## Consequences

- P1-M5 requires `0005`, storage download/export capabilities, application services, Worker tasks, API contracts and Web controls.
- Tests remain limited to synthetic/non-face fixtures and deterministic Providers; production real-image access remains fail closed.
- Recovery, legal retention periods, break-glass operations and future-domain propagation remain explicit Gates rather than implied completed behavior.
