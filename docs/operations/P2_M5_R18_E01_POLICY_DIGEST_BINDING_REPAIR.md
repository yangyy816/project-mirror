# P2-M5-R18 E01 Policy Digest Binding Repair

## Status and bounded authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R18`
- `TASK_NAME: CC04-B E01 Canonical Duplicate-Review Policy Digest Binding Repair`
- `FAILED_CANDIDATE_SHA: e88cfa0e1067f78abaeddf643eb4675a1c9eb53b`
- `FAILED_CANDIDATE_RUN: 32629899685`
- `FAILED_CANDIDATE_GATE_EVIDENCE: SAME_SHA_CI_PASS;EIGHT_ARTIFACTS_PASS;SOL_HIGH_PASS;SECURITY_PRIVACY_LICENSE_RESEARCH_FAIL`
- `REPAIR_CANDIDATE: THIS_COMMIT`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ARTIFACT_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`
- `PRE_CONDITION_CURRENT_STATE: CC04_B_E01=FAILED_PENDING_FORWARD_POLICY_DIGEST_BINDING_REPAIR;CC04_B_EXECUTION=CLOSED`

R17 remains immutable failed-candidate history. Its policy semantics and `1728 < 2500` accounting were accepted by Sol
High, but its prose said to hash all bytes between backticks while its declared digest hashed only the payload value.
Security correctly failed closed. R18 repairs only the canonical byte representation and digest binding. It does not
create or access private input, a receipt, registry, root, locator, GenerationSpecification, Prompt, request, output,
Asset, identity, cohort, runtime, model, Provider, or execution-side state.

## Unambiguous canonical payload authority

- `HUMAN_DUPLICATE_REVIEW_POLICY_VERSION: p2-m5-cc04-b-e01-human-duplicate-review-v2`
- `HUMAN_DUPLICATE_REVIEW_POLICY_CANONICAL_UTF8_BYTE_LENGTH: 358`
- `HUMAN_DUPLICATE_REVIEW_POLICY_SHA256: 83b4e6350cf9cd98d034f95495d04aef88976bc0dc77f95045ab35c0d0773c62`

The sole canonical payload source is the JSON string literal on the next line:

```json
"p2-m5-cc04-b-e01-human-duplicate-review-v2|pair_set=ALL_UNORDERED_CANONICALLY_NORMALIZED_RETURNED_OUTPUT_PAIRS|order=ASC_HAMMING_THEN_ASC_PRIOR_ORDINAL|review_count=ONE_PER_PAIR|actor_role=AUTHORIZED_ACTUAL_HUMAN_REVIEWER|decisions=DISTINCT_SYNTHETIC_IDENTITY,CONFIRMED_SAME_SYNTHETIC_IDENTITY,UNCERTAIN_HARD_STOP|retry=0|free_text=0|automatic_threshold=NONE"
```

`HUMAN_DUPLICATE_REVIEW_POLICY_CANONICAL_PAYLOAD_JSON_STRING` means exactly that one RFC 8259 JSON string literal.
A validator must JSON-decode the literal, encode the resulting 358 Unicode scalar values as UTF-8 without BOM, and
hash exactly those 358 bytes. Markdown list prefixes, field names, colon, spaces, backticks, code-fence delimiters, CR,
LF, and trailing newline are never input bytes. The exact SHA-256 is the value above. Any parse, byte-length, encoding,
version, or digest mismatch returns `BLOCKED_DUPLICATE_REVIEW_AUTHORITY_MISMATCH` before private setup or another call.

## Preserved R17 policy and accounting

R18 changes no duplicate-review semantics. The deterministic candidate set remains every unordered pair of returned
outputs that reached canonical normalization, without an automatic distance cutoff. Current-ordinal pairs remain
ordered by ascending Hamming distance and then ascending prior ordinal. Exactly one Project Owner or Project
Owner-designated actual-human review is required per pair; an Agent or model cannot substitute. Decisions remain only
`DISTINCT_SYNTHETIC_IDENTITY`, `CONFIRMED_SAME_SYNTHETIC_IDENTITY`, or `UNCERTAIN_HARD_STOP`; review retry and second
opinion remain zero; free-text, sensitive, beauty, age, morphology, style-quality, and downstream judgments remain
prohibited.

The exact maxima remain:

- base Vision/measurement/categorical operations: `32 * 23 = 736`;
- Hamming comparisons: `32 * 31 / 2 = 496`;
- governed actual-human pair reviews: `32 * 31 / 2 = 496`;
- corrected inclusive maximum: `736 + 496 + 496 = 1728`;
- global ceiling: `2500`;
- remaining headroom: `772`;
- ordinal 032 maximum: `23 + 31 + 31 = 85`;
- 04-B transform operations: `0`.

All E01 request/output, 24-target, concurrency-one, retry-zero, tranche-four, 4096/4224-MiB storage, V01 runtime,
morphology, adult/safety, custody, no-threshold, holdout, downstream, production, real-user, M6, and P2-M7 boundaries
remain unchanged. Missing actual-human capability remains an execution hard stop and never authorizes Agent/model
substitution or private-byte disclosure.

## Sequencing, validation, and result

Until R18 passes exact-SHA CI, all eight artifacts, independent Security/Privacy/License/Research Integrity,
independent Sol High, and Principal acceptance, E01 and private setup remain closed. Acceptance requires an exact
three-path Markdown allowlist; scoped Prettier and `git diff --check`; R17 failure preservation; exact JSON decoding,
358-byte length, and SHA-256 verification; unchanged pair policy and `1728 < 2500` arithmetic; no private mutation;
adult/custody/holdout/downstream scans; true-EOF last-occurrence, sentinel, and canonical/mirror equality; and all remote
Gates.

- `PRIVATE_ROOT_OR_LOCATOR_CREATED: NO`
- `GENERATION_SPECIFICATION_CREATED: NO`
- `GENERATION_CALLS_EXECUTED: 0`
- `RAW_OUTPUTS_CREATED: 0`
- `ASSET_IDENTITY_OR_COHORT_CREATED: NO`
- `P2_M5_R18_RESULT: PASS`
- `CC04_B_E01_RESULT: PASS_AFTER_R18_ONLY`
- `NEXT_ACTION: EXECUTE_CC04_B_E01_PRIVATE_SETUP_AND_TRANCHE_1_MAX_4_CALLS`

These markers become effective only after every R18 Gate passes. Reject or repair only with a normal forward commit;
never amend, reset, rebase, force-push, rewrite R17, or create a post-acceptance status commit.
