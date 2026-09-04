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
  edit?: BoundEdit;
  selfTransfer?: BoundSelfTransfer;
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

export type DemoRasterEditOperation =
  | "CROP"
  | "ROTATE"
  | "EXPOSURE"
  | "CONTRAST"
  | "SATURATION"
  | "TEMPERATURE";
export type DemoEditRequest = Readonly<{
  operation: DemoRasterEditOperation;
  valuePpm: number;
}>;
type BoundJobAuthority = Readonly<{
  jobId: string;
  jobBindingDigest: string;
  targetId: string;
  targetAuthorityDigest: string;
}>;
type BoundPublishedEdit = Readonly<{
  toolRunId: string;
  toolRunDigest: string;
  verificationResultId: string;
  verifierDigest: string;
  imageVersionId: string;
  imageVersionDigest: string;
  sequence: number;
  parentImageVersionId: string;
  resultAssetId: string;
  resultAssetSha256: string;
}>;
type BoundEditStage =
  | "EDIT_SESSION_CREATE"
  | "EDIT_SESSION_POLL"
  | "PLAN_CREATE"
  | "PLAN_POLL"
  | "EXECUTION_CREATE"
  | "EXECUTION_POLL"
  | "RESULT_READ"
  | "READY";
type BoundEdit = Readonly<{
  request: DemoEditRequest;
  stage: BoundEditStage;
  editSessionIdempotencyKey: string;
  planIdempotencyKey: string;
  executionIdempotencyKey: string;
  editSession?: BoundJobAuthority;
  plan?: BoundJobAuthority;
  execution?: BoundJobAuthority;
  result?: BoundPublishedEdit;
  terminalStatus?: ProfileTerminalStatus;
  progressPromise?: Promise<DemoEditBridgeResult>;
}>;

type SelfTransferStage =
  | "EDIT_SESSION_CREATE"
  | "EDIT_SESSION_POLL"
  | "PLAN_CREATE"
  | "PLAN_POLL"
  | "EXECUTION_CREATE"
  | "EXECUTION_POLL"
  | "RESULT_READ"
  | "PREVIEW_READY"
  | "ACCEPTING"
  | "REFERENCE_PENDING"
  | "REFERENCE_READY";
type BoundSelfTransfer = Readonly<{
  generation: number;
  stage: SelfTransferStage;
  editSessionIdempotencyKey: string;
  planIdempotencyKey: string;
  executionIdempotencyKey: string;
  acceptIdempotencyKey: string;
  editSession?: BoundJobAuthority;
  plan?: BoundJobAuthority;
  execution?: BoundJobAuthority;
  result?: BoundPublishedEdit;
  preview?: Readonly<{
    dimensionKey: "chin_height" | "eye_spacing" | "jaw_width";
    direction: "INCREASE" | "DECREASE";
    stepPpm: 15000 | 30000;
  }>;
  mediaToken?: string;
  mediaExpiresAtMs?: number;
  referenceJobId?: string;
  referenceJobBindingDigest?: string;
  referenceTargetId?: string;
  referenceTargetDigest?: string;
  progressPromise?: Promise<DemoSelfTransferBridgeResult>;
  acceptPromise?: Promise<DemoSelfTransferBridgeResult>;
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

export type DemoEditBridgeResult =
  | Readonly<{ kind: "PENDING" | "IMAGE_VERSION_READY" }>
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

export function validDemoEditRequest(value: unknown): value is DemoEditRequest {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const body = value as Record<string, unknown>;
  if (
    Object.keys(body).length !== 2 ||
    typeof body.operation !== "string" ||
    typeof body.valuePpm !== "number" ||
    !Number.isSafeInteger(body.valuePpm)
  )
    return false;
  if (body.operation === "CROP")
    return body.valuePpm >= 1 && body.valuePpm <= 250_000;
  return (
    ["ROTATE", "EXPOSURE", "CONTRAST", "SATURATION", "TEMPERATURE"].includes(
      body.operation,
    ) &&
    body.valuePpm >= -1_000_000 &&
    body.valuePpm <= 1_000_000
  );
}

function currentEditEntry(
  handle: string,
  expectedSession: BoundSession,
  expectedEdit: BoundEdit,
): boolean {
  const current = currentBoundSession(handle);
  return (
    current !== null &&
    current.session === expectedSession &&
    current.session.edit === expectedEdit
  );
}

function acceptedEditJob(
  body: unknown,
  targetType: "EDITING_SESSION" | "EDIT_PLAN",
  expectedTarget?: Readonly<{ id: string; digest: string }>,
): BoundJobAuthority | null {
  if (!body || typeof body !== "object") return null;
  const value = body as Record<string, unknown>;
  const target = value.target;
  if (!target || typeof target !== "object") return null;
  const targetValue = target as Record<string, unknown>;
  if (
    !validUpstreamId(value.job_id) ||
    value.status !== "PENDING" ||
    value.capability !== "P6_EDITING" ||
    !validUpstreamDigest(value.job_binding_digest) ||
    targetValue.target_type !== targetType ||
    !validUpstreamId(targetValue.target_id) ||
    !validUpstreamDigest(targetValue.authority_digest)
  )
    return null;
  if (
    expectedTarget &&
    (targetValue.target_id !== expectedTarget.id ||
      targetValue.authority_digest !== expectedTarget.digest)
  )
    return null;
  return {
    jobId: value.job_id,
    jobBindingDigest: value.job_binding_digest,
    targetId: targetValue.target_id,
    targetAuthorityDigest: targetValue.authority_digest,
  };
}

type EditJobStatus =
  | "PENDING"
  | "RUNNING"
  | "COMPLETED"
  | "REJECTED"
  | "FAILED"
  | "CANCELLED";

function editJobStatus(
  body: unknown,
  authority: BoundJobAuthority,
  targetType: "EDITING_SESSION" | "EDIT_PLAN",
  completedCode: string,
): EditJobStatus | null {
  if (!body || typeof body !== "object") return null;
  const value = body as Record<string, unknown>;
  const target = value.target;
  if (!target || typeof target !== "object") return null;
  const targetValue = target as Record<string, unknown>;
  const status = value.status;
  if (
    status !== "PENDING" &&
    status !== "RUNNING" &&
    status !== "COMPLETED" &&
    status !== "REJECTED" &&
    status !== "FAILED" &&
    status !== "CANCELLED"
  )
    return null;
  if (
    value.job_id !== authority.jobId ||
    value.capability !== "P6_EDITING" ||
    value.job_binding_digest !== authority.jobBindingDigest ||
    targetValue.target_type !== targetType ||
    targetValue.target_id !== authority.targetId ||
    targetValue.authority_digest !== authority.targetAuthorityDigest ||
    (status === "COMPLETED" && value.result_code !== completedCode)
  )
    return null;
  return status;
}

function publishedEditIsValid(
  body: unknown,
  session: BoundSession,
  edit: BoundEdit,
): body is Readonly<Record<string, unknown>> {
  if (!body || typeof body !== "object") return false;
  const value = body as Record<string, unknown>;
  return (
    value.status === "IMAGE_VERSION_READY" &&
    value.job_id === edit.execution?.jobId &&
    value.session_id === session.sessionId &&
    value.editing_session_id === edit.editSession?.targetId &&
    value.edit_plan_id === edit.plan?.targetId &&
    value.job_binding_digest === edit.execution?.jobBindingDigest &&
    value.plan_digest === edit.plan?.targetAuthorityDigest &&
    value.version_kind === "EDITED" &&
    validUpstreamId(value.tool_run_id) &&
    validUpstreamDigest(value.tool_run_digest) &&
    validUpstreamId(value.verification_result_id) &&
    validUpstreamDigest(value.verifier_digest) &&
    validUpstreamId(value.image_version_id) &&
    validUpstreamDigest(value.image_version_digest) &&
    validPositiveInteger(value.sequence) &&
    validUpstreamId(value.parent_image_version_id) &&
    validUpstreamId(value.result_asset_id) &&
    validUpstreamDigest(value.result_asset_sha256)
  );
}

export function editProjection(result: DemoEditBridgeResult) {
  if (
    result.kind === "PENDING" ||
    result.kind === "IMAGE_VERSION_READY" ||
    result.kind === "REJECTED" ||
    result.kind === "FAILED" ||
    result.kind === "CANCELLED"
  )
    return { status: result.kind };
  return { code: result.kind };
}

function settleEdit(
  handle: string,
  session: BoundSession,
  edit: BoundEdit,
  update: Partial<BoundEdit> = {},
): BoundEdit {
  const next: BoundEdit = { ...edit, ...update, progressPromise: undefined };
  sessions.set(handle, { ...session, edit: next });
  return next;
}

async function advanceBoundEditStage(
  handle: string,
  session: BoundSession,
  edit: BoundEdit,
  configuration: BridgeConfiguration,
): Promise<DemoEditBridgeResult> {
  const client = createMirrorApiClient(serverEnv.API_BASE_URL);
  const headers = { Authorization: `Bearer ${configuration.bearer}` };
  if (edit.stage === "EDIT_SESSION_CREATE") {
    const response = await client
      .POST("/api/v1/demo/editing-sessions", {
        cache: "no-store",
        params: {
          header: { "Idempotency-Key": edit.editSessionIdempotencyKey },
        },
        body: {
          session_id: session.sessionId,
          source_selector: "SESSION_CANONICAL_ASSET",
        },
        headers,
      })
      .catch(() => null);
    if (!currentEditEntry(handle, session, edit)) return { kind: "DENIED" };
    if (!response) {
      settleEdit(handle, session, edit);
      return { kind: "UNAVAILABLE" };
    }
    if (response.response.status !== 202 || response.error) {
      settleEdit(handle, session, edit);
      return { kind: errorForStatus(response.response.status) };
    }
    const authority = acceptedEditJob(response.data, "EDITING_SESSION");
    if (!authority) {
      settleEdit(handle, session, edit);
      return { kind: "STALE_RESPONSE" };
    }
    settleEdit(handle, session, edit, {
      stage: "EDIT_SESSION_POLL",
      editSession: authority,
    });
    return { kind: "PENDING" };
  }

  if (edit.stage === "EDIT_SESSION_POLL") {
    if (!edit.editSession) {
      settleEdit(handle, session, edit);
      return { kind: "STALE_RESPONSE" };
    }
    const response = await client
      .GET("/api/v1/demo/jobs/{job_id}", {
        cache: "no-store",
        params: { path: { job_id: edit.editSession.jobId } },
        headers,
      })
      .catch(() => null);
    if (!currentEditEntry(handle, session, edit)) return { kind: "DENIED" };
    if (!response) {
      settleEdit(handle, session, edit);
      return { kind: "UNAVAILABLE" };
    }
    if (response.error) {
      settleEdit(handle, session, edit);
      return { kind: errorForStatus(response.response.status) };
    }
    const status = editJobStatus(
      response.data,
      edit.editSession,
      "EDITING_SESSION",
      "EDITING_SESSION_INITIALIZED",
    );
    if (!status) {
      settleEdit(handle, session, edit);
      return { kind: "STALE_RESPONSE" };
    }
    if (status === "PENDING" || status === "RUNNING") {
      settleEdit(handle, session, edit);
      return { kind: "PENDING" };
    }
    if (status !== "COMPLETED") {
      settleEdit(handle, session, edit, { terminalStatus: status });
      return { kind: status };
    }
    settleEdit(handle, session, edit, { stage: "PLAN_CREATE" });
    return { kind: "PENDING" };
  }

  if (edit.stage === "PLAN_CREATE") {
    if (!edit.editSession) {
      settleEdit(handle, session, edit);
      return { kind: "STALE_RESPONSE" };
    }
    const response = await client
      .POST("/api/v1/demo/editing-sessions/{editing_session_id}/plans", {
        cache: "no-store",
        params: {
          path: { editing_session_id: edit.editSession.targetId },
          header: { "Idempotency-Key": edit.planIdempotencyKey },
        },
        body: {
          operation: edit.request.operation,
          value_ppm: edit.request.valuePpm,
        },
        headers,
      })
      .catch(() => null);
    if (!currentEditEntry(handle, session, edit)) return { kind: "DENIED" };
    if (!response) {
      settleEdit(handle, session, edit);
      return { kind: "UNAVAILABLE" };
    }
    if (response.response.status !== 202 || response.error) {
      settleEdit(handle, session, edit);
      return { kind: errorForStatus(response.response.status) };
    }
    const authority = acceptedEditJob(response.data, "EDIT_PLAN");
    if (!authority) {
      settleEdit(handle, session, edit);
      return { kind: "STALE_RESPONSE" };
    }
    settleEdit(handle, session, edit, { stage: "PLAN_POLL", plan: authority });
    return { kind: "PENDING" };
  }

  if (edit.stage === "PLAN_POLL") {
    if (!edit.plan) {
      settleEdit(handle, session, edit);
      return { kind: "STALE_RESPONSE" };
    }
    const response = await client
      .GET("/api/v1/demo/jobs/{job_id}", {
        cache: "no-store",
        params: { path: { job_id: edit.plan.jobId } },
        headers,
      })
      .catch(() => null);
    if (!currentEditEntry(handle, session, edit)) return { kind: "DENIED" };
    if (!response) {
      settleEdit(handle, session, edit);
      return { kind: "UNAVAILABLE" };
    }
    if (response.error) {
      settleEdit(handle, session, edit);
      return { kind: errorForStatus(response.response.status) };
    }
    const status = editJobStatus(
      response.data,
      edit.plan,
      "EDIT_PLAN",
      "EDIT_PLAN_READY",
    );
    if (!status) {
      settleEdit(handle, session, edit);
      return { kind: "STALE_RESPONSE" };
    }
    if (status === "PENDING" || status === "RUNNING") {
      settleEdit(handle, session, edit);
      return { kind: "PENDING" };
    }
    if (status !== "COMPLETED") {
      settleEdit(handle, session, edit, { terminalStatus: status });
      return { kind: status };
    }
    settleEdit(handle, session, edit, { stage: "EXECUTION_CREATE" });
    return { kind: "PENDING" };
  }

  if (edit.stage === "EXECUTION_CREATE") {
    if (!edit.plan) {
      settleEdit(handle, session, edit);
      return { kind: "STALE_RESPONSE" };
    }
    const response = await client
      .POST("/api/v1/demo/edit-plans/{edit_plan_id}/executions", {
        cache: "no-store",
        params: {
          path: { edit_plan_id: edit.plan.targetId },
          header: { "Idempotency-Key": edit.executionIdempotencyKey },
        },
        body: {
          execution_mode: "DETERMINISTIC_RASTER",
          expected_plan_digest: edit.plan.targetAuthorityDigest,
        },
        headers,
      })
      .catch(() => null);
    if (!currentEditEntry(handle, session, edit)) return { kind: "DENIED" };
    if (!response) {
      settleEdit(handle, session, edit);
      return { kind: "UNAVAILABLE" };
    }
    if (response.response.status !== 202 || response.error) {
      settleEdit(handle, session, edit);
      return { kind: errorForStatus(response.response.status) };
    }
    const authority = acceptedEditJob(response.data, "EDIT_PLAN", {
      id: edit.plan.targetId,
      digest: edit.plan.targetAuthorityDigest,
    });
    if (!authority) {
      settleEdit(handle, session, edit);
      return { kind: "STALE_RESPONSE" };
    }
    settleEdit(handle, session, edit, {
      stage: "EXECUTION_POLL",
      execution: authority,
    });
    return { kind: "PENDING" };
  }

  if (edit.stage === "EXECUTION_POLL") {
    if (!edit.execution) {
      settleEdit(handle, session, edit);
      return { kind: "STALE_RESPONSE" };
    }
    const response = await client
      .GET("/api/v1/demo/jobs/{job_id}", {
        cache: "no-store",
        params: { path: { job_id: edit.execution.jobId } },
        headers,
      })
      .catch(() => null);
    if (!currentEditEntry(handle, session, edit)) return { kind: "DENIED" };
    if (!response) {
      settleEdit(handle, session, edit);
      return { kind: "UNAVAILABLE" };
    }
    if (response.error) {
      settleEdit(handle, session, edit);
      return { kind: errorForStatus(response.response.status) };
    }
    const status = editJobStatus(
      response.data,
      edit.execution,
      "EDIT_PLAN",
      "EDIT_EXECUTION_COMPLETED",
    );
    if (!status) {
      settleEdit(handle, session, edit);
      return { kind: "STALE_RESPONSE" };
    }
    if (status === "PENDING" || status === "RUNNING") {
      settleEdit(handle, session, edit);
      return { kind: "PENDING" };
    }
    if (status !== "COMPLETED") {
      settleEdit(handle, session, edit, { terminalStatus: status });
      return { kind: status };
    }
    settleEdit(handle, session, edit, { stage: "RESULT_READ" });
    return { kind: "PENDING" };
  }

  if (edit.stage === "RESULT_READ") {
    if (!edit.execution) {
      settleEdit(handle, session, edit);
      return { kind: "STALE_RESPONSE" };
    }
    const response = await client
      .GET("/api/v1/demo/edit-plans/execution-jobs/{job_id}/result", {
        cache: "no-store",
        params: { path: { job_id: edit.execution.jobId } },
        headers,
      })
      .catch(() => null);
    if (!currentEditEntry(handle, session, edit)) return { kind: "DENIED" };
    if (!response) {
      settleEdit(handle, session, edit);
      return { kind: "UNAVAILABLE" };
    }
    if (response.error) {
      settleEdit(handle, session, edit);
      return { kind: errorForStatus(response.response.status) };
    }
    if (!publishedEditIsValid(response.data, session, edit)) {
      settleEdit(handle, session, edit);
      return { kind: "STALE_RESPONSE" };
    }
    const data = response.data as Record<string, unknown>;
    settleEdit(handle, session, edit, {
      stage: "READY",
      result: {
        toolRunId: data.tool_run_id as string,
        toolRunDigest: data.tool_run_digest as string,
        verificationResultId: data.verification_result_id as string,
        verifierDigest: data.verifier_digest as string,
        imageVersionId: data.image_version_id as string,
        imageVersionDigest: data.image_version_digest as string,
        sequence: data.sequence as number,
        parentImageVersionId: data.parent_image_version_id as string,
        resultAssetId: data.result_asset_id as string,
        resultAssetSha256: data.result_asset_sha256 as string,
      },
    });
    return { kind: "IMAGE_VERSION_READY" };
  }

  if (edit.stage === "READY" && edit.result)
    return { kind: "IMAGE_VERSION_READY" };
  settleEdit(handle, session, edit);
  return { kind: "STALE_RESPONSE" };
}

function boundEditResult(edit: BoundEdit): DemoEditBridgeResult {
  if (edit.stage === "READY" && edit.result)
    return { kind: "IMAGE_VERSION_READY" };
  if (edit.terminalStatus) return { kind: edit.terminalStatus };
  return { kind: "PENDING" };
}

async function progressBoundDemoEdit(
  handle: string,
  session: BoundSession,
  edit: BoundEdit,
  configuration: BridgeConfiguration,
): Promise<DemoEditBridgeResult> {
  if (edit.progressPromise) return edit.progressPromise;
  const inFlightEdit = {
    ...edit,
    progressPromise: null as unknown as Promise<DemoEditBridgeResult>,
  };
  const inFlightSession: BoundSession = { ...session, edit: inFlightEdit };
  const promise = advanceBoundEditStage(
    handle,
    inFlightSession,
    inFlightEdit,
    configuration,
  );
  inFlightEdit.progressPromise = promise;
  if (sessions.get(handle) !== session) return { kind: "DENIED" };
  sessions.set(handle, inFlightSession);
  return promise;
}

export async function createBoundDemoEdit(
  handle: string | undefined,
  request: DemoEditRequest,
): Promise<DemoEditBridgeResult> {
  if (!validDemoEditRequest(request)) return { kind: "CONFLICT" };
  const bound = currentBoundSession(handle);
  if (!bound || !handle) return { kind: "DENIED" };
  const { session, configuration } = bound;
  if (!session.profile?.profileId || !session.profile.compilationDigest)
    return { kind: "CONFLICT" };
  const existing = session.edit;
  if (existing) {
    if (
      existing.request.operation !== request.operation ||
      existing.request.valuePpm !== request.valuePpm
    )
      return { kind: "CONFLICT" };
    if (existing.result || existing.terminalStatus)
      return boundEditResult(existing);
    return progressBoundDemoEdit(handle, session, existing, configuration);
  }
  const edit: BoundEdit = {
    request,
    stage: "EDIT_SESSION_CREATE",
    editSessionIdempotencyKey: randomBytes(32).toString("hex"),
    planIdempotencyKey: randomBytes(32).toString("hex"),
    executionIdempotencyKey: randomBytes(32).toString("hex"),
  };
  return progressBoundDemoEdit(handle, session, edit, configuration);
}

export async function readBoundDemoEdit(
  handle: string | undefined,
): Promise<DemoEditBridgeResult> {
  const bound = currentBoundSession(handle);
  if (!bound || !handle) return { kind: "DENIED" };
  const { session, configuration } = bound;
  const edit = session.edit;
  if (!edit) return { kind: "NOT_FOUND" };
  if (edit.result || edit.terminalStatus) return boundEditResult(edit);
  return progressBoundDemoEdit(handle, session, edit, configuration);
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

export type DemoSelfTransferBridgeResult =
  | Readonly<{ kind: "PENDING" }>
  | Readonly<{
      kind: "PREVIEW_READY";
      dimensionKey: "chin_height" | "eye_spacing" | "jaw_width";
      direction: "INCREASE" | "DECREASE";
      stepPpm: 15000 | 30000;
      mediaToken: string;
    }>
  | Readonly<{ kind: "REFERENCE_PROFILE_PENDING" | "REFERENCE_PROFILE_READY" }>
  | Readonly<{
      kind:
        | "NO_COMPATIBLE_CASE"
        | "FAILED"
        | "UNAVAILABLE"
        | "DENIED"
        | "NOT_FOUND"
        | "CONFLICT"
        | "STALE_RESPONSE";
    }>;

function currentSelfTransferEntry(
  handle: string,
  session: BoundSession,
  transfer: BoundSelfTransfer,
) {
  const current = currentBoundSession(handle);
  return (
    current?.session === session && current.session.selfTransfer === transfer
  );
}

function settleSelfTransfer(
  handle: string,
  session: BoundSession,
  transfer: BoundSelfTransfer,
  update: Partial<BoundSelfTransfer> = {},
) {
  const next: BoundSelfTransfer = {
    ...transfer,
    ...update,
    progressPromise: undefined,
    acceptPromise: undefined,
  };
  sessions.set(handle, { ...session, selfTransfer: next });
  return next;
}

function selfTransferState(
  transfer: BoundSelfTransfer,
): DemoSelfTransferBridgeResult {
  if (
    transfer.stage === "PREVIEW_READY" &&
    transfer.preview &&
    transfer.mediaToken
  )
    return {
      kind: "PREVIEW_READY",
      ...transfer.preview,
      mediaToken: transfer.mediaToken,
    };
  if (transfer.stage === "REFERENCE_PENDING")
    return { kind: "REFERENCE_PROFILE_PENDING" };
  if (transfer.stage === "REFERENCE_READY")
    return { kind: "REFERENCE_PROFILE_READY" };
  return { kind: "PENDING" };
}

function profileGeometryPreview(
  value: unknown,
): BoundSelfTransfer["preview"] | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  return (item.dimension_key === "chin_height" ||
    item.dimension_key === "eye_spacing" ||
    item.dimension_key === "jaw_width") &&
    (item.direction === "INCREASE" || item.direction === "DECREASE") &&
    (item.step_ppm === 15000 || item.step_ppm === 30000)
    ? {
        dimensionKey: item.dimension_key,
        direction: item.direction,
        stepPpm: item.step_ppm,
      }
    : null;
}

type JsonUpstreamResponse = Readonly<{
  response: Response;
  data?: unknown;
  error?: unknown;
}>;

function upstreamErrorCode(value: unknown): string | null {
  if (!value || typeof value !== "object") return null;
  const code = (value as Record<string, unknown>).code;
  return typeof code === "string" ? code : null;
}

/** JSON operations must stay on the generated client.  Binary media is the
 * sole deliberately raw server-side fetch below. */
async function selfTransferJson(
  configuration: BridgeConfiguration,
  session: BoundSession,
  transfer: BoundSelfTransfer,
): Promise<JsonUpstreamResponse | null> {
  const client = createMirrorApiClient(serverEnv.API_BASE_URL);
  const headers = { Authorization: `Bearer ${configuration.bearer}` };
  const cast = (value: unknown) => value as JsonUpstreamResponse;
  switch (transfer.stage) {
    case "EDIT_SESSION_CREATE":
      return client
        .POST("/api/v1/demo/editing-sessions", {
          cache: "no-store",
          params: {
            header: { "Idempotency-Key": transfer.editSessionIdempotencyKey },
          },
          body: {
            session_id: session.sessionId,
            source_selector: "SESSION_CANONICAL_ASSET",
          },
          headers,
        })
        .then(cast)
        .catch(() => null);
    case "EDIT_SESSION_POLL":
    case "PLAN_POLL":
    case "EXECUTION_POLL": {
      const authority =
        transfer.stage === "EDIT_SESSION_POLL"
          ? transfer.editSession
          : transfer.stage === "PLAN_POLL"
            ? transfer.plan
            : transfer.execution;
      if (!authority) return null;
      return client
        .GET("/api/v1/demo/jobs/{job_id}", {
          cache: "no-store",
          params: { path: { job_id: authority.jobId } },
          headers,
        })
        .then(cast)
        .catch(() => null);
    }
    case "PLAN_CREATE":
      if (!transfer.editSession) return null;
      return client
        .POST(
          "/api/v1/demo/editing-sessions/{editing_session_id}/profile-geometry-plans",
          {
            cache: "no-store",
            params: {
              path: { editing_session_id: transfer.editSession.targetId },
              header: { "Idempotency-Key": transfer.planIdempotencyKey },
            },
            body: {
              selection_policy_version: "demo-profile-guided-d08-step-v1",
            },
            headers,
          },
        )
        .then(cast)
        .catch(() => null);
    case "EXECUTION_CREATE":
      if (!transfer.plan) return null;
      return client
        .POST("/api/v1/demo/edit-plans/{edit_plan_id}/executions", {
          cache: "no-store",
          params: {
            path: { edit_plan_id: transfer.plan.targetId },
            header: { "Idempotency-Key": transfer.executionIdempotencyKey },
          },
          body: {
            execution_mode: "GEOMETRY",
            expected_plan_digest: transfer.plan.targetAuthorityDigest,
          },
          headers,
        })
        .then(cast)
        .catch(() => null);
    case "RESULT_READ":
      if (!transfer.execution) return null;
      return client
        .GET("/api/v1/demo/edit-plans/execution-jobs/{job_id}/result", {
          cache: "no-store",
          params: { path: { job_id: transfer.execution.jobId } },
          headers,
        })
        .then(cast)
        .catch(() => null);
    case "REFERENCE_PENDING":
      if (!transfer.referenceJobId) return null;
      return client
        .GET("/api/v1/demo/jobs/{job_id}", {
          cache: "no-store",
          params: { path: { job_id: transfer.referenceJobId } },
          headers,
        })
        .then(cast)
        .catch(() => null);
    default:
      return null;
  }
}

async function advanceSelfTransfer(
  handle: string,
  session: BoundSession,
  transfer: BoundSelfTransfer,
  configuration: BridgeConfiguration,
): Promise<DemoSelfTransferBridgeResult> {
  const stage = transfer.stage;
  if (stage === "PREVIEW_READY" || stage === "REFERENCE_READY")
    return selfTransferState(transfer);
  const response = await selfTransferJson(configuration, session, transfer);
  if (!currentSelfTransferEntry(handle, session, transfer))
    return { kind: "DENIED" };
  if (!response) {
    settleSelfTransfer(handle, session, transfer);
    return { kind: "UNAVAILABLE" };
  }
  const body = response.data ?? null;
  if (stage === "REFERENCE_PENDING") {
    const value = body as Record<string, unknown> | null;
    const target = value?.target as Record<string, unknown> | undefined;
    if (
      !value ||
      value.job_id !== transfer.referenceJobId ||
      value.capability !== "P5_REFERENCE_PROFILE" ||
      !validUpstreamDigest(value.job_binding_digest) ||
      (transfer.referenceJobBindingDigest !== undefined &&
        value.job_binding_digest !== transfer.referenceJobBindingDigest) ||
      !target ||
      target.target_type !== "REFERENCE_PROFILE_REQUEST" ||
      !validUpstreamId(target.target_id) ||
      !validUpstreamDigest(target.authority_digest) ||
      (transfer.referenceTargetId !== undefined &&
        target.target_id !== transfer.referenceTargetId) ||
      (transfer.referenceTargetDigest !== undefined &&
        target.authority_digest !== transfer.referenceTargetDigest)
    ) {
      settleSelfTransfer(handle, session, transfer);
      return { kind: "STALE_RESPONSE" };
    }
    if (value.status === "PENDING" || value.status === "RUNNING") {
      settleSelfTransfer(handle, session, transfer, {
        referenceJobBindingDigest: value.job_binding_digest,
        referenceTargetId: target.target_id,
        referenceTargetDigest: target.authority_digest,
      });
      return { kind: "REFERENCE_PROFILE_PENDING" };
    }
    if (value.status === "COMPLETED") {
      const referenceJobId = transfer.referenceJobId;
      if (!referenceJobId) return { kind: "STALE_RESPONSE" };
      const resultResponse = await createMirrorApiClient(serverEnv.API_BASE_URL)
        .GET(
          "/api/v1/demo/reference-profiles/compilation-jobs/{job_id}/result",
          {
            cache: "no-store",
            params: { path: { job_id: referenceJobId } },
            headers: { Authorization: `Bearer ${configuration.bearer}` },
          },
        )
        .then((value) => value as JsonUpstreamResponse)
        .catch(() => null);
      if (
        !currentSelfTransferEntry(handle, session, transfer) ||
        !resultResponse
      )
        return { kind: "DENIED" };
      const result = resultResponse.data as Record<string, unknown> | null;
      if (
        resultResponse.error ||
        !result ||
        result.status !== "REFERENCE_PROFILE_READY" ||
        result.job_id !== transfer.referenceJobId ||
        result.session_id !== session.sessionId ||
        result.job_binding_digest !== value.job_binding_digest ||
        !validUpstreamId(result.reference_profile_id) ||
        !validUpstreamDigest(result.compilation_digest) ||
        !validUpstreamDigest(result.profile_digest)
      ) {
        settleSelfTransfer(handle, session, transfer);
        return { kind: "STALE_RESPONSE" };
      }
      settleSelfTransfer(handle, session, transfer, {
        stage: "REFERENCE_READY",
        referenceJobBindingDigest: value.job_binding_digest,
        referenceTargetId: target.target_id,
        referenceTargetDigest: target.authority_digest,
      });
      return { kind: "REFERENCE_PROFILE_READY" };
    }
    settleSelfTransfer(handle, session, transfer);
    return { kind: "REFERENCE_PROFILE_PENDING" };
  }
  if (
    stage === "PLAN_CREATE" &&
    response.response.status === 409 &&
    upstreamErrorCode(response.error) ===
      "DEMO_PROFILE_GEOMETRY_STEP_UNAVAILABLE"
  ) {
    settleSelfTransfer(handle, session, transfer);
    return { kind: "NO_COMPATIBLE_CASE" };
  }
  if (response.error) {
    settleSelfTransfer(handle, session, transfer);
    return {
      kind: response.response.status === 503 ? "UNAVAILABLE" : "FAILED",
    };
  }
  if (
    stage === "EDIT_SESSION_CREATE" ||
    stage === "PLAN_CREATE" ||
    stage === "EXECUTION_CREATE"
  ) {
    const authority = acceptedEditJob(
      body,
      stage === "EDIT_SESSION_CREATE" ? "EDITING_SESSION" : "EDIT_PLAN",
      stage === "EXECUTION_CREATE" && transfer.plan
        ? {
            id: transfer.plan.targetId,
            digest: transfer.plan.targetAuthorityDigest,
          }
        : undefined,
    );
    if (!authority) {
      settleSelfTransfer(handle, session, transfer);
      return { kind: "STALE_RESPONSE" };
    }
    if (stage === "PLAN_CREATE") {
      const preview = profileGeometryPreview(
        (body as Record<string, unknown>).preview,
      );
      if (!preview) {
        settleSelfTransfer(handle, session, transfer);
        return { kind: "STALE_RESPONSE" };
      }
      settleSelfTransfer(handle, session, transfer, {
        stage: "PLAN_POLL",
        plan: authority,
        preview,
      });
    } else
      settleSelfTransfer(
        handle,
        session,
        transfer,
        stage === "EDIT_SESSION_CREATE"
          ? { stage: "EDIT_SESSION_POLL", editSession: authority }
          : { stage: "EXECUTION_POLL", execution: authority },
      );
    return { kind: "PENDING" };
  }
  if (stage === "RESULT_READ") {
    const resultAuthority: BoundEdit = {
      request: { operation: "CROP", valuePpm: 1 },
      stage: "READY",
      editSessionIdempotencyKey: "",
      planIdempotencyKey: "",
      executionIdempotencyKey: "",
      editSession: transfer.editSession,
      plan: transfer.plan,
      execution: transfer.execution,
    };
    if (!publishedEditIsValid(body, session, resultAuthority)) {
      settleSelfTransfer(handle, session, transfer);
      return { kind: "STALE_RESPONSE" };
    }
    const item = body as Record<string, unknown>;
    const result: BoundPublishedEdit = {
      toolRunId: item.tool_run_id as string,
      toolRunDigest: item.tool_run_digest as string,
      verificationResultId: item.verification_result_id as string,
      verifierDigest: item.verifier_digest as string,
      imageVersionId: item.image_version_id as string,
      imageVersionDigest: item.image_version_digest as string,
      sequence: item.sequence as number,
      parentImageVersionId: item.parent_image_version_id as string,
      resultAssetId: item.result_asset_id as string,
      resultAssetSha256: item.result_asset_sha256 as string,
    };
    const token = randomBytes(32).toString("hex");
    const mediaExpiresAtMs = Math.min(
      Date.now() + 300_000,
      session.expiresAtMs,
    );
    settleSelfTransfer(handle, session, transfer, {
      stage: "PREVIEW_READY",
      result,
      mediaToken: token,
      mediaExpiresAtMs,
    });
    return selfTransferState({
      ...transfer,
      stage: "PREVIEW_READY",
      result,
      mediaToken: token,
      mediaExpiresAtMs,
    });
  }
  const authority =
    stage === "EDIT_SESSION_POLL"
      ? transfer.editSession
      : stage === "PLAN_POLL"
        ? transfer.plan
        : transfer.execution;
  const targetType =
    stage === "EDIT_SESSION_POLL" ? "EDITING_SESSION" : "EDIT_PLAN";
  const completeCode =
    stage === "EDIT_SESSION_POLL"
      ? "EDITING_SESSION_INITIALIZED"
      : stage === "PLAN_POLL"
        ? "EDIT_PLAN_READY"
        : "EDIT_EXECUTION_COMPLETED";
  if (!authority) {
    settleSelfTransfer(handle, session, transfer);
    return { kind: "STALE_RESPONSE" };
  }
  const status = editJobStatus(body, authority, targetType, completeCode);
  if (!status) {
    settleSelfTransfer(handle, session, transfer);
    return { kind: "STALE_RESPONSE" };
  }
  if (status === "PENDING" || status === "RUNNING") {
    settleSelfTransfer(handle, session, transfer);
    return { kind: "PENDING" };
  }
  if (status !== "COMPLETED") {
    settleSelfTransfer(handle, session, transfer);
    return { kind: "FAILED" };
  }
  settleSelfTransfer(handle, session, transfer, {
    stage:
      stage === "EDIT_SESSION_POLL"
        ? "PLAN_CREATE"
        : stage === "PLAN_POLL"
          ? "EXECUTION_CREATE"
          : "RESULT_READ",
  });
  return { kind: "PENDING" };
}

async function progressSelfTransfer(
  handle: string,
  session: BoundSession,
  transfer: BoundSelfTransfer,
  configuration: BridgeConfiguration,
) {
  if (transfer.progressPromise) return transfer.progressPromise;
  const inFlight = {
    ...transfer,
    progressPromise: null as unknown as Promise<DemoSelfTransferBridgeResult>,
  };
  const inFlightSession = { ...session, selfTransfer: inFlight };
  const promise = advanceSelfTransfer(
    handle,
    inFlightSession,
    inFlight,
    configuration,
  );
  inFlight.progressPromise = promise;
  if (sessions.get(handle) !== session)
    return { kind: "DENIED" } as DemoSelfTransferBridgeResult;
  sessions.set(handle, inFlightSession);
  return promise;
}

export async function createBoundDemoSelfTransfer(
  handle: string | undefined,
): Promise<DemoSelfTransferBridgeResult> {
  const bound = currentBoundSession(handle);
  if (!bound || !handle) return { kind: "DENIED" };
  if (
    !bound.session.profile?.profileId ||
    !bound.session.profile.compilationDigest
  )
    return { kind: "CONFLICT" };
  const prior = bound.session.selfTransfer;
  if (prior)
    return progressSelfTransfer(
      handle,
      bound.session,
      prior,
      bound.configuration,
    );
  const transfer: BoundSelfTransfer = {
    generation: 1,
    stage: "EDIT_SESSION_CREATE",
    editSessionIdempotencyKey: randomBytes(32).toString("hex"),
    planIdempotencyKey: randomBytes(32).toString("hex"),
    executionIdempotencyKey: randomBytes(32).toString("hex"),
    acceptIdempotencyKey: randomBytes(32).toString("hex"),
  };
  return progressSelfTransfer(
    handle,
    bound.session,
    transfer,
    bound.configuration,
  );
}

export async function readBoundDemoSelfTransfer(
  handle: string | undefined,
): Promise<DemoSelfTransferBridgeResult> {
  const bound = currentBoundSession(handle);
  if (!bound || !handle) return { kind: "DENIED" };
  const transfer = bound.session.selfTransfer;
  if (!transfer) return { kind: "NOT_FOUND" };
  return progressSelfTransfer(
    handle,
    bound.session,
    transfer,
    bound.configuration,
  );
}

export async function acceptBoundDemoSelfTransfer(
  handle: string | undefined,
): Promise<DemoSelfTransferBridgeResult> {
  const bound = currentBoundSession(handle);
  const transfer = bound?.session.selfTransfer;
  if (!bound || !handle || !transfer) return { kind: "DENIED" };
  if (
    transfer.stage === "REFERENCE_PENDING" ||
    transfer.stage === "REFERENCE_READY"
  )
    return selfTransferState(transfer);
  if (transfer.acceptPromise) return transfer.acceptPromise;
  if (
    transfer.stage !== "PREVIEW_READY" ||
    !transfer.execution ||
    !transfer.result
  )
    return { kind: "CONFLICT" };
  const inFlight = {
    ...transfer,
    stage: "ACCEPTING" as const,
    acceptPromise: null as unknown as Promise<DemoSelfTransferBridgeResult>,
  };
  const inFlightSession = { ...bound.session, selfTransfer: inFlight };
  const promise = (async (): Promise<DemoSelfTransferBridgeResult> => {
    const client = createMirrorApiClient(serverEnv.API_BASE_URL);
    const postAcceptance = () =>
      client.POST(
        "/api/v1/demo/edit-plans/execution-jobs/{job_id}/accept-as-reference",
        {
          cache: "no-store",
          params: {
            path: { job_id: transfer.execution!.jobId },
            header: { "Idempotency-Key": transfer.acceptIdempotencyKey },
          },
          body: { outcome: "FINAL_SAVE_AND_USE_AS_REFERENCE" },
          headers: { Authorization: `Bearer ${bound.configuration.bearer}` },
        },
      );
    let response = await postAcceptance()
      .then((value) => value as JsonUpstreamResponse)
      .catch(() => null);
    if (!currentSelfTransferEntry(handle, inFlightSession, inFlight))
      return { kind: "DENIED" };
    const body = response?.data ?? null;
    if (!response || response.error || !body || typeof body !== "object") {
      settleSelfTransfer(handle, inFlightSession, inFlight, {
        stage: "PREVIEW_READY",
      });
      return {
        kind:
          !response || response.response.status === 503
            ? "UNAVAILABLE"
            : "FAILED",
      };
    }
    const value = body as Record<string, unknown>;
    // A recovery response deliberately has no job. Replaying the exact original
    // idempotency key asks the coordinator to reconcile its already-committed
    // Final Save, never to create a second acceptance.
    if (
      value.status === "REFERENCE_PROFILE_PENDING" &&
      value.queue_state === "RECOVERY_REQUIRED" &&
      value.reference_profile_job_id === null
    ) {
      response = await postAcceptance()
        .then((retry) => retry as JsonUpstreamResponse)
        .catch(() => null);
      const replay = response?.data ?? null;
      if (
        !response ||
        response.error ||
        !replay ||
        typeof replay !== "object"
      ) {
        settleSelfTransfer(handle, inFlightSession, inFlight, {
          stage: "PREVIEW_READY",
        });
        return { kind: "UNAVAILABLE" };
      }
      Object.assign(value, replay as Record<string, unknown>);
    }
    if (
      (value.status !== "REFERENCE_PROFILE_PENDING" &&
        value.status !== "REFERENCE_PROFILE_READY") ||
      !validUpstreamId(value.reference_profile_job_id)
    ) {
      settleSelfTransfer(handle, inFlightSession, inFlight, {
        stage: "PREVIEW_READY",
      });
      return { kind: "STALE_RESPONSE" };
    }
    settleSelfTransfer(handle, inFlightSession, inFlight, {
      // An accept response only establishes the retained job. Even an upstream
      // READY hint must pass the exact job/result authority chain before it can
      // reach the browser projection.
      stage: "REFERENCE_PENDING",
      referenceJobId: value.reference_profile_job_id,
    });
    return { kind: "REFERENCE_PROFILE_PENDING" };
  })();
  inFlight.acceptPromise = promise;
  if (sessions.get(handle) !== bound.session) return { kind: "DENIED" };
  sessions.set(handle, inFlightSession);
  return promise;
}

export async function fetchBoundDemoSelfTransferMedia(
  handle: string | undefined,
  token: string,
  side: "INPUT" | "RESULT",
): Promise<Response | null> {
  const bound = currentBoundSession(handle);
  const transfer = bound?.session.selfTransfer;
  if (
    !bound ||
    !handle ||
    !transfer ||
    transfer.stage !== "PREVIEW_READY" ||
    !transfer.execution ||
    transfer.mediaToken !== token ||
    !transfer.mediaExpiresAtMs ||
    transfer.mediaExpiresAtMs <= Date.now() ||
    !/^[a-f0-9]{64}$/.test(token)
  )
    return null;
  const expectedSession = bound.session;
  const expectedTransfer = transfer;
  const expiresAtMs = transfer.mediaExpiresAtMs;
  const response = await fetch(
    new URL(
      `/api/v1/demo/edit-plans/execution-jobs/${transfer.execution.jobId}/media/${side}`,
      serverEnv.API_BASE_URL,
    ),
    {
      cache: "no-store",
      headers: { Authorization: `Bearer ${bound.configuration.bearer}` },
    },
  ).catch(() => null);
  if (
    !response ||
    !response.ok ||
    response.headers.get("content-type")?.toLowerCase() !== "image/jpeg"
  )
    return null;
  const length = response.headers.get("content-length");
  if (!length || !/^\d+$/.test(length) || Number(length) > 10 * 1024 * 1024)
    return null;
  const content = await response.arrayBuffer().catch(() => null);
  if (
    !content ||
    content.byteLength !== Number(length) ||
    !expiresAtMs ||
    expiresAtMs <= Date.now() ||
    !currentSelfTransferEntry(handle, expectedSession, expectedTransfer)
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

export function selfTransferProjection(result: DemoSelfTransferBridgeResult) {
  if (result.kind === "PREVIEW_READY")
    return {
      status: result.kind,
      dimension_key: result.dimensionKey,
      direction: result.direction,
      step_ppm: result.stepPpm,
      input_image_url: `/api/demo/self-transfer/media/${result.mediaToken}/INPUT`,
      result_image_url: `/api/demo/self-transfer/media/${result.mediaToken}/RESULT`,
    };
  return result.kind === "PENDING" ||
    result.kind === "REFERENCE_PROFILE_PENDING" ||
    result.kind === "REFERENCE_PROFILE_READY" ||
    result.kind === "NO_COMPATIBLE_CASE" ||
    result.kind === "FAILED"
    ? { status: result.kind }
    : { code: result.kind };
}
