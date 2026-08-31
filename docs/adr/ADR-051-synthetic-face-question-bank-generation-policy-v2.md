# ADR-051: Synthetic face and QuestionBank generation policy v2

## Status

Accepted — 2026-08-30

## Context

ADR-024 established China-first, synthetic-only coverage without sensitive-trait
routing. ADR-028 allowed a secondary 26–30 presentation range when required for
coverage. The Owner has now set a stricter long-term generation and admission
policy for subsequent synthetic faces, pairwise QuestionBanks and local Demo
selection: clearly adult 18–25 only, controlled capture, fair pair comparison,
explicit anti-homogenization and no beauty score.

The source instruction also contained the malformed phrase `18 -16: 10%`. It is
incompatible with `ADULT_ONLY_18_TO_25`, the only two allowed age bands and the
explicit prohibition on admitting minors. It therefore creates no under-18
quota or authorization.

## Decision

- All newly generated QuestionBank, pairwise, profile-input and local Demo face
  sources use only `ADULT_18_19` or `ADULT_20_25`. Any under-18 or age-ambiguous
  result fails closed before PostgreSQL admission.
- `ADULT_20_25` is the majority band. The bounded four-source E3 cohort fixes
  the distribution at three `ADULT_20_25` and one non-sexualized
  `ADULT_18_19` source.
- This decision supersedes ADR-028's 26–30 secondary-range permission for new
  QuestionBank and Demo generation after the effective date. It does not
  mutate or invalidate frozen historical P2 evidence.
- Asian/East-Asian-presenting is synthetic visual-context metadata, not a
  classifier, ancestry claim or real-user inference. Continuous morphology,
  reliability and uncertainty remain the only routing inputs.
- Source generation uses a versioned public policy profile and private prompt
  material. Prompt text, seed, locator, Provider raw detail and image bytes
  remain outside Git; tracked authority stores only allowlisted metadata and
  typed digests.
- `GEOMETRY_PAIR` changes one declared geometry dimension for the same base
  synthetic identity and fixed capture conditions. `STYLE_PAIR` preserves
  primary geometry and changes one controlled style axis. Both sides must pass
  visual quality, variable isolation and fair-comparison gates.
- No beauty score, attractiveness ranking, sensitive inference, celebrity
  resemblance, real-person reproduction or production-validity claim is
  introduced.
- E3 source policy metadata is canonical PostgreSQL authority. QuestionPair
  identity/side/dimension and pair QA remain in the existing versioned
  QuestionPair and screening authorities; the admission trigger validates the
  four-source age distribution, unique identity families and complete
  16-pair/32-side graph in one transaction.
- A failed generation, persistence, adult/quality review, runtime execution or
  screening step consumes the current ordinal/cohort as defined by E3 and
  produces zero partial QuestionBank admission rows. No Provider retry is
  authorized.

## Alternatives considered

- Preserve ADR-028's 26–30 secondary range for new QuestionBanks.
- Interpret the malformed `18 -16` text as permission to generate minors.
- Bind the policy only by an opaque digest without semantic database checks.
- Use visual attractiveness scores or demographic labels to balance a batch.
- Lower pair QA after seeing outputs or admit one obviously worse side.

## Consequences

The policy is narrower and easier to audit, but some generated adult sources
will be rejected rather than admitted. Frozen M3/M4 capability authority is not
reopened. D02 E3 schemas and digests change before any E3 Provider call or row
exists, so no historical authority is rewritten. Formal P3–P7, real-user
validity, production security and production release remain unchanged.

## Validation implications

- Test three `ADULT_20_25` plus one `ADULT_18_19` source and reject any other
  band, age ambiguity or relabelled policy profile.
- Test canonical metadata/digest replay in Python and PostgreSQL.
- Test fixed capture/profile diversity, unique base identity families and no
  prompt/path/locator field propagation.
- Preserve existing 4-source, 48-case, 96-M4, 144-result-M3, 24-screened-pair,
  16-selected-pair and atomic rollback gates.
