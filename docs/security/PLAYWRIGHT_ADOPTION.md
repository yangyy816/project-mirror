# Playwright Test Adoption Record

## Status

`APPROVED_FOR_TEST_ONLY` — 2026-08-15

## Scope and purpose

P1-M2-T06 requires real-browser evidence for session bootstrap, protected-route gating, onboarding, refresh recovery and logout. `@playwright/test` is approved only as a pinned development dependency and CI/browser-test runner. It is not a production runtime dependency, Provider, product SDK or authority for authentication state.

## Upstream evidence

- Package: `@playwright/test@1.62.1`
- Registry: npm public registry
- Repository: `https://github.com/microsoft/playwright`
- License reported by npm package metadata: `Apache-2.0`
- Node engine reported by npm package metadata: `>=20`; Project Mirror uses Node 24
- npm dist integrity: `sha512-DTcUc8qii+cpHvtOwggMtBRMjKZHXYWdw8syRYu2vtzuq4Wxphqq4NfCs5Zt44L6mA8rfDfj+PHnxFc/FeK6mQ==`
- Verification command: `npm.cmd view @playwright/test version license repository.url dist.integrity engines --json`

The package lock is authoritative for the resolved transitive dependency graph. CI must run the existing Node license inventory and high-severity vulnerability audit after installation.

## Controls

- Tests use only deterministic synthetic account fixtures and local Fake API/provider behavior.
- Browser installation occurs in CI/test preparation and is not copied into Project Mirror production images.
- Tests must not call real SMS, age assurance, storage, AI or payment providers.
- Traces, screenshots and videos are test artifacts and must not contain real phone numbers, credentials, faces or user data.
- Playwright cannot weaken API authorization, browser token rules, CSRF, popup validation or production fail-closed configuration.

## Change-control decision

The earlier OSS addendum statement that P1-M2 adds no dependencies applies to proposed AI/model/Makeup research dependencies. This narrowly scoped test-only dependency is approved because T06 already requires authoritative browser evidence and the standard must not be replaced by a simulated DOM test. Any production/runtime use requires a new review.
