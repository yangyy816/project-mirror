"use client";

import { Button } from "@mirror/ui";
import { type FormEvent, useEffect, useRef, useState } from "react";

import type {
  OnboardingController,
  OnboardingState,
} from "../../lib/onboarding";
import { policyIdentity } from "../../lib/onboarding";

export type OnboardingFlowController = Pick<
  OnboardingController,
  "acceptPolicies" | "getState" | "startAgeAssurance"
>;

type OnboardingFlowProps = Readonly<{
  controller: OnboardingFlowController;
  onComplete?: () => void;
}>;

const genericError = "该步骤未完成，请稍后重试。";

function blockerMessage(state: OnboardingState): string {
  switch (state.blocker) {
    case "age_provider_unavailable":
      return "年龄核验服务尚未可用，当前无法继续注册。";
    case "policy_manifest_unavailable":
      return "政策文档尚未可用，当前无法继续注册。";
    default:
      return "账号开通条件尚未完整，请稍后重试。";
  }
}

export function OnboardingFlow({
  controller,
  onComplete,
}: OnboardingFlowProps) {
  const [state, setState] = useState(() => controller.getState());
  const [confirmed, setConfirmed] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const errorMessage = useRef<HTMLParagraphElement>(null);
  const operationLock = useRef(false);

  useEffect(() => {
    if (error !== null) errorMessage.current?.focus();
  }, [error]);

  function refreshState(): OnboardingState {
    const next = controller.getState();
    setState(next);
    if (next.status === "complete") onComplete?.();
    return next;
  }

  function togglePolicy(identity: string, checked: boolean): void {
    setConfirmed((current) => {
      const next = new Set(current);
      if (checked) next.add(identity);
      else next.delete(identity);
      return next;
    });
  }

  async function run(operation: () => Promise<void>): Promise<void> {
    if (operationLock.current || isSubmitting) return;
    operationLock.current = true;
    setIsSubmitting(true);
    setError(null);
    try {
      await operation();
      refreshState();
    } catch {
      setError(genericError);
    } finally {
      operationLock.current = false;
      setIsSubmitting(false);
    }
  }

  async function verifyAge(): Promise<void> {
    await run(async () => {
      const result = await controller.startAgeAssurance();
      if (result.result !== "verified") throw new Error("age not verified");
    });
  }

  async function acceptPolicies(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const selected = state.policies.filter((policy) =>
      confirmed.has(policyIdentity(policy)),
    );
    await run(() => controller.acceptPolicies(selected));
  }

  if (state.status === "inactive") return null;

  if (state.status === "complete") {
    return (
      <section aria-labelledby="onboarding-title" className="w-full max-w-xl">
        <h1 id="onboarding-title" className="text-2xl font-semibold text-ink">
          账号已开通
        </h1>
        <p className="mt-2 text-sm leading-6 text-black/65">
          年龄核验与必要政策确认已完成。
        </p>
      </section>
    );
  }

  if (state.status === "blocked") {
    return (
      <section aria-labelledby="onboarding-title" className="w-full max-w-xl">
        <h1 id="onboarding-title" className="text-2xl font-semibold text-ink">
          暂时无法继续
        </h1>
        <p role="alert" className="mt-4 text-sm leading-6 text-black/65">
          {blockerMessage(state)}
        </p>
      </section>
    );
  }

  const allPoliciesConfirmed = state.policies.every((policy) =>
    confirmed.has(policyIdentity(policy)),
  );

  return (
    <section aria-labelledby="onboarding-title" className="w-full max-w-xl">
      <h1 id="onboarding-title" className="text-2xl font-semibold text-ink">
        完成账号开通
      </h1>
      <p className="mt-2 text-sm leading-6 text-black/65">
        请逐项完成年龄核验与政策确认。
      </p>

      {error !== null ? (
        <p
          ref={errorMessage}
          role="alert"
          aria-live="assertive"
          tabIndex={-1}
          className="mt-5 rounded-xl border border-rose/40 bg-rose/10 px-4 py-3 text-sm text-ink outline-none"
        >
          {error}
        </p>
      ) : null}

      {state.requirements.includes("age_assurance") ? (
        <div className="mt-7 rounded-2xl border border-black/10 bg-white/70 p-5">
          <h2 className="font-semibold text-ink">18+ 年龄核验</h2>
          <p className="mt-2 text-sm leading-6 text-black/60">
            核验由外部服务完成；Project Mirror 不要求手工输入证件或出生日期。
          </p>
          <Button
            type="button"
            className="mt-4"
            disabled={isSubmitting}
            onClick={() => void verifyAge()}
          >
            {isSubmitting ? "正在处理…" : "开始年龄核验"}
          </Button>
        </div>
      ) : null}

      {state.requirements.includes("policy_acceptance") ? (
        <form className="mt-7 grid gap-4" onSubmit={acceptPolicies}>
          <fieldset disabled={isSubmitting} className="grid gap-3">
            <legend className="font-semibold text-ink">政策文档</legend>
            {state.policies.map((policy) => {
              const identity = policyIdentity(policy);
              return (
                <label
                  key={identity}
                  className="flex items-start gap-3 rounded-xl border border-black/10 bg-white/70 p-4"
                >
                  <input
                    type="checkbox"
                    checked={confirmed.has(identity)}
                    onChange={(event) =>
                      togglePolicy(identity, event.target.checked)
                    }
                    className="mt-1"
                  />
                  <span className="text-sm leading-6">
                    我已阅读并同意
                    <a
                      href={policy.content_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="ml-1 font-medium text-plum underline underline-offset-4"
                    >
                      {policy.title}
                    </a>
                    <span className="ml-1 text-black/50">
                      版本 {policy.document_version}
                    </span>
                  </span>
                </label>
              );
            })}
          </fieldset>
          <Button
            type="submit"
            disabled={isSubmitting || !allPoliciesConfirmed}
          >
            {isSubmitting ? "正在确认…" : "确认并继续"}
          </Button>
        </form>
      ) : null}
    </section>
  );
}
