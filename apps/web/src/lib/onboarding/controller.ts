import type { AgeAssuranceResponse, CurrentUserResponse } from "../auth/api";
import { BrowserAuthError } from "../auth/errors";
import type { BrowserAuthSession } from "../auth/session";
import type { WebPolicyManifest } from "../web-auth-config";

import type { AgeAssuranceBridge } from "./age-assurance-bridge";

type OnboardingSession = Pick<
  BrowserAuthSession,
  "acceptPolicy" | "config" | "getSnapshot"
>;

export type OnboardingBlocker =
  | "age_provider_unavailable"
  | "policy_manifest_unavailable"
  | "onboarding_incomplete";

export type OnboardingState = Readonly<{
  status: "inactive" | "ready" | "blocked" | "complete";
  requirements: readonly CurrentUserResponse["onboarding_requirements"][number][];
  blocker: OnboardingBlocker | null;
  policies: readonly WebPolicyManifest[];
}>;

function hasRequirement(
  user: CurrentUserResponse,
  requirement: CurrentUserResponse["onboarding_requirements"][number],
): boolean {
  return user.onboarding_requirements.includes(requirement);
}

function policyIdentity(policy: WebPolicyManifest): string {
  return [
    policy.document_code,
    policy.document_version,
    policy.document_digest,
  ].join("\u0000");
}

export class OnboardingController {
  constructor(
    private readonly session: OnboardingSession,
    private readonly ageBridge: AgeAssuranceBridge | null = null,
  ) {}

  getState(): OnboardingState {
    const snapshot = this.session.getSnapshot();
    if (snapshot.status === "active") {
      return {
        status: "complete",
        requirements: [],
        blocker: null,
        policies: [],
      };
    }
    if (snapshot.status !== "pending" || snapshot.user === null) {
      return {
        status: "inactive",
        requirements: [],
        blocker: null,
        policies: [],
      };
    }

    const requirements = snapshot.user.onboarding_requirements;
    if (requirements.length === 0) {
      return {
        status: "blocked",
        requirements,
        blocker: "onboarding_incomplete",
        policies: [],
      };
    }
    if (
      hasRequirement(snapshot.user, "age_assurance") &&
      (this.session.config.ageProvider.status !== "approved" ||
        this.session.config.ageProvider.publicUrl === null ||
        this.session.config.ageProvider.origin === null ||
        this.ageBridge === null)
    ) {
      return {
        status: "blocked",
        requirements,
        blocker: "age_provider_unavailable",
        policies: [],
      };
    }
    if (
      hasRequirement(snapshot.user, "policy_acceptance") &&
      this.session.config.policyManifest.length === 0
    ) {
      return {
        status: "blocked",
        requirements,
        blocker: "policy_manifest_unavailable",
        policies: [],
      };
    }
    return {
      status: "ready",
      requirements,
      blocker: null,
      policies: hasRequirement(snapshot.user, "policy_acceptance")
        ? this.session.config.policyManifest
        : [],
    };
  }

  async startAgeAssurance(): Promise<AgeAssuranceResponse> {
    const state = this.getState();
    if (
      state.status !== "ready" ||
      !state.requirements.includes("age_assurance") ||
      this.ageBridge === null
    ) {
      throw new BrowserAuthError("authentication_failed");
    }
    return this.ageBridge.start();
  }

  async acceptPolicies(
    confirmedPolicies: readonly WebPolicyManifest[],
  ): Promise<void> {
    const state = this.getState();
    if (
      state.status !== "ready" ||
      !state.requirements.includes("policy_acceptance") ||
      !this.hasExactPolicyConfirmation(confirmedPolicies, state.policies)
    ) {
      throw new BrowserAuthError("authentication_failed");
    }
    for (const policy of state.policies) {
      await this.session.acceptPolicy(
        policy,
        `policy-acceptance:${policyIdentity(policy)}`,
      );
    }
  }

  private hasExactPolicyConfirmation(
    confirmedPolicies: readonly WebPolicyManifest[],
    policies: readonly WebPolicyManifest[],
  ): boolean {
    if (confirmedPolicies.length !== policies.length) {
      return false;
    }
    const expected = new Set(policies.map(policyIdentity));
    const confirmed = new Set(confirmedPolicies.map(policyIdentity));
    return (
      expected.size === policies.length &&
      confirmed.size === policies.length &&
      [...confirmed].every((identity) => expected.has(identity))
    );
  }
}

export { policyIdentity };
