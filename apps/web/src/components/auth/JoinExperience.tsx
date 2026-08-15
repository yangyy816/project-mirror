"use client";

import { useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";

import { useBrowserAuth } from "../../lib/auth";
import {
  AgeAssurancePopupBridge,
  type BrowserPopupHost,
  OnboardingController,
} from "../../lib/onboarding";
import { OnboardingFlow } from "../onboarding/OnboardingFlow";

import { AuthenticationFlow } from "./AuthenticationFlow";
import { SessionLoading, SessionRecovery } from "./SessionStatus";

const browserPopupHost: BrowserPopupHost = {
  open: (url, target, features) => window.open(url, target, features),
  addEventListener: (type, listener) => window.addEventListener(type, listener),
  removeEventListener: (type, listener) =>
    window.removeEventListener(type, listener),
  setTimeout: (handler, timeout) => window.setTimeout(handler, timeout),
  clearTimeout: (handle) => window.clearTimeout(handle),
  setInterval: (handler, timeout) => window.setInterval(handler, timeout),
  clearInterval: (handle) => window.clearInterval(handle),
};

export function JoinExperience() {
  const router = useRouter();
  const { session, snapshot } = useBrowserAuth();
  const onboarding = useMemo(
    () =>
      new OnboardingController(
        session,
        new AgeAssurancePopupBridge(session, browserPopupHost),
      ),
    [session],
  );

  useEffect(() => {
    if (snapshot.status === "active") {
      router.replace("/account");
    }
  }, [router, snapshot.status]);

  if (snapshot.status === "bootstrapping") {
    return <SessionLoading />;
  }

  if (snapshot.status === "active") {
    return <SessionLoading />;
  }

  if (snapshot.status === "pending") {
    return (
      <OnboardingFlow
        controller={onboarding}
        onComplete={() => router.replace("/account")}
      />
    );
  }

  return (
    <div className="grid w-full max-w-xl gap-6">
      {snapshot.status === "error" ? (
        <SessionRecovery
          key="session-recovery"
          onRetry={() => void session.bootstrap()}
        />
      ) : null}
      <AuthenticationFlow key="authentication-flow" session={session} />
    </div>
  );
}
