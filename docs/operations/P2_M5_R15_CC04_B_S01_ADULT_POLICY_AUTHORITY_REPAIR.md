# P2-M5-R15 CC04-B-S01 Adult-Policy Authority Repair

## Status and authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R15`
- `TASK_NAME: CC04-B-S01 Adult-Policy Authority Repair`
- `BASELINE_SHA: 188ee6ae77c46155706c3a0cb8a1cfa3cbafb241`
- `FAILED_CANDIDATE: CC04-B-S01_AT_188EE6AE77C46155706C3A0CB8A1CFA3CBAFB241`
- `FAILED_CANDIDATE_CI_RUN: 32624426069`
- `REPAIR_CANDIDATE: THIS_COMMIT`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ARTIFACT_SECURITY_PRIVACY_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`

This is a forward-only governance repair. It preserves the failed S01 candidate, its passing same-SHA CI, eight inspected artifacts, independent Security/Privacy/Research Integrity PASS, and independent Sol High FAIL. It does not amend or reinterpret that failure as acceptance.

The repair does not invoke image generation, access private input, create a registry, root, locator, Asset, identity, cohort, output, or evidence record, consume quota, or authorize execution.

## Defect and frozen authority resolution

The failed S01 candidate combined the accepted Owner/T01 shorthand `ambiguous adult presentation is rejected` and `no ambiguity bypass` with ADR-030 and `P2_AGE_PRESENTATION_CONTROL_V2`, but did not define which ambiguity rule governs this general nonsexual cohort. It also omitted the required non-failure categorical outcome `YOUTHFUL_ADULT_PRESENTATION_ALLOWED`. A future Q01 or operator could therefore apply either an obsolete general `minor ambiguity` hard reject or the current v2 boundary.

For future general nonsexual cohorts, the repository already freezes the forward rule in ADR-030 and `P2_AGE_PRESENTATION_CONTROL_V2`. They supersede the general `minor ambiguity` hard-reject rule while preserving every historical record. This repair applies that rule to 04-B without changing the Owner-selected synthetic-adult source, safety intent, resource envelope, or review DAG:

- `DECLARED_IDENTITY: SYNTHETIC_ADULT_18_PLUS`
- `GENERAL_NONSEXUAL_HARD_REJECT_1: CLEAR_PRE16_PRESENTATION`
- `GENERAL_NONSEXUAL_HARD_REJECT_2: CHILD_OR_STUDENT_MINOR_CONTEXT`
- `YOUTHFUL_ADULT_PRESENTATION_ALLOWED: ALLOWLISTED_NONFAILURE_CATEGORICAL_EVIDENCE`
- `GENERAL_MINOR_AMBIGUITY_INDEPENDENT_HARD_REJECT: PROHIBITED`
- `APPLICABLE_ADULT_HARD_FAIL_BYPASS: PROHIBITED`
- `AUTOMATIC_OR_NUMERIC_AGE_ESTIMATION: PROHIBITED`
- `HUMAN_OVERRIDE_OF_APPLICABLE_HARD_FAIL: PROHIBITED`

Round face, babyface, soft features, small adult face, or youthful appearance alone cannot be treated as minor evidence or a rejection reason. The review remains a categorical presentation decision and stores no predicted age, probability, confidence, score, percentile, ranking, or free-text facial judgment.

## Disposition of earlier ambiguous wording

For this nonsexual 04-B cohort only, earlier Owner/T01/S01 wording about `ambiguous adult presentation`, `adult ambiguity`, `minor ambiguity bypass`, or `clearly-adult hard-fail` is current-authoritatively interpreted as all of the following and nothing broader:

1. the identity must have declared synthetic-adult 18+ provenance;
2. `CLEAR_PRE16_PRESENTATION` and `CHILD_OR_STUDENT_MINOR_CONTEXT` are non-overridable hard rejects;
3. missing provenance, missing policy binding, missing categorical evidence, or an unsupported PASS is fail-closed;
4. youthful or babyface morphology alone is explicitly allowed non-failure evidence;
5. no reviewer may invent or restore an independent general `minor ambiguity` rejection reason.

This interpretation prevents bypass of applicable hard fails without silently reintroducing the v1 rule superseded by ADR-030. It does not modify the historical Owner Pack, T01, S01 candidate, ADR-028, or v1 evidence.

04-B remains nonsexual. `ADULT_SAFE_SEXY`, `CHARMING_ALLURING`, intimate, fetishized, nude, explicit, or sexualized contexts are out of scope. Unexpected sexualization is an immediate hard reject. The v2 `ADULT_ONLY_STYLE_AGE_AMBIGUOUS` rule remains authoritative for any separate adult-only style cohort, but is not an admission path or general reason code for nonsexual 04-B.

## Frozen reason taxonomy

Q01 and any later accepted execution contract must include these current adult-presentation outcomes:

- `CLEAR_PRE16_PRESENTATION` — hard reject;
- `CHILD_OR_STUDENT_MINOR_CONTEXT` — hard reject;
- `UNEXPECTED_SEXUALIZED_CONTEXT` — hard reject for 04-B;
- `YOUTHFUL_ADULT_PRESENTATION_ALLOWED` — accepted categorical evidence, not an age prediction;
- `EVIDENCE_OR_DIGEST_MISSING` — hard stop when declared-adult provenance, policy binding, or required categorical evidence is absent;
- `UNSUPPORTED_PASS_OR_MISSING_EVIDENCE` — hard stop for an unproven admission.

All source, subject, decode, face-count, pose, unsafe-content, sensitive-inference, beauty-score, hidden-network, resource, leakage, production, downstream, legacy-reuse, and non-override controls frozen in the failed S01 candidate remain required. This repair supersedes only the ambiguous adult-policy interpretation and incomplete outcome taxonomy.

## Acceptance and sequencing

- `ADULT_POLICY_AUTHORITY_CONFLICT: RESOLVED_BY_ADR_030_AND_P2_AGE_PRESENTATION_CONTROL_V2_FORWARD_RULE`
- `ADULT_SAFETY_AND_NEGATIVE_CONTROL_REVIEW: PASS_AT_THIS_COMMIT_AFTER_ALL_GATES`
- `CC04_B_EXECUTION: CLOSED`
- `NEXT_REQUIRED_REVIEW_AFTER_ACCEPTANCE: CC04-B-P01`

Acceptance requires exact-SHA CI, eight-artifact content inspection, independent Security/Privacy/Research Integrity review, independent Sol High review, and Principal acceptance. Until every Gate passes, S01 remains failed/pending repair, P01 is not open, and execution and generation remain prohibited.

## Validation

- exact forward parent and exact three-path allowlist;
- scoped Markdown formatting and `git diff --check`;
- ADR-030 and `P2_AGE_PRESENTATION_CONTROL_V2` rule and reason-code scan;
- Owner/T01/S01 historical preservation scan;
- `YOUTHFUL_ADULT_PRESENTATION_ALLOWED` presence and general `minor ambiguity` independent-reject prohibition scan;
- no age estimation, hard-fail override, generation, private access, quota, custody, cohort, downstream opening, or binary/private leakage;
- true-EOF, sentinel, last-occurrence, and canonical/mirror equality checks;
- same-SHA CI, all artifacts, independent reviews, and Principal acceptance.

## Rollback and stop

Reject this candidate without changing the accepted L01 authority if any Gate fails. Correct a remaining defect only with another normal forward repair. Do not amend, reset, rebase, merge, force-push, delete failed evidence, or create a post-acceptance status commit.
