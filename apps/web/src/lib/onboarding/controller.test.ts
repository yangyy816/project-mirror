import { describe, expect, it, vi } from "vitest";

import { BrowserAuthError } from "../auth/errors";
import type { BrowserSessionSnapshot } from "../auth/session";
import type { WebAuthConfig, WebPolicyManifest } from "../web-auth-config";

import { OnboardingController, policyIdentity } from "./controller";

const privacyPolicy: WebPolicyManifest = {
  document_code: "privacy",
  document_version: "2026-08-15",
  document_digest: "a".repeat(64),
  title: "隐私政策",
  content_url: "https://policy.test/privacy",
  status: "approved",
};

const termsPolicy: WebPolicyManifest = {
  document_code: "terms",
  document_version: "2026-08-15",
  document_digest: "b".repeat(64),
  title: "用户协议",
  content_url: "https://policy.test/terms",
  status: "approved",
};

function createConfig(
  policies: readonly WebPolicyManifest[] = [privacyPolicy, termsPolicy],
): WebAuthConfig {
  return {
    appEnv: "test",
    apiBaseUrl: "http://api.test",
    appOrigin: "http://app.test",
    policyManifest: policies,
    ageProvider: {
      status: "approved",
      publicUrl: "https://age.test/verify",
      origin: "https://age.test",
    },
  };
}

function pendingSnapshot(
  requirements: ("age_assurance" | "policy_acceptance")[],
): BrowserSessionSnapshot {
  return {
    status: "pending",
    error: null,
    user: {
      user_id: "user-id",
      status: "pending",
      scope: "pending",
      onboarding_requirements: requirements,
    },
  };
}

function createSession(
  snapshot: BrowserSessionSnapshot,
  config = createConfig(),
) {
  return {
    config,
    getSnapshot: vi.fn(() => snapshot),
    acceptPolicy: vi.fn<
      (
        policy: WebPolicyManifest,
        logicalSubmission: string,
      ) => Promise<{ acceptance_id: string; activated: boolean }>
    >(async () => ({
      acceptance_id: "acceptance-id",
      activated: false,
    })),
  };
}

describe("OnboardingController", () => {
  it("derives inactive, complete, blocked, and ready states", () => {
    const anonymous = createSession({
      status: "anonymous",
      user: null,
      error: null,
    });
    expect(new OnboardingController(anonymous).getState().status).toBe(
      "inactive",
    );

    const active = createSession({
      status: "active",
      error: null,
      user: {
        user_id: "user-id",
        status: "active",
        scope: "active",
        onboarding_requirements: [],
      },
    });
    expect(new OnboardingController(active).getState().status).toBe("complete");

    const noRequirements = createSession(pendingSnapshot([]));
    expect(new OnboardingController(noRequirements).getState()).toMatchObject({
      status: "blocked",
      blocker: "onboarding_incomplete",
    });

    const missingManifest = createSession(
      pendingSnapshot(["policy_acceptance"]),
      createConfig([]),
    );
    expect(new OnboardingController(missingManifest).getState()).toMatchObject({
      status: "blocked",
      blocker: "policy_manifest_unavailable",
    });

    const ready = createSession(pendingSnapshot(["policy_acceptance"]));
    expect(new OnboardingController(ready).getState()).toEqual({
      status: "ready",
      requirements: ["policy_acceptance"],
      blocker: null,
      policies: [privacyPolicy, termsPolicy],
    });
  });

  it("fails closed when age assurance is required without an approved bridge", () => {
    const session = createSession(pendingSnapshot(["age_assurance"]));
    expect(new OnboardingController(session).getState()).toMatchObject({
      status: "blocked",
      blocker: "age_provider_unavailable",
    });
  });

  it("starts the configured age bridge only for the required ready step", async () => {
    const session = createSession(pendingSnapshot(["age_assurance"]));
    const ageBridge = {
      start: vi.fn(async () => ({
        record_id: "record-id",
        result: "verified" as const,
        activated: false,
      })),
      cancel: vi.fn(),
    };
    const controller = new OnboardingController(session, ageBridge);

    await expect(controller.startAgeAssurance()).resolves.toMatchObject({
      result: "verified",
    });
    expect(ageBridge.start).toHaveBeenCalledOnce();

    const policyOnly = new OnboardingController(
      createSession(pendingSnapshot(["policy_acceptance"])),
      ageBridge,
    );
    await expect(policyOnly.startAgeAssurance()).rejects.toBeInstanceOf(
      BrowserAuthError,
    );
  });

  it("requires the exact displayed policy set and submits exact versions", async () => {
    const session = createSession(pendingSnapshot(["policy_acceptance"]));
    const controller = new OnboardingController(session);

    await expect(
      controller.acceptPolicies([privacyPolicy]),
    ).rejects.toBeInstanceOf(BrowserAuthError);
    await expect(
      controller.acceptPolicies([privacyPolicy, privacyPolicy]),
    ).rejects.toBeInstanceOf(BrowserAuthError);
    expect(session.acceptPolicy).not.toHaveBeenCalled();

    await controller.acceptPolicies([termsPolicy, privacyPolicy]);
    expect(session.acceptPolicy).toHaveBeenNthCalledWith(
      1,
      privacyPolicy,
      `policy-acceptance:${policyIdentity(privacyPolicy)}`,
    );
    expect(session.acceptPolicy).toHaveBeenNthCalledWith(
      2,
      termsPolicy,
      `policy-acceptance:${policyIdentity(termsPolicy)}`,
    );
  });

  it("uses stable per-policy idempotency identities when retrying partial completion", async () => {
    const session = createSession(pendingSnapshot(["policy_acceptance"]));
    session.acceptPolicy
      .mockResolvedValueOnce({ acceptance_id: "first", activated: false })
      .mockRejectedValueOnce(new BrowserAuthError("network_error"))
      .mockResolvedValue({ acceptance_id: "replayed", activated: true });
    const controller = new OnboardingController(session);

    await expect(
      controller.acceptPolicies([privacyPolicy, termsPolicy]),
    ).rejects.toBeInstanceOf(BrowserAuthError);
    await controller.acceptPolicies([privacyPolicy, termsPolicy]);

    expect(session.acceptPolicy.mock.calls.map((call) => call[1])).toEqual([
      `policy-acceptance:${policyIdentity(privacyPolicy)}`,
      `policy-acceptance:${policyIdentity(termsPolicy)}`,
      `policy-acceptance:${policyIdentity(privacyPolicy)}`,
      `policy-acceptance:${policyIdentity(termsPolicy)}`,
    ]);
  });
});
