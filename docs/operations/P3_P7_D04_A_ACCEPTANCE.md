# P3–P7 D04-A Acceptance Evidence

## Candidate status

```text
TASK: D04-A — P4 posterior math/domain
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
HANDOFF_SHA: 7ff428549d59721cd0ee927dcf1865df7f621059
HANDOFF_BASE_SHA: 54b72a21f8493442be3fc1a1181a27d089085990
INTEGRATED_SHA: b8fa8edfb1c20731413e3a569cf5ac3eea0ba9ae
INTEGRATED_PARENT: 76eb1c6c00fa3f1729cd842f931a667c0c3cf4b6
INTEGRATED_TREE: e76ee769ae1590749e21ce772f9d081172e877cf
BRANCH: codex/p3-p7-core-demo
CURRENT_STATUS: TASK_ACCEPTED
PRINCIPAL_TASK_ACCEPTANCE: TASK_ACCEPTED
INDEPENDENT_SOL_B_HANDOFF_REVIEW: PASS
INDEPENDENT_SOL_C_INTEGRATED_REVIEW: PASS
D04_B: CLOSED_PENDING_D02_AND_D03_TASK_ACCEPTED
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This acceptance covers only the pure, one-dimensional Bayesian pairwise-logistic posterior domain and its numerical
authority. It does not accept D04-B routing/API integration, any QuestionBank, D02 screening, D03 runtime, Web flow or a
formal P4 Gate.

## Accepted file boundary

The integrated commit changes exactly:

```text
services/api/src/mirror_api/demo_posterior.py
  blob: df244f7e7f69174f449e6aec0d543212025c704e

services/api/tests/test_demo_posterior.py
  blob: 1f2744c551f94696fbc8535a1d20b2e9f3b06edb
```

Those blobs are byte-identical to the independently reviewed handoff. The handoff base is an ancestor of the integrated
parent. Intervening accepted D07-A and D09 commits do not modify the posterior module, its tests, build configuration or
consumer path. No migration, ORM, router, OpenAPI, generated client, Celery registration, Web file or private byte is
part of the D04-A diff.

## Accepted numerical authority

The domain implements a separate one-dimensional posterior per geometry dimension. A single observation can update
only its declared dimension. The accepted configuration binds the prior, tau, bounds, 32-iteration ceiling,
convergence/KKT rules, half-even quantization, contradiction floor and schema versions.

```text
POSTERIOR_CONFIG_DIGEST: a3ce13813e901b935900d7d5251802ff7873cf0d76526088e541362fa365b8de
DIRECTIONAL_RESULT_DIGEST: e9e1af7b3a88adf2dc9291293710ba20dcda08ee785d09ef5baa9d14a0ade59b
NEWTON_ITERATION_LIMIT: 32
PERSISTED_AUTHORITY: INTEGER_PPM_ONLY
RAW_FLOAT_DIGEST_AUTHORITY: FORBIDDEN
```

Accepted behavior includes:

- bounded safeguarded Newton with a strictly negative Hessian and projected/KKT boundary convergence;
- fail-closed handling for non-finite values, invalid Hessian, exhausted iterations and unsatisfied KKT conditions;
- `SKIP` excluded from likelihood and contradiction while remaining visible in ordered evidence authority;
- `INDISTINGUISHABLE` represented as a unit-likelihood response that cannot create false precision;
- Laplace uncertainty with a count-weighted contradiction floor;
- deterministic evidence ordering, complete design-cell binding, Decimal arithmetic and round-half-even integer ppm;
- distinct boundary-censored authority instead of presenting a bounded optimum as an unconstrained interior estimate.

The mandatory numerical coverage includes grid-reference, finite-difference gradient/Hessian, symmetry, choice reversal,
monotonic evidence, no-response shrinkage, contradiction uncertainty, non-convergence failure, boundary KKT and
deterministic replay. Passing this domain suite is not a claim that active routing, morphology-neighborhood scheduling or
multi-dimensional QuestionBank behavior is implemented.

## Integrated validation

The exact integrated tree was tested in Linux/Python 3.13.1 with public network disabled, proxy variables empty and the
source snapshot mounted read-only. Writable cache and local-storage roots were task-scoped under `/tmp`.

```text
POSTERIOR_PYTEST: 49/49 PASS
RUFF_FORMAT: PASS
RUFF_CHECK: PASS
STRICT_MYPY: PASS
GIT_DIFF_CHECK: PASS
PUBLIC_INTERNET_EGRESS: DENIED
PRODUCTION_PROVIDER_CALLS: 0
```

The only warning was a third-party `StarletteDeprecationWarning` imported by the repository-wide test configuration; it
did not change a D04-A assertion or result. Initial attempts to place storage/cache files on the read-only snapshot were
corrected by using task-temporary writable paths; no source or threshold changed.

## Independent review

Independent Sol B accepted the exact handoff with no findings. Independent Sol C then verified the integrated commit's
parent, tree, two-file diff, blob equality, algorithm semantics and isolated validation and returned
`PASS / FINDINGS NONE`. Neither review claimed `TASK_ACCEPTED`; that decision remains the Principal's responsibility.

## Exact-SHA CI evidence

GitHub Actions run [32661895322](https://github.com/yangyy816/project-mirror/actions/runs/32661895322) completed
successfully for exact implementation SHA `b8fa8edfb1c20731413e3a569cf5ac3eea0ba9ae`.

```text
secret-scan: PASS
docker-validation: PASS
quality-and-integration: PASS
```

The quality job passed Python quality, PostgreSQL migration lifecycle, the complete Python suite, Linux Celery,
TypeScript quality/build, browser integration, contract drift, Demo boundary validation, dependency/license audit and
SBOM generation. The repository visibility was reverified as `PUBLIC` before the authorized normal non-force push; the
scoped candidate contained no private bytes.

## Concurrent-work preservation

The pre-existing D02 work in the central worktree was neither staged nor changed by P4 integration. Its five protected
file hashes remained byte-identical before and after transplant, testing and push. The untracked P6 acceptance draft in
its detached topic worktree also remained 7,317 bytes with SHA-256
`5b7843e6c38d27dc5a1b89dd5cff248566a41e5e806438481aa04f8fee60a76b`.

## Principal decision

```text
D04_A: TASK_ACCEPTED
D04_B: CLOSED_PENDING_D02_AND_D03_TASK_ACCEPTED
P4_MULTI_DIMENSION_ACTIVE_ROUTING: NOT_VERIFIED
P4_MORPHOLOGY_NEIGHBORHOOD_ROUTING: NOT_VERIFIED
P4_STOPPING_RULE_INTEGRATION: NOT_VERIFIED
ALGORITHMIC_PROTOTYPE_PLATFORM: NOT_VERIFIED
LOCAL_WEB_AGENT: NOT_VERIFIED
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This acceptance opens no new DAG node by itself. D04-B remains gated until D02, D03 and D04-A are all
`TASK_ACCEPTED` and the Principal publishes the applicable next-wave base.
