# P3–P7 Synthetic Face Generation Policy v2

## Decision status

```text
STATUS: PRINCIPAL_ACCEPTED_OWNER_POLICY
POLICY_VERSION: project-mirror-synthetic-face-generation-v2
EFFECTIVE_DATE: 2026-08-30
SCOPE: SYNTHETIC_FACE / QUESTION_BANK / PAIRWISE / LOCAL_DEMO
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This policy governs future synthetic source generation, QuestionBank admission,
pair construction, QA and Demo selection. It does not authorize real-person
processing or convert synthetic evidence into production or real-user validity.

## Adult-only boundary

All QuestionBank, pairwise, profile-input and Demo face sources are clearly adult
synthetic persons in the declared 18–25 age range. Allowed age bands are only:

- `ADULT_18_19`;
- `ADULT_20_25`.

No under-18 sample may enter generation admission, preference learning or Demo
selection. The malformed `18 -16` percentage in the Owner source instruction is
incompatible with `ADULT_ONLY_18_TO_25`, the allowed age bands and the explicit
minor prohibition; the adult-only rules govern. Operational batches should be
predominantly `ADULT_20_25`; a four-source batch uses three `ADULT_20_25` sources
and one non-sexualized `ADULT_18_19` source.

## Generation priorities

1. Clearly adult, synthetic-only and safe.
2. Fixed capture conditions and controlled variables.
3. Asian/East-Asian-presenting visual context, without sensitive-trait inference.
4. Both pair sides remain visually complete and product-acceptable.
5. Meaningful face-shape, feature-proportion and style variation.
6. Anti-homogenization; no single influencer or template-face convergence.
7. Broader visual diversity only after the above gates hold.

No beauty score, ranking or universal attractiveness label is created. Visual
quality and pair comparability are admission gates, not attractiveness labels.

## Fixed capture grammar

Unless a declared dimension requires otherwise, every source and pair side uses:

- front-facing head pose and direct eye contact;
- neutral or slight natural expression;
- stable shoulder/neck posture and equivalent head scale;
- equivalent lens perspective and close portrait framing;
- soft stable lighting and clean low-distraction background;
- light natural makeup, simple clothing and no prominent accessories;
- unobstructed key facial features;
- natural anatomy, texture and color without heavy retouching.

Reject side views, high/low camera angles, major head rotation, exaggerated
expression, facial occlusion, lighting/background dominance, sexualized context,
celebrity resemblance, real-person reproduction or obvious structural defects.

## Controlled pair families

`GEOMETRY_PAIR` uses the same synthetic base identity, age band, pose, expression,
camera, lighting, hair, makeup, clothing and background. It changes exactly one
declared geometry dimension, with at most one necessary coupled variable, and
preserves unrelated facial attributes.

`STYLE_PAIR` preserves primary facial geometry and changes one declared style
axis such as natural/refined, warm/cool, soft/sharp, sweet/cold or relaxed/polished.
Makeup, clothing, pose, exposure and expression may not manufacture the choice.

Both sides must pass visual quality, variable isolation and comparability. A pair
with an obvious bad answer is rejected rather than admitted with a lower QA bar.

Geometry coverage may include face shape, jaw width, chin height, face length,
cheekbone prominence, eye spacing/length/openness, midface length, nose bridge
or tip scale, lip fullness, forehead height and facial-thirds ratio. Every
dimension remains physiologically plausible, visually natural and explicitly
versioned. The E3 screening preregistration remains limited to its frozen
`jaw_width`, `chin_height` and `eye_spacing` candidate set.

Style coverage may include clear-natural, translucent/refined, gentle-sweet,
refined-cool, relaxed-polished, sharp, confident or individually distinctive
adult presentations. It may not converge to a single influencer/template face
or use sexualized pose, revealing clothing, heavy makeup, hairstyle or
background as the deciding variable. Mature/refined expression is limited to
the `ADULT_20_25` band; `ADULT_18_19` remains non-sexualized.

## Provider prompt policy

Private Provider prompts must express these semantic requirements:

- clearly adult and declared 18–25 age band;
- Asian/East-Asian-presenting visual context;
- front-facing, direct gaze, neutral natural expression;
- stable soft lighting, neutral background and consistent framing;
- natural facial anatomy and a synthetic non-real person;
- no resemblance to celebrities, public figures or identifiable real people.

Geometry-pair prompts additionally require the same base identity and capture
conditions, one named dimension change and preservation of unrelated attributes.
Prompt text, seeds, Provider details and output locators stay outside Git, normal
logs, `MEMORY.md` and the UI. Tracked authority stores only versioned policy and
request digests.

## Admission metadata and gates

Each source or pair projection records the synthetic identity, declared age band,
adult state, visual context, style family, geometry dimensions, controlled and
preserved variables, generation/provider versions, prompt-policy version, source
digest, QA result/reason, pair side and base identity family.

The authority is distributed without duplication:

- the source policy profile records age band, visual context, style family,
  planned geometry dimensions, controlled/preserved variables, abstract
  generation kind/version, prompt-policy version and base identity family;
- the immutable source authority records source digest and source-level QA;
- `DemoSyntheticIdentity` binds the admitted synthetic identity;
- `DemoQuestionPair` plus its strict QA payload records pair ID, both sides,
  dimension, magnitude, source/result lineage, comparability and variable
  isolation;
- the atomic admission binds the four sources, one Report, one bank and all 16
  selected pairs. No opaque digest alone substitutes for semantic validation.

QuestionBank admission requires:

```text
adult_status = VERIFIED_SYNTHETIC_ADULT
declared_age_band IN {ADULT_18_19, ADULT_20_25}
suspected_minor = false
real_person_reference = false
celebrity_resemblance = false
pair_comparability = PASS
variable_isolation = PASS
visual_quality = PASS
anti_homogenization = PASS
```

Batch QA also checks template-face concentration, style and morphology coverage,
age ambiguity, background/makeup confounding, pair quality imbalance and multiple
simultaneous variable changes. Failed samples are rejected or regenerated under a
new authorized batch; thresholds are not lowered after seeing results.

Core generation acquisition may use an approved local proxy only during the
bounded acquisition step. Runtime M3/M4, screening, PostgreSQL, Redis/Celery,
FastAPI, Next.js and private object storage must complete with public Internet
egress denied. Runtime/model/config/weights identities and the versioned recipe
must be verified before a Provider call; a recipe template is not execution
evidence.

## E3 application

E3 contains four new source identities: three `ADULT_20_25` and one
`ADULT_18_19`. It is independent of failed-closed E2 bytes and authority. E3 uses
four primary generation calls, concurrency one, one output per call and no retry
or reserve. A consumed ordinal that fails generation or durable persistence stops
the cohort with zero PostgreSQL admission rows.

E3 remains independent of E2, uses a new task/epoch/output namespace and never
repairs, resigns or represents the unrecoverable E2 bytes. Each successful call
must be durably persisted as PNG, rehashed and decoded, deterministically
normalized to JPEG, bound to a DurableSourceDescriptor and terminal receipt,
then registered under the designated two-copy private evidence root before the
next ordinal begins.
