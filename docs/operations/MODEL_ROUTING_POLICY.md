# Project Mirror Model Routing Policy

## Status and objective

- Status: `ACCEPTED`
- Scope: Codex engineering workflow only; it does not change product requirements, Phase objectives, architecture, security/privacy invariants, research hypotheses, or acceptance Gates.
- Objective: use the lowest-cost model that can reliably complete the task, while keeping architecture and integrated acceptance with higher-authority agents and preserving the user's interactive model choice.

## Five execution tiers

| Tier | Model / role        | Use                                                                                                            |
| ---- | ------------------- | -------------------------------------------------------------------------------------------------------------- |
| 1    | Sol High            | Architecture, high-risk decisions, Phase/Milestone planning, task decomposition and integrated final review    |
| 2    | Terra High          | Difficult implementation with frozen contracts: deep control flow, concurrency, transactions and subtle bugs   |
| 3    | Terra Medium        | Default bounded implementation, tests, ordinary refactors and coordinated but well-understood multi-file work  |
| 4    | Luna Medium         | Deterministic batch changes, format conversion, documentation sync, extraction and template-driven scaffolding |
| 5    | GPT-5.3-Codex-Spark | Small, precise, atomic, reversible and mechanically verifiable low-latency micro tasks                         |

Luna, Terra and Spark may not redefine the Master Specification, Phase/Milestone objectives, architecture, invariants or Gates. Worker PASS is evidence; only the Principal may accept integrated work or decide a Milestone/Phase Gate.

## Default routing and escalation

- Use one agent by default. Delegate only when parallelism, isolation or independent review materially improves speed or quality.
- Use Terra Medium for ordinary bounded work. Do not select Terra High merely because a task spans multiple files.
- Use Terra High only when the objective and contract are frozen and implementation difficulty is established by control-flow, failure-path, concurrency, transaction or boundary evidence.
- Use Luna for repetitive, deterministic work where rules and validation are explicit. Ambiguity or business logic escalates to Terra Medium.
- Use Spark for immediate atomic edits, not for cheap batch processing.
- Use Sol High for architecture, schema or public-contract decisions, security/privacy/authentication/billing decisions, Milestone/Phase planning and final Gate review.
- Default escalation is `Spark/Luna -> Terra Medium -> Terra High -> Sol High -> Principal`.

Every delegated task follows the bounded-task contract in the root `AGENTS.md`, including `BOOTSTRAP_STATUS`, scope, allowed and forbidden areas, acceptance criteria, validation commands, recommended role/tier, output format and escalation condition.

## Private-input routing

- Principal alone classifies private input, validates authority/digest/type/scope, establishes custody, selects the
  handoff mechanism and retains final Gate authority. Model cost never justifies broader input access.
- Terra Medium/High may consume only the exact task-scoped input listed in `PRIVATE_INPUT_HANDOFF`. Luna may perform
  deterministic private processing only when authority and outputs are fully frozen. Spark is denied secret,
  real-user-sensitive, private facial, architecture-sensitive or uncontrolled research input by default.
- Access is non-transitive across agents and tasks. A worker that needs another input stops with
  `PRIVATE_INPUT_SCOPE_EXPANSION_REQUIRED`; it never discovers or enumerates private storage.
- If the runtime cannot enforce least privilege or a stricter ADR requires immediate Principal custody, use
  `PRINCIPAL_EXECUTES_SENSITIVE_STEP` and give reviewers only tracked/redacted outputs.
- Secret values use approved process-bound injection only and are never placed in an Agent packet. Real-user-sensitive
  input remains behind the existing Legal/Consent/Privacy/Security Gates.
- Any worker that creates private output must return its opaque recoverable locator, digest, authority, retention and
  cleanup state to Principal before completion. Routing completion without that handback is `BLOCKED`, not PASS.

The authoritative lifecycle and packet fields are ADR-049 and
`docs/operations/PRIVATE_INPUT_DELEGATION_PROTOCOL.md`.

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

Spark escalation path:

```text
Spark -> Terra Medium -> Terra High -> Sol High -> Principal
```

Unavailable or rate-limited Spark work falls back to Terra Medium, not automatically to Sol.

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
- Project batch agent: `pm_luna_worker` in `.codex/agents/pm-luna-worker.toml` using `gpt-5.6-luna` with medium reasoning.
- Difficult bounded implementation agent: `pm_terra_high_worker` in `.codex/agents/pm-terra-high-worker.toml` using `gpt-5.6-terra` with high reasoning.
- The default subagent is `gpt-5.6-terra` with medium reasoning. Backend, data, frontend, infrastructure and test workers use Terra Medium; the security reviewer remains Terra High; planning and final review remain Sol High.
- Project `.codex/config.toml` intentionally does not define a top-level `model`, `model_reasoning_effort` or plan-mode model. The user remains free to select and change the Principal model from the conversation UI; project routing only binds delegated roles.
- Project concurrency is capped at four threads, but the default remains single-agent execution.
- Python 3.13 `tomllib` parses every project TOML, verifies unique agent names, and asserts that Principal model keys are absent.
- The current desktop sandbox cannot execute the ACL-protected WindowsApps `codex.exe`, so discovery of newly added named agents requires a fresh conversation and remains the only unexecuted smoke check.
