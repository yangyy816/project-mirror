# Dependency, Model and Runtime Qualification Tiers

## Authority and purpose

ADR-043 / `CC-GOV-QUAL-01` defines progressive qualification for important third-party dependencies, models,
weights, native runtimes, research algorithms, Provider SDKs, visual/edit engines and Agent runtimes. The objective
is proportional evidence, not reduced quality. This document applies forward only and does not rewrite frozen
Project Mirror evidence or weaken an active Milestone protocol.

## Mandatory candidate record

Every important candidate report must contain:

```text
QUALIFICATION_TIER
CURRENT_STATUS
APPROVED_SCOPE
PROHIBITED_SCOPE
CANONICAL_PLATFORM
SUPPORTED_PLATFORMS
REAL_USER_DATA_ALLOWED
PRODUCTION_ALLOWED
NETWORK_POLICY
LICENSE_STATUS
MODEL_STATUS
DISTRIBUTION_STATUS
REPRODUCIBILITY_LEVEL
SBOM_STATUS
VULNERABILITY_STATUS
NEXT_PROMOTION_GATE
```

Unknown values remain `NULL` or `NOT_VERIFIED`; they are never inferred from a permissive top-level license,
upstream claim, package name, successful import, Mock, PoC output or model card alone.

## State machine

```text
CANDIDATE
→ RESEARCH_QUALIFIED
→ INTERNAL_ENGINE_CANDIDATE
→ APPROVED_FOR_INTERNAL_ENGINE
→ PRODUCTION_CANDIDATE
→ PRODUCTION_APPROVED
```

Allowed terminal or blocking states are `REJECTED`, `FURTHER_RESEARCH`, `DEFERRED_EXTERNAL_DEPENDENCY`,
`LICENSE_REVIEW_REQUIRED`, `SECURITY_REVIEW_REQUIRED`, `PRIVACY_REVIEW_REQUIRED` and `PRODUCTION_BLOCKED`.
Promotion always requires a Principal decision. Evidence may be reused; approval scope may not be inherited.

## Tier 1 — Research

### Purpose

Prove or disprove technical feasibility in a bounded isolated environment without claiming internal-engine or
production readiness.

### Entry

- A concrete research question, baseline, budget, stop condition and owner are preregistered.
- Exact upstream source/package/artifact/model identifiers and trusted URLs are known.
- No real-user data, production credential, public endpoint or production configuration is required.

### Required evidence

- Exact version/source URL and SHA-256; code, model, weights and dataset terms are separate records.
- Basic license, obvious security/privacy, artifact-origin and high-risk dependency disposition.
- Synthetic-only or non-sensitive fixture provenance.
- Linux isolated virtualenv/container/private PoC root unless the capability is inherently platform-specific.
- Bounded CPU, memory, disk, time and retry budget.
- Deterministic seed or auditable nondeterminism facts.
- Network deny/capture or a complete bounded allowlist; no hidden telemetry or unbounded network.
- Successful and failed attempts retained as evidence.

### Exit

The result is exactly one of `RESEARCH_QUALIFIED`, `REJECTED` or `FURTHER_RESEARCH`. Research qualification does not
authorize project-wide installation, internal runtime integration, distribution, production or real-user data.

## Tier 2 — Internal Engine

### Purpose

Authorize a candidate for one named private synthetic pipeline, internal QuestionBank factory, test system or
non-production engine scope.

### Entry

- The Research Gate is complete.
- The exact phase/milestone, data class, runtime boundary and integration owner are named.
- The candidate is behind a first-party port/adapter and cannot become domain authority.

### Required evidence

- Linux canonical runtime and Docker compatibility with at least two clean reproduction roots.
- Exact runtime/artifact hashes, declared determinism and same-platform reproducibility.
- Windows functional compatibility when Windows is a development or validation platform. Byte-identical Windows
  artifacts are required only when the claim, distribution platform or frozen Milestone protocol requires them.
- Dependency/license inventory, private SBOM and vulnerability disposition.
- Private-path, telemetry and network scans; bounded or zero-network proof.
- Negative controls, resource ceilings, failure/retry/recovery behavior and project integration tests.
- Production configuration remains fail closed.

### Exit

The approval must be scope-specific, for example `APPROVED_FOR_PRIVATE_SYNTHETIC_M4`. It never authorizes real-user
photos, production deployment, public APIs, public release, hosted commercial calls, cross-border processing,
redistribution, payment or launch.

## Tier 3 — Production Candidate

### Purpose

Submit an internal-engine-qualified candidate to the complete production-deployment qualification process.

### Entry and required evidence

- All Internal Engine evidence is complete for the proposed production use.
- Every supported platform and the exact production image/runtime are qualified.
- Production SBOM, full transitive inventory, license notices and separated code/model/weight/data/commercial terms
  are reviewed for commercial use, redistribution and derivative use.
- Vulnerability, security, privacy, telemetry, region, retention, training, deletion, subprocessor and credential
  reviews are complete.
- Production network allowlist, resource ceilings, P50/P95, concurrency, failure rate, cost, failover, rollback,
  observability, incident response, backup and recovery are verified.
- Production-like staging, same-SHA CI/artifacts and independent security/final reviews pass.

### Exit

`PRODUCTION_CANDIDATE` is not an enablement decision. The capability remains fail closed until the responsible Phase
records `PRODUCTION_APPROVAL: GRANTED`. Facial-data processing additionally requires Legal/Consent/PIPIA/Security
approval; payment, public launch, cloud resources and external terms retain their own owner-authorized Gates.

## Permanent rules across every tier

- Exact provenance; unknown facts remain `NULL`.
- Synthetic-only and no real-person fixture unless independently authorized.
- No sensitive inference, beauty score or hidden population target.
- Provider/Adapter boundary and PostgreSQL authority.
- No credential in Git, arbitrary URL, unbounded network or hidden telemetry.
- No unapproved model weight, silent dependency adoption or production claim from a Mock.
- No threshold relaxation after holdout and no fake PASS.
- Research never promotes automatically to internal or production use.

## Grandfathered evidence

| Existing scope                     | Classification                                                    | Meaning                                                                                               |
| ---------------------------------- | ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| P2-M3 Vision/runtime qualification | `LEGACY_STRICT_QUALIFICATION`; `EXCEEDS_CURRENT_RESEARCH_MINIMUM` | Frozen evidence remains valid and is not reopened or downgraded.                                      |
| P2-M4 OpenCV 5 bounded closure     | `APPROVED_FOR_PRIVATE_SYNTHETIC_M4`                               | Scope-specific Internal Engine approval only; no production, distribution or real-user authorization. |
| P2-M5 current evaluation protocol  | Unchanged active protocol                                         | ADR-043 cannot relax complete-case, threshold, split, holdout, MVR or stop rules.                     |

## Promotion checklist

Before every promotion, the Principal verifies the actual diff, exact artifacts, applicable benchmark, security and
privacy impact, license/model/data status, supported platform evidence, approved/prohibited scope, and next promotion
Gate. A worker or upstream `PASS` is evidence only.

`PROGRESSIVE_QUALIFICATION: ACTIVE_FORWARD_ONLY`

`CURRENT_P2_M5_ACCEPTANCE_IMPACT: NONE`

`PRODUCTION_APPROVAL: NOT_GRANTED_BY_THIS_DOCUMENT`
