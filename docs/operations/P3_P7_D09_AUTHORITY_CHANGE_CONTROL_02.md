# P3–P7 D09 Change Control 02 — Final Save PostgreSQL Provenance Authority

## Decision status

```text
CHANGE_CONTROL_ID: CC-P3-P7-DEMO-D09-02
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
STATUS: PENDING_INDEPENDENT_SOL_REVIEW
DISCOVERED_BY: D09 exact-SHA review and Principal adversarial PostgreSQL replay
BASE_SHA: 0c83682599da5794dc562cb710f2da8d36cf5cff
D09_TASK_ACCEPTED: NO
D10: BLOCKED
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This change control repairs a Demo-only PostgreSQL admission gap. It does not change a table, column, ORM model,
public API, formal migration or production authority. It supersedes only the `MIGRATION_CHANGE: NONE` and
`D09_SCHEMA_CHANGE_REQUIRED: NO` dispositions in `CC-P3-P7-DEMO-D09-01`. All other CC01 decisions remain valid,
including event-versus-Final-Save semantics, caller-owned atomicity, ledger sequencing, explicit event time,
trajectory, verifier and event-only exclusion.

## Proven failure and candidate disposition

The D09 epoch 1 application candidate is:

```text
CANDIDATE_SHA: 3c15c65422940934f29bf788ea699f13651a75a1
PARENT_SHA: 0c83682599da5794dc562cb710f2da8d36cf5cff
DISPOSITION: APPLICATION_EVIDENCE_WITH_MANDATORY_POSTGRESQL_FINDING
DO_NOT_CHERRY_PICK_YET: TRUE
```

The service path fills episode provenance from the editing session, but PostgreSQL remains final authority. A direct
SQL writer can currently replace `profile_digest`, `context_digest` and `instruction_digest`, recompute the canonical
payload and content digest, and commit an otherwise valid episode. Principal and independent Sol review both observed:

```text
FORGED_EPISODE_PROVENANCE_ACCEPTED_BY_POSTGRESQL
```

Shape validation and canonical self-consistency cannot prove provenance equality. Application validation does not
replace the database Gate.

## Frozen provenance authority

For every `demo_accepted_visual_episodes` insert, PostgreSQL must prove one terminal `RESULT` plan selected through the
accepted image's `plan_digest`, with actor, session and editing-session ownership equal across the episode, image,
editing session and plan.

```text
episode.profile_digest
  = editing_session.desired_delta_profile_digest
  = terminal_result_plan.desired_delta_profile_digest

episode.context_digest
  = editing_session.context_digest

episode.instruction_digest
  = editing_session.instruction_digest
  = terminal_result_plan.instruction_digest
```

The following retained checks remain mandatory and are not replaced by the new equality Gate:

- source and final Asset authority and checksums;
- complete root-to-terminal ImageVersion trajectory;
- terminal plan, operation and completed ToolRun binding;
- `PASS` VerificationResult bound to the accepted image and final Asset;
- actor/session-bound explicit `IMAGE_ACCEPTED` event targeting the accepted image;
- append-only canonical payload and episode content digest.

Style, identity-constraint and tool-registry equality are not added to the database contract by this corrective change.
The application may retain stricter checks, but they are not a substitute for the frozen three-field PostgreSQL Gate.

## Forward prototype migration

```text
MODULE: demo_0004_d09_episode_provenance.py
REVISION: demo_0004_d09_episode_prov
REVISION_LENGTH: 26
DOWN_REVISION: demo_0003_d02_import_auth
PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
TABLE_OR_COLUMN_CHANGE: NONE
ORM_MODEL_CHANGE: NONE
PUBLIC_API_CHANGE: NONE
```

Upgrade must use `CREATE OR REPLACE FUNCTION mirror_demo_validate_accepted_episode()` and retain the existing trigger
attachment. The complete prior validator body is copied forward and strengthened; accepted migrations
`demo_0001`–`demo_0003` remain immutable.

Before reading any episode, upgrade acquires
`LOCK TABLE demo_accepted_visual_episodes IN ACCESS EXCLUSIVE MODE`. The transaction-scoped lock is held through the
complete existing-row audit, hardened function replacement, Alembic revision update and transaction commit. This
serializes every concurrent insert across the authority-version boundary; an insert that was already in flight finishes
before the audit, while a later insert resumes only after commit and is evaluated by the hardened function.

With that lock held, upgrade scans every existing episode using the same equality matrix. Any invalid row fails the
migration. The migration must never update, delete, re-sign or silently quarantine historical evidence. A valid
pre-existing episode remains byte-identical.

## Downgrade and recovery

- Downgrade acquires the same transaction-scoped `ACCESS EXCLUSIVE` table lock before its emptiness check and holds it
  through function restoration, Alembic revision update and transaction commit. No concurrent insert may pass between
  the check and restoration.
- If any episode exists, `demo_0004 -> demo_0003` fails closed before replacing the hardened function. Even valid
  evidence may not be left under the weaker admission authority.
- If the episode table is empty, downgrade restores the complete `demo_0003` function body frozen inside this migration;
  it must not dynamically import a historical migration module.
- A failed downgrade leaves the revision, function and data at `demo_0004`.
- Empty-database round trip must compare `pg_get_functiondef` with the `demo_0003` baseline and then re-upgrade to the
  hardened definition.

If upgrade discovers a forged pre-existing episode, this change control does not authorize evidence deletion or
rewriting. Principal must stop and open a separate data-disposition change control.

## Required application and PostgreSQL evidence

The epoch 2 implementation must retain the two epoch 1 application files, add terminal-plan tool-registry equality at
the service boundary, and prove the following on real PostgreSQL with zero skipped cases:

1. legal service Final Save persists one event and one episode with the frozen provenance values;
2. separately re-signed profile-only, context-only and instruction-only direct-SQL forgeries are rejected;
3. a combined three-field re-signed forgery is rejected;
4. terminal plan profile or instruction drift is rejected;
5. actor/session/editing-session/terminal-plan mixing is rejected;
6. each failed episode insert in a caller-owned transaction rolls back its event and does not consume sequence;
7. two concurrent Final Saves for one accepted image produce one canonical winner and no duplicate event or episode;
8. cancellation after event flush but before episode flush rolls back both rows;
9. event-only acceptance, reject, learning-disabled and lock/unlock evidence are not promoted to stable profile/context
   authority by D09;
10. RESET accepts only a strict earlier watermark and preserves append-only history;
11. a second PostgreSQL connection attempting an episode insert during upgrade is serialized until commit, after which
    a forged insert is rejected by the hardened validator;
12. a second connection cannot insert between downgrade's empty-table check and weak-function restoration; the lock is
    held until downgrade commit and the regression proves there is no check/replace traversal window.

Compiler behavior remains a D10 responsibility. D09 tests prove only that D09 does not itself materialize or reinforce a
stable profile/context from ineligible evidence.

## Migration and integration evidence

Mandatory lifecycle and regression checks are:

```text
fresh 0014 -> demo_0004 head
demo_0003 -> demo_0004 with no episodes
demo_0003 -> demo_0004 with legal episode; row byte-identical
demo_0003 -> demo_0004 with forged episode: FAIL_CLOSED at demo_0003
demo_0004 -> demo_0003 with no episodes
demo_0003 -> demo_0004
populated demo_0004 -> demo_0003: FAIL_CLOSED
alembic heads: single head
alembic check: zero drift
formal non-Demo DDL drift: zero
```

Targeted D09 tests, Demo schema invariant tests, affected migration regressions, Ruff, strict mypy, diff check, scoped
Gitleaks, exact-SHA CI and an independent Sol exact-SHA implementation review are all mandatory. Historical CC01 CI
does not verify CC02.

## File and ownership boundary

Only the Integration Principal owns the migration, central migration tests, CI head/history wiring, change-control
documents, integration commit and acceptance state. Topic workers may update only their explicitly dispatched D09
domain/test files and may not commit migration, ORM, router, OpenAPI, generated client, Celery registration or MEMORY.

## Exit disposition

```text
CC_P3_P7_DEMO_D09_02_ACCEPTED: NO
D09_POSTGRESQL_PROVENANCE: NOT_VERIFIED
D09_TASK_ACCEPTED: NO
D10: BLOCKED
FORMAL_MAINLINE_IMPACT: NONE_EXPECTED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```
