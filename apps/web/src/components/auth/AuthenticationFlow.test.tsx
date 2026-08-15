// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BrowserAuthError } from "../../lib/auth";
import type { BrowserSessionSnapshot } from "../../lib/auth";

import {
  AuthenticationFlow,
  type AuthenticationController,
} from "./AuthenticationFlow";

class FakeAuthenticationController implements AuthenticationController {
  requestSmsChallenge = vi.fn(async () => ({
    challenge_id: "c".repeat(32),
    expires_at: "2026-08-15T00:00:00Z",
  }));
  completeSession = vi.fn(async () => undefined);
  restartSubmission = vi.fn();
  private snapshot: BrowserSessionSnapshot = {
    status: "anonymous",
    user: null,
    error: null,
  };

  getSnapshot(): BrowserSessionSnapshot {
    return this.snapshot;
  }

  subscribe(): () => void {
    return () => undefined;
  }
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("AuthenticationFlow", () => {
  it("uses labels and keyboard submission, then clears phone and invite from the DOM", async () => {
    const session = new FakeAuthenticationController();
    render(<AuthenticationFlow session={session} cooldownSeconds={0} />);

    const phone = screen.getByLabelText("手机号");
    expect(phone).toHaveFocus();
    fireEvent.change(phone, { target: { value: "synthetic-phone" } });
    fireEvent.change(screen.getByLabelText("邀请码（如有）"), {
      target: { value: "synthetic-invite" },
    });
    fireEvent.submit(phone.closest("form")!);

    await waitFor(() =>
      expect(session.requestSmsChallenge).toHaveBeenCalledTimes(1),
    );
    await waitFor(() => expect(screen.getByLabelText("验证码")).toHaveFocus());
    expect(screen.queryByLabelText("手机号")).toBeNull();
    expect(screen.queryByLabelText("邀请码（如有）")).toBeNull();
    expect(document.body.textContent).not.toContain("synthetic-phone");
    expect(document.body.textContent).not.toContain("synthetic-invite");
  });

  it("prevents duplicate OTP submission and clears the OTP after completion", async () => {
    const session = new FakeAuthenticationController();
    render(<AuthenticationFlow session={session} cooldownSeconds={0} />);

    const phone = screen.getByLabelText("手机号");
    fireEvent.change(phone, { target: { value: "synthetic-phone" } });
    fireEvent.submit(phone.closest("form")!);
    const otp = await screen.findByLabelText("验证码");
    fireEvent.change(otp, { target: { value: "654321" } });
    fireEvent.submit(otp.closest("form")!);
    fireEvent.submit(otp.closest("form")!);

    await waitFor(() =>
      expect(session.completeSession).toHaveBeenCalledTimes(1),
    );
    await waitFor(() => expect(otp).toHaveValue(""));
    expect(document.body.textContent).not.toContain("654321");
  });

  it("uses generic non-enumerating copy and focuses a throttling error", async () => {
    const session = new FakeAuthenticationController();
    session.requestSmsChallenge.mockRejectedValueOnce(
      new BrowserAuthError("authentication_throttled", 429),
    );
    render(<AuthenticationFlow session={session} />);

    const phone = screen.getByLabelText("手机号");
    fireEvent.change(phone, { target: { value: "synthetic-phone" } });
    fireEvent.submit(phone.closest("form")!);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("请求过于频繁，请稍后再试。");
    expect(alert).toHaveFocus();
    expect(document.body.textContent).not.toMatch(
      /账号不存在|邀请码无效|未注册/,
    );
  });

  it("recovers from a sanitized network error without exposing submitted values", async () => {
    const session = new FakeAuthenticationController();
    session.requestSmsChallenge.mockRejectedValueOnce(
      new BrowserAuthError("network_error"),
    );
    render(<AuthenticationFlow session={session} cooldownSeconds={0} />);

    const phone = screen.getByLabelText("手机号");
    fireEvent.change(phone, { target: { value: "synthetic-phone" } });
    fireEvent.submit(phone.closest("form")!);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "网络暂时不可用，请稍后重试。",
    );
    fireEvent.submit(phone.closest("form")!);

    await waitFor(() =>
      expect(session.requestSmsChallenge).toHaveBeenCalledTimes(2),
    );
    await screen.findByLabelText("验证码");
    expect(document.body.textContent).not.toContain("synthetic-phone");
  });

  it("restarts with fresh logical submissions and returns focus to the phone field", async () => {
    const session = new FakeAuthenticationController();
    render(<AuthenticationFlow session={session} cooldownSeconds={0} />);

    const phone = screen.getByLabelText("手机号");
    fireEvent.change(phone, { target: { value: "synthetic-phone" } });
    fireEvent.submit(phone.closest("form")!);
    await screen.findByLabelText("验证码");
    fireEvent.click(screen.getByRole("button", { name: "重新开始" }));

    expect(session.restartSubmission).toHaveBeenNthCalledWith(
      1,
      "auth-sms-challenge",
    );
    expect(session.restartSubmission).toHaveBeenNthCalledWith(
      2,
      "auth-otp-session",
    );
    await waitFor(() => expect(screen.getByLabelText("手机号")).toHaveFocus());
  });

  it("clears the active OTP DOM when the component unmounts", async () => {
    const session = new FakeAuthenticationController();
    const view = render(
      <AuthenticationFlow session={session} cooldownSeconds={0} />,
    );

    const phone = screen.getByLabelText("手机号");
    fireEvent.change(phone, { target: { value: "synthetic-phone" } });
    fireEvent.submit(phone.closest("form")!);
    const otp = await screen.findByLabelText("验证码");
    fireEvent.change(otp, { target: { value: "654321" } });
    view.unmount();

    expect(document.body.textContent).not.toContain("654321");
  });
});
