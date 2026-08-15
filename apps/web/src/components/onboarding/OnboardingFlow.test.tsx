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

import type { OnboardingState } from "../../lib/onboarding";
import type { WebPolicyManifest } from "../../lib/web-auth-config";

import {
  OnboardingFlow,
  type OnboardingFlowController,
} from "./OnboardingFlow";

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

const readyState: OnboardingState = {
  status: "ready",
  requirements: ["age_assurance", "policy_acceptance"],
  blocker: null,
  policies: [privacyPolicy, termsPolicy],
};

class FakeOnboardingController implements OnboardingFlowController {
  state: OnboardingState = readyState;
  getState = vi.fn(() => this.state);
  startAgeAssurance = vi.fn(async () => ({
    record_id: "record-id",
    result: "verified" as const,
    activated: false,
  }));
  acceptPolicies = vi.fn(async () => undefined);
}

afterEach(() => cleanup());

describe("OnboardingFlow", () => {
  it("renders exact approved policy links and requires individual confirmation", async () => {
    const controller = new FakeOnboardingController();
    render(<OnboardingFlow controller={controller} />);

    const privacy = screen.getByRole("link", { name: "隐私政策" });
    const terms = screen.getByRole("link", { name: "用户协议" });
    expect(privacy).toHaveAttribute("href", privacyPolicy.content_url);
    expect(terms).toHaveAttribute("href", termsPolicy.content_url);
    expect(
      screen.getAllByText("版本 2026-08-15", { selector: "span" }),
    ).toHaveLength(2);

    const submit = screen.getByRole("button", { name: "确认并继续" });
    expect(submit).toBeDisabled();
    const boxes = screen.getAllByRole("checkbox");
    fireEvent.click(boxes[0]!);
    expect(submit).toBeDisabled();
    fireEvent.click(boxes[1]!);
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    await waitFor(() =>
      expect(controller.acceptPolicies).toHaveBeenCalledOnce(),
    );
    expect(controller.acceptPolicies).toHaveBeenCalledWith([
      privacyPolicy,
      termsPolicy,
    ]);
  });

  it("uses the external age action without rendering a credential input", async () => {
    const controller = new FakeOnboardingController();
    render(<OnboardingFlow controller={controller} />);

    expect(screen.queryByLabelText(/credential|证件|出生日期/i)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "开始年龄核验" }));

    await waitFor(() =>
      expect(controller.startAgeAssurance).toHaveBeenCalledOnce(),
    );
  });

  it("renders fail-closed blocked states without an unsafe fallback", () => {
    const controller = new FakeOnboardingController();
    controller.state = {
      status: "blocked",
      requirements: ["age_assurance"],
      blocker: "age_provider_unavailable",
      policies: [],
    };
    render(<OnboardingFlow controller={controller} />);

    expect(screen.getByRole("alert")).toHaveTextContent("年龄核验服务尚未可用");
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("sanitizes operation errors, focuses the alert, and permits retry", async () => {
    const controller = new FakeOnboardingController();
    controller.startAgeAssurance
      .mockRejectedValueOnce(new Error("one-shot-credential"))
      .mockResolvedValueOnce({
        record_id: "record-id",
        result: "verified",
        activated: false,
      });
    render(<OnboardingFlow controller={controller} />);

    const action = screen.getByRole("button", { name: "开始年龄核验" });
    fireEvent.click(action);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("该步骤未完成，请稍后重试。");
    expect(alert).toHaveFocus();
    expect(document.body.textContent).not.toContain("one-shot-credential");

    fireEvent.click(action);
    await waitFor(() =>
      expect(controller.startAgeAssurance).toHaveBeenCalledTimes(2),
    );
  });

  it("announces completion after controller state advances", async () => {
    const controller = new FakeOnboardingController();
    controller.state = {
      ...readyState,
      requirements: ["age_assurance"],
      policies: [],
    };
    controller.startAgeAssurance.mockImplementationOnce(async () => {
      controller.state = {
        status: "complete",
        requirements: [],
        blocker: null,
        policies: [],
      };
      return { record_id: "record-id", result: "verified", activated: true };
    });
    const onComplete = vi.fn();
    render(<OnboardingFlow controller={controller} onComplete={onComplete} />);

    fireEvent.click(screen.getByRole("button", { name: "开始年龄核验" }));

    expect(
      await screen.findByRole("heading", { name: "账号已开通" }),
    ).toBeTruthy();
    expect(onComplete).toHaveBeenCalledOnce();
  });
});
