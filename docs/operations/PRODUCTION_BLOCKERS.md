# Production Blockers

本登记只记录不阻塞当前 synthetic research、但必须在相关生产能力启用前关闭的 durable blockers。

## PRODUCTION-BLOCKER-IMAGEGEN-PROVIDER

- Status: `OPEN`
- Research impact: does not block P2 synthetic-only research under ADR-026
- Production impact: blocks all runtime image generation and any production release that depends on it
- Current production Provider: `NOT_CONFIGURED`
- Current production generation: `FAIL_CLOSED`
- Required closure evidence:
  - approved mainland-China-compatible Provider and Adapter;
  - code, SDK, dependency, license and SBOM review;
  - model terms, input/output rights and commercial-use terms;
  - retention, public/private training, data residency, subprocessors and deletion terms;
  - content safety, rate limits, cost, SLA and failover behavior;
  - approved credential location without committed values;
  - integration tests and a controlled benchmark with actual facts.

Codex native `image_gen` is an operator-assisted development source and cannot close this blocker.
