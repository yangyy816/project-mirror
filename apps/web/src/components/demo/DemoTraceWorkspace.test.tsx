// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DemoTraceWorkspace } from "./DemoTraceWorkspace";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("DemoTraceWorkspace", () => {
  it("uses one explicit replay timestamp without sending browser authorization", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response('{"status":"SESSION_READY"}', { status: 201 }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: "READY",
            recall_at: "2099-01-01T00:00:00.000Z",
            context: {
              profile_id: "2".repeat(32),
              compilation_digest: "f".repeat(64),
              expires_at: "2099-01-01T00:15:00Z",
            },
            trace: {
              context_compilation_id: "3".repeat(32),
              evidence_digest: "f".repeat(64),
            },
          }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<DemoTraceWorkspace />);
    fireEvent.click(
      screen.getByRole("button", { name: "读取 Context 与 Trace" }),
    );

    await waitFor(() =>
      expect(screen.getByText("只读回放完成。")).toBeVisible(),
    );
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/demo/session");
    expect(fetchMock.mock.calls[1]?.[0]).toContain(
      "recall_at=2099-01-01T00%3A00%3A00.000Z",
    );
    for (const [, options] of fetchMock.mock.calls) {
      expect((options as RequestInit).headers).not.toHaveProperty(
        "Authorization",
      );
    }
    expect(screen.queryByText("1".repeat(32))).toBeNull();
  });

  it("renders stale responses without showing a synthetic replacement", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response('{"status":"SESSION_READY"}', { status: 201 }),
      )
      .mockResolvedValueOnce(
        new Response('{"code":"STALE_RESPONSE"}', { status: 409 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<DemoTraceWorkspace />);
    fireEvent.click(
      screen.getByRole("button", { name: "读取 Context 与 Trace" }),
    );

    await waitFor(() =>
      expect(screen.getByText(/权威 digest 不一致/)).toBeVisible(),
    );
    expect(screen.queryByText("DETERMINISTIC_READ_ONLY")).toBeNull();
  });

  it("does not claim logout after a denied or unavailable BFF response", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response('{"code":"DENIED"}', { status: 403 }))
      .mockResolvedValueOnce(
        new Response('{"code":"UNAVAILABLE"}', { status: 503 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<DemoTraceWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "结束 Demo 会话" }));
    await waitFor(() => expect(screen.getByText(/会话已过期/)).toBeVisible());

    fireEvent.click(screen.getByRole("button", { name: "结束 Demo 会话" }));
    await waitFor(() =>
      expect(screen.getByText(/Demo API 当前不可用/)).toBeVisible(),
    );
  });
});
