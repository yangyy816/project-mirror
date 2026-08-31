import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  boundSessionFor,
  canonicalRecallAt,
  clearDemoSessionRegistryForTest,
  createBoundDemoSession,
  demoSessionRegistrySize,
  errorForStatus,
  isSameOriginRequest,
} from "./server";

const bearer = "x".repeat(32);
const sessionId = "1".repeat(32);

beforeEach(() => {
  process.env.DEMO_BEARER_TOKEN = bearer;
  process.env.DEMO_SESSION_ID = sessionId;
  process.env.DEMO_SESSION_TTL_SECONDS = "60";
  clearDemoSessionRegistryForTest();
});

afterEach(() => {
  clearDemoSessionRegistryForTest();
  delete process.env.DEMO_BEARER_TOKEN;
  delete process.env.DEMO_SESSION_ID;
  delete process.env.DEMO_SESSION_TTL_SECONDS;
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

  it("reuses valid handles, expires them, and never grows past the registry cap", () => {
    const first = createBoundDemoSession(undefined, 1_000);
    expect(first).not.toBeNull();
    const reused = createBoundDemoSession(first?.handle, 1_001);
    expect(reused?.handle).toBe(first?.handle);
    process.env.DEMO_SESSION_ID = "2".repeat(32);
    const rotated = createBoundDemoSession(first?.handle, 1_002);
    expect(rotated?.handle).not.toBe(first?.handle);
    expect(boundSessionFor(first?.handle, 1_002)).toBeNull();
    expect(boundSessionFor(first?.handle, 61_000)).toBeNull();

    for (let index = 0; index < 64; index += 1) {
      expect(createBoundDemoSession(undefined, 100_000)).not.toBeNull();
    }
    expect(demoSessionRegistrySize(100_000)).toBe(64);
    expect(createBoundDemoSession(undefined, 100_000)).toBeNull();
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
