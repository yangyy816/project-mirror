"use client";

/* eslint-disable @next/next/no-img-element -- BFF media is an opaque same-origin, no-store URL. */

import { useEffect, useRef, useState } from "react";

import { Badge, Button } from "@mirror/ui";

type Phase = "analysis" | "questionnaire" | "profile";
type Choice = "LEFT" | "RIGHT" | "INDISTINGUISHABLE" | "SKIP";
type Question = Readonly<{
  presentationToken: string;
  leftImageUrl: string;
  rightImageUrl: string;
}>;
type AnswerSubmission = Readonly<{
  question: Question;
  shownAt: number;
  choice: Choice;
  responseLatencyMs: number;
}>;
type State =
  | { kind: "IDLE" }
  | { kind: "SESSION_CREATING" }
  | { kind: "SESSION_ENDING" }
  | { kind: "ANALYSIS_STARTING" }
  | { kind: "ANALYSIS_PENDING" }
  | { kind: "ANALYSIS_COMPLETED" }
  | { kind: "QUESTIONNAIRE_STARTING" }
  | { kind: "QUESTIONNAIRE_PENDING" }
  | { kind: "QUESTION"; question: Question; shownAt: number }
  | { kind: "RESPONSE_SUBMITTING"; question: Question; shownAt: number }
  | { kind: "COMPLETED" }
  | { kind: "PROFILE_STARTING" }
  | { kind: "PROFILE_PENDING" }
  | { kind: "PROFILE_READY" }
  | { kind: "SELF_TRANSFER_STARTING" }
  | { kind: "SELF_TRANSFER_PENDING" }
  | {
      kind: "PREVIEW_READY";
      inputUrl: string;
      resultUrl: string;
      dimension: string;
      direction: string;
      stepPpm: number;
      inputLoaded: boolean;
      resultLoaded: boolean;
    }
  | { kind: "SELF_TRANSFER_SAVING" }
  | { kind: "REFERENCE_PROFILE_PENDING" }
  | { kind: "REFERENCE_PROFILE_READY" }
  | { kind: "NO_COMPATIBLE_CASE" }
  | {
      kind: "ERROR";
      phase: Phase | "session";
      code: string;
      answerSubmission?: AnswerSubmission;
      retrySelfTransfer?: true;
    };

const errorMessages: Record<string, string> = {
  DENIED: "Demo 会话不可用或已过期。",
  NOT_FOUND: "当前 Demo 状态不存在。",
  CONFLICT: "当前操作与最新状态冲突，请重试。",
  UNAVAILABLE: "Demo 服务暂时不可用，请稍后重试。",
  UNSUPPORTED: "当前 Demo 不支持该操作。",
  STALE_RESPONSE: "收到过期响应，未显示可能不一致的结果。",
  FAILED: "处理未完成，请重试。",
  REJECTED: "处理被安全规则拒绝。",
  CANCELLED: "处理已取消。",
  POLL_TIMEOUT: "等待时间已到，请重试当前步骤。",
  LOGOUT_UNAVAILABLE: "结束 Demo 尚未完成，请重试清理会话。",
  RECOVERY_REQUIRED: "该预览需要恢复后才能继续，请重新生成安全预览。",
};

const geometryDimensionLabels: Record<string, string> = {
  chin_height: "下巴高度",
  eye_spacing: "眼距",
  jaw_width: "下颌宽度",
};

const geometryDirectionLabels: Record<string, string> = {
  INCREASE: "增加",
  DECREASE: "减少",
};

function currentTimeMs() {
  return new Date().getTime();
}

function describe(state: State) {
  switch (state.kind) {
    case "IDLE":
      return "本演示只使用合成人物与真实 Demo 服务流程。";
    case "SESSION_CREATING":
      return "正在建立 Demo 会话。";
    case "SESSION_ENDING":
      return "正在安全结束 Demo 会话。";
    case "ANALYSIS_STARTING":
      return "正在启动分析。";
    case "ANALYSIS_PENDING":
      return "分析正在进行。";
    case "ANALYSIS_COMPLETED":
      return "分析完成，可以开始偏好问卷。";
    case "QUESTIONNAIRE_STARTING":
      return "正在启动偏好问卷。";
    case "QUESTIONNAIRE_PENDING":
      return "正在准备下一道偏好题。";
    case "QUESTION":
      return "请选择更符合你偏好的方案。";
    case "RESPONSE_SUBMITTING":
      return "正在提交本题选择。";
    case "COMPLETED":
      return "偏好问卷已完成。";
    case "PROFILE_STARTING":
      return "正在生成偏好档案。";
    case "PROFILE_PENDING":
      return "偏好档案正在准备。";
    case "PROFILE_READY":
      return "偏好档案已准备完成。";
    case "SELF_TRANSFER_STARTING":
      return "正在准备档案引导的几何预览。";
    case "SELF_TRANSFER_PENDING":
      return "档案引导的几何编辑正在执行和验证。";
    case "PREVIEW_READY":
      return "请确认编辑前后合成图，再决定是否最终保存。";
    case "SELF_TRANSFER_SAVING":
      return "正在最终保存并建立参考档案。";
    case "REFERENCE_PROFILE_PENDING":
      return "已保存，参考档案待恢复";
    case "REFERENCE_PROFILE_READY":
      return "已保存并更新参考档案";
    case "NO_COMPATIBLE_CASE":
      return "当前档案暂无可用的安全几何步骤";
    case "ERROR":
      return errorMessages[state.code] ?? "请求未完成，请重试。";
  }
}

async function request(path: string, init?: RequestInit) {
  return fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: { ...(init?.headers ?? {}) },
  });
}

function codeFrom(response: Response, body: unknown) {
  const value = body as { code?: unknown; status?: unknown } | null;
  if (typeof value?.code === "string") return value.code;
  if (value?.status === "RECOVERY_REQUIRED") return "RECOVERY_REQUIRED";
  if (
    typeof value?.status === "string" &&
    ["FAILED", "REJECTED", "CANCELLED"].includes(value.status)
  )
    return value.status;
  if (response.status === 403) return "DENIED";
  if (response.status === 404) return "NOT_FOUND";
  if (response.status === 409) return "CONFLICT";
  if (response.status === 501) return "UNSUPPORTED";
  return "UNAVAILABLE";
}

function questionFrom(body: Record<string, unknown> | null): Question | null {
  const token = body?.presentation_token;
  if (body?.status !== "QUESTION" || typeof token !== "string") return null;
  if (!/^[a-f0-9]{64}$/.test(token)) return null;
  const left = `/api/demo/questionnaire/media/${token}/LEFT`;
  const right = `/api/demo/questionnaire/media/${token}/RIGHT`;
  if (body.left_image_url !== left || body.right_image_url !== right)
    return null;
  return {
    presentationToken: token,
    leftImageUrl: left,
    rightImageUrl: right,
  };
}

function completedAnalysis(body: Record<string, unknown> | null) {
  return (
    body?.status === "COMPLETED" &&
    (body.analysis_state === "SUPPORTED" ||
      body.analysis_state === "UNSUPPORTED") &&
    body.self_state === "READY"
  );
}

function completedProfile(body: Record<string, unknown> | null) {
  return body?.status === "PROFILE_READY";
}

function isRecoverableError(code: string) {
  return [
    "UNAVAILABLE",
    "CONFLICT",
    "STALE_RESPONSE",
    "POLL_TIMEOUT",
    "LOGOUT_UNAVAILABLE",
  ].includes(code);
}

export function DemoRealFlowWorkspace() {
  const [state, setState] = useState<State>({ kind: "IDLE" });
  const generation = useRef(0);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollCount = useRef(0);
  const activePhase = useRef<Phase | null>(null);
  const sessionCreation = useRef<Promise<Response> | null>(null);

  function invalidate() {
    generation.current += 1;
    if (pollTimer.current) clearTimeout(pollTimer.current);
    pollTimer.current = null;
    activePhase.current = null;
  }
  useEffect(() => () => invalidate(), []);

  function error(
    phase: Phase | "session",
    code: string,
    token: number,
    answerSubmission?: AnswerSubmission,
    retrySelfTransfer?: true,
  ) {
    if (generation.current === token)
      setState({
        kind: "ERROR",
        phase,
        code,
        answerSubmission,
        retrySelfTransfer,
      });
  }
  function schedulePoll(phase: Phase, token: number) {
    if (generation.current !== token) return;
    if (pollCount.current >= 120) return error(phase, "POLL_TIMEOUT", token);
    pollTimer.current = setTimeout(() => {
      void poll(phase, token);
    }, 1000);
  }
  function advanceToProfile(token: number) {
    if (generation.current !== token) return;
    activePhase.current = null;
    setState({ kind: "PROFILE_STARTING" });
    void startPhase("profile", token);
  }
  async function poll(phase: Phase, token: number) {
    if (generation.current !== token || activePhase.current !== phase) return;
    pollCount.current += 1;
    try {
      const response = await request(`/api/demo/${phase}`);
      const body = (await response.json().catch(() => null)) as Record<
        string,
        unknown
      > | null;
      if (generation.current !== token) return;
      if (!response.ok) return error(phase, codeFrom(response, body), token);
      if (body?.status === "PENDING") return schedulePoll(phase, token);
      if (phase === "analysis" && completedAnalysis(body)) {
        activePhase.current = null;
        setState({ kind: "ANALYSIS_COMPLETED" });
        return;
      }
      const question = phase === "questionnaire" ? questionFrom(body) : null;
      if (question) {
        activePhase.current = null;
        setState({
          kind: "QUESTION",
          question,
          shownAt: currentTimeMs(),
        });
        return;
      }
      if (phase === "questionnaire" && body?.status === "COMPLETED") {
        advanceToProfile(token);
        return;
      }
      if (phase === "profile" && completedProfile(body)) {
        activePhase.current = null;
        setState({ kind: "PROFILE_READY" });
        return;
      }
      error(phase, codeFrom(response, body), token);
    } catch {
      error(phase, "UNAVAILABLE", token);
    }
  }
  async function startPhase(phase: Phase, token: number) {
    activePhase.current = phase;
    pollCount.current = 0;
    try {
      const response = await request(`/api/demo/${phase}`, { method: "POST" });
      const body = (await response.json().catch(() => null)) as Record<
        string,
        unknown
      > | null;
      if (generation.current !== token) return;
      if (!response.ok) return error(phase, codeFrom(response, body), token);
      if (body?.status === "PENDING") {
        setState({
          kind:
            phase === "analysis"
              ? "ANALYSIS_PENDING"
              : phase === "questionnaire"
                ? "QUESTIONNAIRE_PENDING"
                : "PROFILE_PENDING",
        });
        return schedulePoll(phase, token);
      }
      if (phase === "questionnaire" && body?.status === "QUESTION") {
        activePhase.current = null;
        const question = questionFrom(body);
        if (question)
          setState({
            kind: "QUESTION",
            question,
            shownAt: currentTimeMs(),
          });
        else error(phase, "STALE_RESPONSE", token);
        return;
      }
      if (phase === "questionnaire" && body?.status === "COMPLETED") {
        advanceToProfile(token);
        return;
      }
      if (phase === "profile" && completedProfile(body)) {
        activePhase.current = null;
        setState({ kind: "PROFILE_READY" });
        return;
      }
      error(phase, codeFrom(response, body), token);
    } catch {
      error(phase, "UNAVAILABLE", token);
    }
  }
  function selfTransferPreview(body: Record<string, unknown> | null) {
    const token = body?.input_image_url;
    const result = body?.result_image_url;
    if (
      body?.status !== "PREVIEW_READY" ||
      typeof token !== "string" ||
      typeof result !== "string" ||
      !/^\/api\/demo\/self-transfer\/media\/[a-f0-9]{64}\/INPUT$/.test(token) ||
      result !== token.replace(/INPUT$/, "RESULT") ||
      typeof body.dimension_key !== "string" ||
      !["chin_height", "eye_spacing", "jaw_width"].includes(
        body.dimension_key,
      ) ||
      typeof body.direction !== "string" ||
      !["INCREASE", "DECREASE"].includes(body.direction) ||
      (body.step_ppm !== 15000 && body.step_ppm !== 30000)
    )
      return null;
    return {
      inputUrl: token,
      resultUrl: result,
      dimension: body.dimension_key,
      direction: body.direction,
      stepPpm: body.step_ppm,
    };
  }
  async function pollSelfTransfer(token: number) {
    try {
      const response = await request("/api/demo/self-transfer");
      const body = (await response.json().catch(() => null)) as Record<
        string,
        unknown
      > | null;
      if (generation.current !== token) return;
      const preview = selfTransferPreview(body);
      if (preview)
        return setState({
          kind: "PREVIEW_READY",
          ...preview,
          inputLoaded: false,
          resultLoaded: false,
        });
      if (body?.status === "PENDING") return scheduleSelfTransferPoll(token);
      if (body?.status === "REFERENCE_PROFILE_PENDING") {
        setState({ kind: "REFERENCE_PROFILE_PENDING" });
        return scheduleSelfTransferPoll(token);
      }
      if (body?.status === "REFERENCE_PROFILE_READY")
        return setState({ kind: "REFERENCE_PROFILE_READY" });
      if (body?.status === "NO_COMPATIBLE_CASE")
        return setState({ kind: "NO_COMPATIBLE_CASE" });
      return error("profile", codeFrom(response, body), token, undefined, true);
    } catch {
      error("profile", "UNAVAILABLE", token, undefined, true);
    }
  }
  function scheduleSelfTransferPoll(token: number) {
    if (generation.current !== token) return;
    if (pollCount.current >= 120)
      return error("profile", "POLL_TIMEOUT", token);
    pollTimer.current = setTimeout(() => {
      pollCount.current += 1;
      void pollSelfTransfer(token);
    }, 1000);
  }
  async function startSelfTransfer(token: number) {
    pollCount.current = 0;
    try {
      const response = await request("/api/demo/self-transfer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "PROFILE_GUIDED_GEOMETRY_PREVIEW" }),
      });
      const body = (await response.json().catch(() => null)) as Record<
        string,
        unknown
      > | null;
      if (generation.current !== token) return;
      const preview = selfTransferPreview(body);
      if (preview)
        return setState({
          kind: "PREVIEW_READY",
          ...preview,
          inputLoaded: false,
          resultLoaded: false,
        });
      if (body?.status === "PENDING") {
        setState({ kind: "SELF_TRANSFER_PENDING" });
        return scheduleSelfTransferPoll(token);
      }
      if (body?.status === "NO_COMPATIBLE_CASE")
        return setState({ kind: "NO_COMPATIBLE_CASE" });
      error("profile", codeFrom(response, body), token, undefined, true);
    } catch {
      error("profile", "UNAVAILABLE", token, undefined, true);
    }
  }
  async function acceptSelfTransfer(token: number) {
    try {
      const response = await request("/api/demo/self-transfer/accept", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outcome: "FINAL_SAVE_AND_USE_AS_REFERENCE" }),
      });
      const body = (await response.json().catch(() => null)) as Record<
        string,
        unknown
      > | null;
      if (generation.current !== token) return;
      if (body?.status === "REFERENCE_PROFILE_PENDING") {
        setState({ kind: "REFERENCE_PROFILE_PENDING" });
        pollCount.current = 0;
        return scheduleSelfTransferPoll(token);
      }
      if (body?.status === "REFERENCE_PROFILE_READY")
        return setState({ kind: "REFERENCE_PROFILE_READY" });
      error("profile", codeFrom(response, body), token, undefined, true);
    } catch {
      error("profile", "UNAVAILABLE", token, undefined, true);
    }
  }
  async function startDemo() {
    invalidate();
    const token = generation.current;
    setState({ kind: "SESSION_CREATING" });
    const creation = request("/api/demo/session", { method: "POST" });
    sessionCreation.current = creation;
    try {
      const response = await creation;
      if (generation.current !== token) return;
      if (!response.ok)
        return error(
          "session",
          codeFrom(response, await response.json().catch(() => null)),
          token,
        );
      setState({ kind: "ANALYSIS_STARTING" });
      void startPhase("analysis", token);
    } catch {
      error("session", "UNAVAILABLE", token);
    } finally {
      if (sessionCreation.current === creation) sessionCreation.current = null;
    }
  }

  async function submitAnswer(
    submission: AnswerSubmission,
    token: number,
    reconcileConflicts: boolean,
  ) {
    try {
      const response = await request("/api/demo/questionnaire/response", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          presentation_token: submission.question.presentationToken,
          choice: submission.choice,
          response_latency_ms: submission.responseLatencyMs,
        }),
      });
      const body = (await response.json().catch(() => null)) as Record<
        string,
        unknown
      > | null;
      if (generation.current !== token) return;
      if (!response.ok) {
        const code = codeFrom(response, body);
        if (
          reconcileConflicts &&
          (code === "CONFLICT" || code === "STALE_RESPONSE")
        ) {
          activePhase.current = "questionnaire";
          pollCount.current = 0;
          setState({ kind: "QUESTIONNAIRE_PENDING" });
          schedulePoll("questionnaire", token);
          return;
        }
        return error("questionnaire", code, token, submission);
      }
      if (body?.status === "COMPLETED") {
        advanceToProfile(token);
        return;
      }
      const nextQuestion = questionFrom(body);
      if (nextQuestion) {
        setState({
          kind: "QUESTION",
          question: nextQuestion,
          shownAt: currentTimeMs(),
        });
        return;
      }
      if (body?.status === "PENDING") {
        activePhase.current = "questionnaire";
        pollCount.current = 0;
        setState({ kind: "QUESTIONNAIRE_PENDING" });
        schedulePoll("questionnaire", token);
        return;
      }
      error("questionnaire", codeFrom(response, body), token, submission);
    } catch {
      error("questionnaire", "UNAVAILABLE", token, submission);
    }
  }

  function answer(choice: Choice) {
    if (state.kind !== "QUESTION") return;
    const submission: AnswerSubmission = {
      question: state.question,
      shownAt: state.shownAt,
      choice,
      responseLatencyMs: Math.min(
        3_600_000,
        Math.max(0, Math.round(currentTimeMs() - state.shownAt)),
      ),
    };
    const token = ++generation.current;
    setState({
      kind: "RESPONSE_SUBMITTING",
      question: submission.question,
      shownAt: submission.shownAt,
    });
    void submitAnswer(submission, token, false);
  }

  async function endDemo() {
    invalidate();
    const token = generation.current;
    setState({ kind: "SESSION_ENDING" });
    const pendingCreation = sessionCreation.current;
    try {
      if (pendingCreation) await pendingCreation.catch(() => null);
      if (generation.current !== token) return;
      const response = await request("/api/demo/session", { method: "DELETE" });
      if (generation.current !== token) return;
      if (!response.ok) return error("session", "LOGOUT_UNAVAILABLE", token);
      setState({ kind: "IDLE" });
    } catch {
      error("session", "LOGOUT_UNAVAILABLE", token);
    }
  }
  function retry() {
    if (state.kind !== "ERROR" || !isRecoverableError(state.code)) return;
    const token = ++generation.current;
    if (state.phase === "session") {
      if (state.code === "LOGOUT_UNAVAILABLE") void endDemo();
      else void startDemo();
      return;
    }
    if (state.answerSubmission) {
      setState({
        kind: "RESPONSE_SUBMITTING",
        question: state.answerSubmission.question,
        shownAt: state.answerSubmission.shownAt,
      });
      void submitAnswer(state.answerSubmission, token, true);
      return;
    }
    if (state.retrySelfTransfer) {
      setState({ kind: "SELF_TRANSFER_STARTING" });
      void startSelfTransfer(token);
      return;
    }
    setState({
      kind:
        state.phase === "analysis"
          ? "ANALYSIS_STARTING"
          : state.phase === "questionnaire"
            ? "QUESTIONNAIRE_STARTING"
            : state.phase === "profile"
              ? "PROFILE_STARTING"
              : "PROFILE_STARTING",
    });
    void startPhase(state.phase, token);
  }
  const submitting = state.kind === "RESPONSE_SUBMITTING";
  const question =
    state.kind === "QUESTION" || submitting ? state.question : null;
  return (
    <section
      aria-labelledby="demo-real-flow-title"
      className="mt-8 rounded-[2rem] border border-black/10 bg-white/70 p-7 shadow-[0_24px_80px_rgba(109,63,85,0.13)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium tracking-[0.2em] text-plum">
            SYNTHETIC DEMO
          </p>
          <h2 className="mt-2 text-xl font-semibold" id="demo-real-flow-title">
            偏好问卷、档案与编辑演示
          </h2>
        </div>
        <Badge tone={state.kind === "ERROR" ? "warning" : "success"}>
          {state.kind}
        </Badge>
      </div>
      <p
        aria-live="polite"
        className="mt-5 rounded-2xl border border-dashed border-black/20 p-4 text-sm leading-6 text-black/70"
      >
        {describe(state)}
      </p>
      {state.kind === "IDLE" ? (
        <Button className="mt-5" onClick={startDemo} type="button">
          开始 Demo
        </Button>
      ) : null}
      {state.kind === "ANALYSIS_COMPLETED" ? (
        <Button
          className="mt-5"
          onClick={() => {
            const token = ++generation.current;
            setState({ kind: "QUESTIONNAIRE_STARTING" });
            void startPhase("questionnaire", token);
          }}
          type="button"
        >
          开始偏好问卷
        </Button>
      ) : null}
      {state.kind === "PROFILE_READY" ? (
        <div className="mt-5 rounded-2xl border border-black/10 p-4">
          <Button
            onClick={() => {
              const token = ++generation.current;
              setState({ kind: "SELF_TRANSFER_STARTING" });
              void startSelfTransfer(token);
            }}
            type="button"
          >
            生成档案引导的几何预览
          </Button>
        </div>
      ) : null}
      {state.kind === "PREVIEW_READY" ? (
        <div className="mt-6">
          <p className="text-sm">
            {geometryDimensionLabels[state.dimension]} ·{" "}
            {geometryDirectionLabels[state.direction]} ·{" "}
            {state.stepPpm === 15000 ? "1.5%" : "3%"}
          </p>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <figure>
              <img
                alt="编辑前合成图"
                className="aspect-square w-full rounded-2xl object-cover"
                onLoad={() =>
                  setState((current) =>
                    current.kind === "PREVIEW_READY" &&
                    current.inputUrl === state.inputUrl
                      ? { ...current, inputLoaded: true }
                      : current,
                  )
                }
                onError={() =>
                  setState((current) =>
                    current.kind === "PREVIEW_READY" &&
                    current.inputUrl === state.inputUrl
                      ? { ...current, inputLoaded: false }
                      : current,
                  )
                }
                src={state.inputUrl}
              />
              <figcaption className="mt-2 text-center text-sm">
                编辑前合成图
              </figcaption>
            </figure>
            <figure>
              <img
                alt="编辑后合成图"
                className="aspect-square w-full rounded-2xl object-cover"
                onLoad={() =>
                  setState((current) =>
                    current.kind === "PREVIEW_READY" &&
                    current.resultUrl === state.resultUrl
                      ? { ...current, resultLoaded: true }
                      : current,
                  )
                }
                onError={() =>
                  setState((current) =>
                    current.kind === "PREVIEW_READY" &&
                    current.resultUrl === state.resultUrl
                      ? { ...current, resultLoaded: false }
                      : current,
                  )
                }
                src={state.resultUrl}
              />
              <figcaption className="mt-2 text-center text-sm">
                编辑后合成图
              </figcaption>
            </figure>
          </div>
          <Button
            className="mt-5"
            disabled={!state.inputLoaded || !state.resultLoaded}
            onClick={() => {
              const token = ++generation.current;
              setState({ kind: "SELF_TRANSFER_SAVING" });
              void acceptSelfTransfer(token);
            }}
            type="button"
          >
            最终保存并用作参考
          </Button>
        </div>
      ) : null}
      {state.kind === "ERROR" && isRecoverableError(state.code) ? (
        <Button className="mt-5" onClick={retry} type="button">
          重试当前步骤
        </Button>
      ) : null}
      {question ? (
        <div className="mt-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <figure>
              <img
                alt="左侧方案"
                className="aspect-square w-full rounded-2xl object-cover"
                src={question.leftImageUrl}
              />
              <figcaption className="mt-2 text-center text-sm">
                左侧方案
              </figcaption>
            </figure>
            <figure>
              <img
                alt="右侧方案"
                className="aspect-square w-full rounded-2xl object-cover"
                src={question.rightImageUrl}
              />
              <figcaption className="mt-2 text-center text-sm">
                右侧方案
              </figcaption>
            </figure>
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            {(
              [
                ["LEFT", "更偏好左侧"],
                ["RIGHT", "更偏好右侧"],
                ["INDISTINGUISHABLE", "难以区分"],
                ["SKIP", "跳过此题"],
              ] as const
            ).map(([choice, label]) => (
              <Button
                disabled={submitting}
                key={choice}
                onClick={() => answer(choice)}
                type="button"
                variant={choice === "SKIP" ? "secondary" : undefined}
              >
                {label}
              </Button>
            ))}
          </div>
        </div>
      ) : null}
      {state.kind !== "IDLE" && state.kind !== "SESSION_ENDING" ? (
        <Button
          className="mt-6"
          onClick={endDemo}
          type="button"
          variant="secondary"
        >
          结束 Demo
        </Button>
      ) : null}
    </section>
  );
}
