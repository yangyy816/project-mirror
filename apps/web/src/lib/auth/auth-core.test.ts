import { afterEach, describe, expect, it, vi } from "vitest";

import { parseWebAuthConfig } from "../web-auth-config";

import { GeneratedBrowserAuthApi } from "./api";
import { BrowserAuthError } from "./errors";
import { IdempotencyKeyPool } from "./idempotency";
import { BrowserAuthSession } from "./session";
import type {
  AccessTokenResponse,
  BrowserAuthApi,
  BrowserDataRightsApi,
  CurrentUserResponse,
  SessionCredentials,
  SmsChallengeInput,
} from "./api";

class FakeDataRightsApi implements BrowserDataRightsApi {
  listResult: () => Promise<{
    assets: [];
  }> = async () => ({ assets: [] });
  statusTokens: string[] = [];

  async listAssets() {
    return this.listResult();
  }

  async getAsset() {
    return {
      asset_id: "a".repeat(32),
      asset_role: "synthetic" as const,
      mime_type: "image/jpeg" as const,
      byte_size: 4,
      width: 1,
      height: 1,
      created_at: "2099-01-01T00:00:00Z",
    };
  }

  async downloadAsset() {
    return new Blob();
  }

  async deleteAsset() {
    return {
      deletion_request_id: "d".repeat(32),
      job_id: "j".repeat(32),
      status: "requested" as const,
    };
  }

  async createDataExport() {
    return this.dataExport("requested");
  }

  async getDataExport() {
    return this.dataExport("ready");
  }

  async downloadDataExport() {
    return new Blob();
  }

  async createAccountDeletion() {
    return this.accountDeletion("requested");
  }

  async getCurrentAccountDeletion(accessToken: string) {
    this.statusTokens.push(accessToken);
    return this.accountDeletion("completed");
  }

  private dataExport(status: "requested" | "ready") {
    return {
      export_id: "e".repeat(32),
      job_id: "j".repeat(32),
      status,
      schema_version: "mirror-data-export-v1" as const,
      requested_at: "2099-01-01T00:00:00Z",
      ready_at: status === "ready" ? "2099-01-01T00:00:01Z" : null,
      expires_at: status === "ready" ? "2099-01-02T00:00:01Z" : null,
    };
  }

  private accountDeletion(status: "requested" | "completed") {
    return {
      deletion_request_id: "d".repeat(32),
      job_id: "j".repeat(32),
      status,
      requested_at: "2099-01-01T00:00:00Z",
      completed_at: status === "completed" ? "2099-01-01T00:00:01Z" : null,
    };
  }
}

const config = parseWebAuthConfig({
  appEnv: "test",
  apiBaseUrl: "http://api.test",
  appOrigin: "http://web.test",
  policyManifest: JSON.stringify([
    {
      document_code: "privacy",
      document_version: "v1",
      document_digest: "c".repeat(64),
      title: "测试政策",
      content_url: "http://web.test/policies/privacy-v1",
      status: "approved",
    },
  ]),
  ageProviderStatus: "unconfigured",
});

const pendingUser: CurrentUserResponse = {
  user_id: "u".repeat(32),
  status: "pending",
  scope: "pending",
  onboarding_requirements: ["age_assurance"],
};

const activeUser: CurrentUserResponse = {
  ...pendingUser,
  status: "active",
  scope: "active",
  onboarding_requirements: [],
};

const token = (value: string): AccessTokenResponse => ({
  access_token: value,
  token_type: "Bearer",
  scope: "pending",
});

class FakeAuthApi implements BrowserAuthApi {
  refreshCalls = 0;
  refreshKeys: string[] = [];
  currentTokens: string[] = [];
  createSessionCalls = 0;
  smsKeys: string[] = [];
  ageKeys: string[] = [];
  policyKeys: string[] = [];
  current: (accessToken: string) => Promise<CurrentUserResponse> = async () =>
    pendingUser;

  async requestSmsChallenge(_: SmsChallengeInput, key: string) {
    this.smsKeys.push(key);
    return { challenge_id: "c".repeat(32), expires_at: "2026-08-15T00:00:00Z" };
  }

  async createSession(payload: SessionCredentials, idempotencyKey: string) {
    void payload;
    void idempotencyKey;
    this.createSessionCalls += 1;
    return token("first-token");
  }

  async refresh(key: string) {
    this.refreshCalls += 1;
    this.refreshKeys.push(key);
    return token("refreshed-token");
  }

  async currentUser(accessToken: string) {
    this.currentTokens.push(accessToken);
    return this.current(accessToken);
  }

  async recordAgeAssurance(
    credential: string,
    accessToken: string,
    key: string,
  ) {
    void credential;
    void accessToken;
    this.ageKeys.push(key);
    return {
      record_id: "a".repeat(32),
      result: "verified" as const,
      activated: false,
    };
  }

  async acceptPolicy(_: unknown, __: string, key: string) {
    this.policyKeys.push(key);
    return { activated: false };
  }

  async logout(accessToken: string) {
    void accessToken;
  }
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("generated browser auth adapter", () => {
  it("uses cookie credentials plus CSRF after validating the exact browser origin", async () => {
    vi.stubGlobal("document", { cookie: "mirror_csrf=csrf-fixture" });
    vi.stubGlobal("window", { location: { origin: "http://web.test" } });
    const requests: Request[] = [];
    const api = new GeneratedBrowserAuthApi(config, async (request) => {
      requests.push(request);
      return new Response(
        request.method === "DELETE" ? null : JSON.stringify(token("fresh")),
        {
          status: request.method === "DELETE" ? 204 : 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    });

    await api.refresh("refresh-key");
    await api.logout("access-fixture");

    expect(requests.map((request) => request.credentials)).toEqual([
      "include",
      "include",
    ]);
    expect(requests[0]?.headers.get("X-CSRF-Token")).toBe("csrf-fixture");
    expect(requests[0]?.headers.get("Idempotency-Key")).toBe("refresh-key");
    expect(requests[1]?.headers.get("Authorization")).toBe(
      "Bearer access-fixture",
    );
    expect(requests[1]?.headers.get("Origin")).toBeNull();
  });

  it("fails closed before CSRF requests when the runtime origin differs", async () => {
    vi.stubGlobal("document", { cookie: "mirror_csrf=csrf-fixture" });
    vi.stubGlobal("window", { location: { origin: "http://attacker.test" } });
    const fetchImpl = vi.fn();
    const api = new GeneratedBrowserAuthApi(config, fetchImpl);

    await expect(api.refresh("refresh-key")).rejects.toMatchObject({
      code: "authentication_failed",
    });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("returns stable sanitized errors without request values", async () => {
    const api = new GeneratedBrowserAuthApi(
      config,
      async () =>
        new Response(
          JSON.stringify({ code: "unexpected", message: "otp-secret-value" }),
          {
            status: 401,
            headers: { "Content-Type": "application/json" },
          },
        ),
    );

    await expect(
      api.createSession(
        { challengeId: "challenge", otp: "otp-secret-value" },
        "key",
      ),
    ).rejects.toMatchObject({ code: "authentication_failed", status: 401 });
    await expect(
      api.createSession(
        { challengeId: "challenge", otp: "otp-secret-value" },
        "key",
      ),
    ).rejects.not.toThrow("otp-secret-value");
  });

  it("ignores malformed encoded CSRF cookies", async () => {
    vi.stubGlobal("document", { cookie: "mirror_csrf=%E0%A4" });
    vi.stubGlobal("window", { location: { origin: "http://web.test" } });
    const api = new GeneratedBrowserAuthApi(config, vi.fn());

    await expect(api.refresh("refresh-key")).rejects.toMatchObject({
      code: "csrf_unavailable",
    });
  });
});

describe("browser memory session", () => {
  it("sanitizes generated-client network failures and retains the uncertain submission key", async () => {
    const marker = "phone-and-otp-must-not-escape";
    const requestKeys: string[] = [];
    let firstRequest = true;
    const api = new GeneratedBrowserAuthApi(config, async (request) => {
      requestKeys.push(request.headers.get("Idempotency-Key") ?? "");
      if (firstRequest) {
        firstRequest = false;
        throw new TypeError(marker);
      }
      return new Response(
        JSON.stringify({
          challenge_id: "c".repeat(32),
          expires_at: "2026-08-15T00:00:00Z",
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      );
    });
    const session = new BrowserAuthSession(api, config);

    await expect(
      session.requestSmsChallenge(
        { phone: marker, inviteCode: marker },
        "challenge-submit",
      ),
    ).rejects.toMatchObject({ code: "network_error" });
    expect(session.getSnapshot().error).toMatchObject({
      code: "network_error",
    });
    expect(JSON.stringify(session.getSnapshot())).not.toContain(marker);

    await session.requestSmsChallenge(
      { phone: marker, inviteCode: marker },
      "challenge-submit",
    );

    expect(requestKeys).toHaveLength(2);
    expect(requestKeys[0]).toBe(requestKeys[1]);
  });

  it("exposes only high-level auth operations and releases successful submission keys", async () => {
    const api = new FakeAuthApi();
    const session = new BrowserAuthSession(api, config);

    await session.requestSmsChallenge(
      { phone: "synthetic" },
      "challenge-submit",
    );
    await session.requestSmsChallenge(
      { phone: "synthetic" },
      "challenge-submit",
    );

    expect(api.smsKeys).toHaveLength(2);
    expect(api.smsKeys[0]).not.toBe(api.smsKeys[1]);
    expect(
      (session as { getAccessToken?: unknown }).getAccessToken,
    ).toBeUndefined();
  });

  it("retains a submission key only while the network outcome is uncertain", async () => {
    const api = new FakeAuthApi();
    let shouldFail = true;
    api.requestSmsChallenge = async (_, key) => {
      api.smsKeys.push(key);
      if (shouldFail) {
        shouldFail = false;
        throw new BrowserAuthError("network_error");
      }
      return {
        challenge_id: "c".repeat(32),
        expires_at: "2026-08-15T00:00:00Z",
      };
    };
    const session = new BrowserAuthSession(api, config);

    await expect(
      session.requestSmsChallenge({ phone: "synthetic" }, "challenge-submit"),
    ).rejects.toThrow(BrowserAuthError);
    await session.requestSmsChallenge(
      { phone: "synthetic" },
      "challenge-submit",
    );

    expect(api.smsKeys).toHaveLength(2);
    expect(api.smsKeys[0]).toBe(api.smsKeys[1]);
  });

  it("releases a completed refresh idempotency key before the next rotation", async () => {
    const api = new FakeAuthApi();
    const session = new BrowserAuthSession(api, config);

    await session.refresh();
    await session.refresh();

    expect(api.refreshKeys).toHaveLength(2);
    expect(api.refreshKeys[0]).not.toBe(api.refreshKeys[1]);
  });

  it("uses one refresh for concurrent bootstrap callers and enters pending", async () => {
    const api = new FakeAuthApi();
    const session = new BrowserAuthSession(api, config);

    await Promise.all([session.bootstrap(), session.bootstrap()]);

    expect(api.refreshCalls).toBe(1);
    expect(session.getSnapshot()).toMatchObject({
      status: "pending",
      user: pendingUser,
    });
  });

  it("moves to a stable error state without retaining account data on bootstrap failure", async () => {
    const api = new FakeAuthApi();
    api.refresh = async () => {
      throw new BrowserAuthError("network_error");
    };
    const session = new BrowserAuthSession(api, config);

    await session.bootstrap();

    expect(session.getSnapshot()).toMatchObject({
      status: "error",
      user: null,
    });
    expect(session.getSnapshot().error).toMatchObject({
      code: "network_error",
    });
  });

  it("treats a missing bootstrap CSRF cookie as an anonymous session", async () => {
    const api = new FakeAuthApi();
    api.refresh = async () => {
      throw new BrowserAuthError("csrf_unavailable");
    };
    const session = new BrowserAuthSession(api, config);

    await session.bootstrap();

    expect(session.getSnapshot()).toEqual({
      status: "anonymous",
      user: null,
      error: null,
    });
  });

  it("replays a protected request once after a 401 and then enters active", async () => {
    const api = new FakeAuthApi();
    api.current = async (accessToken) => {
      if (accessToken === "first-token") {
        throw new BrowserAuthError("authentication_failed", 401);
      }
      return activeUser;
    };
    const session = new BrowserAuthSession(api, config);

    await session.completeSession("challenge", "otp", "session-submit");

    expect(api.createSessionCalls).toBe(1);
    expect(api.refreshCalls).toBe(1);
    expect(api.currentTokens).toEqual(["first-token", "refreshed-token"]);
    expect(session.getSnapshot()).toMatchObject({
      status: "active",
      user: activeUser,
    });
  });

  it("does not rotate twice when concurrent 401 responses arrive after a refresh", async () => {
    const api = new FakeAuthApi();
    api.refresh = async () => {
      api.refreshCalls += 1;
      return token(api.refreshCalls === 1 ? "stale-token" : "fresh-token");
    };
    api.current = async (accessToken) => {
      if (accessToken === "stale-token") {
        throw new BrowserAuthError("authentication_failed", 401);
      }
      return activeUser;
    };
    const session = new BrowserAuthSession(api, config);

    await Promise.all([session.bootstrap(), session.bootstrap()]);

    expect(api.refreshCalls).toBe(2);
    expect(api.currentTokens).toEqual([
      "stale-token",
      "stale-token",
      "fresh-token",
      "fresh-token",
    ]);
    expect(session.getSnapshot().status).toBe("active");
  });

  it("refreshes a stale pending token after activation and keeps credential transient", async () => {
    const api = new FakeAuthApi();
    api.current = async (accessToken) => {
      if (accessToken === "first-token") {
        return pendingUser;
      }
      return activeUser;
    };
    const session = new BrowserAuthSession(api, config);

    await session.completeSession("challenge", "otp", "session-submit");
    api.current = async (accessToken) => {
      if (accessToken === "first-token") {
        throw new BrowserAuthError("authentication_failed", 401);
      }
      return activeUser;
    };
    await session.recordAgeAssurance("credential-only-in-flight", "age-submit");
    await session.acceptPolicy(config.policyManifest[0]!, "policy-submit");

    expect(api.ageKeys).toHaveLength(1);
    expect(api.policyKeys).toHaveLength(1);
    expect(api.refreshCalls).toBe(1);
    expect(session.getSnapshot()).toMatchObject({
      status: "active",
      user: activeUser,
    });
    expect(JSON.stringify(session.getSnapshot())).not.toContain(
      "credential-only-in-flight",
    );
  });

  it("does not touch browser storage while recovering a session", async () => {
    const storage = { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn() };
    vi.stubGlobal("localStorage", storage);
    vi.stubGlobal("sessionStorage", storage);
    const session = new BrowserAuthSession(new FakeAuthApi(), config);

    await session.bootstrap();

    expect(storage.getItem).not.toHaveBeenCalled();
    expect(storage.setItem).not.toHaveBeenCalled();
    expect(storage.removeItem).not.toHaveBeenCalled();
  });
});

describe("data-rights session boundary", () => {
  it("keeps an active session available after a transient data-rights failure", async () => {
    const auth = new FakeAuthApi();
    auth.current = async () => activeUser;
    const dataRights = new FakeDataRightsApi();
    dataRights.listResult = async () => {
      throw new BrowserAuthError("network_error", 503);
    };
    const session = new BrowserAuthSession(auth, config, dataRights);
    await session.bootstrap();

    await expect(session.listAssets()).rejects.toMatchObject({
      code: "network_error",
      status: 503,
    });
    expect(session.getSnapshot()).toMatchObject({
      status: "active",
      user: activeUser,
    });

    dataRights.listResult = async () => ({ assets: [] });
    await expect(session.listAssets()).resolves.toEqual({ assets: [] });
  });

  it("polls account deletion with the existing access token and never refreshes the revoked family", async () => {
    vi.stubGlobal("crypto", {
      getRandomValues(bytes: Uint8Array) {
        bytes.fill(7);
        return bytes;
      },
    });
    const auth = new FakeAuthApi();
    auth.current = async () => activeUser;
    const dataRights = new FakeDataRightsApi();
    const session = new BrowserAuthSession(auth, config, dataRights);
    await session.bootstrap();
    expect(auth.refreshCalls).toBe(1);

    await session.createAccountDeletion("account-deletion");
    await expect(session.getCurrentAccountDeletion()).resolves.toMatchObject({
      status: "completed",
    });

    expect(auth.refreshCalls).toBe(1);
    expect(dataRights.statusTokens).toEqual(["refreshed-token"]);
    session.clearAfterAccountDeletion();
    expect(session.getSnapshot()).toMatchObject({ status: "anonymous" });
  });
});

describe("idempotency lifecycle", () => {
  it("retains a Web Crypto key for uncertain retries and replaces it only on restart", async () => {
    let seed = 0;
    vi.stubGlobal("crypto", {
      getRandomValues(bytes: Uint8Array) {
        bytes.fill(seed++);
        return bytes;
      },
    });
    const keys = new IdempotencyKeyPool();

    const first = await keys.retain("submit");
    expect(await keys.retain("submit")).toBe(first);
    keys.restart("submit");
    expect(await keys.retain("submit")).not.toBe(first);
  });
});
