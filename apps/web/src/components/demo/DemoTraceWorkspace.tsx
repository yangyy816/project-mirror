"use client";

import { useState } from "react";

import { Badge, Button } from "@mirror/ui";

type RecallReady = Readonly<{
  status: "READY";
  recall_at: string;
  session_id: string;
  context: Readonly<{
    profile_id: string;
    compilation_digest: string;
    expires_at: string;
  }>;
  trace: Readonly<{
    context_compilation_id: string;
    evidence_digest: string;
  }>;
}>;

type WorkspaceState =
  | Readonly<{ kind: "IDLE" }>
  | Readonly<{ kind: "LOADING" }>
  | Readonly<{ kind: "READY"; data: RecallReady }>
  | Readonly<{ kind: "EMPTY" }>
  | Readonly<{ kind: "UNAVAILABLE" }>
  | Readonly<{ kind: "DENIED" }>
  | Readonly<{ kind: "CONFLICT" }>
  | Readonly<{ kind: "UNSUPPORTED" }>
  | Readonly<{ kind: "STALE_RESPONSE" }>
  | Readonly<{ kind: "INVALID_RECALL_AT" }>;

const defaultRecallAt = "2099-01-01T00:00:00.000Z";

function stateDescription(state: WorkspaceState): string {
  switch (state.kind) {
    case "IDLE":
      return "选择显式回放时间后，建立仅服务端持有凭据的 Demo 会话。";
    case "LOADING":
      return "正在执行可重试的只读回放。";
    case "EMPTY":
      return "当前回放时间没有可显示的 Context 或 Trace。";
    case "UNAVAILABLE":
      return "Demo API 当前不可用；没有使用缓存或 fixture 替代真实响应。";
    case "DENIED":
      return "Demo 会话已过期、未初始化或被拒绝。请重新建立会话。";
    case "CONFLICT":
      return "当前回放与权威状态发生冲突；没有显示不一致的数据。";
    case "UNSUPPORTED":
      return "当前 Demo API 不支持该只读投影。";
    case "STALE_RESPONSE":
      return "Context 与 Trace 的权威 digest 不一致，页面已拒绝显示可能过期的组合。";
    case "INVALID_RECALL_AT":
      return "回放时间必须是带时区的 ISO-8601 时间。";
    case "READY":
      return "只读回放完成。";
  }
}

async function bridgeRequest(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  return fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: { ...(init?.headers ?? {}) },
  });
}

export function DemoTraceWorkspace() {
  const [recallAt, setRecallAt] = useState(defaultRecallAt);
  const [state, setState] = useState<WorkspaceState>({ kind: "IDLE" });

  async function replay() {
    setState({ kind: "LOADING" });
    try {
      const session = await bridgeRequest("/api/demo/session", {
        method: "POST",
      });
      if (!session.ok) {
        setState({ kind: session.status === 403 ? "DENIED" : "UNAVAILABLE" });
        return;
      }
      const response = await bridgeRequest(
        `/api/demo/recall?recall_at=${encodeURIComponent(recallAt)}`,
      );
      if (response.ok) {
        const data = (await response.json()) as RecallReady;
        setState({ kind: "READY", data });
        return;
      }
      const body = (await response.json().catch(() => null)) as Readonly<{
        code?: string;
      }> | null;
      if (body?.code === "STALE_RESPONSE") setState({ kind: "STALE_RESPONSE" });
      else if (body?.code === "INVALID_RECALL_AT")
        setState({ kind: "INVALID_RECALL_AT" });
      else if (body?.code === "CONFLICT") setState({ kind: "CONFLICT" });
      else if (body?.code === "UNSUPPORTED") setState({ kind: "UNSUPPORTED" });
      else if (response.status === 403) setState({ kind: "DENIED" });
      else if (response.status === 404) setState({ kind: "EMPTY" });
      else setState({ kind: "UNAVAILABLE" });
    } catch {
      setState({ kind: "UNAVAILABLE" });
    }
  }

  async function logout() {
    try {
      const response = await bridgeRequest("/api/demo/session", {
        method: "DELETE",
      });
      if (response.ok) setState({ kind: "IDLE" });
      else if (response.status === 403) setState({ kind: "DENIED" });
      else setState({ kind: "UNAVAILABLE" });
    } catch {
      setState({ kind: "UNAVAILABLE" });
    }
  }

  const ready = state.kind === "READY" ? state.data : null;
  return (
    <section
      aria-labelledby="demo-trace-workspace-title"
      className="mt-8 rounded-[2rem] border border-black/10 bg-white/70 p-7 shadow-[0_24px_80px_rgba(109,63,85,0.13)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium tracking-[0.2em] text-plum">
            D11 TRACE WORKSPACE
          </p>
          <h2
            className="mt-2 text-xl font-semibold"
            id="demo-trace-workspace-title"
          >
            Context 与 Trace 回放
          </h2>
          <p className="mt-2 text-sm leading-6 text-black/65">
            UI_CONTRACT_ONLY · SYNTHETIC_DEMO · RUNTIME_EVIDENCE_DEFERRED
          </p>
        </div>
        <Badge tone="warning">{state.kind}</Badge>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-[1fr_auto_auto] md:items-end">
        <label
          className="grid gap-2 text-sm font-medium"
          htmlFor="demo-recall-at"
        >
          回放时间（显式、带时区）
          <input
            className="rounded-xl border border-black/15 bg-white px-3 py-2 font-mono text-sm"
            id="demo-recall-at"
            onChange={(event) => setRecallAt(event.target.value)}
            value={recallAt}
          />
        </label>
        <Button
          disabled={state.kind === "LOADING"}
          onClick={replay}
          type="button"
        >
          读取 Context 与 Trace
        </Button>
        <Button onClick={logout} type="button" variant="secondary">
          结束 Demo 会话
        </Button>
      </div>

      <p
        aria-live="polite"
        className="mt-5 rounded-2xl border border-dashed border-black/20 p-4 text-sm leading-6 text-black/70"
      >
        {stateDescription(state)}
      </p>

      {ready ? (
        <div className="mt-6 grid gap-5 lg:grid-cols-2">
          <article className="rounded-2xl border border-black/10 bg-white p-5">
            <h3 className="font-semibold">真实 Context projection</h3>
            <dl className="mt-4 grid gap-3 text-sm">
              <TraceRow label="session id" value={ready.session_id} />
              <TraceRow label="recall_at" value={ready.recall_at} />
              <TraceRow label="profile id" value={ready.context.profile_id} />
              <TraceRow
                label="compilation digest"
                value={ready.context.compilation_digest}
              />
              <TraceRow
                label="generation / watermark"
                value="UNAVAILABLE_IN_CURRENT_CONTRACT"
              />
              <TraceRow label="expires_at" value={ready.context.expires_at} />
            </dl>
          </article>
          <article className="rounded-2xl border border-black/10 bg-white p-5">
            <h3 className="font-semibold">真实 Trace projection</h3>
            <dl className="mt-4 grid gap-3 text-sm">
              <TraceRow
                label="context compilation id"
                value={ready.trace.context_compilation_id}
              />
              <TraceRow
                label="evidence digest"
                value={ready.trace.evidence_digest}
              />
              <TraceRow label="replay" value="DETERMINISTIC_READ_ONLY" />
            </dl>
          </article>
        </div>
      ) : null}

      <article className="mt-6 rounded-2xl border border-dashed border-plum/35 bg-plum/5 p-5">
        <h3 className="font-semibold">Synthetic fixture view model</h3>
        <p className="mt-2 text-sm leading-6 text-black/65">
          以下不是实时 API 结果：它只验证将来 event list、source、precedence 与
          watermark 的可访问 UI 结构。
        </p>
        <ul className="mt-4 space-y-2 text-sm">
          <li>
            PreferenceEvent · source: SYNTHETIC_DEMO · precedence:
            UI_CONTRACT_ONLY
          </li>
          <li>AcceptedVisualEpisode · watermark: RUNTIME_EVIDENCE_DEFERRED</li>
        </ul>
      </article>
    </section>
  );
}

function TraceRow({
  label,
  value,
}: Readonly<{ label: string; value: string }>) {
  return (
    <div className="grid gap-1 border-b border-black/10 pb-3 last:border-0">
      <dt className="text-black/55">{label}</dt>
      <dd className="break-all font-mono text-xs text-black/80">{value}</dd>
    </div>
  );
}
