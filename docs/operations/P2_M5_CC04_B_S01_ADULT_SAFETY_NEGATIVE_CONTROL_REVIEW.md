# CC04-B-S01 Adult Safety and Negative-Control Review

## Status and authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC04-B-S01`
- `TASK_NAME: Adult Safety and Negative-Control Review`
- `PARENT_AUTHORITY: CC04-B-L01`
- `BASELINE_SHA: 885a6b24857eac199fc1e2e6b1b7e49342eda02c`
- `REVIEW_CANDIDATE: THIS_COMMIT`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ARTIFACT_SECURITY_PRIVACY_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`
- `PRE_CONDITION_CURRENT_STATE: CC04_B_S01=REVIEW_CANDIDATE_PENDING_ACCEPTANCE; CC04_B_EXECUTION=CLOSED`

This is a review-only checkpoint. It does not invoke image generation, access private input, create a root or locator, create an Asset or identity, form a cohort, consume quota, or authorize execution.

## Review authority

The review binds the accepted T01 contract, ADR-028, ADR-029, ADR-030, `P2_AGE_PRESENTATION_CONTROL_V2`, and `P2_STYLE_PRESENTATION_CONTROL_V2`. ADR-030 is the current forward authority for youthful adult presentation: youthful facial morphology alone is not minor evidence, while clear pre-16 presentation and child/student-minor context are hard rejects. This interpretation does not weaken the T01 requirement that every 04-B identity is declared 18+, synthetic-only, and adult-presenting.

04-B is nonsexual. `ADULT_SAFE_SEXY`, `CHARMING_ALLURING`, intimate, fetishized, nude, explicit, or sexualized contexts are not part of this calibration cohort. Unexpected sexualization is a hard reject, not a reason to apply a looser age rule.

## Frozen adult-safety boundary

- `DECLARED_IDENTITY: SYNTHETIC_ADULT_18_PLUS`
- `GENERAL_PRESENTATION_RULE: YOUTHFUL_ADULT_FEATURES_ALLOWED_WITHOUT_CHILD_OR_STUDENT_CONTEXT`
- `GENERAL_HARD_REJECT_1: CLEAR_PRE16_PRESENTATION`
- `GENERAL_HARD_REJECT_2: CHILD_OR_STUDENT_MINOR_CONTEXT`
- `UNEXPECTED_SEXUALIZED_CONTEXT: HARD_REJECT`
- `AUTOMATIC_AGE_ESTIMATION: PROHIBITED`
- `NUMERIC_ESTIMATED_AGE_OR_CONFIDENCE: PROHIBITED`
- `MINOR_AMBIGUITY_BYPASS: PROHIBITED`
- `YOUTHFUL_OR_BABYFACE_ONLY_REJECTION: PROHIBITED`
- `HUMAN_OVERRIDE_OF_ADULT_HARD_FAIL: PROHIBITED`

The review decision is categorical and policy-versioned. It records only an allowlisted outcome, reason code, actor authority, timestamp, and evidence digest. It must not persist a predicted age, probability, score, percentile, ranking, free-text facial judgment, Prompt, private path, object key, URL, Provider payload, or image bytes.

## Frozen source and subject hard rejects

Every future raw output is untrusted and must be rejected before admission when any of these conditions applies:

1. real-person, User Asset, celebrity, influencer, internet-scraped, face-swap, named-identity, or identity-reproduction reference;
2. a real or synthetic child identity, clear pre-16 presentation, child/student-minor context, school uniform, or minor-coded campus framing;
3. malformed bytes, unsupported format, multi-frame input, decode failure, decompression/pixel/size overflow, or failed canonical re-decode;
4. zero faces, multiple faces, materially occluded face, protocol-disallowed pose, or a face-count/pose result below the frozen reliability boundary;
5. nudity, explicit sexualization, fetishized or exploitative framing, unexpected intimate/alluring context, or other unsafe content;
6. sensitive-trait classification or inference, including race, ethnicity, ancestry, nationality, religion, health, politics, or sexual orientation;
7. beauty, attractiveness, desirability, normality, or age scoring, ranking, percentile, or universal-template comparison;
8. a hidden standard-face objective, repeated-template identity collapse, or morphology selection based on a concealed aesthetic ideal;
9. reuse or discovery of CC01-C, CC02, M4, User, real-person, or any legacy Asset, identity, output, locator, report, or private evidence.

No automatic or human review may turn a hard-rejected output into an eligible identity. A soft coverage or style observation can only exclude an otherwise safe candidate; it can never override a hard failure.

## Frozen operational negative controls

The later P01/Q01/O01 and execution contract must implement auditable fail-closed controls for:

- `HIDDEN_NETWORK_OR_UNREVIEWED_PROVIDER: HARD_STOP`
- `REQUEST_OR_OUTPUT_COUNT_OVERFLOW: HARD_STOP`
- `STORAGE_LEDGER_OVERFLOW: HARD_STOP`
- `CONCURRENCY_GREATER_THAN_ONE: HARD_STOP`
- `AUTOMATIC_OR_MANUAL_RETRY_BYPASS: HARD_STOP`
- `HOLDOUT_QUOTA_USE_OR_TRANSFER: HARD_STOP`
- `UNSUPPORTED_PASS_OR_MISSING_EVIDENCE: HARD_STOP`
- `UNKNOWN_DIGEST_OR_TAMPER: HARD_STOP`
- `PROMPT_PATH_KEY_URL_CREDENTIAL_OR_PRIVATE_PAYLOAD_LEAKAGE: HARD_STOP`
- `PRODUCTION_PROVIDER_OR_PRODUCTION_GENERATION_BYPASS: HARD_STOP`
- `MVR_M6_QUESTIONBANK_OR_PUBLIC_RELEASE_BYPASS: HARD_STOP`
- `POST_HOLDOUT_THRESHOLD_FORMULA_DIMENSION_OR_SPLIT_CHANGE: HARD_STOP`

A negative-control failure ends the current task attempt and preserves request/output counts and allowlisted failure evidence. It does not trigger an automatic retry, replacement generation, quota transfer, threshold change, private discovery, or deletion of historical audit facts.

## Reason-code minimum

The future GenerationSpecification and QA admission policy must include, at minimum:

- `CLEAR_PRE16_PRESENTATION`
- `CHILD_OR_STUDENT_MINOR_CONTEXT`
- `UNEXPECTED_SEXUALIZED_CONTEXT`
- `REAL_OR_USER_REFERENCE_PROHIBITED`
- `CELEBRITY_OR_SCRAPED_REFERENCE_PROHIBITED`
- `MALFORMED_OR_UNSUPPORTED_IMAGE`
- `FACE_COUNT_NOT_ONE`
- `POSE_OR_VISIBILITY_OUT_OF_POLICY`
- `UNSAFE_CONTENT`
- `SENSITIVE_INFERENCE_PROHIBITED`
- `BEAUTY_OR_AGE_SCORING_PROHIBITED`
- `LEGACY_REUSE_PROHIBITED`
- `HIDDEN_NETWORK_DETECTED`
- `RESOURCE_ENVELOPE_EXCEEDED`
- `EVIDENCE_OR_DIGEST_MISSING`
- `PRIVATE_FIELD_LEAKAGE_DETECTED`
- `DOWNSTREAM_OR_PRODUCTION_BYPASS_ATTEMPTED`

P01, Q01, and O01 may add narrower reason codes but cannot remove, weaken, or make these controls overridable.

## Review result

- `ADULT_SAFETY_AND_NEGATIVE_CONTROL_REVIEW: PASS`
- `PASS_SCOPE: FUTURE_NONSEXUAL_PRIVATE_SYNTHETIC_CALIBRATION_ONLY`
- `AUTOMATED_OR_HUMAN_HARD_FAIL_OVERRIDE: PROHIBITED`
- `NEXT_REQUIRED_REVIEW: CC04-B-P01`

This result becomes effective only after this exact commit passes same-SHA CI, artifact inspection, independent Security/Privacy/Research Integrity review, independent Sol High review, and Principal acceptance. Until then S01 remains a candidate and generation remains prohibited.

## Acceptance criteria

1. Adult-presentation semantics exactly follow current ADR-030/v2 authority without age estimation or youthful-feature discrimination.
2. 04-B remains nonsexual, synthetic-only, female-oriented, China-market-first/East-Asian-presenting first coverage, and free of real/User/celebrity/scraped references.
3. Every required source, adult, decode, face-count, unsafe-content, sensitive-inference, beauty-score, network, resource, evidence, leakage, production, and downstream negative control is fail-closed and non-overridable.
4. No generation, private input, custody, Asset, identity, cohort, quota, dependency, model, schema, API, workflow, MVR, M6, P2-M7, or shared-summary change occurs.
5. Acceptance and Execution Protocol contain an exact true-EOF current-authority mirror and keep 04-B execution closed.

## Validation

- scoped Markdown formatting and `git diff --check`;
- exact three-path allowlist;
- ADR-028/029/030 and age/style-v2 semantic scans;
- required reason-code and hard-stop scans;
- no generation/private/quota/downstream execution and no binary/private leakage;
- true-EOF, sentinel, last-occurrence, and canonical/mirror equality checks;
- same-SHA CI, all artifacts, independent Security/Privacy/Research Integrity and Sol High reviews, then Principal acceptance.

## Stop and sequencing

After S01 acceptance, stop S01 and open only `CC04-B-P01`. Do not start Q01 or O01, write an execution contract, create private custody, or invoke image generation in this task.
