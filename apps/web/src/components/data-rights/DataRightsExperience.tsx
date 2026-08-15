"use client";

import { Button } from "@mirror/ui";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import type {
  AccountDeletionResponse,
  AssetDeletionResponse,
  AssetResponse,
  DataExportResponse,
} from "../../lib/auth/api";
import { useBrowserAuth } from "../../lib/auth";

const ACCOUNT_DELETION_PHRASE = "删除我的账号";
const POLL_INTERVAL_MS = 250;
const ACCOUNT_DELETION_POLL_WINDOW_MS = 4 * 60 * 1000;

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  anchor.click();
  URL.revokeObjectURL(url);
}

function friendlyError(): string {
  return "请求未完成，请稍后重试。";
}

export function DataRightsExperience({
  onAccountDeletionStarted,
}: Readonly<{
  onAccountDeletionStarted: (request: AccountDeletionResponse) => void;
}>) {
  const { session } = useBrowserAuth();
  const [assets, setAssets] = useState<AssetResponse[] | null>(null);
  const [assetDetail, setAssetDetail] = useState<AssetResponse | null>(null);
  const [assetError, setAssetError] = useState<string | null>(null);
  const [assetBusy, setAssetBusy] = useState<string | null>(null);
  const [assetDeletion, setAssetDeletion] =
    useState<AssetDeletionResponse | null>(null);
  const [dataExport, setDataExport] = useState<DataExportResponse | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportBusy, setExportBusy] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [deletionBusy, setDeletionBusy] = useState(false);
  const [deletionError, setDeletionError] = useState<string | null>(null);
  const mounted = useRef(true);

  async function loadAssets(): Promise<void> {
    setAssetError(null);
    try {
      const response = await session.listAssets();
      if (mounted.current) setAssets(response.assets);
    } catch {
      if (mounted.current) setAssetError(friendlyError());
    }
  }

  useEffect(() => {
    mounted.current = true;
    let cancelled = false;
    void session
      .listAssets()
      .then((response) => {
        if (!cancelled) setAssets(response.assets);
      })
      .catch(() => {
        if (!cancelled) setAssetError(friendlyError());
      });
    return () => {
      cancelled = true;
      mounted.current = false;
    };
  }, [session]);

  useEffect(() => {
    if (
      dataExport === null ||
      !["requested", "processing"].includes(dataExport.status)
    ) {
      return;
    }
    const timer = window.setTimeout(() => {
      void session
        .getDataExport(dataExport.export_id)
        .then((next) => {
          if (mounted.current) setDataExport(next);
        })
        .catch(() => {
          if (mounted.current) setExportError(friendlyError());
        });
    }, POLL_INTERVAL_MS);
    return () => window.clearTimeout(timer);
  }, [dataExport, session]);

  async function showAsset(assetId: string): Promise<void> {
    setAssetBusy(`detail:${assetId}`);
    setAssetError(null);
    try {
      setAssetDetail(await session.getAsset(assetId));
    } catch {
      setAssetError(friendlyError());
    } finally {
      setAssetBusy(null);
    }
  }

  async function downloadAsset(assetId: string): Promise<void> {
    setAssetBusy(`download:${assetId}`);
    setAssetError(null);
    try {
      const blob = await session.downloadAsset(
        assetId,
        `asset-download:${assetId}`,
      );
      saveBlob(blob, `mirror-asset-${assetId}.jpg`);
    } catch {
      setAssetError(friendlyError());
    } finally {
      setAssetBusy(null);
    }
  }

  async function deleteAsset(assetId: string): Promise<void> {
    setAssetBusy(`delete:${assetId}`);
    setAssetError(null);
    try {
      const result = await session.deleteAsset(
        assetId,
        `asset-delete:${assetId}`,
      );
      setAssetDeletion(result);
      setAssetDetail(null);
      await loadAssets();
    } catch {
      setAssetError(friendlyError());
    } finally {
      setAssetBusy(null);
    }
  }

  async function requestExport(): Promise<void> {
    setExportBusy(true);
    setExportError(null);
    try {
      setDataExport(await session.createDataExport("data-export:create"));
    } catch {
      setExportError(friendlyError());
    } finally {
      setExportBusy(false);
    }
  }

  async function downloadExport(): Promise<void> {
    if (dataExport?.status !== "ready") return;
    setExportBusy(true);
    setExportError(null);
    try {
      const blob = await session.downloadDataExport(
        dataExport.export_id,
        `data-export-download:${dataExport.export_id}`,
      );
      saveBlob(blob, "project-mirror-data-export.zip");
    } catch {
      setExportError(friendlyError());
    } finally {
      setExportBusy(false);
    }
  }

  async function requestAccountDeletion(): Promise<void> {
    if (confirmation !== ACCOUNT_DELETION_PHRASE) return;
    setDeletionBusy(true);
    setDeletionError(null);
    try {
      const request = await session.createAccountDeletion(
        "account-deletion:create",
      );
      onAccountDeletionStarted(request);
    } catch {
      setDeletionError(friendlyError());
      setDeletionBusy(false);
    }
  }

  return (
    <div className="mt-8 space-y-6">
      <section
        aria-labelledby="assets-title"
        className="rounded-2xl border border-black/10 bg-white/70 p-5"
      >
        <h2 id="assets-title" className="text-xl font-semibold text-ink">
          我的图片资产
        </h2>
        <p className="mt-2 text-sm leading-6 text-black/60">
          这里只列出已经安全摄入且仍可访问的私有资产。
        </p>
        {assetError !== null && (
          <p role="alert" className="mt-3 text-sm text-rose">
            {assetError}
          </p>
        )}
        {assets === null ? (
          <p role="status" className="mt-4 text-sm">
            正在读取资产…
          </p>
        ) : assets.length === 0 ? (
          <p className="mt-4 text-sm text-black/55">暂无可访问资产。</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {assets.map((asset) => (
              <li
                key={asset.asset_id}
                className="rounded-xl border border-black/10 p-4"
              >
                <p className="font-medium">
                  {asset.width} × {asset.height} ·{" "}
                  {(asset.byte_size / 1024).toFixed(1)} KB
                </p>
                <p className="mt-1 text-xs text-black/50">
                  {asset.asset_role} ·{" "}
                  {new Date(asset.created_at).toLocaleString("zh-CN")}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={assetBusy !== null}
                    onClick={() => void showAsset(asset.asset_id)}
                  >
                    查看详情
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={assetBusy !== null}
                    onClick={() => void downloadAsset(asset.asset_id)}
                  >
                    下载
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={assetBusy !== null}
                    onClick={() => void deleteAsset(asset.asset_id)}
                  >
                    删除
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
        {assetDetail !== null && (
          <dl
            aria-label="资产详情"
            className="mt-4 grid grid-cols-2 gap-2 rounded-xl bg-black/5 p-4 text-sm"
          >
            <dt>类型</dt>
            <dd>{assetDetail.mime_type}</dd>
            <dt>尺寸</dt>
            <dd>
              {assetDetail.width} × {assetDetail.height}
            </dd>
            <dt>角色</dt>
            <dd>{assetDetail.asset_role}</dd>
          </dl>
        )}
        {assetDeletion !== null && (
          <p role="status" className="mt-4 text-sm">
            删除请求状态：
            {assetDeletion.status === "completed"
              ? "已完成"
              : assetDeletion.status === "failed"
                ? "失败"
                : "处理中"}
          </p>
        )}
        {assetError !== null && (
          <Button
            type="button"
            variant="secondary"
            className="mt-3"
            onClick={() => void loadAssets()}
          >
            重试读取资产
          </Button>
        )}
      </section>

      <section
        aria-labelledby="export-title"
        className="rounded-2xl border border-black/10 bg-white/70 p-5"
      >
        <h2 id="export-title" className="text-xl font-semibold text-ink">
          导出我的数据
        </h2>
        <p className="mt-2 text-sm leading-6 text-black/60">
          导出文件为短期私有 ZIP；准备完成前不会显示为可下载。
        </p>
        {exportError !== null && (
          <p role="alert" className="mt-3 text-sm text-rose">
            {exportError}
          </p>
        )}
        {dataExport === null ? (
          <Button
            type="button"
            className="mt-4"
            disabled={exportBusy}
            onClick={() => void requestExport()}
          >
            {exportBusy ? "正在提交…" : "申请数据导出"}
          </Button>
        ) : (
          <div className="mt-4">
            <p role="status" className="text-sm">
              导出状态：
              {dataExport.status === "ready"
                ? "可下载"
                : dataExport.status === "failed"
                  ? "失败"
                  : dataExport.status === "expired"
                    ? "已过期"
                    : "准备中"}
            </p>
            {dataExport.status === "ready" && (
              <Button
                type="button"
                className="mt-3"
                disabled={exportBusy}
                onClick={() => void downloadExport()}
              >
                {exportBusy ? "正在下载…" : "下载数据导出"}
              </Button>
            )}
            {(dataExport.status === "failed" || exportError !== null) && (
              <Button
                type="button"
                variant="secondary"
                className="mt-3"
                onClick={() => void requestExport()}
              >
                重新申请
              </Button>
            )}
          </div>
        )}
      </section>

      <section
        aria-labelledby="delete-account-title"
        className="rounded-2xl border border-rose/30 bg-rose/5 p-5"
      >
        <h2
          id="delete-account-title"
          className="text-xl font-semibold text-ink"
        >
          删除账号
        </h2>
        <p className="mt-2 text-sm leading-6 text-black/65">
          提交后会立即冻结账号并撤销会话，后台继续删除资产和导出。物理删除完成后无法恢复。
        </p>
        <label
          htmlFor="account-deletion-confirmation"
          className="mt-4 block text-sm font-medium"
        >
          输入“{ACCOUNT_DELETION_PHRASE}”确认
        </label>
        <input
          id="account-deletion-confirmation"
          value={confirmation}
          onChange={(event) => setConfirmation(event.target.value)}
          autoComplete="off"
          className="mt-2 w-full rounded-xl border border-black/15 bg-white px-4 py-3"
        />
        {deletionError !== null && (
          <p role="alert" className="mt-3 text-sm text-rose">
            {deletionError}
          </p>
        )}
        <Button
          type="button"
          variant="secondary"
          className="mt-4"
          disabled={deletionBusy || confirmation !== ACCOUNT_DELETION_PHRASE}
          onClick={() => void requestAccountDeletion()}
        >
          {deletionBusy ? "正在提交…" : "永久删除账号"}
        </Button>
      </section>
    </div>
  );
}

export function AccountDeletionStatus({
  initialRequest,
}: Readonly<{ initialRequest: AccountDeletionResponse }>) {
  const router = useRouter();
  const { session } = useBrowserAuth();
  const [request, setRequest] = useState(initialRequest);
  const [error, setError] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const pollingStartedAt = useRef<number | null>(null);

  useEffect(() => {
    if (pollingStartedAt.current === null) {
      pollingStartedAt.current = Date.now();
    }
    if (request.status === "completed") {
      session.clearAfterAccountDeletion();
      router.replace("/join");
      return;
    }
    if (request.status === "failed") return;
    if (
      Date.now() - pollingStartedAt.current >=
      ACCOUNT_DELETION_POLL_WINDOW_MS
    ) {
      session.clearAfterAccountDeletion();
      router.replace("/join");
      return;
    }
    const timer = window.setTimeout(() => {
      void session
        .getCurrentAccountDeletion()
        .then((next) => {
          setError(null);
          setRequest(next);
        })
        .catch(() => {
          setError(friendlyError());
          setRetryTick((current) => current + 1);
        });
    }, POLL_INTERVAL_MS);
    return () => window.clearTimeout(timer);
  }, [request, retryTick, router, session]);

  return (
    <section
      aria-labelledby="deletion-status-title"
      className="w-full max-w-xl rounded-2xl border border-rose/30 bg-white/75 p-6"
    >
      <h1
        id="deletion-status-title"
        className="text-2xl font-semibold text-ink"
      >
        账号删除处理中
      </h1>
      <p role="status" className="mt-3 text-sm leading-6 text-black/65">
        当前状态：
        {request.status === "completed"
          ? "已完成"
          : request.status === "failed"
            ? "失败，需要人工支持"
            : "正在安全删除数据"}
      </p>
      <p className="mt-2 text-sm text-black/55">
        账号内容和其他操作已立即隐藏，会话不会被恢复。
      </p>
      {error !== null && (
        <p role="alert" className="mt-3 text-sm text-rose">
          {error} 状态检查会继续重试。
        </p>
      )}
    </section>
  );
}
