import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearDemoSessionRegistryForTest,
  acceptBoundDemoSelfTransfer,
  fetchBoundDemoSelfTransferMedia,
  createBoundDemoAnalysis,
  createBoundDemoEdit,
  createBoundDemoSelfTransfer,
  createBoundDemoProfile,
  createBoundDemoQuestionnaire,
  createBoundDemoSession,
  demoSessionCookieName,
  editProjection,
  profileProjection,
  readBoundDemoAnalysis,
  readBoundDemoEdit,
  readBoundDemoProfile,
  readBoundDemoSelfTransfer,
  readBoundDemoQuestionnaire,
  removeBoundDemoSession,
  selfTransferProjection,
  validDemoEditRequest,
} from "./server";

const bearer = "x".repeat(32);
const identityId = "a".repeat(32);
const sessionId = "1".repeat(32);
const analysisJobId = "2".repeat(32);
const analysisId = "3".repeat(32);
const questionnaireJobId = "4".repeat(32);
const questionnaireRunId = "5".repeat(32);
const profileJobId = "6".repeat(32);
const actorId = "7".repeat(32);
const editingJobId = "8".repeat(32);
const editingSessionId = "9".repeat(32);
const planJobId = "a".repeat(32);
const planId = "b".repeat(32);
const executionJobId = "c".repeat(32);

type EditStatuses = {
  editSession: string;
  plan: string;
  execution: string;
  mismatchedResult?: boolean;
};

function json(body: object, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function pathname(input: string | URL | Request) {
  return new URL(
    typeof input === "string" || input instanceof URL ? input : input.url,
  ).pathname;
}

function upstreamFetch(
  profileStatus: { value: string },
  editStatuses: EditStatuses = {
    editSession: "COMPLETED",
    plan: "COMPLETED",
    execution: "COMPLETED",
  },
  recoverAcceptance = false,
  referenceJobStatus = "PENDING",
  mismatchedReferenceResult = false,
  acceptReady = false,
) {
  let acceptanceAttempts = 0;
  const referenceJobId = "e".repeat(32);
  return vi.fn(async (input: string | URL | Request) => {
    const path = pathname(input);
    const method = input instanceof Request ? input.method : "GET";
    if (path === "/api/v1/demo/identities")
      return json({
        identities: [
          {
            identity_id: identityId,
            canonical_asset_digest: "8".repeat(64),
            admission_status: "ADMITTED",
          },
        ],
      });
    if (path === "/api/v1/demo/sessions" && method === "POST")
      return json(
        {
          session_id: sessionId,
          synthetic_identity_id: identityId,
          status: "ACTIVE",
          expires_at: new Date(Date.now() + 900_000).toISOString(),
        },
        201,
      );
    if (path.endsWith("/analysis") && method === "POST")
      return json(
        {
          job_id: analysisJobId,
          status: "PENDING",
          capability: "P3_FACE_ANALYSIS",
          job_binding_digest: "9".repeat(64),
          target: {
            target_type: "ANALYSIS_RUN",
            target_id: analysisId,
            authority_digest: "a".repeat(64),
          },
        },
        202,
      );
    if (path === `/api/v1/demo/jobs/${analysisJobId}`)
      return json({
        job_id: analysisJobId,
        status: "COMPLETED",
        capability: "P3_FACE_ANALYSIS",
        job_binding_digest: "9".repeat(64),
        target: {
          target_type: "ANALYSIS_RUN",
          target_id: analysisId,
          authority_digest: "a".repeat(64),
        },
      });
    if (path === `/api/v1/demo/analyses/${analysisId}`)
      return json({
        analysis_id: analysisId,
        session_id: sessionId,
        state: "SUPPORTED",
        observation_digest: "b".repeat(64),
        self_state_id: "8".repeat(32),
      });
    if (path.endsWith("/questionnaire") && method === "POST")
      return json(
        {
          job_id: questionnaireJobId,
          status: "PENDING",
          capability: "P4_QUESTIONNAIRE",
          job_binding_digest: "c".repeat(64),
          target: {
            target_type: "QUESTIONNAIRE_RUN",
            target_id: questionnaireRunId,
            authority_digest: "d".repeat(64),
          },
        },
        202,
      );
    if (path === `/api/v1/demo/jobs/${questionnaireJobId}`)
      return json({
        job_id: questionnaireJobId,
        status: "COMPLETED",
        capability: "P4_QUESTIONNAIRE",
        job_binding_digest: "c".repeat(64),
        target: {
          target_type: "QUESTIONNAIRE_RUN",
          target_id: questionnaireRunId,
          authority_digest: "d".repeat(64),
        },
      });
    if (path.endsWith("/next"))
      return json({ kind: "COMPLETED", run_id: questionnaireRunId });
    if (path === "/api/v1/demo/profiles/compile" && method === "POST")
      return json(
        {
          job_id: profileJobId,
          status: "PENDING",
          capability: "P5_COMPILER",
          job_binding_digest: "e".repeat(64),
          target: {
            target_type: "DEMO_ACTOR",
            target_id: actorId,
            authority_digest: "f".repeat(64),
          },
        },
        202,
      );
    if (path === `/api/v1/demo/jobs/${profileJobId}`)
      return json({
        job_id: profileJobId,
        status: profileStatus.value,
        capability: "P5_COMPILER",
        job_binding_digest: "e".repeat(64),
        target: {
          target_type: "DEMO_ACTOR",
          target_id: actorId,
          authority_digest: "f".repeat(64),
        },
      });
    if (path.endsWith(`/profiles/compilation-jobs/${profileJobId}/result`))
      return json({
        status: "PROFILE_READY",
        job_id: profileJobId,
        session_id: sessionId,
        profile_id: "b".repeat(32),
        job_binding_digest: "e".repeat(64),
        compilation_digest: "1".repeat(64),
      });
    if (path === "/api/v1/demo/editing-sessions" && method === "POST")
      return json(
        {
          job_id: editingJobId,
          status: "PENDING",
          capability: "P6_EDITING_SESSION",
          job_binding_digest: "2".repeat(64),
          target: {
            target_type: "EDITING_SESSION",
            target_id: editingSessionId,
            authority_digest: "3".repeat(64),
          },
        },
        202,
      );
    if (path === `/api/v1/demo/jobs/${editingJobId}`)
      return json({
        job_id: editingJobId,
        status: editStatuses.editSession,
        capability: "P6_EDITING_SESSION",
        job_binding_digest: "2".repeat(64),
        target: {
          target_type: "EDITING_SESSION",
          target_id: editingSessionId,
          authority_digest: "3".repeat(64),
        },
        result_code:
          editStatuses.editSession === "COMPLETED"
            ? "EDITING_SESSION_INITIALIZED"
            : null,
      });
    if (
      path === `/api/v1/demo/editing-sessions/${editingSessionId}/plans` &&
      method === "POST"
    )
      return json(
        {
          job_id: planJobId,
          status: "PENDING",
          capability: "P6_EDIT_PLAN",
          job_binding_digest: "4".repeat(64),
          target: {
            target_type: "EDIT_PLAN",
            target_id: planId,
            authority_digest: "5".repeat(64),
          },
        },
        202,
      );
    if (
      path ===
        `/api/v1/demo/editing-sessions/${editingSessionId}/profile-geometry-plans` &&
      method === "POST"
    )
      return json(
        {
          job_id: planJobId,
          status: "PENDING",
          capability: "P6_EDIT_PLAN",
          job_binding_digest: "4".repeat(64),
          target: {
            target_type: "EDIT_PLAN",
            target_id: planId,
            authority_digest: "5".repeat(64),
          },
          preview: {
            dimension_key: "chin_height",
            direction: "INCREASE",
            step_ppm: 15000,
          },
        },
        202,
      );
    if (path === `/api/v1/demo/jobs/${planJobId}`)
      return json({
        job_id: planJobId,
        status: editStatuses.plan,
        capability: "P6_EDIT_PLAN",
        job_binding_digest: "4".repeat(64),
        target: {
          target_type: "EDIT_PLAN",
          target_id: planId,
          authority_digest: "5".repeat(64),
        },
        result_code:
          editStatuses.plan === "COMPLETED" ? "EDIT_PLAN_READY" : null,
      });
    if (
      path === `/api/v1/demo/edit-plans/${planId}/executions` &&
      method === "POST"
    )
      return json(
        {
          job_id: executionJobId,
          status: "PENDING",
          capability: "P6_EDIT_EXECUTION",
          job_binding_digest: "6".repeat(64),
          target: {
            target_type: "EDIT_PLAN",
            target_id: planId,
            authority_digest: "5".repeat(64),
          },
        },
        202,
      );
    if (path === `/api/v1/demo/jobs/${executionJobId}`)
      return json({
        job_id: executionJobId,
        status: editStatuses.execution,
        capability: "P6_EDIT_EXECUTION",
        job_binding_digest: "6".repeat(64),
        target: {
          target_type: "EDIT_PLAN",
          target_id: planId,
          authority_digest: "5".repeat(64),
        },
        result_code:
          editStatuses.execution === "COMPLETED"
            ? "EDIT_EXECUTION_COMPLETED"
            : null,
      });
    if (
      path === `/api/v1/demo/edit-plans/execution-jobs/${executionJobId}/result`
    )
      return json({
        status: "IMAGE_VERSION_READY",
        job_id: executionJobId,
        session_id: sessionId,
        editing_session_id: editingSessionId,
        edit_plan_id: planId,
        job_binding_digest: "6".repeat(64),
        plan_digest: editStatuses.mismatchedResult
          ? "0".repeat(64)
          : "5".repeat(64),
        tool_run_id: "d".repeat(32),
        tool_run_digest: "7".repeat(64),
        verification_result_id: "e".repeat(32),
        verifier_digest: "8".repeat(64),
        image_version_id: "f".repeat(32),
        image_version_digest: "9".repeat(64),
        version_kind: "EDITED",
        sequence: 1,
        parent_image_version_id: "0".repeat(32),
        result_asset_id: "1".repeat(32),
        result_asset_sha256: "a".repeat(64),
      });
    if (
      path ===
        `/api/v1/demo/edit-plans/execution-jobs/${executionJobId}/accept-as-reference` &&
      method === "POST"
    ) {
      const recovery = recoverAcceptance && acceptanceAttempts++ === 0;
      return json(
        recovery
          ? {
              status: "REFERENCE_PROFILE_PENDING",
              reference_profile_job_id: null,
              queue_state: "RECOVERY_REQUIRED",
            }
          : {
              status: acceptReady
                ? "REFERENCE_PROFILE_READY"
                : "REFERENCE_PROFILE_PENDING",
              reference_profile_job_id: referenceJobId,
              queue_state: "PENDING",
            },
        202,
      );
    }
    if (path === `/api/v1/demo/jobs/${referenceJobId}`)
      return json({
        job_id: referenceJobId,
        status: referenceJobStatus,
        capability: "P5_REFERENCE_PROFILE",
        job_binding_digest: "6".repeat(64),
        target: {
          target_type: "REFERENCE_PROFILE_REQUEST",
          target_id: "7".repeat(32),
          authority_digest: "8".repeat(64),
        },
      });
    if (
      path ===
      `/api/v1/demo/reference-profiles/compilation-jobs/${referenceJobId}/result`
    )
      return json({
        status: "REFERENCE_PROFILE_READY",
        job_id: referenceJobId,
        session_id: mismatchedReferenceResult ? "0".repeat(32) : sessionId,
        reference_profile_id: "9".repeat(32),
        job_binding_digest: "6".repeat(64),
        compilation_digest: "a".repeat(64),
        profile_digest: "b".repeat(64),
      });
    if (
      path ===
      `/api/v1/demo/edit-plans/execution-jobs/${executionJobId}/media/INPUT`
    )
      return new Response(new Uint8Array([1, 2, 3]), {
        headers: { "content-type": "image/jpeg", "content-length": "3" },
      });
    if (
      path ===
      `/api/v1/demo/edit-plans/execution-jobs/${executionJobId}/media/RESULT`
    )
      return new Response(new Uint8Array([4, 5, 6]), {
        headers: { "content-type": "image/jpeg", "content-length": "3" },
      });
    return new Response(null, { status: 404 });
  });
}

async function completedQuestionnaire() {
  const created = await createBoundDemoSession(undefined, Date.now());
  expect(created).not.toBeNull();
  expect(await createBoundDemoAnalysis(created?.handle)).toEqual({
    kind: "PENDING",
  });
  expect(await readBoundDemoAnalysis(created?.handle)).toMatchObject({
    kind: "COMPLETED",
  });
  expect(await createBoundDemoQuestionnaire(created?.handle)).toEqual({
    kind: "PENDING",
  });
  expect(await readBoundDemoQuestionnaire(created?.handle)).toEqual({
    kind: "COMPLETED",
  });
  return created!.handle;
}

async function completedProfile(profileStatus: { value: string }) {
  const handle = await completedQuestionnaire();
  expect(await createBoundDemoProfile(handle)).toEqual({ kind: "PENDING" });
  profileStatus.value = "COMPLETED";
  expect(await readBoundDemoProfile(handle)).toEqual({ kind: "PROFILE_READY" });
  return handle;
}

async function previewReady(handle: string) {
  expect(await createBoundDemoSelfTransfer(handle)).toEqual({
    kind: "PENDING",
  });
  for (let index = 0; index < 6; index += 1)
    await readBoundDemoSelfTransfer(handle);
  const preview = await readBoundDemoSelfTransfer(handle);
  expect(preview.kind).toBe("PREVIEW_READY");
  if (preview.kind !== "PREVIEW_READY") throw new Error("expected preview");
  return preview;
}

beforeEach(() => {
  process.env.DEMO_BEARER_TOKEN = bearer;
  process.env.DEMO_BOOTSTRAP_IDENTITY_ID = identityId;
  process.env.DEMO_SESSION_TTL_SECONDS = "60";
  clearDemoSessionRegistryForTest();
});

afterEach(() => {
  clearDemoSessionRegistryForTest();
  delete process.env.DEMO_BEARER_TOKEN;
  delete process.env.DEMO_BOOTSTRAP_IDENTITY_ID;
  delete process.env.DEMO_SESSION_TTL_SECONDS;
  vi.unstubAllGlobals();
});

describe("D11 exact profile bridge", () => {
  it("deduplicates concurrent starts and rejects acceptance before a preview", async () => {
    const profileStatus = { value: "PENDING" };
    const fetchMock = upstreamFetch(profileStatus);
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);
    expect(await acceptBoundDemoSelfTransfer(handle)).toEqual({
      kind: "DENIED",
    });
    expect(
      await Promise.all([
        createBoundDemoSelfTransfer(handle),
        createBoundDemoSelfTransfer(handle),
      ]),
    ).toEqual([{ kind: "PENDING" }, { kind: "PENDING" }]);
    expect(
      fetchMock.mock.calls.filter(
        ([input]) =>
          pathname(input) === "/api/v1/demo/editing-sessions" &&
          input instanceof Request,
      ),
    ).toHaveLength(1);
  });

  it.each(["P6_EDITING", "P6_EDIT_PLAN", "P6_EDIT_EXECUTION"])(
    "rejects the wrong editing-session capability %s",
    async (capability) => {
      const profileStatus = { value: "PENDING" };
      const baseFetch = upstreamFetch(profileStatus);
      vi.stubGlobal(
        "fetch",
        vi.fn(async (input: string | URL | Request) => {
          const result = await baseFetch(input);
          if (pathname(input) !== "/api/v1/demo/editing-sessions")
            return result;
          return json({ ...(await result.json()), capability }, result.status);
        }),
      );
      const handle = await completedProfile(profileStatus);
      expect(await createBoundDemoSelfTransfer(handle)).toEqual({
        kind: "STALE_RESPONSE",
      });
    },
  );

  it("keeps profile-guided JSON calls on the generated client and publishes only a safe preview", async () => {
    const profileStatus = { value: "PENDING" };
    const fetchMock = upstreamFetch(profileStatus);
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);

    expect(await createBoundDemoSelfTransfer(handle)).toEqual({
      kind: "PENDING",
    });
    expect(await readBoundDemoSelfTransfer(handle)).toEqual({
      kind: "PENDING",
    });
    expect(await readBoundDemoSelfTransfer(handle)).toEqual({
      kind: "PENDING",
    });
    expect(await readBoundDemoSelfTransfer(handle)).toEqual({
      kind: "PENDING",
    });
    expect(await readBoundDemoSelfTransfer(handle)).toEqual({
      kind: "PENDING",
    });
    expect(await readBoundDemoSelfTransfer(handle)).toEqual({
      kind: "PENDING",
    });
    const preview = await readBoundDemoSelfTransfer(handle);
    expect(preview).toMatchObject({
      kind: "PREVIEW_READY",
      dimensionKey: "chin_height",
      direction: "INCREASE",
      stepPpm: 15000,
    });
    if (preview.kind !== "PREVIEW_READY") throw new Error("expected preview");
    expect(preview).not.toHaveProperty("jobId");
    expect(preview).not.toHaveProperty("digest");

    const geometryRequest = fetchMock.mock.calls
      .map(([input]) => input)
      .find(
        (input) =>
          pathname(input).endsWith("/profile-geometry-plans") &&
          input instanceof Request,
      ) as Request | undefined;
    expect(geometryRequest).toBeInstanceOf(Request);
    expect(geometryRequest?.headers.get("Idempotency-Key")).toMatch(
      /^[a-f0-9]{64}$/,
    );
    expect(await geometryRequest?.clone().json()).toEqual({
      selection_policy_version: "demo-profile-guided-d08-step-v1",
    });
  });

  it("fails closed on mismatched execution authority without projecting upstream details", async () => {
    const profileStatus = { value: "PENDING" };
    const fetchMock = upstreamFetch(profileStatus);
    const original = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      if (pathname(input).endsWith("/executions"))
        return new Response(
          JSON.stringify({
            job_id: planJobId,
            status: "PENDING",
            capability: "P6_EDIT_EXECUTION",
            job_binding_digest: "4".repeat(64),
            target: {
              target_type: "EDIT_PLAN",
              target_id: planId,
              authority_digest: "0".repeat(64),
            },
            preview: {
              dimension_key: "chin_height",
              direction: "INCREASE",
              step_ppm: 15000,
            },
          }),
          { status: 202 },
        );
      return original!(input);
    });
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);
    await createBoundDemoSelfTransfer(handle);
    for (let index = 0; index < 3; index += 1)
      await readBoundDemoSelfTransfer(handle);
    const outcome = await readBoundDemoSelfTransfer(handle);
    expect(outcome).toEqual({ kind: "STALE_RESPONSE" });
    expect(selfTransferProjection(outcome)).toEqual({ code: "STALE_RESPONSE" });
  });

  it("maps only the generated-client 409 step-unavailable envelope to no-compatible", async () => {
    const profileStatus = { value: "PENDING" };
    const fetchMock = upstreamFetch(profileStatus);
    const original = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (input: string | URL | Request) => {
      if (pathname(input).endsWith("/profile-geometry-plans"))
        return new Response(
          JSON.stringify({
            code: "DEMO_PROFILE_GEOMETRY_STEP_UNAVAILABLE",
            message: "redacted",
            request_id: "0".repeat(32),
            details: {},
          }),
          { status: 409, headers: { "content-type": "application/json" } },
        );
      return original!(input);
    });
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);
    await createBoundDemoSelfTransfer(handle);
    await readBoundDemoSelfTransfer(handle);
    const outcome = await readBoundDemoSelfTransfer(handle);
    expect(outcome).toEqual({ kind: "NO_COMPATIBLE_CASE" });
    expect(selfTransferProjection(outcome)).toEqual({
      status: "NO_COMPATIBLE_CASE",
    });
  });

  it("replays RECOVERY_REQUIRED with the original acceptance key and retains one reference job", async () => {
    const profileStatus = { value: "PENDING" };
    const fetchMock = upstreamFetch(profileStatus, undefined, true);
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);
    await createBoundDemoSelfTransfer(handle);
    for (let index = 0; index < 6; index += 1)
      await readBoundDemoSelfTransfer(handle);

    expect(await acceptBoundDemoSelfTransfer(handle)).toEqual({
      kind: "REFERENCE_PROFILE_PENDING",
    });
    expect(await readBoundDemoSelfTransfer(handle)).toEqual({
      kind: "REFERENCE_PROFILE_PENDING",
    });
    const acceptanceRequests = fetchMock.mock.calls
      .map(([input]) => input)
      .filter(
        (input) =>
          pathname(input).endsWith("/accept-as-reference") &&
          input instanceof Request,
      ) as Request[];
    expect(acceptanceRequests).toHaveLength(2);
    expect(acceptanceRequests[0]?.headers.get("Idempotency-Key")).toBe(
      acceptanceRequests[1]?.headers.get("Idempotency-Key"),
    );
  });

  it("deduplicates concurrent Final Save requests with one retained acceptance key", async () => {
    const profileStatus = { value: "PENDING" };
    const fetchMock = upstreamFetch(profileStatus);
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);
    await previewReady(handle);
    expect(
      await Promise.all([
        acceptBoundDemoSelfTransfer(handle),
        acceptBoundDemoSelfTransfer(handle),
      ]),
    ).toEqual([
      { kind: "REFERENCE_PROFILE_PENDING" },
      { kind: "REFERENCE_PROFILE_PENDING" },
    ]);
    const requests = fetchMock.mock.calls
      .map(([input]) => input)
      .filter(
        (input) =>
          pathname(input).endsWith("/accept-as-reference") &&
          input instanceof Request,
      ) as Request[];
    expect(requests).toHaveLength(1);
    expect(requests[0]?.headers.get("Idempotency-Key")).toMatch(
      /^[a-f0-9]{64}$/,
    );
  });

  it("does not trust an accept READY hint before the exact retained Reference result", async () => {
    const profileStatus = { value: "PENDING" };
    const mismatchFetch = upstreamFetch(
      profileStatus,
      undefined,
      false,
      "COMPLETED",
      true,
      true,
    );
    vi.stubGlobal("fetch", mismatchFetch);
    const mismatchHandle = await completedProfile(profileStatus);
    await previewReady(mismatchHandle);
    expect(await acceptBoundDemoSelfTransfer(mismatchHandle)).toEqual({
      kind: "REFERENCE_PROFILE_PENDING",
    });
    expect(await readBoundDemoSelfTransfer(mismatchHandle)).toEqual({
      kind: "STALE_RESPONSE",
    });

    clearDemoSessionRegistryForTest();
    const readyFetch = upstreamFetch(
      profileStatus,
      undefined,
      false,
      "COMPLETED",
      false,
      true,
    );
    vi.stubGlobal("fetch", readyFetch);
    const readyHandle = await completedProfile(profileStatus);
    await previewReady(readyHandle);
    expect(await acceptBoundDemoSelfTransfer(readyHandle)).toEqual({
      kind: "REFERENCE_PROFILE_PENDING",
    });
    expect(await readBoundDemoSelfTransfer(readyHandle)).toEqual({
      kind: "REFERENCE_PROFILE_READY",
    });
  });

  it("serves exact media bytes only while its bound session and configuration remain current", async () => {
    const profileStatus = { value: "PENDING" };
    const fetchMock = upstreamFetch(profileStatus);
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);
    const preview = await previewReady(handle);

    const input = await fetchBoundDemoSelfTransferMedia(
      handle,
      preview.mediaToken,
      "INPUT",
    );
    const result = await fetchBoundDemoSelfTransferMedia(
      handle,
      preview.mediaToken,
      "RESULT",
    );
    expect(new Uint8Array(await input!.arrayBuffer())).toEqual(
      new Uint8Array([1, 2, 3]),
    );
    expect(new Uint8Array(await result!.arrayBuffer())).toEqual(
      new Uint8Array([4, 5, 6]),
    );
    expect(input?.headers.get("cache-control")).toBe("private, no-store");
    expect(input?.headers.get("x-content-type-options")).toBe("nosniff");
    expect(
      await fetchBoundDemoSelfTransferMedia(handle, "0".repeat(64), "INPUT"),
    ).toBeNull();
    removeBoundDemoSession(handle);
    expect(
      await fetchBoundDemoSelfTransferMedia(
        handle,
        preview.mediaToken,
        "INPUT",
      ),
    ).toBeNull();
  });

  it("fails media closed for upstream type, length, and configuration rotation", async () => {
    const profileStatus = { value: "PENDING" };
    const fetchMock = upstreamFetch(profileStatus);
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);
    const preview = await previewReady(handle);
    fetchMock.mockResolvedValueOnce(
      new Response(new Uint8Array([1]), {
        headers: { "content-type": "image/png", "content-length": "1" },
      }),
    );
    expect(
      await fetchBoundDemoSelfTransferMedia(
        handle,
        preview.mediaToken,
        "INPUT",
      ),
    ).toBeNull();
    fetchMock.mockResolvedValueOnce(
      new Response(new Uint8Array([1]), {
        headers: { "content-type": "image/jpeg", "content-length": "10485761" },
      }),
    );
    expect(
      await fetchBoundDemoSelfTransferMedia(
        handle,
        preview.mediaToken,
        "INPUT",
      ),
    ).toBeNull();
    process.env.DEMO_BEARER_TOKEN = "y".repeat(32);
    expect(
      await fetchBoundDemoSelfTransferMedia(
        handle,
        preview.mediaToken,
        "INPUT",
      ),
    ).toBeNull();
  });

  it("drops a media response that completes after logout or session expiry", async () => {
    const profileStatus = { value: "PENDING" };
    const fetchMock = upstreamFetch(profileStatus);
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);
    const preview = await previewReady(handle);
    const delayed = deferred<Response>();
    fetchMock.mockImplementationOnce(() => delayed.promise);
    const pending = fetchBoundDemoSelfTransferMedia(
      handle,
      preview.mediaToken,
      "INPUT",
    );
    removeBoundDemoSession(handle);
    delayed.resolve(
      new Response(new Uint8Array([1, 2, 3]), {
        headers: { "content-type": "image/jpeg", "content-length": "3" },
      }),
    );
    expect(await pending).toBeNull();
  });

  it("expires a media token with its Demo session, even before the five minute token ceiling", async () => {
    const profileStatus = { value: "PENDING" };
    const fetchMock = upstreamFetch(profileStatus);
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);
    const preview = await previewReady(handle);
    vi.useFakeTimers();
    vi.setSystemTime(Date.now() + 61_000);
    expect(
      await fetchBoundDemoSelfTransferMedia(
        handle,
        preview.mediaToken,
        "INPUT",
      ),
    ).toBeNull();
  });

  it("rejects browser authority, operation, and media-side overrides at the BFF route", async () => {
    const { POST, GET } = await import(
      "../../app/api/demo/self-transfer/route"
    );
    const { POST: accept } = await import(
      "../../app/api/demo/self-transfer/accept/route"
    );
    const { GET: media } = await import(
      "../../app/api/demo/self-transfer/media/[media_token]/[side]/route"
    );
    const headers = { Origin: "https://demo.example" };
    const invalidStart = await POST(
      new Request("https://demo.example/api/demo/self-transfer", {
        method: "POST",
        headers: { ...headers, "content-type": "application/json" },
        body: JSON.stringify({
          action: "PROFILE_GUIDED_GEOMETRY_PREVIEW",
          ppm: 1,
        }),
      }),
    );
    expect(invalidStart.status).toBe(403);
    expect(
      (
        await GET(
          new Request("https://demo.example/api/demo/self-transfer?job_id=x", {
            headers,
          }),
        )
      ).status,
    ).toBe(403);
    expect(
      (
        await accept(
          new Request("https://demo.example/api/demo/self-transfer/accept", {
            method: "POST",
            headers: { ...headers, "content-type": "application/json" },
            body: JSON.stringify({
              outcome: "FINAL_SAVE_AND_USE_AS_REFERENCE",
              id: "x",
            }),
          }),
        )
      ).status,
    ).toBe(403);
    expect(
      (
        await media(
          new Request(
            "https://demo.example/api/demo/self-transfer/media/x/OTHER",
            {
              headers,
            },
          ),
          { params: Promise.resolve({ media_token: "x", side: "OTHER" }) },
        )
      ).status,
    ).toBe(403);
  });

  it("allows same-origin image requests without Origin and keeps Reference pending GET successful", async () => {
    const profileStatus = { value: "PENDING" };
    const fetchMock = upstreamFetch(profileStatus);
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);
    const preview = await previewReady(handle);
    const { GET: transferGet } = await import(
      "../../app/api/demo/self-transfer/route"
    );
    const { GET: media } = await import(
      "../../app/api/demo/self-transfer/media/[media_token]/[side]/route"
    );
    const cookie = `${demoSessionCookieName}=${handle}`;
    const image = await media(
      new Request(
        `https://demo.example/api/demo/self-transfer/media/${preview.mediaToken}/INPUT`,
        { headers: { Cookie: cookie, "Sec-Fetch-Site": "same-origin" } },
      ),
      {
        params: Promise.resolve({
          media_token: preview.mediaToken,
          side: "INPUT",
        }),
      },
    );
    expect(image.status).toBe(200);
    expect(image.headers.get("vary")).toBe("Cookie");
    expect(image.headers.get("cache-control")).toBe("private, no-store");
    expect(image.headers.get("x-content-type-options")).toBe("nosniff");
    expect(
      (
        await media(
          new Request(
            "https://demo.example/api/demo/self-transfer/media/x/INPUT",
            {
              headers: { Cookie: cookie, "Sec-Fetch-Site": "cross-site" },
            },
          ),
          { params: Promise.resolve({ media_token: "x", side: "INPUT" }) },
        )
      ).status,
    ).toBe(403);
    expect(
      (
        await media(
          new Request(
            "https://demo.example/api/demo/self-transfer/media/x/INPUT",
            {
              headers: {
                Cookie: cookie,
                "Sec-Fetch-Site": "same-origin",
                Authorization: "Bearer forbidden",
              },
            },
          ),
          { params: Promise.resolve({ media_token: "x", side: "INPUT" }) },
        )
      ).status,
    ).toBe(403);
    expect(await acceptBoundDemoSelfTransfer(handle)).toEqual({
      kind: "REFERENCE_PROFILE_PENDING",
    });
    expect(
      (
        await transferGet(
          new Request("https://demo.example/api/demo/self-transfer", {
            headers: { Cookie: cookie, Origin: "https://demo.example" },
          }),
        )
      ).status,
    ).toBe(200);
  });

  it("binds the completed questionnaire to one exact profile result", async () => {
    const profileStatus = { value: "PENDING" };
    const fetchMock = upstreamFetch(profileStatus);
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedQuestionnaire();

    expect(
      await Promise.all([
        createBoundDemoProfile(handle),
        createBoundDemoProfile(handle),
      ]),
    ).toEqual([{ kind: "PENDING" }, { kind: "PENDING" }]);
    expect(await readBoundDemoProfile(handle)).toEqual({ kind: "PENDING" });
    profileStatus.value = "COMPLETED";
    expect(await readBoundDemoProfile(handle)).toEqual({
      kind: "PROFILE_READY",
    });
    expect(await readBoundDemoProfile(handle)).toEqual({
      kind: "PROFILE_READY",
    });
    expect(profileProjection({ kind: "PROFILE_READY" })).toEqual({
      status: "PROFILE_READY",
    });

    const profileCalls = fetchMock.mock.calls.filter(([input]) =>
      pathname(input).includes("/profiles/"),
    );
    expect(profileCalls).toHaveLength(2);
    const createRequest = profileCalls[0]?.[0];
    expect(createRequest).toBeInstanceOf(Request);
    expect((createRequest as Request).headers.get("Authorization")).toBe(
      `Bearer ${bearer}`,
    );
    expect((createRequest as Request).headers.get("Idempotency-Key")).toMatch(
      /^[a-f0-9]{64}$/,
    );
    expect(await (createRequest as Request).clone().json()).toEqual({
      session_id: sessionId,
      compiler_version: "demo-profile-compiler-v1",
    });
  });

  it("retains one server-side idempotency key after an uncertain create", async () => {
    const profileStatus = { value: "PENDING" };
    const baseFetch = upstreamFetch(profileStatus);
    const createKeys: string[] = [];
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      if (
        pathname(input) === "/api/v1/demo/profiles/compile" &&
        input instanceof Request
      ) {
        createKeys.push(input.headers.get("Idempotency-Key") ?? "");
        if (createKeys.length === 1) return new Response(null, { status: 503 });
      }
      return baseFetch(input);
    });
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedQuestionnaire();

    expect(await createBoundDemoProfile(handle)).toEqual({
      kind: "UNAVAILABLE",
    });
    expect(await createBoundDemoProfile(handle)).toEqual({ kind: "PENDING" });
    expect(createKeys).toHaveLength(2);
    expect(createKeys[0]).toMatch(/^[a-f0-9]{64}$/);
    expect(createKeys[1]).toBe(createKeys[0]);
  });

  it("drops an in-flight result after logout", async () => {
    const profileStatus = { value: "PENDING" };
    const fetchMock = upstreamFetch(profileStatus);
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedQuestionnaire();
    await createBoundDemoProfile(handle);
    profileStatus.value = "COMPLETED";

    const pending = readBoundDemoProfile(handle);
    removeBoundDemoSession(handle);
    expect(await pending).toEqual({ kind: "DENIED" });
    expect(await readBoundDemoProfile(handle)).toEqual({ kind: "DENIED" });
  });

  it("projects only profile state and rejects browser overrides", async () => {
    const profileStatus = { value: "PENDING" };
    vi.stubGlobal("fetch", upstreamFetch(profileStatus));
    const handle = await completedQuestionnaire();
    const { GET, POST } = await import("../../app/api/demo/profile/route");
    const headers = {
      Origin: "https://demo.test",
      Cookie: `mirror_demo_session=${handle}`,
    };

    const started = await POST(
      new Request("https://demo.test/api/demo/profile", {
        method: "POST",
        headers,
      }),
    );
    expect(started.status).toBe(202);
    expect(await started.json()).toEqual({ status: "PENDING" });
    profileStatus.value = "COMPLETED";
    const ready = await GET(
      new Request("https://demo.test/api/demo/profile", { headers }),
    );
    expect(ready.status).toBe(200);
    expect(await ready.json()).toEqual({ status: "PROFILE_READY" });

    const query = await GET(
      new Request("https://demo.test/api/demo/profile?job_id=override", {
        headers,
      }),
    );
    const body = await POST(
      new Request("https://demo.test/api/demo/profile", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: "{}",
      }),
    );
    const authorization = await GET(
      new Request("https://demo.test/api/demo/profile", {
        headers: { ...headers, Authorization: "Bearer forbidden" },
      }),
    );
    expect([query.status, body.status, authorization.status]).toEqual([
      403, 403, 403,
    ]);
  });
});

describe("D11 exact edit bridge", () => {
  it("accepts only frozen deterministic raster request ranges", () => {
    expect(validDemoEditRequest({ operation: "CROP", valuePpm: 1 })).toBe(true);
    expect(validDemoEditRequest({ operation: "CROP", valuePpm: 250_000 })).toBe(
      true,
    );
    expect(validDemoEditRequest({ operation: "CROP", valuePpm: 0 })).toBe(
      false,
    );
    expect(validDemoEditRequest({ operation: "CROP", valuePpm: 250_001 })).toBe(
      false,
    );
    expect(
      validDemoEditRequest({ operation: "ROTATE", valuePpm: -1_000_000 }),
    ).toBe(true);
    expect(
      validDemoEditRequest({ operation: "TEMPERATURE", valuePpm: 1_000_000 }),
    ).toBe(true);
    expect(validDemoEditRequest({ operation: "GEOMETRY", valuePpm: 1 })).toBe(
      false,
    );
    expect(validDemoEditRequest({ operation: "EXPOSURE", valuePpm: 1.5 })).toBe(
      false,
    );
  });

  it("advances one immutable request through exact D08 jobs and publication", async () => {
    const profileStatus = { value: "PENDING" };
    const fetchMock = upstreamFetch(profileStatus);
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);
    const request = { operation: "EXPOSURE" as const, valuePpm: 250_000 };

    expect(
      await Promise.all([
        createBoundDemoEdit(handle, request),
        createBoundDemoEdit(handle, request),
      ]),
    ).toEqual([{ kind: "PENDING" }, { kind: "PENDING" }]);
    for (let index = 0; index < 5; index += 1)
      expect(await readBoundDemoEdit(handle)).toEqual({ kind: "PENDING" });
    expect(await readBoundDemoEdit(handle)).toEqual({
      kind: "IMAGE_VERSION_READY",
    });
    expect(await readBoundDemoEdit(handle)).toEqual({
      kind: "IMAGE_VERSION_READY",
    });
    expect(editProjection({ kind: "IMAGE_VERSION_READY" })).toEqual({
      status: "IMAGE_VERSION_READY",
    });

    const editPosts = fetchMock.mock.calls
      .map(([input]) => input)
      .filter(
        (input) =>
          input instanceof Request &&
          input.method === "POST" &&
          (pathname(input).includes("editing-sessions") ||
            pathname(input).includes("edit-plans")),
      ) as Request[];
    expect(editPosts).toHaveLength(3);
    expect(await editPosts[0]!.clone().json()).toEqual({
      session_id: sessionId,
      source_selector: "SESSION_CANONICAL_ASSET",
    });
    expect(await editPosts[1]!.clone().json()).toEqual({
      operation: "EXPOSURE",
      value_ppm: 250_000,
    });
    expect(await editPosts[2]!.clone().json()).toEqual({
      execution_mode: "DETERMINISTIC_RASTER",
      expected_plan_digest: "5".repeat(64),
    });
    const keys = editPosts.map((item) => item.headers.get("Idempotency-Key"));
    expect(keys).toHaveLength(3);
    expect(new Set(keys).size).toBe(3);
    expect(keys.every((item) => /^[a-f0-9]{64}$/.test(item ?? ""))).toBe(true);
    expect(
      editPosts.every(
        (item) => item.headers.get("Authorization") === `Bearer ${bearer}`,
      ),
    ).toBe(true);
  });

  it("keeps terminal and mismatched result states fail closed", async () => {
    const profileStatus = { value: "PENDING" };
    const terminalStatuses: EditStatuses = {
      editSession: "COMPLETED",
      plan: "FAILED",
      execution: "COMPLETED",
    };
    vi.stubGlobal("fetch", upstreamFetch(profileStatus, terminalStatuses));
    const handle = await completedProfile(profileStatus);
    const request = { operation: "CONTRAST" as const, valuePpm: 100_000 };
    await createBoundDemoEdit(handle, request);
    expect(
      await createBoundDemoEdit(handle, { ...request, valuePpm: 200_000 }),
    ).toEqual({
      kind: "CONFLICT",
    });
    expect(await readBoundDemoEdit(handle)).toEqual({ kind: "PENDING" });
    expect(await readBoundDemoEdit(handle)).toEqual({ kind: "PENDING" });
    expect(await readBoundDemoEdit(handle)).toEqual({ kind: "FAILED" });
    expect(await readBoundDemoEdit(handle)).toEqual({ kind: "FAILED" });

    clearDemoSessionRegistryForTest();
    const mismatchProfile = { value: "PENDING" };
    vi.stubGlobal(
      "fetch",
      upstreamFetch(mismatchProfile, {
        editSession: "COMPLETED",
        plan: "COMPLETED",
        execution: "COMPLETED",
        mismatchedResult: true,
      }),
    );
    const mismatchHandle = await completedProfile(mismatchProfile);
    await createBoundDemoEdit(mismatchHandle, request);
    for (let index = 0; index < 5; index += 1)
      await readBoundDemoEdit(mismatchHandle);
    expect(await readBoundDemoEdit(mismatchHandle)).toEqual({
      kind: "STALE_RESPONSE",
    });
  });

  it("retains the editing admission key after an uncertain response", async () => {
    const profileStatus = { value: "PENDING" };
    const baseFetch = upstreamFetch(profileStatus);
    const keys: string[] = [];
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      if (
        pathname(input) === "/api/v1/demo/editing-sessions" &&
        input instanceof Request
      ) {
        keys.push(input.headers.get("Idempotency-Key") ?? "");
        if (keys.length === 1) return new Response(null, { status: 503 });
      }
      return baseFetch(input);
    });
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);
    const request = { operation: "SATURATION" as const, valuePpm: 300_000 };

    expect(await createBoundDemoEdit(handle, request)).toEqual({
      kind: "UNAVAILABLE",
    });
    expect(await createBoundDemoEdit(handle, request)).toEqual({
      kind: "PENDING",
    });
    expect(keys).toHaveLength(2);
    expect(keys[0]).toMatch(/^[a-f0-9]{64}$/);
    expect(keys[1]).toBe(keys[0]);
  });

  it.each([
    ["plan", "/api/v1/demo/editing-sessions/", 2],
    ["execution", `/api/v1/demo/edit-plans/${planId}/executions`, 4],
  ] as const)(
    "retains the %s admission key after an uncertain response",
    async (_stage, expectedPath, readsBeforeAdmission) => {
      const profileStatus = { value: "PENDING" };
      const baseFetch = upstreamFetch(profileStatus);
      const keys: string[] = [];
      const fetchMock = vi.fn(async (input: string | URL | Request) => {
        if (
          pathname(input).includes(expectedPath) &&
          input instanceof Request &&
          input.method === "POST"
        ) {
          keys.push(input.headers.get("Idempotency-Key") ?? "");
          if (keys.length === 1) return new Response(null, { status: 503 });
        }
        return baseFetch(input);
      });
      vi.stubGlobal("fetch", fetchMock);
      const handle = await completedProfile(profileStatus);
      const request = { operation: "SATURATION" as const, valuePpm: 300_000 };

      expect(await createBoundDemoEdit(handle, request)).toEqual({
        kind: "PENDING",
      });
      for (let index = 0; index < readsBeforeAdmission - 1; index += 1)
        expect(await readBoundDemoEdit(handle)).toEqual({ kind: "PENDING" });
      expect(await readBoundDemoEdit(handle)).toEqual({ kind: "UNAVAILABLE" });
      expect(await readBoundDemoEdit(handle)).toEqual({ kind: "PENDING" });
      expect(keys).toHaveLength(2);
      expect(keys[0]).toMatch(/^[a-f0-9]{64}$/);
      expect(keys[1]).toBe(keys[0]);
    },
  );

  it("fails closed when the execution job no longer names its retained plan", async () => {
    const profileStatus = { value: "PENDING" };
    const baseFetch = upstreamFetch(profileStatus);
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      if (pathname(input) === `/api/v1/demo/jobs/${executionJobId}`)
        return json({
          job_id: executionJobId,
          status: "COMPLETED",
          capability: "P6_EDIT_EXECUTION",
          job_binding_digest: "6".repeat(64),
          target: {
            target_type: "EDIT_PLAN",
            target_id: "0".repeat(32),
            authority_digest: "5".repeat(64),
          },
          result_code: "EDIT_EXECUTION_COMPLETED",
        });
      return baseFetch(input);
    });
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);

    await createBoundDemoEdit(handle, {
      operation: "EXPOSURE",
      valuePpm: 250_000,
    });
    for (let index = 0; index < 4; index += 1)
      expect(await readBoundDemoEdit(handle)).toEqual({ kind: "PENDING" });
    expect(await readBoundDemoEdit(handle)).toEqual({ kind: "STALE_RESPONSE" });
  });

  it("drops an in-flight edit admission after configuration rotation", async () => {
    const profileStatus = { value: "PENDING" };
    const baseFetch = upstreamFetch(profileStatus);
    const admission = deferred<Response>();
    const started = deferred<void>();
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      if (pathname(input) === "/api/v1/demo/editing-sessions") {
        started.resolve();
        return admission.promise;
      }
      return baseFetch(input);
    });
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);
    const response = await baseFetch(
      new Request("http://upstream/api/v1/demo/editing-sessions", {
        method: "POST",
      }),
    );

    const pending = createBoundDemoEdit(handle, {
      operation: "EXPOSURE",
      valuePpm: 250_000,
    });
    await started.promise;
    process.env.DEMO_BEARER_TOKEN = "y".repeat(32);
    admission.resolve(response);
    expect(await pending).toEqual({ kind: "DENIED" });
  });

  it("projects only edit status and rejects browser authority overrides", async () => {
    const profileStatus = { value: "PENDING" };
    vi.stubGlobal("fetch", upstreamFetch(profileStatus));
    const handle = await completedProfile(profileStatus);
    const { GET, POST } = await import("../../app/api/demo/edit/route");
    const headers = {
      Origin: "https://demo.test",
      Cookie: `mirror_demo_session=${handle}`,
    };
    const started = await POST(
      new Request("https://demo.test/api/demo/edit", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ operation: "TEMPERATURE", value_ppm: 400_000 }),
      }),
    );
    expect(started.status).toBe(202);
    expect(await started.json()).toEqual({ status: "PENDING" });
    for (let index = 0; index < 5; index += 1) {
      const pending = await GET(
        new Request("https://demo.test/api/demo/edit", { headers }),
      );
      expect(await pending.json()).toEqual({ status: "PENDING" });
    }
    const ready = await GET(
      new Request("https://demo.test/api/demo/edit", { headers }),
    );
    expect(ready.status).toBe(200);
    expect(await ready.json()).toEqual({ status: "IMAGE_VERSION_READY" });

    const invalid = await POST(
      new Request("https://demo.test/api/demo/edit", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ operation: "GEOMETRY", value_ppm: 1 }),
      }),
    );
    const query = await GET(
      new Request("https://demo.test/api/demo/edit?job_id=forbidden", {
        headers,
      }),
    );
    const authorization = await GET(
      new Request("https://demo.test/api/demo/edit", {
        headers: { ...headers, Authorization: "Bearer forbidden" },
      }),
    );
    expect([invalid.status, query.status, authorization.status]).toEqual([
      403, 403, 403,
    ]);
  });

  it("drops an in-flight published result after logout", async () => {
    const profileStatus = { value: "PENDING" };
    const baseFetch = upstreamFetch(profileStatus);
    const resultResponse = await baseFetch(
      new Request(
        `http://upstream/api/v1/demo/edit-plans/execution-jobs/${executionJobId}/result`,
      ),
    );
    const pendingResult = deferred<Response>();
    const resultStarted = deferred<void>();
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      if (pathname(input).includes("/edit-plans/execution-jobs/")) {
        resultStarted.resolve();
        return pendingResult.promise;
      }
      return baseFetch(input);
    });
    vi.stubGlobal("fetch", fetchMock);
    const handle = await completedProfile(profileStatus);
    await createBoundDemoEdit(handle, {
      operation: "EXPOSURE",
      valuePpm: 250_000,
    });
    for (let index = 0; index < 5; index += 1) await readBoundDemoEdit(handle);

    const pending = readBoundDemoEdit(handle);
    await resultStarted.promise;
    removeBoundDemoSession(handle);
    pendingResult.resolve(resultResponse);
    expect(await pending).toEqual({ kind: "DENIED" });
    expect(await readBoundDemoEdit(handle)).toEqual({ kind: "DENIED" });
  });
});
