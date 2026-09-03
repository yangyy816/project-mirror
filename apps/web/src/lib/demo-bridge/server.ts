import "server-only";

import { createHash, randomBytes } from "node:crypto";

import { serverEnv } from "@mirror/config/server";
import { createMirrorApiClient } from "@mirror/contracts";

export type DemoContextResponse = Readonly<{
  session_id: string;
  profile_id: string;
  compilation_digest: string;
  expires_at: string;
}>;
export type DemoTraceResponse = Readonly<{
  session_id: string;
  evidence_digest: string;
  context_compilation_id: string;
}>;

export type DemoContextProjection = Readonly<{
  profile_id: string;
  compilation_digest: string;
  expires_at: string;
}>;
export type DemoTraceProjection = Readonly<{
  evidence_digest: string;
  context_compilation_id: string;
}>;

type BoundSession = Readonly<{
  sessionId: string;
  expiresAtMs: number;
  bindingFingerprint: string;
  analysis?: BoundAnalysis;
}>;

type BoundAnalysis = Readonly<{
  createIdempotencyKey: string;
  jobId?: string;
  analysisId?: string;
  jobBindingDigest?: string;
  targetAuthorityDigest?: string;
  selfStateId?: string;
  createPromise?: Promise<DemoAnalysisBridgeResult>;
}>;

type BridgeConfiguration = Readonly<{
  identityId: string;
  bearer: string;
  maxAge: number;
  bindingFingerprint: string;
}>;

export const demoSessionCookieName = "mirror_demo_session";
export const demoSessionPath = "/api/demo";

const registryKey = Symbol.for("project-mirror.demo-bridge.sessions.v1");
type DemoBridgeGlobal = typeof globalThis & {
  [registryKey]?: Map<string, BoundSession>;
};
const bridgeGlobal = globalThis as DemoBridgeGlobal;
const sessions =
  bridgeGlobal[registryKey] ??
  (bridgeGlobal[registryKey] = new Map<string, BoundSession>());
const maximumSessions = 64;

export type BridgeErrorCode =
  | "DENIED"
  | "UNAVAILABLE"
  | "NOT_FOUND"
  | "CONFLICT"
  | "UNSUPPORTED"
  | "INVALID_RECALL_AT"
  | "STALE_RESPONSE";

export type BridgeResult =
  | Readonly<{
      kind: "READY";
      recallAt: string;
      context: DemoContextProjection;
      trace: DemoTraceProjection;
    }>
  | Readonly<{ kind: BridgeErrorCode }>;

export type DemoAnalysisBridgeResult =
  | Readonly<{ kind: "PENDING" }>
  | Readonly<{
      kind: "COMPLETED";
      analysisState: "SUPPORTED" | "UNSUPPORTED";
      selfState: "READY";
    }>
  | Readonly<{ kind: "CANCELLED" | "REJECTED" | "FAILED" }>
  | Readonly<{ kind: BridgeErrorCode }>;

function configuredTtlSeconds(): number | null {
  const raw = process.env.DEMO_SESSION_TTL_SECONDS;
  if (raw === undefined) return 900;
  if (!/^\d+$/.test(raw)) return null;
  const value = Number(raw);
  return value >= 60 && value <= 900 ? value : null;
}

function configuredBootstrapIdentityId(): string | null {
  const value = process.env.DEMO_BOOTSTRAP_IDENTITY_ID;
  return value && /^[a-f0-9]{32}$/.test(value) ? value : null;
}

function configuredBearer(): string | null {
  const value = process.env.DEMO_BEARER_TOKEN;
  if (!value || value !== value.trim()) return null;
  return value.length >= 16 && value.length <= 512 ? value : null;
}

function currentBridgeConfiguration(): BridgeConfiguration | null {
  const identityId = configuredBootstrapIdentityId();
  const bearer = configuredBearer();
  const maxAge = configuredTtlSeconds();
  if (!identityId || !bearer || maxAge === null) return null;
  return {
    identityId,
    bearer,
    maxAge,
    bindingFingerprint: createHash("sha256")
      .update(
        JSON.stringify([identityId, bearer, serverEnv.API_BASE_URL, maxAge]),
      )
      .digest("hex"),
  };
}

export function isSameOriginRequest(request: Request): boolean {
  const expectedOrigin = new URL(request.url).origin;
  const origin = request.headers.get("origin");
  const fetchSite = request.headers.get("sec-fetch-site");
  if (origin === null && fetchSite === null) return false;
  if (origin !== null && origin !== expectedOrigin) return false;
  return fetchSite === null || fetchSite === "same-origin";
}

export function canonicalRecallAt(value: string | null): string | null {
  if (!value || !/(?:Z|[+-]\d\d:\d\d)$/i.test(value)) return null;
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return null;
  return new Date(timestamp).toISOString();
}

function sweepExpiredSessions(nowMs: number): void {
  for (const [handle, session] of sessions) {
    if (session.expiresAtMs <= nowMs) sessions.delete(handle);
  }
}

function validUpstreamSessionId(value: string): boolean {
  return /^[a-f0-9]{32}$/.test(value);
}

function validUpstreamDigest(value: unknown): value is string {
  return typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
}

function validUpstreamId(value: unknown): value is string {
  return typeof value === "string" && /^[a-f0-9]{32}$/.test(value);
}

function validUpstreamExpiry(value: string): number | null {
  if (!/(?:Z|[+-]\d\d:\d\d)$/i.test(value)) return null;
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}

export async function createBoundDemoSession(
  existingHandle?: string,
  nowMs = Date.now(),
): Promise<Readonly<{ handle: string; maxAge: number }> | null> {
  sweepExpiredSessions(nowMs);
  const configuration = currentBridgeConfiguration();
  const existing = existingHandle ? sessions.get(existingHandle) : undefined;
  if (
    existingHandle &&
    existing &&
    configuration &&
    existing.expiresAtMs > nowMs &&
    existing.bindingFingerprint === configuration.bindingFingerprint
  ) {
    return {
      handle: existingHandle,
      maxAge: Math.max(1, Math.floor((existing.expiresAtMs - nowMs) / 1_000)),
    };
  }
  if (existingHandle && existing) sessions.delete(existingHandle);
  if (!configuration) return null;
  if (sessions.size >= maximumSessions) return null;

  const client = createMirrorApiClient(serverEnv.API_BASE_URL);
  const headers = { Authorization: `Bearer ${configuration.bearer}` };
  const created = await (async () => {
    const identities = await client.GET("/api/v1/demo/identities", {
      cache: "no-store",
      headers,
    });
    if (identities.error || !identities.data) return null;
    if (
      !identities.data.identities.some(
        (identity) =>
          identity.identity_id === configuration.identityId &&
          identity.admission_status === "ADMITTED",
      )
    ) {
      return null;
    }
    const session = await client.POST("/api/v1/demo/sessions", {
      body: {
        synthetic_identity_id: configuration.identityId,
        context_seed: randomBytes(32).toString("hex"),
      },
      params: {
        header: {
          "Idempotency-Key": randomBytes(32).toString("hex"),
        },
      },
      headers: {
        ...headers,
      },
    });
    if (session.error || !session.data) return null;
    return session.data;
  })().catch(() => null);
  if (
    !created ||
    created.synthetic_identity_id !== configuration.identityId ||
    created.status !== "ACTIVE" ||
    !validUpstreamSessionId(created.session_id)
  ) {
    return null;
  }
  const upstreamExpiryMs = validUpstreamExpiry(created.expires_at);
  if (upstreamExpiryMs === null || upstreamExpiryMs <= nowMs) return null;
  const maxAge = Math.min(
    configuration.maxAge,
    Math.floor((upstreamExpiryMs - nowMs) / 1_000),
  );
  if (maxAge < 1) return null;
  if (sessions.size >= maximumSessions) return null;

  const handle = randomBytes(32).toString("hex");
  sessions.set(handle, {
    sessionId: created.session_id,
    expiresAtMs: nowMs + maxAge * 1_000,
    bindingFingerprint: configuration.bindingFingerprint,
  });
  return { handle, maxAge };
}

export function removeBoundDemoSession(handle: string | undefined): void {
  if (handle) sessions.delete(handle);
}

export function boundSessionFor(
  handle: string | undefined,
  nowMs = Date.now(),
): BoundSession | null {
  if (!handle) return null;
  const entry = sessions.get(handle);
  if (!entry) return null;
  if (entry.expiresAtMs <= nowMs) {
    sessions.delete(handle);
    return null;
  }
  return entry;
}

export function errorForStatus(status: number): BridgeErrorCode {
  if (status === 401 || status === 403) return "DENIED";
  if (status === 404) return "NOT_FOUND";
  if (status === 409 || status === 422) return "CONFLICT";
  if (status === 501) return "UNSUPPORTED";
  return "UNAVAILABLE";
}

export function demoSessionRegistrySize(nowMs = Date.now()): number {
  sweepExpiredSessions(nowMs);
  return sessions.size;
}

export function clearDemoSessionRegistryForTest(): void {
  sessions.clear();
}

function currentBoundSession(handle: string | undefined): Readonly<{
  session: BoundSession;
  configuration: BridgeConfiguration;
}> | null {
  const session = boundSessionFor(handle);
  if (!session) return null;
  const configuration = currentBridgeConfiguration();
  if (!configuration) {
    removeBoundDemoSession(handle);
    return null;
  }
  if (session.bindingFingerprint !== configuration.bindingFingerprint) {
    removeBoundDemoSession(handle);
    return null;
  }
  return { session, configuration };
}

function currentAnalysisEntry(
  handle: string,
  expectedSession: BoundSession,
  expectedAnalysis: BoundAnalysis,
): boolean {
  const current = currentBoundSession(handle);
  return (
    current !== null &&
    current.session === expectedSession &&
    current.session.analysis === expectedAnalysis
  );
}

function createdAnalysisIsValid(body: unknown): body is Readonly<{
  job_id: string;
  status: "PENDING";
  capability: "P3_FACE_ANALYSIS";
  job_binding_digest: string;
  target: Readonly<{
    target_type: "ANALYSIS_RUN";
    target_id: string;
    authority_digest: string;
  }>;
}> {
  if (!body || typeof body !== "object") return false;
  const value = body as Record<string, unknown>;
  const target = value.target;
  if (!target || typeof target !== "object") return false;
  const targetValue = target as Record<string, unknown>;
  return (
    validUpstreamId(value.job_id) &&
    value.status === "PENDING" &&
    value.capability === "P3_FACE_ANALYSIS" &&
    validUpstreamDigest(value.job_binding_digest) &&
    targetValue.target_type === "ANALYSIS_RUN" &&
    validUpstreamId(targetValue.target_id) &&
    validUpstreamDigest(targetValue.authority_digest)
  );
}

function jobIsValid(
  body: unknown,
  analysis: BoundAnalysis,
): body is Readonly<{
  job_id: string;
  status:
    | "PENDING"
    | "RUNNING"
    | "COMPLETED"
    | "REJECTED"
    | "FAILED"
    | "CANCELLED";
  capability: "P3_FACE_ANALYSIS";
  job_binding_digest: string;
  target: Readonly<{
    target_type: "ANALYSIS_RUN";
    target_id: string;
    authority_digest: string;
  }>;
}> {
  if (!body || typeof body !== "object") return false;
  const value = body as Record<string, unknown>;
  const target = value.target;
  if (!target || typeof target !== "object") return false;
  const targetValue = target as Record<string, unknown>;
  return (
    value.job_id === analysis.jobId &&
    (value.status === "PENDING" ||
      value.status === "RUNNING" ||
      value.status === "COMPLETED" ||
      value.status === "REJECTED" ||
      value.status === "FAILED" ||
      value.status === "CANCELLED") &&
    value.capability === "P3_FACE_ANALYSIS" &&
    value.job_binding_digest === analysis.jobBindingDigest &&
    targetValue.target_type === "ANALYSIS_RUN" &&
    targetValue.target_id === analysis.analysisId &&
    targetValue.authority_digest === analysis.targetAuthorityDigest
  );
}

function snapshotIsValid(
  body: unknown,
  sessionId: string,
  analysis: BoundAnalysis,
): body is Readonly<{
  analysis_id: string;
  session_id: string;
  state: "SUPPORTED" | "UNSUPPORTED";
  observation_digest: string;
  self_state_id: string;
}> {
  if (!body || typeof body !== "object") return false;
  const value = body as Record<string, unknown>;
  return (
    value.analysis_id === analysis.analysisId &&
    value.session_id === sessionId &&
    (value.state === "SUPPORTED" || value.state === "UNSUPPORTED") &&
    validUpstreamDigest(value.observation_digest) &&
    validUpstreamId(value.self_state_id)
  );
}

export async function createBoundDemoAnalysis(
  handle: string | undefined,
): Promise<DemoAnalysisBridgeResult> {
  const bound = currentBoundSession(handle);
  if (!bound || !handle) return { kind: "DENIED" };
  const { session, configuration } = bound;
  if (session.analysis?.createPromise) return session.analysis.createPromise;
  if (session.analysis?.jobId) return { kind: "PENDING" };

  const analysis: BoundAnalysis = {
    createIdempotencyKey:
      session.analysis?.createIdempotencyKey ?? randomBytes(32).toString("hex"),
  };
  const inFlightAnalysis = {
    ...analysis,
    createPromise: null as unknown as Promise<DemoAnalysisBridgeResult>,
  };
  const inFlightSession: BoundSession = {
    ...session,
    analysis: inFlightAnalysis,
  };
  const promise = (async (): Promise<DemoAnalysisBridgeResult> => {
    const client = createMirrorApiClient(serverEnv.API_BASE_URL);
    const response = await client
      .POST("/api/v1/demo/sessions/{session_id}/analysis", {
        params: {
          path: { session_id: session.sessionId },
          header: { "Idempotency-Key": analysis.createIdempotencyKey },
        },
        headers: { Authorization: `Bearer ${configuration.bearer}` },
        cache: "no-store",
      })
      .catch(() => null);
    if (!currentAnalysisEntry(handle, inFlightSession, inFlightAnalysis)) {
      return { kind: "DENIED" };
    }
    if (!response) {
      sessions.set(handle, { ...inFlightSession, analysis });
      return { kind: "UNAVAILABLE" };
    }
    if (response.response.status !== 202) {
      sessions.set(handle, { ...inFlightSession, analysis });
      return { kind: errorForStatus(response.response.status) };
    }
    if (response.error || !response.data) {
      sessions.set(handle, { ...inFlightSession, analysis });
      return { kind: "STALE_RESPONSE" };
    }
    if (!createdAnalysisIsValid(response.data)) {
      sessions.set(handle, { ...inFlightSession, analysis });
      return { kind: "STALE_RESPONSE" };
    }
    if (!currentAnalysisEntry(handle, inFlightSession, inFlightAnalysis)) {
      return { kind: "DENIED" };
    }
    sessions.set(handle, {
      ...inFlightSession,
      analysis: {
        createIdempotencyKey: analysis.createIdempotencyKey,
        jobId: response.data.job_id,
        analysisId: response.data.target.target_id,
        jobBindingDigest: response.data.job_binding_digest,
        targetAuthorityDigest: response.data.target.authority_digest,
      },
    });
    return { kind: "PENDING" };
  })();
  inFlightAnalysis.createPromise = promise;
  if (sessions.get(handle) !== session) return { kind: "DENIED" };
  sessions.set(handle, inFlightSession);
  return promise;
}

export async function readBoundDemoAnalysis(
  handle: string | undefined,
): Promise<DemoAnalysisBridgeResult> {
  const bound = currentBoundSession(handle);
  if (!bound) return { kind: "DENIED" };
  const { session, configuration } = bound;
  const analysis = session.analysis;
  if (!analysis?.jobId || !analysis.analysisId) return { kind: "NOT_FOUND" };
  const client = createMirrorApiClient(serverEnv.API_BASE_URL);
  const job = await client
    .GET("/api/v1/demo/jobs/{job_id}", {
      cache: "no-store",
      params: { path: { job_id: analysis.jobId } },
      headers: { Authorization: `Bearer ${configuration.bearer}` },
    })
    .catch(() => null);
  if (!currentAnalysisEntry(handle!, session, analysis))
    return { kind: "DENIED" };
  if (!job) return { kind: "UNAVAILABLE" };
  if (job.error) return { kind: errorForStatus(job.response.status) };
  if (!job.data || job.response.status !== 200)
    return { kind: "STALE_RESPONSE" };
  if (!jobIsValid(job.data, analysis)) return { kind: "STALE_RESPONSE" };
  if (job.data.status === "PENDING" || job.data.status === "RUNNING") {
    if (!currentAnalysisEntry(handle!, session, analysis))
      return { kind: "DENIED" };
    return { kind: "PENDING" };
  }
  if (job.data.status !== "COMPLETED") {
    if (!currentAnalysisEntry(handle!, session, analysis))
      return { kind: "DENIED" };
    return { kind: job.data.status };
  }
  const snapshot = await client
    .GET("/api/v1/demo/analyses/{analysis_id}", {
      cache: "no-store",
      params: { path: { analysis_id: analysis.analysisId } },
      headers: { Authorization: `Bearer ${configuration.bearer}` },
    })
    .catch(() => null);
  if (!currentAnalysisEntry(handle!, session, analysis))
    return { kind: "DENIED" };
  if (!snapshot) return { kind: "UNAVAILABLE" };
  if (snapshot.error) return { kind: errorForStatus(snapshot.response.status) };
  if (snapshot.response.status !== 200 || !snapshot.data)
    return { kind: "STALE_RESPONSE" };
  if (!snapshotIsValid(snapshot.data, session.sessionId, analysis)) {
    return { kind: "STALE_RESPONSE" };
  }
  if (!currentAnalysisEntry(handle!, session, analysis))
    return { kind: "DENIED" };
  sessions.set(handle!, {
    ...session,
    analysis: { ...analysis, selfStateId: snapshot.data.self_state_id },
  });
  return {
    kind: "COMPLETED",
    analysisState: snapshot.data.state,
    selfState: "READY",
  };
}

export async function readBoundDemoRecall(
  handle: string | undefined,
  requestedRecallAt: string | null,
): Promise<BridgeResult> {
  const session = boundSessionFor(handle);
  if (!session) return { kind: "DENIED" };
  const configuration = currentBridgeConfiguration();
  if (!configuration) {
    removeBoundDemoSession(handle);
    return { kind: "UNAVAILABLE" };
  }
  if (session.bindingFingerprint !== configuration.bindingFingerprint) {
    removeBoundDemoSession(handle);
    return { kind: "DENIED" };
  }
  const recallAt = canonicalRecallAt(requestedRecallAt);
  if (!recallAt) return { kind: "INVALID_RECALL_AT" };

  const client = createMirrorApiClient(serverEnv.API_BASE_URL);
  const headers = { Authorization: `Bearer ${configuration.bearer}` };
  const [contextResult, traceResult] = await Promise.all([
    client.GET("/api/v1/demo/sessions/{session_id}/context", {
      cache: "no-store",
      params: {
        path: { session_id: session.sessionId },
        query: { recall_at: recallAt },
      },
      headers,
    }),
    client.GET("/api/v1/demo/traces/{session_id}", {
      cache: "no-store",
      params: {
        path: { session_id: session.sessionId },
        query: { recall_at: recallAt },
      },
      headers,
    }),
  ]).catch(() => [null, null] as const);
  if (!contextResult || !traceResult) return { kind: "UNAVAILABLE" };
  if (contextResult.error)
    return { kind: errorForStatus(contextResult.response.status) };
  if (traceResult.error)
    return { kind: errorForStatus(traceResult.response.status) };
  const context = contextResult.data;
  const trace = traceResult.data;
  if (!context || !trace) return { kind: "UNAVAILABLE" };
  if (
    context.session_id !== session.sessionId ||
    trace.session_id !== session.sessionId ||
    context.compilation_digest !== trace.evidence_digest
  ) {
    return { kind: "STALE_RESPONSE" };
  }
  return {
    kind: "READY",
    recallAt,
    context: {
      profile_id: context.profile_id,
      compilation_digest: context.compilation_digest,
      expires_at: context.expires_at,
    },
    trace: {
      context_compilation_id: trace.context_compilation_id,
      evidence_digest: trace.evidence_digest,
    },
  };
}

export function sessionCookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    sameSite: "strict" as const,
    path: demoSessionPath,
    maxAge,
    secure: process.env.NODE_ENV === "production",
  };
}
