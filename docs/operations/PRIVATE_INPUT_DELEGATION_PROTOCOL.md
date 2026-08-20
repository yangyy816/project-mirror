# Principal-Managed Private Input Delegation Protocol

## Authority and invariants

Authority: ADR-049. This protocol applies to every Project Mirror bounded task that consumes untracked or controlled
input. It does not supersede a stricter task ADR, ADR-048, Legal/Consent/Privacy/Security Gates or production approval.

```text
PRIVATE_INPUT_OWNER_HANDOFF_ONCE
SUBAGENT_NO_PRIVATE_DISCOVERY
PRIVATE_INPUT_NON_PROPAGATION
PRINCIPAL_RETAINS_AUTHORITY
```

Owner releases an unchanged input for an unchanged authorized purpose once. Principal owns all later classification,
verification, custody, least-privilege handoff, revocation, cleanup and integrated acceptance.

## Classification

| Class                        | Default handling                                                                                    |
| ---------------------------- | --------------------------------------------------------------------------------------------------- |
| `PUBLIC_REPOSITORY_INPUT`    | Normal workspace access                                                                             |
| `TRACKED_INTERNAL_INPUT`     | Only task-relevant Agent context                                                                    |
| `PRIVATE_NONSENSITIVE_INPUT` | Task-scoped handoff after exact validation                                                          |
| `PRIVATE_SENSITIVE_INPUT`    | Read-only, exact digest, no Git/artifact/Prompt/plaintext propagation                               |
| `SECRET_CREDENTIAL`          | Process-bound approved injection only; sub-agent sees presence, never value                         |
| `REAL_USER_SENSITIVE_INPUT`  | Closed unless the existing legal, consent, privacy and security Gates explicitly open the exact use |

Use the strictest applicable class. Native image or model availability does not change classification or production
qualification.

## Principal registry

The registry is memory-only or outside Git. Each record contains:

```text
INPUT_ID
CLASSIFICATION
AUTHORITY
EXPECTED_DIGEST
ACTUAL_DIGEST
BYTE_SIZE
READ_ONLY
ALLOWED_TASK_IDS
ALLOWED_AGENT
ALLOWED_OPERATION
PROHIBITED_OPERATION
CUSTODY_STATUS
HANDOFF_STATUS
CLEANUP_STATUS
```

Absolute private paths, secret values and Prompt text are prohibited from durable evidence. A path supplied by Owner
is a capability, not permission to enumerate its parent.

## Principal private-output registry

Every private output created by Principal or a sub-agent must remain recoverable for its approved retention window. A
Git-external registry records:

```text
INPUT_OR_OUTPUT_ID
CREATING_TASK
CREATING_AGENT
OPAQUE_LOCATOR
EXPECTED_DIGEST
ACTUAL_DIGEST
BYTE_SIZE
AUTHORITY
RETENTION
ALLOWED_FUTURE_TASKS
CUSTODY
CLEANUP_STATUS
```

Sub-agents return the authority and recoverable locator to Principal before completion. Principal owns later handoff
and may not ask Owner to recreate or re-upload task-owned output. Recovery must start from the exact task receipt,
registry or preserved task-owned volume; it must not scan broad disks, user homes, unrelated projects or protected
temporary roots. If bounded recovery fails, report `EVIDENCE_LOCATION_LOST` and use forward change control rather than
silently regenerating legacy evidence.

Tracked docs may retain only opaque ID, digest, authority, retention and status. Private bytes and locator stay outside
Git and ordinary CI.

## Required handoff packet

Every private-input delegation adds this block to the normal bounded-task contract:

```text
PRIVATE_INPUT_HANDOFF
TASK_ID
AGENT_ROLE
INPUT_IDS
AUTHORIZED_PURPOSE
READ_PERMISSION
WRITE_PERMISSION
EXPECTED_DIGESTS
MAX_BYTES
ALLOWED_OUTPUTS
FORBIDDEN_OUTPUTS
NETWORK_POLICY
CLEANUP_REQUIREMENT
ESCALATION_CONDITION
```

The packet grants only the exact task, role, input and operation. A sibling or later task has no derived authority.
Sub-agents must not search, glob, enumerate parent directories, request a broader root or reuse an input from another
task. Missing scope returns `PRIVATE_INPUT_SCOPE_EXPANSION_REQUIRED` to Principal.

## Handoff selection and lifecycle

Select the first method that the current runtime can prove safe:

1. inherited task-scoped attachment or handle;
2. exact task-scoped read-only reference;
3. task-scoped environment reference;
4. byte-identical temporary private copy;
5. `PRINCIPAL_EXECUTES_SENSITIVE_STEP`, followed by redacted reviewer input.

For a temporary copy:

- use a repository-external root or ignored `.private-handoff/<unpredictable-task-token>/`;
- copy only the exact Owner-released file, never a directory;
- verify regular/non-reparse type, maximum bytes and SHA-256 before and after copying;
- make the copy read-only where supported;
- expose only the exact capability required by the runtime, not its parent;
- revoke and remove it at task completion, then verify absence;
- record only input ID, digest, `HANDOFF_COMPLETE` and `CLEANUP_COMPLETE` durably.

`.gitignore` is defense in depth, not access control. If runtime isolation cannot enforce the packet, Principal executes
the sensitive step.

## Fail-closed outcomes

Return `OWNER_ACTION_REQUIRED` only when the original input is missing, its authority/digest cannot be proved,
permission/custody cannot be established, consent/use changed, an external system must reissue it or secret/legal
authorization changed. Starting a new sub-agent alone is not a reason to ask Owner again.

Digest/type/size/scope/agent/task/network/output mismatch stops before use. Cleanup uncertainty keeps the task
unaccepted. Secret values are never copied. Real-user sensitive inputs remain closed by default.

## Git, CI and logging

- Never add private inputs or handoff roots to Git.
- Ordinary CI receives only tracked synthetic tests and redacted aggregate evidence.
- Never upload a handoff root as an artifact or include it in cache paths.
- Never log absolute private paths, bytes, directory listings, Prompt text, raw exceptions or secret values.
- MEMORY may record the durable governance decision only; it must not record paths or secrets.

## CC02 binding

CC02 inherits this protocol and retains stricter ADR-048 custody. The two legacy reports are prior Principal Stage C
`PRIVATE_SENSITIVE_INPUT` outputs. Recovery is allowed only from the original task receipt/registry/task-owned root;
broad disk discovery and regeneration are prohibited. Principal verifies them and is the default unique builder
executor. Reviewers receive only the tracked manifest/preregistration and redacted status; CI never receives either
report.

## Synthetic reference validation

`scripts/governance/private_input_handoff.py` is a zero-network reference state machine for policy tests. It models
exact registration, task/role authorization, non-propagation, byte-identical handoff and cleanup. It is not a secure
cross-process broker and does not authorize real private input or replace runtime custody controls.
