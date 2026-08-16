# Phase 1 Observability Runbook

## Boundary

Phase 1 emits payload-free structured operational events through Python standard-library logging and preserves append-only domain `AuditLog` evidence in PostgreSQL. It does not claim that a production telemetry backend, pager or dashboard has been deployed. Tencent Cloud log routing and alert delivery remain P9 work.

## Event contract

Operational events are canonical JSON with a fixed allowlist:

- `event_name`, `outcome`, `operation`
- `request_id`
- optional `job_id`, `duration_ms`, `status_code`, HTTP method and route template

The HTTP event uses the framework route template, never the raw URL. Job dispatch events distinguish `succeeded` from `deferred`; a deferred dispatch remains a durable PostgreSQL Job and is recovered by the existing reconciler.

Forbidden fields include phone, OTP, invite, access/refresh token, Cookie, credential, signed URL, upload/download handle, object key, image bytes/metadata, Provider payload and prompt. The emitter does not accept arbitrary metadata. Domain audit metadata remains a static event label.

## Correlation

1. Start with `request_id` from the API response/event.
2. Use an emitted `job_id` to follow dispatch, Worker and authoritative PostgreSQL Job/attempt/final evidence.
3. Use the matching append-only `AuditLog.request_id` to inspect the authorized domain transition. Session and user identifiers stay in the restricted database evidence rather than general operational logs.

## Collector-derived signals

| Signal                     | Derivation                                                         | Initial investigation trigger                               |
| -------------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------- |
| API error ratio            | `http.request.completed` grouped by route template and status      | sustained `5xx`; sudden `401/403/429` increase              |
| API latency                | `duration_ms` by route template                                    | sustained p95 increase relative to the environment baseline |
| Dispatch deferral          | `job.dispatch.completed` with `outcome=deferred`                   | any sustained nonzero rate or queue-depth growth            |
| Authentication abuse       | auth route templates with `401/429` plus restricted audit evidence | burst by deployment/environment, never by raw phone         |
| Upload/ingestion rejection | upload/ingestion route result plus Job final result code           | sudden format/limit/revocation increase                     |
| Deletion/export SLA        | authoritative request/job timestamps and terminal evidence         | oldest pending age exceeds reviewed operational target      |

Thresholds are operational targets and must be tuned with Beta evidence. Until a production collector and paging path are deployed and tested, alert delivery remains `NOT_DEPLOYED` rather than simulated.

## Incident checks

- Confirm the event contains only the allowlist before sharing logs.
- Query by request/job correlation, not phone, URL, token or object key.
- Treat Redis/Celery state as non-authoritative; reconcile against PostgreSQL.
- For deletion/export, do not infer success from task return alone; require terminal database and object evidence.
- For a suspected leak, restrict access, rotate affected credentials where applicable, preserve minimal audit evidence and follow the future P9 incident-response process.
