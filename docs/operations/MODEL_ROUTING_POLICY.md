# Project Mirror Model Routing Policy

## Status and objective

- Status: `ACCEPTED`
- Scope: Codex engineering workflow only; it does not change product requirements, Phase objectives, architecture, security/privacy invariants, research hypotheses, or acceptance Gates.
- Objective: use the fastest model that can safely complete an already-bounded task, while keeping architecture and integrated acceptance with higher-authority agents.

## Three execution tiers

| Tier | Model / role        | Use                                                                                                                                          |
| ---- | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Sol High            | Planning, architecture-aware decomposition, risk decisions, acceptance definitions, integrated final review                                  |
| 2    | Terra High          | Bounded engineering across one or more coordinated files/modules, integration, investigation, tests, infrastructure and security remediation |
| 3    | GPT-5.3-Codex-Spark | Small, precise, atomic, reversible and mechanically verifiable micro tasks                                                                   |

Neither Terra nor Spark may redefine the Master Specification, Phase/Milestone objectives, architecture, invariants or Gates. Worker PASS is evidence; only the Principal may accept integrated work or decide a Milestone/Phase Gate.

## SPARK eligibility gate

A task is Spark-eligible only when every applicable SPARK condition is true:

- **Small**: normally 1–3 closely related files and a localized change.
- **Precise**: expected behavior and exact change are already decided.
- **Atomic**: it can be reviewed independently without coordinated architectural changes.
- **Reversible**: it can be reverted without a data/migration recovery strategy.
- **Known validation**: a specific test, lint, typecheck, build, snapshot or deterministic reproduction exists.

When uncertain between Spark and Terra, choose Terra. When architecture may be involved, escalate to Sol.

## Required Spark task contract

Every Spark delegation must state:

```text
OBJECTIVE
ALLOWED FILES / AREA
EXPECTED CHANGE
FORBIDDEN CHANGES
VALIDATION
```

Spark may not expand scope, invent behavior, add major dependencies, edit generated code instead of its source, weaken tests, fake success, or make speculative adjacent fixes.

Spark must not autonomously decide authentication/authorization, cryptography, secrets, rate limits, consent, facial-data handling, signed URLs, payments, database schema/migration/transaction semantics, retention, `SelfState`, `IdentityAnchor`, `DesiredDeltaProfile`, evidence precedence, anti-homogenization, Profile/original-image/CreditLedger immutability, or any other security-sensitive/domain invariant. An exact pre-approved mechanical fix in such an area still requires downstream review.

## Stop and escalation

Spark must return `ESCALATION_REQUIRED` without expanding implementation when architecture, public API redesign, unclear security/database semantics, conflicting ADR/specification, unrelated failures, cross-subsystem coordination, or materially larger scope is discovered.

Escalation path:

```text
Spark -> Terra -> Sol -> Principal
```

Unavailable or rate-limited Spark work falls back to Terra, not automatically to Sol.

## Validation and output

Spark always runs the smallest relevant validation. A change without required validation is `IMPLEMENTED_NOT_VERIFIED`, never `PASS`. Shared/public-contract changes trigger progressively broader validation; authoritative Milestone and Phase suites remain mandatory.

Every Spark report contains:

```text
TASK
FILES_READ
FILES_CHANGED
CHANGE_SUMMARY
VALIDATION_EXECUTED
VALIDATION_RESULT
SCOPE_DEVIATION
DISCOVERED_ADJACENT_ISSUES
ESCALATION_REQUIRED
```

Future bounded-task plans should also record `RECOMMENDED_AGENT`, `RECOMMENDED_MODEL_TIER`, routing rationale and escalation condition.

## Configuration evidence

- Official model identifier: `gpt-5.3-codex-spark`.
- Project agent: `pm_fast_worker` in `.codex/agents/pm-fast-worker.toml`.
- The existing default remains `gpt-5.6-terra`; existing Sol/Terra agents remain unchanged.
- The installed local Codex CLI is `0.148.0-alpha.9`. The WindowsApps executable is ACL-protected in the desktop sandbox; the app-managed `.codex/.sandbox-bin/codex.exe` entry completed fresh version, dynamic-model-catalog and strict-config checks.
- Current official OpenAI documentation confirms project-scoped custom agents, the exact Spark identifier, and `medium` reasoning in a Spark custom-agent example.
- A read-only, ephemeral CLI smoke started `gpt-5.3-codex-spark` with `medium` reasoning and completed without modifying project files.
- A read-only named-agent smoke discovered `pm_fast_worker`, delegated one no-tool task and returned the required contract, validation and escalation rules. The first ephemeral delegation attempt could not create a child thread; the normal read-only retry passed.
- Non-blocking local warnings remain: the `.sandbox-bin` copy lacks `codex-code-mode-host.exe`, PowerShell shell snapshots are unsupported, and two plugin icon paths are ignored. None prevented strict config parsing, direct Spark execution or named-agent delegation.
