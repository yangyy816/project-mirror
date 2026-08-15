"use client";

import { Button } from "@mirror/ui";

export function SessionLoading() {
  return (
    <section
      aria-busy="true"
      aria-live="polite"
      className="w-full max-w-xl rounded-2xl border border-black/10 bg-white/70 p-6"
    >
      <h1 className="text-xl font-semibold text-ink">正在恢复安全会话</h1>
      <p className="mt-2 text-sm leading-6 text-black/60">
        验证完成前不会显示账号内容。
      </p>
    </section>
  );
}

export function SessionRecovery({
  onRetry,
}: Readonly<{ onRetry: () => void }>) {
  return (
    <section className="w-full max-w-xl rounded-2xl border border-rose/30 bg-white/70 p-6">
      <p role="alert" className="text-sm leading-6 text-ink">
        暂时无法确认会话状态。你可以重新检查，或重新完成手机号验证。
      </p>
      <Button
        type="button"
        variant="secondary"
        className="mt-4"
        onClick={onRetry}
      >
        重新检查会话
      </Button>
    </section>
  );
}
