// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DemoRealFlowWorkspace } from "./DemoRealFlowWorkspace";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

describe("DemoRealFlowWorkspace", () => {
  it("starts the bounded flow, submits all supported choice values and rotates the question projection", async () => {
    const choices = ["LEFT", "RIGHT", "INDISTINGUISHABLE", "SKIP"] as const;
    for (const choice of choices) {
      const firstToken = "a".repeat(64);
      const secondToken = "b".repeat(64);
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(response({ status: "SESSION_READY" }, 201))
        .mockResolvedValueOnce(response({ status: "PENDING" }, 202))
        .mockResolvedValueOnce(
          response({
            status: "COMPLETED",
            analysis_state: "SUPPORTED",
            self_state: "READY",
          }),
        )
        .mockResolvedValueOnce(
          response({
            status: "QUESTION",
            presentation_token: firstToken,
            left_image_url: `/api/demo/questionnaire/media/${firstToken}/LEFT`,
            right_image_url: `/api/demo/questionnaire/media/${firstToken}/RIGHT`,
          }),
        )
        .mockResolvedValueOnce(
          response({
            status: "QUESTION",
            presentation_token: secondToken,
            left_image_url: `/api/demo/questionnaire/media/${secondToken}/LEFT`,
            right_image_url: `/api/demo/questionnaire/media/${secondToken}/RIGHT`,
          }),
        );
      vi.stubGlobal("fetch", fetchMock);
      const { unmount } = render(<DemoRealFlowWorkspace />);
      fireEvent.click(screen.getByRole("button", { name: "开始 Demo" }));
      await waitFor(
        () =>
          expect(
            screen.getByRole("button", { name: "开始偏好问卷" }),
          ).toBeVisible(),
        { timeout: 2_000 },
      );
      fireEvent.click(screen.getByRole("button", { name: "开始偏好问卷" }));
      await waitFor(() =>
        expect(screen.getByRole("img", { name: "左侧方案" })).toHaveAttribute(
          "src",
          `/api/demo/questionnaire/media/${firstToken}/LEFT`,
        ),
      );
      fireEvent.click(
        screen.getByRole("button", {
          name: (
            {
              LEFT: "更偏好左侧",
              RIGHT: "更偏好右侧",
              INDISTINGUISHABLE: "难以区分",
              SKIP: "跳过此题",
            } as const
          )[choice],
        }),
      );
      await waitFor(() =>
        expect(screen.getByRole("img", { name: "左侧方案" })).toHaveAttribute(
          "src",
          `/api/demo/questionnaire/media/${secondToken}/LEFT`,
        ),
      );
      const body = JSON.parse(fetchMock.mock.calls.at(-1)?.[1].body as string);
      expect(body.choice).toBe(choice);
      expect(body.response_latency_ms).toBeGreaterThanOrEqual(0);
      expect(body.response_latency_ms).toBeLessThanOrEqual(3_600_000);
      for (const [, init] of fetchMock.mock.calls)
        expect((init as RequestInit).headers).not.toHaveProperty(
          "Authorization",
        );
      unmount();
      vi.unstubAllGlobals();
    }
  });

  it("rejects a media URL that is not exactly bound to the opaque token", async () => {
    const token = "a".repeat(64);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ status: "SESSION_READY" }, 201))
      .mockResolvedValueOnce(response({ status: "PENDING" }, 202))
      .mockResolvedValueOnce(
        response({
          status: "COMPLETED",
          analysis_state: "SUPPORTED",
          self_state: "READY",
        }),
      )
      .mockResolvedValueOnce(
        response({
          status: "QUESTION",
          presentation_token: token,
          left_image_url: "https://example.invalid/leak.jpg",
          right_image_url: `/api/demo/questionnaire/media/${token}/RIGHT`,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<DemoRealFlowWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "开始 Demo" }));
    await waitFor(
      () =>
        expect(
          screen.getByRole("button", { name: "开始偏好问卷" }),
        ).toBeVisible(),
      { timeout: 2_000 },
    );
    fireEvent.click(screen.getByRole("button", { name: "开始偏好问卷" }));
    await waitFor(() => expect(screen.getByText(/收到过期响应/)).toBeVisible());
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("shows a recoverable error and clears UI state when ending the demo", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ code: "UNAVAILABLE" }, 503))
      .mockResolvedValueOnce(response({ status: "LOGGED_OUT" }));
    vi.stubGlobal("fetch", fetchMock);
    render(<DemoRealFlowWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "开始 Demo" }));
    await waitFor(() =>
      expect(screen.getByText(/服务暂时不可用/)).toBeVisible(),
    );
    expect(screen.getByRole("button", { name: "重试当前步骤" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "结束 Demo" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "开始 Demo" })).toBeVisible(),
    );
    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe("/api/demo/session");
    expect(fetchMock.mock.calls.at(-1)?.[1]).toMatchObject({
      method: "DELETE",
    });
  });

  it("does not let an old session response revive UI after ending the demo", async () => {
    const pendingSession = deferred<Response>();
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/demo/session" && init?.method === "POST")
        return pendingSession.promise;
      if (path === "/api/demo/session" && init?.method === "DELETE")
        return Promise.resolve(response({ status: "LOGGED_OUT" }));
      throw new Error(`unexpected request: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<DemoRealFlowWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "开始 Demo" }));
    fireEvent.click(screen.getByRole("button", { name: "结束 Demo" }));
    expect(screen.getByText("正在安全结束 Demo 会话。")).toBeVisible();
    expect(
      fetchMock.mock.calls.filter(
        ([path, init]) =>
          path === "/api/demo/session" && init?.method === "DELETE",
      ),
    ).toHaveLength(0);
    pendingSession.resolve(response({ status: "SESSION_READY" }, 201));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "开始 Demo" })).toBeVisible(),
    );
    expect(
      fetchMock.mock.calls.filter(([path]) => path === "/api/demo/analysis"),
    ).toHaveLength(0);
    expect(
      fetchMock.mock.calls.filter(
        ([path, init]) =>
          path === "/api/demo/session" && init?.method === "DELETE",
      ),
    ).toHaveLength(1);
  });

  it("retries an uncertain answer exactly and reconciles a stale token by reading", async () => {
    const token = "a".repeat(64);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ status: "SESSION_READY" }, 201))
      .mockResolvedValueOnce(response({ status: "PENDING" }, 202))
      .mockResolvedValueOnce(
        response({
          status: "COMPLETED",
          analysis_state: "SUPPORTED",
          self_state: "READY",
        }),
      )
      .mockResolvedValueOnce(
        response({
          status: "QUESTION",
          presentation_token: token,
          left_image_url: `/api/demo/questionnaire/media/${token}/LEFT`,
          right_image_url: `/api/demo/questionnaire/media/${token}/RIGHT`,
        }),
      )
      .mockResolvedValueOnce(response({ code: "UNAVAILABLE" }, 503))
      .mockResolvedValueOnce(response({ code: "CONFLICT" }, 409))
      .mockResolvedValueOnce(response({ status: "COMPLETED" }))
      .mockResolvedValueOnce(response({ status: "PENDING" }, 202))
      .mockResolvedValueOnce(response({ status: "PROFILE_READY" }))
      .mockResolvedValueOnce(response({ code: "UNAVAILABLE" }, 503))
      .mockResolvedValueOnce(
        response({
          status: "PREVIEW_READY",
          input_image_url: `/api/demo/self-transfer/media/${"b".repeat(64)}/INPUT`,
          result_image_url: `/api/demo/self-transfer/media/${"b".repeat(64)}/RESULT`,
          dimension_key: "chin_height",
          direction: "INCREASE",
          step_ppm: 30000,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<DemoRealFlowWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "开始 Demo" }));
    await waitFor(
      () =>
        expect(
          screen.getByRole("button", { name: "开始偏好问卷" }),
        ).toBeVisible(),
      { timeout: 2_000 },
    );
    fireEvent.click(screen.getByRole("button", { name: "开始偏好问卷" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "更偏好左侧" })).toBeVisible(),
    );
    fireEvent.click(screen.getByRole("button", { name: "更偏好左侧" }));
    await waitFor(() =>
      expect(screen.getByText(/服务暂时不可用/)).toBeVisible(),
    );
    const first = fetchMock.mock.calls.filter(
      ([path]) => path === "/api/demo/questionnaire/response",
    )[0]?.[1]?.body;
    fireEvent.click(screen.getByRole("button", { name: "重试当前步骤" }));
    await waitFor(
      () => expect(screen.getByText("偏好档案已准备完成。")).toBeVisible(),
      { timeout: 2_500 },
    );
    const attempts = fetchMock.mock.calls.filter(
      ([path]) => path === "/api/demo/questionnaire/response",
    );
    expect(attempts).toHaveLength(2);
    expect(attempts[1]?.[1]?.body).toBe(first);

    fireEvent.click(
      screen.getByRole("button", { name: "生成档案引导的几何预览" }),
    );
    await waitFor(
      () => expect(screen.getByText(/服务暂时不可用/)).toBeVisible(),
      { timeout: 2_500 },
    );
    fireEvent.click(screen.getByRole("button", { name: "重试当前步骤" }));
    await screen.findByRole("img", { name: "编辑前合成图" });
    const previewPosts = fetchMock.mock.calls.filter(
      ([path, init]) =>
        path === "/api/demo/self-transfer" && init?.method === "POST",
    );
    expect(previewPosts).toHaveLength(2);
    expect(previewPosts.map(([, init]) => init?.body)).toEqual([
      JSON.stringify({ action: "PROFILE_GUIDED_GEOMETRY_PREVIEW" }),
      JSON.stringify({ action: "PROFILE_GUIDED_GEOMETRY_PREVIEW" }),
    ]);
  });

  it("retries a recoverable profile-guided preview admission", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ status: "SESSION_READY" }, 201))
      .mockResolvedValueOnce(response({ status: "PENDING" }, 202))
      .mockResolvedValueOnce(
        response({
          status: "COMPLETED",
          analysis_state: "SUPPORTED",
          self_state: "READY",
        }),
      )
      .mockResolvedValueOnce(response({ status: "COMPLETED" }))
      .mockResolvedValueOnce(response({ status: "PENDING" }, 202))
      .mockResolvedValueOnce(response({ status: "PROFILE_READY" }))
      .mockResolvedValueOnce(response({ code: "UNAVAILABLE" }, 503))
      .mockResolvedValueOnce(
        response({
          status: "PREVIEW_READY",
          input_image_url: `/api/demo/self-transfer/media/${"c".repeat(64)}/INPUT`,
          result_image_url: `/api/demo/self-transfer/media/${"c".repeat(64)}/RESULT`,
          dimension_key: "eye_spacing",
          direction: "DECREASE",
          step_ppm: 15000,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<DemoRealFlowWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "开始 Demo" }));
    await waitFor(
      () =>
        expect(
          screen.getByRole("button", { name: "开始偏好问卷" }),
        ).toBeVisible(),
      { timeout: 2_000 },
    );
    fireEvent.click(screen.getByRole("button", { name: "开始偏好问卷" }));
    await waitFor(
      () => expect(screen.getByText("偏好档案已准备完成。")).toBeVisible(),
      { timeout: 2_500 },
    );

    fireEvent.click(
      screen.getByRole("button", { name: "生成档案引导的几何预览" }),
    );
    await waitFor(() =>
      expect(screen.getByText(/服务暂时不可用/)).toBeVisible(),
    );
    fireEvent.click(screen.getByRole("button", { name: "重试当前步骤" }));
    await screen.findByRole("img", { name: "编辑后合成图" });
    expect(screen.queryByRole("slider")).toBeNull();
    const previewPosts = fetchMock.mock.calls.filter(
      ([path, init]) =>
        path === "/api/demo/self-transfer" && init?.method === "POST",
    );
    expect(previewPosts).toHaveLength(2);
    expect(previewPosts.map(([, init]) => init?.body)).toEqual([
      JSON.stringify({ action: "PROFILE_GUIDED_GEOMETRY_PREVIEW" }),
      JSON.stringify({ action: "PROFILE_GUIDED_GEOMETRY_PREVIEW" }),
    ]);
  });

  it("renders a terminal profile result without creating another job", async () => {
    const token = "a".repeat(64);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ status: "SESSION_READY" }, 201))
      .mockResolvedValueOnce(response({ status: "PENDING" }, 202))
      .mockResolvedValueOnce(
        response({
          status: "COMPLETED",
          analysis_state: "SUPPORTED",
          self_state: "READY",
        }),
      )
      .mockResolvedValueOnce(
        response({
          status: "QUESTION",
          presentation_token: token,
          left_image_url: `/api/demo/questionnaire/media/${token}/LEFT`,
          right_image_url: `/api/demo/questionnaire/media/${token}/RIGHT`,
        }),
      )
      .mockResolvedValueOnce(response({ status: "COMPLETED" }))
      .mockResolvedValueOnce(response({ status: "PENDING" }, 202))
      .mockResolvedValueOnce(response({ status: "FAILED" }));
    vi.stubGlobal("fetch", fetchMock);
    render(<DemoRealFlowWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "开始 Demo" }));
    await waitFor(
      () =>
        expect(
          screen.getByRole("button", { name: "开始偏好问卷" }),
        ).toBeVisible(),
      { timeout: 2_000 },
    );
    fireEvent.click(screen.getByRole("button", { name: "开始偏好问卷" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "跳过此题" })).toBeVisible(),
    );
    fireEvent.click(screen.getByRole("button", { name: "跳过此题" }));

    await waitFor(() => expect(screen.getByText(/处理未完成/)).toBeVisible(), {
      timeout: 2_500,
    });
    expect(screen.queryByRole("button", { name: "重试当前步骤" })).toBeNull();
    expect(
      fetchMock.mock.calls.filter(
        ([path, init]) =>
          path === "/api/demo/profile" && init?.method === "POST",
      ),
    ).toHaveLength(1);
  });

  it("renders a terminal analysis result without offering a mutating retry", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ status: "SESSION_READY" }, 201))
      .mockResolvedValueOnce(response({ status: "PENDING" }, 202))
      .mockResolvedValueOnce(response({ status: "FAILED" }));
    vi.stubGlobal("fetch", fetchMock);
    render(<DemoRealFlowWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "开始 Demo" }));
    await waitFor(() => expect(screen.getByText(/处理未完成/)).toBeVisible(), {
      timeout: 2_000,
    });
    expect(screen.queryByRole("button", { name: "重试当前步骤" })).toBeNull();
    expect(screen.getByRole("button", { name: "结束 Demo" })).toBeVisible();
  });

  it("stops an indefinitely pending phase at the frozen poll limit", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ status: "SESSION_READY" }, 201))
      .mockResolvedValueOnce(response({ status: "PENDING" }, 202))
      .mockImplementation(() =>
        Promise.resolve(response({ status: "PENDING" })),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<DemoRealFlowWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "开始 Demo" }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });
    expect(screen.getByText(/等待时间已到/)).toBeVisible();
    expect(
      fetchMock.mock.calls.filter(
        ([path, init]) =>
          path === "/api/demo/analysis" && init?.method !== "POST",
      ),
    ).toHaveLength(120);
  });

  it("requires both geometry previews to load before an explicit final save", async () => {
    const mediaToken = "a".repeat(64);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ status: "SESSION_READY" }, 201))
      .mockResolvedValueOnce(response({ status: "PENDING" }, 202))
      .mockResolvedValueOnce(
        response({
          status: "COMPLETED",
          analysis_state: "SUPPORTED",
          self_state: "READY",
        }),
      )
      .mockResolvedValueOnce(response({ status: "COMPLETED" }))
      .mockResolvedValueOnce(response({ status: "PROFILE_READY" }))
      .mockResolvedValueOnce(
        response({
          status: "PREVIEW_READY",
          input_image_url: `/api/demo/self-transfer/media/${mediaToken}/INPUT`,
          result_image_url: `/api/demo/self-transfer/media/${mediaToken}/RESULT`,
          dimension_key: "jaw_width",
          direction: "DECREASE",
          step_ppm: 15000,
        }),
      )
      .mockResolvedValueOnce(
        response({ status: "REFERENCE_PROFILE_PENDING" }, 202),
      )
      .mockResolvedValueOnce(response({ status: "REFERENCE_PROFILE_READY" }));
    vi.stubGlobal("fetch", fetchMock);
    render(<DemoRealFlowWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "开始 Demo" }));
    await waitFor(
      () =>
        expect(
          screen.getByRole("button", { name: "开始偏好问卷" }),
        ).toBeVisible(),
      { timeout: 2_500 },
    );
    fireEvent.click(screen.getByRole("button", { name: "开始偏好问卷" }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "生成档案引导的几何预览" }),
      ).toBeVisible(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "生成档案引导的几何预览" }),
    );
    const before = await screen.findByRole("img", { name: "编辑前合成图" });
    const after = screen.getByRole("img", { name: "编辑后合成图" });
    const accept = screen.getByRole("button", { name: "最终保存并用作参考" });
    expect(accept).toBeDisabled();
    expect(screen.queryByRole("slider")).toBeNull();
    expect(screen.getByText("下颌宽度 · 减少 · 1.5%")).toBeVisible();
    fireEvent.load(before);
    fireEvent.load(after);
    await waitFor(() => expect(accept).toBeEnabled());
    fireEvent.error(after);
    expect(accept).toBeDisabled();
    fireEvent.load(after);
    await waitFor(() => expect(accept).toBeEnabled());
    fireEvent.click(accept);
    await screen.findByText("已保存，参考档案待恢复");
    await waitFor(
      () => expect(screen.getByText("已保存并更新参考档案")).toBeVisible(),
      { timeout: 2_500 },
    );
    const acceptRequest = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/api/demo/self-transfer/accept" && init?.method === "POST",
    );
    expect(JSON.parse(acceptRequest?.[1]?.body as string)).toEqual({
      outcome: "FINAL_SAVE_AND_USE_AS_REFERENCE",
    });
    expect(
      fetchMock.mock.calls.filter(
        ([path, init]) =>
          path === "/api/demo/self-transfer/accept" && init?.method === "POST",
      ),
    ).toHaveLength(1);
  });

  it("projects no-compatible-case and recovery-required without rendering media", async () => {
    const profileResponses = [
      response({ status: "SESSION_READY" }, 201),
      response({ status: "PENDING" }, 202),
      response({
        status: "COMPLETED",
        analysis_state: "SUPPORTED",
        self_state: "READY",
      }),
      response({ status: "COMPLETED" }),
      response({ status: "PROFILE_READY" }),
      response({ status: "NO_COMPATIBLE_CASE" }),
    ];
    const fetchMock = vi.fn();
    for (const item of profileResponses) fetchMock.mockResolvedValueOnce(item);
    vi.stubGlobal("fetch", fetchMock);
    render(<DemoRealFlowWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "开始 Demo" }));
    await waitFor(
      () =>
        expect(
          screen.getByRole("button", { name: "开始偏好问卷" }),
        ).toBeVisible(),
      { timeout: 2_500 },
    );
    fireEvent.click(screen.getByRole("button", { name: "开始偏好问卷" }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "生成档案引导的几何预览" }),
      ).toBeVisible(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "生成档案引导的几何预览" }),
    );
    await screen.findByText("当前档案暂无可用的安全几何步骤");
    expect(screen.queryByRole("img", { name: "编辑前合成图" })).toBeNull();
    expect(document.body.textContent).not.toMatch(/digest|bearer|locator/i);
  });
});
