"use client";

import { Button } from "@mirror/ui";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { BrowserAuthError } from "../../lib/auth";
import type { BrowserAuthSession } from "../../lib/auth";

export type AuthenticationController = Pick<
  BrowserAuthSession,
  | "completeSession"
  | "getSnapshot"
  | "requestSmsChallenge"
  | "restartSubmission"
  | "subscribe"
>;

type AuthenticationFlowProps = Readonly<{
  session: AuthenticationController;
  cooldownSeconds?: number;
  onSessionCreated?: () => void;
}>;

type Step = "phone" | "otp";

const genericError = "认证请求未完成，请检查后重试。";

function messageFor(error: unknown): string {
  if (error instanceof BrowserAuthError) {
    if (error.code === "authentication_throttled") {
      return "请求过于频繁，请稍后再试。";
    }
    if (error.code === "network_error") {
      return "网络暂时不可用，请稍后重试。";
    }
  }
  return genericError;
}

export function AuthenticationFlow({
  session,
  cooldownSeconds = 60,
  onSessionCreated,
}: AuthenticationFlowProps) {
  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [otp, setOtp] = useState("");
  const [challengeId, setChallengeId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const phoneInput = useRef<HTMLInputElement>(null);
  const otpInput = useRef<HTMLInputElement>(null);
  const errorMessage = useRef<HTMLParagraphElement>(null);
  const submissionLock = useRef(false);

  useEffect(() => {
    return session.subscribe(() => undefined);
  }, [session]);

  useEffect(() => {
    if (remainingSeconds === 0) return;
    const timer = window.setInterval(() => {
      setRemainingSeconds((current) => Math.max(0, current - 1));
    }, 1_000);
    return () => window.clearInterval(timer);
  }, [remainingSeconds]);

  useEffect(() => {
    if (error !== null) {
      errorMessage.current?.focus();
      return;
    }
    if (step === "phone") phoneInput.current?.focus();
    else otpInput.current?.focus();
  }, [error, step]);

  async function submitPhone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submissionLock.current || isSubmitting || remainingSeconds > 0) return;
    submissionLock.current = true;
    setIsSubmitting(true);
    setError(null);
    try {
      const challenge = await session.requestSmsChallenge(
        { phone, ...(inviteCode ? { inviteCode } : {}) },
        "auth-sms-challenge",
      );
      setChallengeId(challenge.challenge_id);
      setPhone("");
      setInviteCode("");
      setStep("otp");
      setRemainingSeconds(cooldownSeconds);
    } catch (reason) {
      setError(messageFor(reason));
    } finally {
      submissionLock.current = false;
      setIsSubmitting(false);
    }
  }

  async function submitOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submissionLock.current || isSubmitting || challengeId === null) return;
    submissionLock.current = true;
    setIsSubmitting(true);
    setError(null);
    try {
      await session.completeSession(challengeId, otp, "auth-otp-session");
      setOtp("");
      setChallengeId(null);
      onSessionCreated?.();
    } catch (reason) {
      setOtp("");
      setError(messageFor(reason));
    } finally {
      submissionLock.current = false;
      setIsSubmitting(false);
    }
  }

  function restart(): void {
    if (submissionLock.current || isSubmitting) return;
    session.restartSubmission("auth-sms-challenge");
    session.restartSubmission("auth-otp-session");
    setOtp("");
    setChallengeId(null);
    setError(null);
    setRemainingSeconds(0);
    setStep("phone");
  }

  return (
    <section aria-labelledby="authentication-title" className="w-full max-w-md">
      <h1 id="authentication-title" className="text-2xl font-semibold text-ink">
        加入 Project Mirror 私测
      </h1>
      <p
        id="authentication-description"
        className="mt-2 text-sm leading-6 text-black/65"
      >
        使用手机号完成私测验证。我们会以相同方式处理每一次请求。
      </p>

      {error !== null ? (
        <p
          ref={errorMessage}
          aria-live="assertive"
          role="alert"
          tabIndex={-1}
          className="mt-5 rounded-xl border border-rose/40 bg-rose/10 px-4 py-3 text-sm text-ink outline-none"
        >
          {error}
        </p>
      ) : null}

      {step === "phone" ? (
        <form className="mt-7 grid gap-5" onSubmit={submitPhone}>
          <fieldset
            disabled={isSubmitting || remainingSeconds > 0}
            className="grid gap-5"
          >
            <legend className="sr-only">手机号验证</legend>
            <div className="grid gap-2">
              <label htmlFor="auth-phone" className="text-sm font-medium">
                手机号
              </label>
              <input
                ref={phoneInput}
                id="auth-phone"
                name="phone"
                autoComplete="tel"
                inputMode="tel"
                required
                aria-describedby="authentication-description"
                className="rounded-xl border border-black/20 bg-white px-4 py-3 outline-none focus:border-plum focus:ring-2 focus:ring-plum/25"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <label htmlFor="auth-invite" className="text-sm font-medium">
                邀请码（如有）
              </label>
              <input
                id="auth-invite"
                name="inviteCode"
                autoComplete="off"
                aria-describedby="invite-help"
                className="rounded-xl border border-black/20 bg-white px-4 py-3 outline-none focus:border-plum focus:ring-2 focus:ring-plum/25"
                value={inviteCode}
                onChange={(event) => setInviteCode(event.target.value)}
              />
              <p id="invite-help" className="text-xs leading-5 text-black/55">
                已有账号时可以不填写邀请码。
              </p>
            </div>
          </fieldset>
          <Button type="submit" disabled={isSubmitting || remainingSeconds > 0}>
            {isSubmitting ? "正在提交…" : "获取验证码"}
          </Button>
        </form>
      ) : (
        <form className="mt-7 grid gap-5" onSubmit={submitOtp}>
          <fieldset disabled={isSubmitting} className="grid gap-5">
            <legend className="sr-only">输入验证码</legend>
            <div className="grid gap-2">
              <label htmlFor="auth-otp" className="text-sm font-medium">
                验证码
              </label>
              <input
                ref={otpInput}
                id="auth-otp"
                name="otp"
                autoComplete="one-time-code"
                inputMode="numeric"
                maxLength={6}
                required
                aria-describedby="otp-help"
                className="rounded-xl border border-black/20 bg-white px-4 py-3 tracking-[0.35em] outline-none focus:border-plum focus:ring-2 focus:ring-plum/25"
                value={otp}
                onChange={(event) => setOtp(event.target.value)}
              />
              <p id="otp-help" className="text-xs leading-5 text-black/55">
                请在验证码有效期内完成输入。
              </p>
            </div>
          </fieldset>
          <Button type="submit" disabled={isSubmitting || challengeId === null}>
            {isSubmitting ? "正在验证…" : "继续"}
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={isSubmitting || remainingSeconds > 0}
            onClick={restart}
          >
            {remainingSeconds > 0
              ? `可在 ${remainingSeconds} 秒后重新开始`
              : "重新开始"}
          </Button>
        </form>
      )}
    </section>
  );
}
