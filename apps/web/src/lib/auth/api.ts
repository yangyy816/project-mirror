import { createMirrorApiClient } from "@mirror/contracts";

import type { WebAuthConfig } from "../web-auth-config";

import { BrowserAuthError, sanitizeAuthFailure } from "./errors";

const CSRF_COOKIE_NAME = "mirror_csrf";

export type BrowserFetch = (input: Request) => Promise<Response>;

export type SessionCredentials = Readonly<{
  challengeId: string;
  otp: string;
}>;

export type SmsChallengeInput = Readonly<{
  phone: string;
  inviteCode?: string;
}>;

export function readCookieValue(
  cookieHeader: string,
  name: string,
): string | null {
  const prefix = `${name}=`;
  for (const entry of cookieHeader.split(";")) {
    const trimmed = entry.trim();
    if (trimmed.startsWith(prefix)) {
      try {
        return decodeURIComponent(trimmed.slice(prefix.length));
      } catch {
        return null;
      }
    }
  }
  return null;
}

function browserCsrfToken(): string {
  if (typeof document === "undefined") {
    throw new BrowserAuthError("csrf_unavailable");
  }
  const token = readCookieValue(document.cookie, CSRF_COOKIE_NAME);
  if (token === null || token.length === 0) {
    throw new BrowserAuthError("csrf_unavailable");
  }
  return token;
}

function authHeader(accessToken: string): Record<"authorization", string> {
  return { authorization: `Bearer ${accessToken}` };
}

function csrfHeaders(): Record<"X-CSRF-Token", string> {
  return { "X-CSRF-Token": browserCsrfToken() };
}

function requireConfiguredBrowserOrigin(config: WebAuthConfig): void {
  if (
    typeof window === "undefined" ||
    window.location.origin !== config.appOrigin
  ) {
    throw new BrowserAuthError("authentication_failed");
  }
}

function idempotencyHeaders(
  idempotencyKey: string,
): Record<"Idempotency-Key", string> {
  return { "Idempotency-Key": idempotencyKey };
}

export class GeneratedBrowserAuthApi {
  private readonly client;
  private readonly fetchImpl: BrowserFetch;

  constructor(
    private readonly config: WebAuthConfig,
    fetchImpl: BrowserFetch = (request) => fetch(request),
  ) {
    this.client = createMirrorApiClient(config.apiBaseUrl);
    this.fetchImpl = fetchImpl;
  }

  async requestSmsChallenge(
    payload: SmsChallengeInput,
    idempotencyKey: string,
  ) {
    const result = await this.client.POST("/api/v1/auth/sms-challenges", {
      body: { phone: payload.phone, invite_code: payload.inviteCode },
      params: { header: idempotencyHeaders(idempotencyKey) },
      credentials: "include",
      fetch: this.fetchImpl,
    });
    return this.unwrap(result);
  }

  async createSession(payload: SessionCredentials, idempotencyKey: string) {
    const result = await this.client.POST("/api/v1/auth/sessions", {
      body: { challenge_id: payload.challengeId, otp: payload.otp },
      params: { header: idempotencyHeaders(idempotencyKey) },
      credentials: "include",
      fetch: this.fetchImpl,
    });
    return this.unwrap(result);
  }

  async refresh(idempotencyKey: string) {
    requireConfiguredBrowserOrigin(this.config);
    const result = await this.client.POST("/api/v1/auth/token/refresh", {
      params: {
        header: { ...idempotencyHeaders(idempotencyKey), ...csrfHeaders() },
      },
      credentials: "include",
      fetch: this.fetchImpl,
    });
    return this.unwrap(result);
  }

  async currentUser(accessToken: string) {
    const result = await this.client.GET("/api/v1/users/me", {
      params: { header: authHeader(accessToken) },
      credentials: "include",
      fetch: this.fetchImpl,
    });
    return this.unwrap(result);
  }

  async recordAgeAssurance(
    credential: string,
    accessToken: string,
    idempotencyKey: string,
  ) {
    const result = await this.client.POST("/api/v1/users/me/age-assurances", {
      body: { credential },
      params: {
        header: {
          ...authHeader(accessToken),
          ...idempotencyHeaders(idempotencyKey),
        },
      },
      credentials: "include",
      fetch: this.fetchImpl,
    });
    return this.unwrap(result);
  }

  async acceptPolicy(
    policy: WebAuthConfig["policyManifest"][number],
    accessToken: string,
    idempotencyKey: string,
  ) {
    const result = await this.client.POST(
      "/api/v1/users/me/policy-acceptances",
      {
        body: {
          document_code: policy.document_code,
          document_version: policy.document_version,
          document_digest: policy.document_digest,
        },
        params: {
          header: {
            ...authHeader(accessToken),
            ...idempotencyHeaders(idempotencyKey),
          },
        },
        credentials: "include",
        fetch: this.fetchImpl,
      },
    );
    return this.unwrap(result);
  }

  async logout(accessToken: string): Promise<void> {
    requireConfiguredBrowserOrigin(this.config);
    const result = await this.client.DELETE("/api/v1/auth/sessions/current", {
      params: { header: { ...authHeader(accessToken), ...csrfHeaders() } },
      credentials: "include",
      fetch: this.fetchImpl,
    });
    if (result.error !== undefined) {
      throw sanitizeAuthFailure(result.response.status, result.error);
    }
  }

  private unwrap<T>(result: {
    data?: T;
    error?: unknown;
    response: Response;
  }): T {
    if (result.error !== undefined || result.data === undefined) {
      throw sanitizeAuthFailure(result.response.status, result.error);
    }
    return result.data;
  }
}

export type AccessTokenResponse = Awaited<
  ReturnType<GeneratedBrowserAuthApi["refresh"]>
>;
export type AgeAssuranceResponse = Awaited<
  ReturnType<GeneratedBrowserAuthApi["recordAgeAssurance"]>
>;
export type CurrentUserResponse = Awaited<
  ReturnType<GeneratedBrowserAuthApi["currentUser"]>
>;
export type PolicyAcceptanceResponse = Awaited<
  ReturnType<GeneratedBrowserAuthApi["acceptPolicy"]>
>;
export type SmsChallengeResponse = Awaited<
  ReturnType<GeneratedBrowserAuthApi["requestSmsChallenge"]>
>;

export interface BrowserAuthApi {
  requestSmsChallenge(
    payload: SmsChallengeInput,
    idempotencyKey: string,
  ): Promise<SmsChallengeResponse>;
  createSession(
    payload: SessionCredentials,
    idempotencyKey: string,
  ): Promise<AccessTokenResponse>;
  refresh(idempotencyKey: string): Promise<AccessTokenResponse>;
  currentUser(accessToken: string): Promise<CurrentUserResponse>;
  recordAgeAssurance(
    credential: string,
    accessToken: string,
    idempotencyKey: string,
  ): Promise<AgeAssuranceResponse>;
  acceptPolicy(
    policy: WebAuthConfig["policyManifest"][number],
    accessToken: string,
    idempotencyKey: string,
  ): Promise<PolicyAcceptanceResponse>;
  logout(accessToken: string): Promise<void>;
}
