# P2-M5 CC04-B E01 First-Wave East-Asian-Presenting Generation Policy

- `POLICY_VERSION: p2-m5-cc04-b-e01-first-wave-east-asian-presenting/v1`
- `OWNER_DECISION_ID: OD-P2-M5-CC04-B-E01-R29-001`
- `EFFECTIVE_ORDINAL_RANGE: CAL-REQ-002_TO_CAL-REQ-032_AFTER_A02_ACCEPTANCE_ONLY`

## Approved presentation context

The first China-market-first invite-only Beta wave uses the generation presentation context
`EAST_ASIAN_PRESENTING_ADULT_SYNTHETIC_FACES`. It applies only to synthetic adult generation priority, not to
classification of people. It is not race, ethnicity, ancestry, nationality, a user-routing label, a sensitive identity
field, or an inference about any real person. Persist only `PRESENTATION_CONTEXT: EAST_ASIAN_PRESENTING_FIRST_WAVE`;
do not persist `ETHNICITY: ASIAN` or equivalent labels.

## Diversity and safety invariants

The priority preserves the frozen six morphology cells and six style cells, continuous morphology diversity, upper/
mid/lower-face geometry diversity, face-shape and proportion diversity, and non-sensitive style-context diversity.
It requires standardized lighting/background/expression and prohibits a hidden ideal face, homogenization, celebrity
or real-person imitation, beauty scoring/ranking, sensitive-trait inference, sexualization, child/student-minor
context, and Prompt or image-byte publication.

## Downstream restriction

This policy does not itself generate an image, admit an identity, modify a QuestionBank, or open MVR/M6. A first-wave
candidate remains synthetic-only, non-user, non-production, and `INVITE_ONLY_BETA_PENDING_HUMAN_SECOND_ROUND` until all
separate E01, 04-C, 04-D, 04-E, M5 technical, MVR, M6, immutable-manifest, and revocation Gates pass.
