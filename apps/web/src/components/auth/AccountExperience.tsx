"use client";

import { Button } from "@mirror/ui";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { useBrowserAuth } from "../../lib/auth";
import type { AccountDeletionResponse } from "../../lib/auth/api";
import {
  AccountDeletionStatus,
  DataRightsExperience,
} from "../data-rights/DataRightsExperience";

import { SessionLoading, SessionRecovery } from "./SessionStatus";

export function AccountExperience() {
  const router = useRouter();
  const { session, snapshot } = useBrowserAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutFailed, setLogoutFailed] = useState(false);
  const [accountDeletion, setAccountDeletion] =
    useState<AccountDeletionResponse | null>(null);
  const logoutLock = useRef(false);

  useEffect(() => {
    if (snapshot.status === "anonymous" || snapshot.status === "pending") {
      router.replace("/join");
    }
  }, [router, snapshot.status]);

  async function logout(): Promise<void> {
    if (logoutLock.current) return;
    logoutLock.current = true;
    setIsLoggingOut(true);
    setLogoutFailed(false);
    try {
      await session.logout();
      router.replace("/join");
    } catch {
      setLogoutFailed(true);
    } finally {
      logoutLock.current = false;
      setIsLoggingOut(false);
    }
  }

  if (snapshot.status === "bootstrapping") {
    return <SessionLoading />;
  }

  if (logoutFailed) {
    return (
      <section className="w-full max-w-xl rounded-2xl border border-rose/30 bg-white/70 p-6">
        <p role="alert" className="text-sm leading-6 text-ink">
          退出尚未由服务器确认，账号内容已隐藏。请重试以完成会话撤销。
        </p>
        <Button
          type="button"
          variant="secondary"
          className="mt-4"
          disabled={isLoggingOut}
          onClick={() => void logout()}
        >
          {isLoggingOut ? "正在重试…" : "重试退出"}
        </Button>
      </section>
    );
  }

  if (snapshot.status === "error") {
    return <SessionRecovery onRetry={() => void session.bootstrap()} />;
  }

  if (snapshot.status !== "active" || snapshot.user === null) {
    return <SessionLoading />;
  }

  if (accountDeletion !== null) {
    return <AccountDeletionStatus initialRequest={accountDeletion} />;
  }

  return (
    <section aria-labelledby="account-title" className="w-full max-w-2xl">
      <p className="text-sm font-medium tracking-[0.18em] text-rose">
        PRIVATE BETA · ACTIVE
      </p>
      <h1 id="account-title" className="mt-3 text-3xl font-semibold text-ink">
        账号基础已就绪
      </h1>
      <p className="mt-3 text-sm leading-6 text-black/65">
        当前阶段仅开放账号与授权基础。真实图片处理、AI 编辑和支付仍未启用。
      </p>
      <dl className="mt-7 rounded-2xl border border-black/10 bg-white/70 p-5 text-sm">
        <div className="flex items-center justify-between gap-6">
          <dt className="text-black/55">账号状态</dt>
          <dd className="font-medium">已激活</dd>
        </div>
      </dl>
      <DataRightsExperience onAccountDeletionStarted={setAccountDeletion} />
      <Button
        type="button"
        variant="secondary"
        className="mt-6"
        disabled={isLoggingOut}
        onClick={() => void logout()}
      >
        {isLoggingOut ? "正在退出…" : "退出登录"}
      </Button>
    </section>
  );
}
