import { afterEach, describe, expect, it, vi } from "vitest";

import { getDemoCapabilities } from "./demo-capabilities";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("demo capabilities server adapter", () => {
  it("returns a generated-contract-compatible response after strict validation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          track: "DEMO_PROTOTYPE",
          capabilities: [{ code: "P5_COMPILER", status: "AVAILABLE" }],
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(getDemoCapabilities()).resolves.toEqual({
      kind: "AVAILABLE",
      data: {
        track: "DEMO_PROTOTYPE",
        capabilities: [{ code: "P5_COMPILER", status: "AVAILABLE" }],
      },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/demo/capabilities",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(fetchMock.mock.calls[0]?.[1]).not.toHaveProperty("headers");
  });

  it("reports the tracked bearer boundary without sending a credential", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getDemoCapabilities()).resolves.toEqual({
      kind: "AUTH_REQUIRED",
      data: null,
    });
    expect(fetchMock.mock.calls[0]?.[1]).not.toHaveProperty("headers");
  });

  it.each([
    { track: "NOT_A_TRACK" },
    {
      track: "DEMO_PROTOTYPE",
      capabilities: [
        { code: "P5_COMPILER", status: "AVAILABLE", unexpected: true },
      ],
    },
    {
      track: "DEMO_PROTOTYPE",
      capabilities: [
        {
          code: "P6_MAKEUP",
          status: "DEFERRED_WITH_EXPLICIT_REASON",
          reason: "",
        },
      ],
    },
  ])("fails closed for an invalid response %#", async (payload) => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(payload), { status: 200 }),
        ),
    );

    await expect(getDemoCapabilities()).resolves.toEqual({
      kind: "UNAVAILABLE",
      data: null,
    });
  });
});
