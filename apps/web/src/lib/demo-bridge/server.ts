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
  questionnaire?: BoundQuestionnaire;
  profile?: BoundProfile;
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

type QuestionnaireChoice = "LEFT" | "RIGHT" | "INDISTINGUISHABLE" | "SKIP";
type QuestionnaireResponsePayload = Readonly<{
  presentationToken: string;
  choice: QuestionnaireChoice;
  responseLatencyMs: number;
}>;
type BoundQuestion = Readonly<{
  stepId: string;
  pairId: string;
  stepSequence: number;
  runVersion: number;
  presentationToken: string;
}>;
type BoundQuestionnaire = Readonly<{
  createIdempotencyKey: string;
  jobId?: string;
  runId?: string;
  jobBindingDigest?: string;
  targetAuthorityDigest?: string;
  question?: BoundQuestion;
  completed?: true;
  createPromise?: Promise<DemoQuestionnaireBridgeResult>;
  response?: Readonly<{
    payload: QuestionnaireResponsePayload;
    idempotencyKey: string;
    promise?: Promise<DemoQuestionnaireBridgeResult>;
  }>;
}>;

type ProfileTerminalStatus = "REJECTED" | "FAILED" | "CANCELLED";
type BoundProfile = Readonly<{
  createIdempotencyKey: string;
  jobId?: string;
  jobBindingDigest?: string;
  targetActorId?: string;
  targetAuthorityDigest?: string;
  profileId?: string;
  compilationDigest?: string;
  terminalStatus?: ProfileTerminalStatus;
  createPromise?: Promise<DemoProfileBridgeResult>;
  readPromise?: Promise<DemoProfileBridgeResult>;
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

export type DemoQuestionnaireBridgeResult =
  | Readonly<{ kind: "PENDING" }>
  | Readonly<{
      kind: "QUESTION";
      presentationToken: string;
    }>
  | Readonly<{ kind: "COMPLETED" }>
  | Readonly<{ kind: "CANCELLED" | "REJECTED" | "FAILED" }>
  | Readonly<{ kind: BridgeErrorCode }>;

export type DemoProfileBridgeResult =
  | Readonly<{ kind: "PENDING" | "PROFILE_READY" }>
  | Readonly<{ kind: ProfileTerminalStatus }>
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

function currentQuestionnaireEntry(
  handle: string,
  expectedSession: BoundSession,
  expectedQuestionnaire: BoundQuestionnaire,
): boolean {
  const current = currentBoundSession(handle);
  return (
    current !== null &&
    current.session === expectedSession &&
    current.session.questionnaire === expectedQuestionnaire
  );
}

function validPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 1;
}

function questionIsValid(
  body: unknown,
  runId: string,
): body is Readonly<{
  kind: "QUESTION";
  step_id: string;
  question_pair_id: string;
  step_sequence: number;
  run_version: number;
}> {
  if (!body || typeof body !== "object") return false;
  const value = body as Record<string, unknown>;
  return (
    value.kind === "QUESTION" &&
    value.run_id === runId &&
    validUpstreamId(value.step_id) &&
    validUpstreamId(value.question_pair_id) &&
    validPositiveInteger(value.step_sequence) &&
    validPositiveInteger(value.run_version) &&
    typeof runId === "string"
  );
}

function completedQuestionnaireIsValid(body: unknown, runId: string): boolean {
  if (!body || typeof body !== "object") return false;
  const value = body as Record<string, unknown>;
  return value.kind === "COMPLETED" && value.run_id === runId;
}

function createdQuestionnaireIsValid(body: unknown): body is Readonly<{
  job_id: string;
  status: "PENDING";
  capability: "P4_QUESTIONNAIRE";
  job_binding_digest: string;
  target: Readonly<{
    target_type: "QUESTIONNAIRE_RUN";
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
    value.capability === "P4_QUESTIONNAIRE" &&
    validUpstreamDigest(value.job_binding_digest) &&
    targetValue.target_type === "QUESTIONNAIRE_RUN" &&
    validUpstreamId(targetValue.target_id) &&
    validUpstreamDigest(targetValue.authority_digest)
  );
}

function questionnaireJobIsValid(
  body: unknown,
  questionnaire: BoundQuestionnaire,
): boolean {
  if (!body || typeof body !== "object") return false;
  const value = body as Record<string, unknown>;
  const target = value.target;
  if (!target || typeof target !== "object") return false;
  const targetValue = target as Record<string, unknown>;
  return (
    value.job_id === questionnaire.jobId &&
    (value.status === "PENDING" ||
      value.status === "RUNNING" ||
      value.status === "COMPLETED" ||
      value.status === "REJECTED" ||
      value.status === "FAILED" ||
      value.status === "CANCELLED") &&
    value.capability === "P4_QUESTIONNAIRE" &&
    value.job_binding_digest === questionnaire.jobBindingDigest &&
    targetValue.target_type === "QUESTIONNAIRE_RUN" &&
    targetValue.target_id === questionnaire.runId &&
    targetValue.authority_digest === questionnaire.targetAuthorityDigest
  );
}

function questionResult(
  question: BoundQuestion,
): DemoQuestionnaireBridgeResult {
  return { kind: "QUESTION", presentationToken: question.presentationToken };
}

async function fetchNextQuestion(
  handle: string,
  session: BoundSession,
  questionnaire: BoundQuestionnaire,
  configuration: BridgeConfiguration,
): Promise<DemoQuestionnaireBridgeResult> {
  if (!questionnaire.runId) return { kind: "STALE_RESPONSE" };
  const client = createMirrorApiClient(serverEnv.API_BASE_URL);
  const result = await client
    .GET("/api/v1/demo/questionnaires/runs/{run_id}/next", {
      cache: "no-store",
      params: { path: { run_id: questionnaire.runId } },
      headers: { Authorization: `Bearer ${configuration.bearer}` },
    })
    .catch(() => null);
  if (!currentQuestionnaireEntry(handle, session, questionnaire))
    return { kind: "DENIED" };
  if (!result) return { kind: "UNAVAILABLE" };
  if (result.error) return { kind: errorForStatus(result.response.status) };
  if (!result.data) return { kind: "STALE_RESPONSE" };
  if (completedQuestionnaireIsValid(result.data, questionnaire.runId)) {
    sessions.set(handle, {
      ...session,
      questionnaire: {
        ...questionnaire,
        completed: true,
        question: undefined,
        response: undefined,
      },
    });
    return { kind: "COMPLETED" };
  }
  if (!questionIsValid(result.data, questionnaire.runId))
    return { kind: "STALE_RESPONSE" };
  const question: BoundQuestion = {
    stepId: result.data.step_id,
    pairId: result.data.question_pair_id,
    stepSequence: result.data.step_sequence,
    runVersion: result.data.run_version,
    presentationToken: randomBytes(32).toString("hex"),
  };
  sessions.set(handle, {
    ...session,
    questionnaire: { ...questionnaire, question, response: undefined },
  });
  return questionResult(question);
}

export async function createBoundDemoQuestionnaire(
  handle: string | undefined,
): Promise<DemoQuestionnaireBridgeResult> {
  const bound = currentBoundSession(handle);
  if (!bound || !handle) return { kind: "DENIED" };
  const { session, configuration } = bound;
  const analysis = session.analysis;
  if (!analysis?.analysisId || !analysis.selfStateId)
    return { kind: "NOT_FOUND" };
  if (session.questionnaire?.createPromise)
    return session.questionnaire.createPromise;
  if (session.questionnaire?.jobId) return { kind: "PENDING" };
  const questionnaire: BoundQuestionnaire = {
    createIdempotencyKey:
      session.questionnaire?.createIdempotencyKey ??
      randomBytes(32).toString("hex"),
  };
  const inFlightQuestionnaire = {
    ...questionnaire,
    createPromise: null as unknown as Promise<DemoQuestionnaireBridgeResult>,
  };
  const inFlightSession: BoundSession = {
    ...session,
    questionnaire: inFlightQuestionnaire,
  };
  const promise = (async (): Promise<DemoQuestionnaireBridgeResult> => {
    const client = createMirrorApiClient(serverEnv.API_BASE_URL);
    const result = await client
      .POST("/api/v1/demo/analyses/{analysis_id}/questionnaire", {
        cache: "no-store",
        params: {
          path: { analysis_id: analysis.analysisId! },
          header: { "Idempotency-Key": questionnaire.createIdempotencyKey },
        },
        headers: { Authorization: `Bearer ${configuration.bearer}` },
      })
      .catch(() => null);
    if (
      !currentQuestionnaireEntry(handle, inFlightSession, inFlightQuestionnaire)
    )
      return { kind: "DENIED" };
    if (!result) {
      sessions.set(handle, { ...inFlightSession, questionnaire });
      return { kind: "UNAVAILABLE" };
    }
    if (result.response.status !== 202 || result.error) {
      sessions.set(handle, { ...inFlightSession, questionnaire });
      return { kind: errorForStatus(result.response.status) };
    }
    if (!createdQuestionnaireIsValid(result.data)) {
      sessions.set(handle, { ...inFlightSession, questionnaire });
      return { kind: "STALE_RESPONSE" };
    }
    sessions.set(handle, {
      ...inFlightSession,
      questionnaire: {
        createIdempotencyKey: questionnaire.createIdempotencyKey,
        jobId: result.data.job_id,
        runId: result.data.target.target_id,
        jobBindingDigest: result.data.job_binding_digest,
        targetAuthorityDigest: result.data.target.authority_digest,
      },
    });
    return { kind: "PENDING" };
  })();
  inFlightQuestionnaire.createPromise = promise;
  if (sessions.get(handle) !== session) return { kind: "DENIED" };
  sessions.set(handle, inFlightSession);
  return promise;
}

export async function readBoundDemoQuestionnaire(
  handle: string | undefined,
): Promise<DemoQuestionnaireBridgeResult> {
  const bound = currentBoundSession(handle);
  if (!bound || !handle) return { kind: "DENIED" };
  const { session, configuration } = bound;
  const questionnaire = session.questionnaire;
  if (!questionnaire?.jobId || !questionnaire.runId)
    return { kind: "NOT_FOUND" };
  if (questionnaire.completed) return { kind: "COMPLETED" };
  if (questionnaire.question && !questionnaire.response)
    return questionResult(questionnaire.question);
  if (questionnaire.response?.promise) return questionnaire.response.promise;
  const client = createMirrorApiClient(serverEnv.API_BASE_URL);
  const job = await client
    .GET("/api/v1/demo/jobs/{job_id}", {
      cache: "no-store",
      params: { path: { job_id: questionnaire.jobId } },
      headers: { Authorization: `Bearer ${configuration.bearer}` },
    })
    .catch(() => null);
  if (!currentQuestionnaireEntry(handle, session, questionnaire))
    return { kind: "DENIED" };
  if (!job) return { kind: "UNAVAILABLE" };
  if (job.error) return { kind: errorForStatus(job.response.status) };
  if (!job.data || !questionnaireJobIsValid(job.data, questionnaire))
    return { kind: "STALE_RESPONSE" };
  const status = job.data.status;
  if (status === "PENDING" || status === "RUNNING" || status === "COMPLETED")
    return fetchNextQuestion(handle, session, questionnaire, configuration);
  return { kind: status };
}

export function questionnaireProjection(result: DemoQuestionnaireBridgeResult) {
  if (result.kind === "QUESTION")
    return {
      status: "QUESTION" as const,
      presentation_token: result.presentationToken,
      left_image_url: `/api/demo/questionnaire/media/${result.presentationToken}/LEFT`,
      right_image_url: `/api/demo/questionnaire/media/${result.presentationToken}/RIGHT`,
    };
  if (result.kind === "COMPLETED") return { status: "COMPLETED" as const };
  if (result.kind === "PENDING") return { status: "PENDING" as const };
  if (
    result.kind === "CANCELLED" ||
    result.kind === "REJECTED" ||
    result.kind === "FAILED"
  )
    return { status: result.kind };
  return { code: result.kind };
}

function currentProfileEntry(
  handle: string,
  expectedSession: BoundSession,
  expectedProfile: BoundProfile,
): boolean {
  const current = currentBoundSession(handle);
  return (
    current !== null &&
    current.session === expectedSession &&
    current.session.profile === expectedProfile
  );
}

function createdProfileIsValid(body: unknown): body is Readonly<{
  job_id: string;
  status: "PENDING";
  capability: "P5_COMPILER";
  job_binding_digest: string;
  target: Readonly<{
    target_type: "DEMO_ACTOR";
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
    value.capability === "P5_COMPILER" &&
    validUpstreamDigest(value.job_binding_digest) &&
    targetValue.target_type === "DEMO_ACTOR" &&
    validUpstreamId(targetValue.target_id) &&
    validUpstreamDigest(targetValue.authority_digest)
  );
}

function profileJobIsValid(body: unknown, profile: BoundProfile): boolean {
  if (!body || typeof body !== "object") return false;
  const value = body as Record<string, unknown>;
  const target = value.target;
  if (!target || typeof target !== "object") return false;
  const targetValue = target as Record<string, unknown>;
  return (
    value.job_id === profile.jobId &&
    (value.status === "PENDING" ||
      value.status === "RUNNING" ||
      value.status === "COMPLETED" ||
      value.status === "REJECTED" ||
      value.status === "FAILED" ||
      value.status === "CANCELLED") &&
    value.capability === "P5_COMPILER" &&
    value.job_binding_digest === profile.jobBindingDigest &&
    targetValue.target_type === "DEMO_ACTOR" &&
    targetValue.target_id === profile.targetActorId &&
    targetValue.authority_digest === profile.targetAuthorityDigest
  );
}

function profileResultIsValid(
  body: unknown,
  session: BoundSession,
  profile: BoundProfile,
): body is Readonly<{
  status: "PROFILE_READY";
  job_id: string;
  session_id: string;
  profile_id: string;
  job_binding_digest: string;
  compilation_digest: string;
}> {
  if (!body || typeof body !== "object") return false;
  const value = body as Record<string, unknown>;
  return (
    value.status === "PROFILE_READY" &&
    value.job_id === profile.jobId &&
    value.session_id === session.sessionId &&
    validUpstreamId(value.profile_id) &&
    value.job_binding_digest === profile.jobBindingDigest &&
    validUpstreamDigest(value.compilation_digest)
  );
}

function profileResult(profile: BoundProfile): DemoProfileBridgeResult {
  if (profile.profileId && profile.compilationDigest)
    return { kind: "PROFILE_READY" };
  if (profile.terminalStatus) return { kind: profile.terminalStatus };
  return { kind: "PENDING" };
}

export async function createBoundDemoProfile(
  handle: string | undefined,
): Promise<DemoProfileBridgeResult> {
  const bound = currentBoundSession(handle);
  if (!bound || !handle) return { kind: "DENIED" };
  const { session, configuration } = bound;
  if (!session.questionnaire?.completed) return { kind: "CONFLICT" };
  if (session.profile?.profileId || session.profile?.terminalStatus)
    return profileResult(session.profile);
  if (session.profile?.createPromise) return session.profile.createPromise;
  if (session.profile?.jobId) return { kind: "PENDING" };

  const profile: BoundProfile = {
    createIdempotencyKey:
      session.profile?.createIdempotencyKey ?? randomBytes(32).toString("hex"),
  };
  const inFlightProfile = {
    ...profile,
    createPromise: null as unknown as Promise<DemoProfileBridgeResult>,
  };
  const inFlightSession: BoundSession = {
    ...session,
    profile: inFlightProfile,
  };
  const promise = (async (): Promise<DemoProfileBridgeResult> => {
    const client = createMirrorApiClient(serverEnv.API_BASE_URL);
    const response = await client
      .POST("/api/v1/demo/profiles/compile", {
        cache: "no-store",
        params: {
          header: { "Idempotency-Key": profile.createIdempotencyKey },
        },
        body: {
          session_id: session.sessionId,
          compiler_version: "demo-profile-compiler-v1",
        },
        headers: { Authorization: `Bearer ${configuration.bearer}` },
      })
      .catch(() => null);
    if (!currentProfileEntry(handle, inFlightSession, inFlightProfile))
      return { kind: "DENIED" };
    if (!response) {
      sessions.set(handle, { ...session, profile });
      return { kind: "UNAVAILABLE" };
    }
    if (response.response.status !== 202 || response.error) {
      sessions.set(handle, { ...session, profile });
      return { kind: errorForStatus(response.response.status) };
    }
    if (!createdProfileIsValid(response.data)) {
      sessions.set(handle, { ...session, profile });
      return { kind: "STALE_RESPONSE" };
    }
    sessions.set(handle, {
      ...session,
      profile: {
        createIdempotencyKey: profile.createIdempotencyKey,
        jobId: response.data.job_id,
        jobBindingDigest: response.data.job_binding_digest,
        targetActorId: response.data.target.target_id,
        targetAuthorityDigest: response.data.target.authority_digest,
      },
    });
    return { kind: "PENDING" };
  })();
  inFlightProfile.createPromise = promise;
  if (sessions.get(handle) !== session) return { kind: "DENIED" };
  sessions.set(handle, inFlightSession);
  return promise;
}

export async function readBoundDemoProfile(
  handle: string | undefined,
): Promise<DemoProfileBridgeResult> {
  const bound = currentBoundSession(handle);
  if (!bound || !handle) return { kind: "DENIED" };
  const { session, configuration } = bound;
  const profile = session.profile;
  if (!profile) return { kind: "NOT_FOUND" };
  if (profile.profileId || profile.terminalStatus)
    return profileResult(profile);
  if (profile.createPromise) return profile.createPromise;
  if (
    !profile.jobId ||
    !profile.jobBindingDigest ||
    !profile.targetActorId ||
    !profile.targetAuthorityDigest
  )
    return { kind: "NOT_FOUND" };
  if (profile.readPromise) return profile.readPromise;

  const inFlightProfile = {
    ...profile,
    readPromise: null as unknown as Promise<DemoProfileBridgeResult>,
  };
  const inFlightSession: BoundSession = {
    ...session,
    profile: inFlightProfile,
  };
  const promise = (async (): Promise<DemoProfileBridgeResult> => {
    const client = createMirrorApiClient(serverEnv.API_BASE_URL);
    const job = await client
      .GET("/api/v1/demo/jobs/{job_id}", {
        cache: "no-store",
        params: { path: { job_id: profile.jobId! } },
        headers: { Authorization: `Bearer ${configuration.bearer}` },
      })
      .catch(() => null);
    if (!currentProfileEntry(handle, inFlightSession, inFlightProfile))
      return { kind: "DENIED" };
    if (!job) {
      sessions.set(handle, { ...session, profile });
      return { kind: "UNAVAILABLE" };
    }
    if (job.error) {
      sessions.set(handle, { ...session, profile });
      return { kind: errorForStatus(job.response.status) };
    }
    if (!job.data || !profileJobIsValid(job.data, profile)) {
      sessions.set(handle, { ...session, profile });
      return { kind: "STALE_RESPONSE" };
    }
    if (job.data.status === "PENDING" || job.data.status === "RUNNING") {
      sessions.set(handle, { ...session, profile });
      return { kind: "PENDING" };
    }
    if (job.data.status !== "COMPLETED") {
      sessions.set(handle, {
        ...session,
        profile: { ...profile, terminalStatus: job.data.status },
      });
      return { kind: job.data.status };
    }

    const result = await client
      .GET("/api/v1/demo/profiles/compilation-jobs/{job_id}/result", {
        cache: "no-store",
        params: { path: { job_id: profile.jobId! } },
        headers: { Authorization: `Bearer ${configuration.bearer}` },
      })
      .catch(() => null);
    if (!currentProfileEntry(handle, inFlightSession, inFlightProfile))
      return { kind: "DENIED" };
    if (!result) {
      sessions.set(handle, { ...session, profile });
      return { kind: "UNAVAILABLE" };
    }
    if (result.error) {
      sessions.set(handle, { ...session, profile });
      return { kind: errorForStatus(result.response.status) };
    }
    if (!result.data || !profileResultIsValid(result.data, session, profile)) {
      sessions.set(handle, { ...session, profile });
      return { kind: "STALE_RESPONSE" };
    }
    sessions.set(handle, {
      ...session,
      profile: {
        ...profile,
        profileId: result.data.profile_id,
        compilationDigest: result.data.compilation_digest,
      },
    });
    return { kind: "PROFILE_READY" };
  })();
  inFlightProfile.readPromise = promise;
  if (sessions.get(handle) !== session) return { kind: "DENIED" };
  sessions.set(handle, inFlightSession);
  return promise;
}

export function profileProjection(result: DemoProfileBridgeResult) {
  if (
    result.kind === "PENDING" ||
    result.kind === "PROFILE_READY" ||
    result.kind === "CANCELLED" ||
    result.kind === "REJECTED" ||
    result.kind === "FAILED"
  )
    return { status: result.kind };
  return { code: result.kind };
}

export async function respondBoundDemoQuestionnaire(
  handle: string | undefined,
  payload: QuestionnaireResponsePayload,
): Promise<DemoQuestionnaireBridgeResult> {
  const bound = currentBoundSession(handle);
  if (!bound || !handle) return { kind: "DENIED" };
  const { session, configuration } = bound;
  const questionnaire = session.questionnaire;
  const question = questionnaire?.question;
  if (!questionnaire || !question || questionnaire.completed)
    return { kind: "CONFLICT" };
  if (question.presentationToken !== payload.presentationToken)
    return { kind: "CONFLICT" };
  const existing = questionnaire.response;
  if (existing) {
    if (JSON.stringify(existing.payload) !== JSON.stringify(payload))
      return { kind: "CONFLICT" };
    if (existing.promise) return existing.promise;
  }
  const response = existing ?? {
    payload,
    idempotencyKey: randomBytes(32).toString("hex"),
  };
  const inFlightQuestionnaire = {
    ...questionnaire,
    response: {
      ...response,
      promise: null as unknown as Promise<DemoQuestionnaireBridgeResult>,
    },
  };
  const inFlightSession: BoundSession = {
    ...session,
    questionnaire: inFlightQuestionnaire,
  };
  const promise = (async (): Promise<DemoQuestionnaireBridgeResult> => {
    const client = createMirrorApiClient(serverEnv.API_BASE_URL);
    const submitted = await client
      .POST("/api/v1/demo/questionnaires/runs/{run_id}/responses", {
        cache: "no-store",
        params: {
          path: { run_id: questionnaire.runId! },
          header: { "Idempotency-Key": response.idempotencyKey },
        },
        body: {
          selected_side: payload.choice,
          expected_step_sequence: question.stepSequence,
          expected_run_version: question.runVersion,
          response_latency_ms: payload.responseLatencyMs,
        },
        headers: { Authorization: `Bearer ${configuration.bearer}` },
      })
      .catch(() => null);
    if (
      !currentQuestionnaireEntry(handle, inFlightSession, inFlightQuestionnaire)
    )
      return { kind: "DENIED" };
    if (!submitted) {
      sessions.set(handle, {
        ...inFlightSession,
        questionnaire: { ...questionnaire, response },
      });
      return { kind: "UNAVAILABLE" };
    }
    if (submitted.response.status !== 201 || submitted.error) {
      sessions.set(handle, {
        ...inFlightSession,
        questionnaire: { ...questionnaire, response },
      });
      return { kind: errorForStatus(submitted.response.status) };
    }
    const body = submitted.data as Record<string, unknown> | undefined;
    if (
      !body ||
      body.run_id !== questionnaire.runId ||
      !validUpstreamId(body.step_id) ||
      body.step_id === question.stepId ||
      body.event_type !== "RESPONDED" ||
      body.step_sequence !== question.stepSequence + 1 ||
      body.run_version !== question.runVersion + 1
    )
      return { kind: "STALE_RESPONSE" };
    const advanced: BoundQuestionnaire = { ...questionnaire, response };
    const advancedSession: BoundSession = {
      ...session,
      questionnaire: advanced,
    };
    if (
      !currentQuestionnaireEntry(handle, inFlightSession, inFlightQuestionnaire)
    )
      return { kind: "DENIED" };
    sessions.set(handle, advancedSession);
    return fetchNextQuestion(handle, advancedSession, advanced, configuration);
  })();
  inFlightQuestionnaire.response.promise = promise;
  if (sessions.get(handle) !== session) return { kind: "DENIED" };
  sessions.set(handle, inFlightSession);
  return promise;
}

export async function fetchBoundQuestionnaireMedia(
  handle: string | undefined,
  presentationToken: string,
  side: "LEFT" | "RIGHT",
): Promise<Response | null> {
  const bound = currentBoundSession(handle);
  const questionnaire = bound?.session.questionnaire;
  if (
    !bound ||
    !handle ||
    !questionnaire?.runId ||
    !questionnaire.question ||
    questionnaire.question.presentationToken !== presentationToken ||
    questionnaire.response
  )
    return null;
  const expectedSession = bound.session;
  const expectedQuestionnaire = questionnaire;
  const response = await fetch(
    new URL(
      `/api/v1/demo/questionnaires/runs/${questionnaire.runId}/presentation-media/${side}`,
      serverEnv.API_BASE_URL,
    ),
    {
      cache: "no-store",
      headers: { Authorization: `Bearer ${bound.configuration.bearer}` },
    },
  ).catch(() => null);
  if (!response || !response.ok) return null;
  if (response.headers.get("content-type")?.toLowerCase() !== "image/jpeg")
    return null;
  const length = response.headers.get("content-length");
  if (!length || !/^\d+$/.test(length) || Number(length) > 10 * 1024 * 1024)
    return null;
  const content = await response.arrayBuffer().catch(() => null);
  if (
    !content ||
    content.byteLength !== Number(length) ||
    !currentQuestionnaireEntry(handle, expectedSession, expectedQuestionnaire)
  )
    return null;
  return new Response(content, {
    status: 200,
    headers: {
      "Content-Type": "image/jpeg",
      "Content-Length": String(content.byteLength),
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
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
