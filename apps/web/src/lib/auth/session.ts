import type { WebAuthConfig } from "../web-auth-config";

import type {
  AgeAssuranceResponse,
  BrowserAuthApi,
  CurrentUserResponse,
  PolicyAcceptanceResponse,
  SmsChallengeInput,
  SmsChallengeResponse,
} from "./api";
import { BrowserAuthError } from "./errors";
import { IdempotencyKeyPool } from "./idempotency";

export type BrowserSessionStatus =
  | "bootstrapping"
  | "anonymous"
  | "pending"
  | "active"
  | "error";

export type BrowserSessionSnapshot = Readonly<{
  status: BrowserSessionStatus;
  user: CurrentUserResponse | null;
  error: BrowserAuthError | null;
}>;

type SessionListener = (snapshot: BrowserSessionSnapshot) => void;

const initialSnapshot: BrowserSessionSnapshot = {
  status: "bootstrapping",
  user: null,
  error: null,
};

export class BrowserAuthSession {
  private accessToken: string | null = null;
  private accessGeneration = 0;
  private refreshPromise: Promise<void> | null = null;
  private snapshot = initialSnapshot;
  private readonly listeners = new Set<SessionListener>();
  private readonly idempotency = new IdempotencyKeyPool();

  constructor(
    private readonly api: BrowserAuthApi,
    readonly config: WebAuthConfig,
  ) {}

  getSnapshot(): BrowserSessionSnapshot {
    return this.snapshot;
  }

  subscribe(listener: SessionListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  restartSubmission(logicalSubmission: string): void {
    this.idempotency.restart(logicalSubmission);
  }

  async bootstrap(): Promise<BrowserSessionSnapshot> {
    this.update({ status: "bootstrapping", user: null, error: null });
    try {
      await this.refresh();
      await this.resumeCurrentUser();
    } catch (error) {
      if (error instanceof BrowserAuthError && error.status === 401) {
        this.clearToAnonymous();
      } else {
        this.update({
          status: "error",
          user: null,
          error: this.sanitize(error),
        });
      }
    }
    return this.snapshot;
  }

  async completeSession(
    challengeId: string,
    otp: string,
    logicalSubmission: string,
  ): Promise<void> {
    return this.surface(async () => {
      const key = await this.idempotency.retain(logicalSubmission);
      const result = await this.api.createSession({ challengeId, otp }, key);
      this.idempotency.restart(logicalSubmission);
      this.accessToken = result.access_token;
      await this.resumeCurrentUser();
    });
  }

  async requestSmsChallenge(
    payload: SmsChallengeInput,
    logicalSubmission: string,
  ): Promise<SmsChallengeResponse> {
    return this.surface(async () => {
      const key = await this.idempotency.retain(logicalSubmission);
      const challenge = await this.api.requestSmsChallenge(payload, key);
      this.idempotency.restart(logicalSubmission);
      return challenge;
    });
  }

  async recordAgeAssurance(
    credential: string,
    logicalSubmission: string,
  ): Promise<AgeAssuranceResponse> {
    return this.surface(async () => {
      const key = await this.idempotency.retain(logicalSubmission);
      const outcome = await this.withAuthorizedRequest((token) =>
        this.api.recordAgeAssurance(credential, token, key),
      );
      this.idempotency.restart(logicalSubmission);
      await this.resumeCurrentUser();
      return outcome;
    });
  }

  async acceptPolicy(
    policy: WebAuthConfig["policyManifest"][number],
    logicalSubmission: string,
  ): Promise<PolicyAcceptanceResponse> {
    return this.surface(async () => {
      const approvedPolicy = this.config.policyManifest.find(
        (candidate) =>
          candidate.document_code === policy.document_code &&
          candidate.document_version === policy.document_version &&
          candidate.document_digest === policy.document_digest,
      );
      if (approvedPolicy === undefined) {
        throw new BrowserAuthError("authentication_failed");
      }
      const key = await this.idempotency.retain(logicalSubmission);
      const outcome = await this.withAuthorizedRequest((token) =>
        this.api.acceptPolicy(approvedPolicy, token, key),
      );
      this.idempotency.restart(logicalSubmission);
      await this.resumeCurrentUser();
      return outcome;
    });
  }

  async resumeCurrentUser(): Promise<CurrentUserResponse> {
    return this.surface(async () => {
      const user = await this.withAuthorizedRequest((token) =>
        this.api.currentUser(token),
      );
      this.applyUser(user);
      return user;
    });
  }

  async refresh(): Promise<void> {
    if (this.refreshPromise === null) {
      this.refreshPromise = this.refreshAccessToken().finally(() => {
        this.refreshPromise = null;
      });
    }
    try {
      await this.refreshPromise;
    } catch (error) {
      throw this.fail(error);
    }
  }

  async logout(): Promise<void> {
    try {
      await this.withAuthorizedRequest((token) => this.api.logout(token));
    } catch (error) {
      const sanitized = this.sanitize(error);
      this.update({ status: "error", user: null, error: sanitized });
      throw sanitized;
    }
    this.clearToAnonymous();
  }

  private async refreshAccessToken(): Promise<void> {
    const key = await this.idempotency.retain("refresh");
    try {
      const result = await this.api.refresh(key);
      this.accessToken = result.access_token;
      this.accessGeneration += 1;
      this.idempotency.restart("refresh");
    } catch (error) {
      this.accessToken = null;
      throw this.sanitize(error);
    }
  }

  private async withAuthorizedRequest<T>(
    request: (accessToken: string) => Promise<T>,
  ): Promise<T> {
    if (this.accessToken === null) {
      await this.refresh();
    }
    const accessToken = this.requireAccessToken();
    const generation = this.accessGeneration;
    try {
      return await request(accessToken);
    } catch (error) {
      const sanitized = this.sanitize(error);
      if (sanitized.status !== 401) {
        throw sanitized;
      }
      if (this.accessGeneration !== generation) {
        try {
          return await request(this.requireAccessToken());
        } catch (retryError) {
          throw this.sanitize(retryError);
        }
      }
      await this.refresh();
      try {
        return await request(this.requireAccessToken());
      } catch (retryError) {
        throw this.sanitize(retryError);
      }
    }
  }

  private requireAccessToken(): string {
    if (this.accessToken === null) {
      throw new BrowserAuthError("authentication_failed", 401);
    }
    return this.accessToken;
  }

  private applyUser(user: CurrentUserResponse): void {
    const status =
      user.status === "active" && user.scope === "active"
        ? "active"
        : "pending";
    this.update({ status, user, error: null });
  }

  private clearToAnonymous(): void {
    this.accessToken = null;
    this.update({ status: "anonymous", user: null, error: null });
  }

  private sanitize(error: unknown): BrowserAuthError {
    if (error instanceof BrowserAuthError) {
      return error;
    }
    return new BrowserAuthError("network_error");
  }

  private async surface<T>(operation: () => Promise<T>): Promise<T> {
    try {
      return await operation();
    } catch (error) {
      throw this.fail(error);
    }
  }

  private fail(error: unknown): BrowserAuthError {
    const sanitized = this.sanitize(error);
    this.accessToken = null;
    this.update({ status: "error", user: null, error: sanitized });
    return sanitized;
  }

  private update(snapshot: BrowserSessionSnapshot): void {
    this.snapshot = snapshot;
    for (const listener of this.listeners) {
      listener(snapshot);
    }
  }
}
