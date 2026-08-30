# P3–P7 D09 Image Feedback API Contract 01

```text
CHANGE_CONTROL_ID: P3_P7_D09_IMAGE_FEEDBACK_API_CONTRACT_01
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_ACCEPTED_FOR_IMPLEMENTATION
PUBLIC_OPERATION: POST /api/v1/demo/image-versions/{image_version_id}/feedback
MIGRATION_REQUIRED: NO
ORM_CHANGE_REQUIRED: NO
D02_DEPENDENCY: NONE
PRODUCTION_AUTHORITY: NOT_GRANTED
```

## Problem

The accepted D09 authority deliberately distinguishes an event-only `IMAGE_ACCEPTED`
signal from a durable Final Save backed by `DemoAcceptedVisualEpisode`. The D01-C
request shape exposed only `feedback=ACCEPT`, so the application adapter could not
determine which accepted operation the user intended. Inferring intent from an image,
an idempotency key, intensity, a hidden header or current UI state is forbidden.

## Frozen request semantics

`DemoImageFeedbackRequest` retains `feedback=ACCEPT | REJECT | ADJUST` and adds the
explicit optional field:

```text
acceptance_kind: EVENT_ONLY | FINAL_SAVE | null
```

The valid combinations are:

| feedback | acceptance_kind | intensity_ppm                   | effect                                                                        |
| -------- | --------------- | ------------------------------- | ----------------------------------------------------------------------------- |
| `ACCEPT` | `EVENT_ONLY`    | absent                          | append one event-only `IMAGE_ACCEPTED`                                        |
| `ACCEPT` | `FINAL_SAVE`    | absent                          | atomically append `IMAGE_ACCEPTED` and create one `DemoAcceptedVisualEpisode` |
| `REJECT` | absent          | absent                          | append one `IMAGE_REJECTED`                                                   |
| `ADJUST` | absent          | required integer `0..1_000_000` | append one `IMAGE_ADJUSTED`                                                   |

Every other combination fails request validation. This is a pre-freeze correction to
the existing operation, not a new endpoint or capability.

## Application invariants

- The authenticated Demo actor must own the target `DemoImageVersion`; its persisted
  session and editing-session lineage are the only accepted ownership source.
- `EVENT_ONLY` never creates or consumes an `AcceptedVisualEpisode`.
- `FINAL_SAVE` must call `finalize_demo_accepted_visual_episode`; direct append of an
  acceptance event is not an implementation of Final Save.
- Final Save remains eligible only for a complete lineage whose terminal verifier is
  `PASS`. `FAIL` and `HUMAN_REVIEW` cannot publish an ImageVersion and cannot be saved.
- `REJECT` and `ADJUST` are negative/corrective evidence and never create an episode.
- The existing PostgreSQL `image_version.feedback` command binding is the sole
  idempotency authority. Same-key replay returns the same event; a changed semantic
  payload returns a conflict; concurrent requests leave no partial event or episode.
- A pre-existing canonical Final Save for the same image may be returned only when its
  event and episode exactly match this operation's frozen semantics. Mismatch fails
  closed as authority conflict/corruption.

## Validation boundary

Acceptance requires Pydantic combination tests, owner/session negatives, event-only
exclusion, atomic Final Save, invalid-lineage rollback, same-key replay, payload
collision, concurrent single episode/event, route error-envelope parity, OpenAPI
regeneration and generated TypeScript freshness on real PostgreSQL where persistence
is involved.
