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

import type {
  AccessTokenResponse,
  BrowserAuthApi,
  CurrentUserResponse,
} from "../../lib/auth/api";
import { BrowserAuthError } from "../../lib/auth/errors";
import { BrowserAuthProvider } from "../../lib/auth/runtime";
import { BrowserAuthSession } from "../../lib/auth/session";
import type { WebAuthConfig } from "../../lib/web-auth-config";

import { AccountExperience } from "./AccountExperience";
import { JoinExperience } from "./JoinExperience";

const navigation = vi.hoisted(() => ({ replace: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
}));

const policy = {
  document_code: "privacy",
  document_version: "2026-08-15",
  document_digest: "a".repeat(64),
  title: "隐私政策",
  content_url: "https://policy.test/privacy",
  status: "approved" as const,
};

const config: WebAuthConfig = {
  appEnv: "test",
  apiBaseUrl: "http://api.test",
  appOrigin: "http://app.test",
  policyManifest: [policy],
  ageProvider: { status: "unconfigured", publicUrl: null, origin: null },
};

const pendingUser: CurrentUserResponse = {
  user_id: "synthetic-user",
  status: "pending",
  scope: "pending",
  onboarding_requirements: ["policy_acceptance"],
};

const activeUser: CurrentUserResponse = {
  ...pendingUser,
  status: "active",
  scope: "active",
  onboarding_requirements: [],
};

function accessToken(value: string): AccessTokenResponse {
  return { access_token: value, token_type: "Bearer", scope: "active" };
}

class FakeBrowserAuthApi implements BrowserAuthApi {
  refreshCalls = 0;
  logoutCalls = 0;
  logoutResult: () => Promise<void> = async () => undefined;
  smsResult: () => Promise<{
    challenge_id: string;
    expires_at: string;
  }> = async () => ({
    challenge_id: "synthetic-challenge",
    expires_at: "2099-01-01T00:00:00Z",
  });
  currentUserResult: CurrentUserResponse = activeUser;
  refreshResult: () => Promise<AccessTokenResponse> = async () =>
    accessToken("synthetic-access-token");

  async requestSmsChallenge() {
    return this.smsResult();
  }

  async createSession() {
    return accessToken("synthetic-session-token");
  }

  async refresh() {
    this.refreshCalls += 1;
    return this.refreshResult();
  }

  async currentUser() {
    return this.currentUserResult;
  }

  async recordAgeAssurance() {
    return {
      record_id: "synthetic-record",
      result: "verified" as const,
      activated: false,
    };
  }

  async acceptPolicy() {
    return { activated: false };
  }

  async logout() {
    this.logoutCalls += 1;
    return this.logoutResult();
  }
}

function renderWithSession(child: React.ReactNode, api: FakeBrowserAuthApi) {
  const session = new BrowserAuthSession(api, config);
  return {
    session,
    ...render(
      <BrowserAuthProvider config={config} session={session}>
        {child}
      </BrowserAuthProvider>,
    ),
  };
}

afterEach(() => {
  cleanup();
  navigation.replace.mockReset();
});

describe("P1-M2 protected session integration", () => {
  it("restores an active session after a complete reload without protected-data flash", async () => {
    const api = new FakeBrowserAuthApi();
    renderWithSession(<AccountExperience />, api);

    expect(screen.getByText("正在恢复安全会话")).toBeInTheDocument();
    expect(screen.queryByText("账号基础已就绪")).toBeNull();

    expect(
      await screen.findByRole("heading", { name: "账号基础已就绪" }),
    ).toBeInTheDocument();
    expect(api.refreshCalls).toBe(1);
  });

  it("redirects an anonymous account request without rendering protected content", async () => {
    const api = new FakeBrowserAuthApi();
    api.refreshResult = async () => {
      throw new BrowserAuthError("authentication_failed", 401);
    };
    renderWithSession(<AccountExperience />, api);

    expect(screen.queryByText("账号基础已就绪")).toBeNull();
    await waitFor(() =>
      expect(navigation.replace).toHaveBeenCalledWith("/join"),
    );
    expect(screen.queryByText("账号基础已就绪")).toBeNull();
  });

  it("resumes the server-authoritative pending onboarding requirements", async () => {
    const api = new FakeBrowserAuthApi();
    api.currentUserResult = pendingUser;
    renderWithSession(<JoinExperience />, api);

    expect(await screen.findByText("完成账号开通")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "隐私政策" })).toHaveAttribute(
      "href",
      policy.content_url,
    );
    expect(screen.queryByText("18+ 年龄核验")).toBeNull();
  });

  it("recovers a bootstrap network failure and then routes an active session", async () => {
    const api = new FakeBrowserAuthApi();
    let fail = true;
    api.refreshResult = async () => {
      if (fail) {
        fail = false;
        throw new BrowserAuthError("network_error");
      }
      return accessToken("recovered-token");
    };
    renderWithSession(<JoinExperience />, api);

    fireEvent.click(
      await screen.findByRole("button", { name: "重新检查会话" }),
    );

    await waitFor(() =>
      expect(navigation.replace).toHaveBeenCalledWith("/account"),
    );
    expect(api.refreshCalls).toBe(2);
  });

  it("keeps the authentication flow mounted when a local request fails", async () => {
    const api = new FakeBrowserAuthApi();
    api.refreshResult = async () => {
      throw new BrowserAuthError("authentication_failed", 401);
    };
    api.smsResult = async () => {
      throw new BrowserAuthError("network_error");
    };
    renderWithSession(<JoinExperience />, api);

    fireEvent.change(await screen.findByLabelText("手机号"), {
      target: { value: "synthetic-phone" },
    });
    fireEvent.click(screen.getByRole("button", { name: "获取验证码" }));

    expect(
      await screen.findByText("网络暂时不可用，请稍后重试。"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "加入 Project Mirror 私测" }),
    ).toBeInTheDocument();
  });

  it("logs out once, clears the client session, and returns to join", async () => {
    const api = new FakeBrowserAuthApi();
    const { session } = renderWithSession(<AccountExperience />, api);
    fireEvent.click(await screen.findByRole("button", { name: "退出登录" }));

    await waitFor(() => expect(api.logoutCalls).toBe(1));
    expect(session.getSnapshot().status).toBe("anonymous");
    expect(navigation.replace).toHaveBeenCalledWith("/join");
  });

  it("does not claim logout success when server revocation is unconfirmed", async () => {
    const api = new FakeBrowserAuthApi();
    let fail = true;
    api.logoutResult = async () => {
      if (fail) {
        fail = false;
        throw new BrowserAuthError("network_error");
      }
    };
    const { session } = renderWithSession(<AccountExperience />, api);
    fireEvent.click(await screen.findByRole("button", { name: "退出登录" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "退出尚未由服务器确认",
      ),
    );
    expect(session.getSnapshot()).toMatchObject({
      status: "error",
      user: null,
    });
    expect(navigation.replace).not.toHaveBeenCalledWith("/join");

    fireEvent.click(screen.getByRole("button", { name: "重试退出" }));
    await waitFor(() => expect(api.logoutCalls).toBe(2));
    expect(session.getSnapshot().status).toBe("anonymous");
    expect(navigation.replace).toHaveBeenCalledWith("/join");
  });
});
