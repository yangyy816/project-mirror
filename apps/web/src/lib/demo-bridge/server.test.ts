import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  boundSessionFor,
  canonicalRecallAt,
  clearDemoSessionRegistryForTest,
  createBoundDemoSession,
  demoSessionRegistrySize,
  errorForStatus,
  isSameOriginRequest,
  readBoundDemoRecall,
} from "./server";

const bearer = "x".repeat(32);
const identityId = "a".repeat(32);
const sessionId = "1".repeat(32);

function upstreamFetch(expiresAtMs = 901_000) {
  return vi.fn(async (input: string | URL | Request) => {
    const url = new URL(
      typeof input === "string" || input instanceof URL ? input : input.url,
    );
    if (url.pathname === "/api/v1/demo/identities") {
      return new Response(
        JSON.stringify({
          identities: [
            {
              identity_id: identityId,
              canonical_asset_digest: "d".repeat(64),
              admission_status: "ADMITTED",
            },
          ],
        }),
        { status: 200 },
      );
    }
    if (url.pathname === "/api/v1/demo/sessions") {
      return new Response(
        JSON.stringify({
          session_id: sessionId,
          synthetic_identity_id: identityId,
          status: "ACTIVE",
          expires_at: new Date(expiresAtMs).toISOString(),
        }),
        { status: 201 },
      );
    }
    if (url.pathname.includes("/context")) {
      return new Response(
        JSON.stringify({
          session_id: sessionId,
          profile_id: "2".repeat(32),
          compilation_digest: "f".repeat(64),
          expires_at: new Date(expiresAtMs).toISOString(),
        }),
        { status: 200 },
      );
    }
    if (url.pathname.includes("/traces/")) {
      return new Response(
        JSON.stringify({
          session_id: sessionId,
          context_compilation_id: "3".repeat(32),
          evidence_digest: "f".repeat(64),
        }),
        { status: 200 },
      );
    }
    return new Response(null, { status: 404 });
  });
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

describe("demo bridge server boundary", () => {
  it("requires a matching Origin and/or same-origin fetch metadata", () => {
    expect(
      isSameOriginRequest(
        new Request("https://demo.test/api/demo/session", {
          headers: {
            Origin: "https://demo.test",
            "Sec-Fetch-Site": "same-origin",
          },
        }),
      ),
    ).toBe(true);
    expect(
      isSameOriginRequest(
        new Request("https://demo.test/api/demo/session", {
          headers: { Origin: "https://attacker.test" },
        }),
      ),
    ).toBe(false);
    expect(
      isSameOriginRequest(
        new Request("https://demo.test/api/demo/session", {
          headers: { "Sec-Fetch-Site": "cross-site" },
        }),
      ),
    ).toBe(false);
    expect(
      isSameOriginRequest(new Request("https://demo.test/api/demo/session")),
    ).toBe(false);
  });

  it("canonicalizes timezone-aware recall values and rejects implicit time", () => {
    expect(canonicalRecallAt("2099-01-01T08:00:00+08:00")).toBe(
      "2099-01-01T00:00:00.000Z",
    );
    expect(canonicalRecallAt("2099-01-01T00:00:00")).toBeNull();
  });

  it("creates an admitted server-side session, caps TTL, and reuses its handle", async () => {
    const nowMs = Date.now();
    const fetchMock = upstreamFetch(nowMs + 900_000);
    vi.stubGlobal("fetch", fetchMock);

    const first = await createBoundDemoSession(undefined, nowMs);
    expect(first).toMatchObject({ maxAge: 60 });
    expect(first?.handle).toMatch(/^[a-f0-9]{64}$/);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const createRequest = fetchMock.mock.calls[1]?.[0] as Request;
    expect(await createRequest.json()).toMatchObject({
      synthetic_identity_id: identityId,
      context_seed: expect.stringMatching(/^[a-f0-9]{64}$/),
    });
    expect(createRequest.headers.get("Authorization")).toBe(`Bearer ${bearer}`);
    expect(createRequest.headers.get("Idempotency-Key")).toMatch(
      /^[a-f0-9]{64}$/,
    );

    const reused = await createBoundDemoSession(first?.handle, nowMs + 1);
    expect(reused?.handle).toBe(first?.handle);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(boundSessionFor(first?.handle, nowMs + 60_000)).toBeNull();
  });

  it("invalidates a prior handle when configuration is missing, rotated, or invalid", async () => {
    const nowMs = Date.now();
    const fetchMock = upstreamFetch(nowMs + 900_000);
    vi.stubGlobal("fetch", fetchMock);
    const first = await createBoundDemoSession(undefined, nowMs);
    delete process.env.DEMO_BEARER_TOKEN;
    expect(await createBoundDemoSession(first?.handle, nowMs + 1)).toBeNull();
    expect(boundSessionFor(first?.handle, nowMs + 1)).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);

    process.env.DEMO_BEARER_TOKEN = bearer;
    const second = await createBoundDemoSession(undefined, nowMs + 2);
    process.env.DEMO_BOOTSTRAP_IDENTITY_ID = "b".repeat(32);
    expect(await createBoundDemoSession(second?.handle, nowMs + 3)).toBeNull();
    expect(boundSessionFor(second?.handle, nowMs + 3)).toBeNull();

    process.env.DEMO_BOOTSTRAP_IDENTITY_ID = identityId;
    const third = await createBoundDemoSession(undefined, nowMs + 4);
    process.env.DEMO_BEARER_TOKEN = "y".repeat(32);
    const rotated = await createBoundDemoSession(third?.handle, nowMs + 5);
    expect(rotated?.handle).toMatch(/^[a-f0-9]{64}$/);
    expect(rotated?.handle).not.toBe(third?.handle);

    process.env.DEMO_SESSION_TTL_SECONDS = "59";
    expect(await createBoundDemoSession(rotated?.handle, nowMs + 6)).toBeNull();
    expect(boundSessionFor(rotated?.handle, nowMs + 6)).toBeNull();
  });

  it("fails closed for cross-bound or expired upstream sessions", async () => {
    const nowMs = Date.now();
    const fetchMock = upstreamFetch(nowMs + 900_000);
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          identities: [
            {
              identity_id: identityId,
              canonical_asset_digest: "d".repeat(64),
              admission_status: "ADMITTED",
            },
          ],
        }),
        { status: 200 },
      ),
    );
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          session_id: sessionId,
          synthetic_identity_id: "b".repeat(32),
          status: "ACTIVE",
          expires_at: new Date(nowMs + 900_000).toISOString(),
        }),
        { status: 201 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    expect(await createBoundDemoSession(undefined, nowMs)).toBeNull();
    expect(demoSessionRegistrySize(nowMs)).toBe(0);

    clearDemoSessionRegistryForTest();
    vi.stubGlobal("fetch", upstreamFetch(nowMs));
    expect(await createBoundDemoSession(undefined, nowMs)).toBeNull();
    expect(demoSessionRegistrySize(nowMs)).toBe(0);
  });

  it("never exceeds the bounded registry capacity", async () => {
    const nowMs = Date.now();
    const fetchMock = upstreamFetch(nowMs + 900_000);
    vi.stubGlobal("fetch", fetchMock);
    for (let index = 0; index < 64; index += 1) {
      expect(await createBoundDemoSession(undefined, nowMs)).not.toBeNull();
    }
    expect(demoSessionRegistrySize(nowMs)).toBe(64);
    expect(await createBoundDemoSession(undefined, nowMs)).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(128);
  });

  it("projects recall only after internal verification without leaking session_id", async () => {
    const nowMs = Date.now();
    vi.stubGlobal("fetch", upstreamFetch(nowMs + 900_000));
    const session = await createBoundDemoSession(undefined, nowMs);
    const result = await readBoundDemoRecall(
      session?.handle,
      "2099-01-01T00:00:00Z",
    );
    expect(result).toMatchObject({ kind: "READY" });
    expect(JSON.stringify(result)).not.toContain("session_id");
    expect(JSON.stringify(result)).not.toContain(sessionId);
  });

  it("maps upstream statuses to redacted stable codes", () => {
    expect(errorForStatus(401)).toBe("DENIED");
    expect(errorForStatus(403)).toBe("DENIED");
    expect(errorForStatus(404)).toBe("NOT_FOUND");
    expect(errorForStatus(409)).toBe("CONFLICT");
    expect(errorForStatus(422)).toBe("CONFLICT");
    expect(errorForStatus(503)).toBe("UNAVAILABLE");
  });

  it("rejects BFF query and body overrides with no-store redacted responses", async () => {
    const { POST } = await import("../../app/api/demo/session/route");
    const response = await POST(
      new Request("https://demo.test/api/demo/session?session_id=override", {
        method: "POST",
        headers: { Origin: "https://demo.test" },
      }),
    );
    expect(response.status).toBe(403);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(await response.text()).not.toContain(bearer);

    const bodyResponse = await POST(
      new Request("https://demo.test/api/demo/session", {
        method: "POST",
        headers: {
          Origin: "https://demo.test",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ session_id: "override" }),
      }),
    );
    expect(bodyResponse.status).toBe(403);
    expect(bodyResponse.headers.get("cache-control")).toBe("no-store");
  });
});
