"use client";

import { useState } from "react";

import { Badge, Button } from "@mirror/ui";

import {
  abbreviateDemoAuthority,
  demoVersionHistoryFixture,
  type DemoPublishedImageVersion,
  type DemoVersionHistoryEntry,
} from "../../lib/demo-version-history";

type FixtureView = "READY" | "LOADING" | "EMPTY" | "UNAVAILABLE";
type ActionState =
  | "IDLE"
  | "RESTORE_PENDING"
  | "RESTORED"
  | "ROLLBACK_PENDING"
  | "ROLLED_BACK"
  | "CANCELLED"
  | "FAILED"
  | "UNSUPPORTED"
  | "NOT_PUBLISHED"
  | "NO_PARENT";

const currentVersion: DemoPublishedImageVersion = demoVersionHistoryFixture[0];
const parentVersion: DemoPublishedImageVersion = demoVersionHistoryFixture[1];

function isPublishedVersion(
  entry: DemoVersionHistoryEntry,
): entry is DemoPublishedImageVersion {
  return entry.kind === "IMAGE_VERSION";
}

function blockedAction(entry: DemoVersionHistoryEntry): ActionState {
  if (!isPublishedVersion(entry)) {
    return entry.execution === "NOT_SUPPORTED"
      ? "UNSUPPORTED"
      : "NOT_PUBLISHED";
  }
  return entry.parentId === null ? "NO_PARENT" : "IDLE";
}

function actionDescription(state: ActionState): string {
  const messages: Record<ActionState, string> = {
    IDLE: "选择一个可验证版本以检查恢复或回滚的 UI 状态。",
    RESTORE_PENDING:
      "合成 fixture：恢复请求待确认，尚未写入任何真实 ImageVersion。",
    RESTORED: "合成 fixture：恢复已显示为完成；不代表真实资产或执行已发生。",
    ROLLBACK_PENDING: "合成 fixture：将当前版本回滚到直接父版本，等待确认。",
    ROLLED_BACK: "合成 fixture：回滚已显示为完成；不代表真实执行已发生。",
    CANCELLED: "合成 fixture：操作已取消，未声明成功。",
    FAILED: "合成 fixture：操作失败，未声明成功。",
    UNSUPPORTED: "当前 fixture 版本没有获批执行能力，操作不受支持。",
    NOT_PUBLISHED: "所选条目是未发布的 execution event，不能恢复或回滚。",
    NO_PARENT: "所选已发布 ImageVersion 没有父版本，不能回滚。",
  };
  return messages[state];
}

function statusTone(status: string): "success" | "warning" {
  return status === "PASS" || status === "CURRENT" || status === "COMPLETED"
    ? "success"
    : "warning";
}

export function DemoVersionHistoryWorkspace() {
  const [divider, setDivider] = useState(50);
  const [view, setView] = useState<FixtureView>("READY");
  const [selectedId, setSelectedId] = useState<string>(currentVersion.entryId);
  const [action, setAction] = useState<ActionState>("IDLE");
  const selected =
    demoVersionHistoryFixture.find((entry) => entry.entryId === selectedId) ??
    currentVersion;
  const selectedPublished = isPublishedVersion(selected) ? selected : null;
  const canRestore = selectedPublished !== null;
  const canRollback =
    selectedPublished !== null && selectedPublished.parentId !== null;

  function beginRestore() {
    setAction(canRestore ? "RESTORE_PENDING" : blockedAction(selected));
  }

  function beginRollback() {
    setAction(canRollback ? "ROLLBACK_PENDING" : blockedAction(selected));
  }

  return (
    <section
      aria-labelledby="demo-version-history-title"
      className="mt-8 rounded-[2rem] border border-black/10 bg-white/70 p-5 shadow-[0_24px_80px_rgba(109,63,85,0.13)] sm:p-7"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium tracking-[0.2em] text-plum">
            D11 IMAGEVERSION HISTORY
          </p>
          <h2
            className="mt-2 text-xl font-semibold"
            id="demo-version-history-title"
          >
            Before / After 与版本历史
          </h2>
          <p className="mt-2 text-sm leading-6 text-black/65">
            UI_CONTRACT_ONLY · SYNTHETIC_DEMO · REAL_ASSET_RUNTIME_PENDING ·
            PRODUCTION_RELEASE_NOT_AUTHORIZED
          </p>
        </div>
        <Badge tone="warning">{view}</Badge>
      </div>

      <p className="mt-5 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        合成演示只验证呈现和状态机：不读取、上传或发布真实资产，不是 D02/D07/D12
        的运行时证据。
      </p>

      <div
        className="mt-6 flex flex-wrap gap-2"
        aria-label="Fixture display state"
      >
        {(["READY", "LOADING", "EMPTY", "UNAVAILABLE"] as const).map(
          (state) => (
            <button
              className="rounded-full border border-black/15 px-3 py-1 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-plum"
              key={state}
              onClick={() => setView(state)}
              type="button"
            >
              {state}
            </button>
          ),
        )}
      </div>

      {view === "READY" ? (
        <>
          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)]">
            <article className="rounded-2xl border border-black/10 bg-white p-4 sm:p-5">
              <div className="flex items-center justify-between gap-3 text-sm">
                <span>Before: {parentVersion.label}</span>
                <span>After: {currentVersion.label}</span>
              </div>
              <div
                className="relative mt-4 aspect-[16/10] overflow-hidden rounded-xl border border-black/10 bg-slate-100"
                aria-label="Before and after comparison preview"
              >
                <div className="absolute inset-0 bg-[linear-gradient(135deg,#d5c4d2_0%,#f4e8dd_50%,#b88677_100%)]" />
                <div
                  className="absolute inset-y-0 left-0 bg-[linear-gradient(135deg,#b2a2b9_0%,#d5e1da_55%,#79949e_100%)]"
                  style={{ width: `${divider}%` }}
                />
                <div
                  className="absolute inset-y-0 w-0.5 bg-white shadow-[0_0_0_2px_rgba(0,0,0,0.12)] motion-reduce:transition-none"
                  style={{ left: `${divider}%` }}
                />
                <span className="absolute left-3 top-3 rounded bg-black/65 px-2 py-1 text-xs text-white">
                  Before · synthetic preview
                </span>
                <span className="absolute bottom-3 right-3 rounded bg-black/65 px-2 py-1 text-xs text-white">
                  After · synthetic preview
                </span>
              </div>
              <label
                className="mt-4 grid gap-2 text-sm font-medium"
                htmlFor="version-comparison-slider"
              >
                对比滑杆：{divider}%
                <input
                  aria-valuetext={`当前对比位置 ${divider}%`}
                  className="accent-plum focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-plum"
                  id="version-comparison-slider"
                  max="100"
                  min="0"
                  onChange={(event) => setDivider(Number(event.target.value))}
                  type="range"
                  value={divider}
                />
              </label>
            </article>

            <article className="rounded-2xl border border-black/10 bg-white p-5">
              <h3 className="font-semibold">当前与已选条目</h3>
              <dl className="mt-4 grid gap-3 text-sm">
                <Detail
                  label="current ImageVersion"
                  value={currentVersion.id}
                />
                <Detail
                  label="selected entry"
                  value={`${selected.entryId} · ${selected.kind}`}
                />
                <Detail
                  label="selected published ImageVersion"
                  value={selectedPublished?.id ?? "none (not published)"}
                />
                <Detail
                  label="selected parent"
                  value={selectedPublished?.parentId ?? "none"}
                />
                <Detail label="operation summary" value={selected.operation} />
                <Detail label="verifier" value={selected.verifier} />
                <Detail label="execution" value={selected.execution} />
                <Detail
                  label="display digest"
                  value={abbreviateDemoAuthority(selected.digest)}
                />
                <Detail
                  label="display lineage"
                  value={
                    selectedPublished
                      ? abbreviateDemoAuthority(selectedPublished.lineage)
                      : "none (not published)"
                  }
                />
              </dl>
              <p className="mt-4 text-xs leading-5 text-black/55">
                digest / lineage 仅为脱敏截断 fixture 展示，不是凭据、签名 URL
                或真实 authority。
              </p>
            </article>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(20rem,0.8fr)]">
            <article className="rounded-2xl border border-black/10 bg-white p-5">
              <h3 className="font-semibold">版本时间线</h3>
              <ol className="mt-4 space-y-3" aria-label="ImageVersion timeline">
                {demoVersionHistoryFixture.map((entry) => (
                  <li key={entry.entryId}>
                    <button
                      aria-pressed={selected.entryId === entry.entryId}
                      className="flex w-full items-center justify-between gap-3 rounded-xl border border-black/10 p-3 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-plum"
                      onClick={() => {
                        setSelectedId(entry.entryId);
                        setAction(blockedAction(entry));
                      }}
                      type="button"
                    >
                      <span>
                        <span className="block font-medium">{entry.label}</span>
                        <span className="mt-1 block text-xs text-black/55">
                          {entry.kind} · {entry.operation}
                        </span>
                      </span>
                      <Badge tone={statusTone(entry.verifier)}>
                        {entry.verifier}
                      </Badge>
                    </button>
                  </li>
                ))}
              </ol>
            </article>
            <article className="rounded-2xl border border-dashed border-plum/35 bg-plum/5 p-5">
              <h3 className="font-semibold">
                Restore / Rollback fixture state
              </h3>
              <p
                aria-live="polite"
                className="mt-3 text-sm leading-6 text-black/70"
              >
                {actionDescription(action)}
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <Button
                  disabled={!canRestore}
                  onClick={beginRestore}
                  type="button"
                >
                  恢复到所选版本
                </Button>
                <Button
                  disabled={!canRollback}
                  onClick={beginRollback}
                  type="button"
                  variant="secondary"
                >
                  回滚到父版本
                </Button>
              </div>
              {action === "RESTORE_PENDING" || action === "ROLLBACK_PENDING" ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    className="rounded-lg border border-black/15 px-3 py-2 text-sm"
                    onClick={() =>
                      setAction(
                        action === "RESTORE_PENDING"
                          ? "RESTORED"
                          : "ROLLED_BACK",
                      )
                    }
                    type="button"
                  >
                    确认完成
                  </button>
                  <button
                    className="rounded-lg border border-black/15 px-3 py-2 text-sm"
                    onClick={() => setAction("CANCELLED")}
                    type="button"
                  >
                    取消
                  </button>
                  <button
                    className="rounded-lg border border-black/15 px-3 py-2 text-sm"
                    onClick={() => setAction("FAILED")}
                    type="button"
                  >
                    标记失败
                  </button>
                </div>
              ) : null}
            </article>
          </div>
        </>
      ) : (
        <p
          aria-live="polite"
          className="mt-6 rounded-2xl border border-dashed border-black/20 p-5 text-sm text-black/70"
        >
          {view === "LOADING"
            ? "正在加载合成版本呈现状态。"
            : view === "EMPTY"
              ? "当前合成 fixture 没有可显示的 ImageVersion。"
              : "版本历史当前不可用；没有以缓存或真实资产替代。"}
        </p>
      )}
    </section>
  );
}

function Detail({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div className="grid gap-1 border-b border-black/10 pb-2 last:border-0">
      <dt className="text-black/55">{label}</dt>
      <dd className="break-all font-mono text-xs text-black/80">{value}</dd>
    </div>
  );
}
