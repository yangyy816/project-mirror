import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearDemoSessionRegistryForTest,
  createBoundDemoAnalysis,
  createBoundDemoProfile,
  createBoundDemoQuestionnaire,
  createBoundDemoSession,
  profileProjection,
  readBoundDemoAnalysis,
  readBoundDemoProfile,
  readBoundDemoQuestionnaire,
  removeBoundDemoSession,
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

function json(body: object, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function pathname(input: string | URL | Request) {
  return new URL(
    typeof input === "string" || input instanceof URL ? input : input.url,
  ).pathname;
}

function upstreamFetch(profileStatus: { value: string }) {
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
