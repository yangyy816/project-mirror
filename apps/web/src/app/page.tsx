import { Badge, Button } from "@mirror/ui";
import Link from "next/link";

import { getApiStatus } from "@/lib/api";

export default async function HomePage() {
  const { live, ready } = await getApiStatus();
  const isLive = live?.status === "live";
  const isReady = ready?.status === "ready";

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8 md:px-10">
      <nav className="flex items-center justify-between">
        <span className="text-sm font-semibold uppercase tracking-[0.24em] text-plum">
          Project Mirror
        </span>
        <Badge tone={isReady ? "success" : "warning"}>
          {isReady ? "服务已就绪" : isLive ? "有限能力模式" : "API 未连接"}
        </Badge>
      </nav>

      <section className="grid flex-1 items-center gap-12 py-20 lg:grid-cols-[1.2fr_0.8fr]">
        <div>
          <p className="mb-5 text-sm font-medium tracking-[0.2em] text-rose">
            PRIVATE BETA · 18+
          </p>
          <h1 className="max-w-3xl text-5xl font-semibold leading-[1.08] tracking-tight md:text-7xl">
            让每一次修图，
            <span className="text-plum">都更懂你的审美。</span>
          </h1>
          <p className="mt-7 max-w-2xl text-lg leading-8 text-black/65">
            Project Mirror
            正在建立一套可解释、可回滚、由你亲自选择驱动的个人审美档案。当前仅开放中国大陆邀请制私测。
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link
              href="/join"
              className="rounded-full bg-plum px-5 py-3 text-sm font-semibold text-white transition hover:bg-plum/90"
            >
              凭邀请码加入
            </Link>
            <Button variant="secondary" disabled>
              查看隐私说明
            </Button>
          </div>
        </div>

        <aside className="rounded-[2rem] border border-black/10 bg-white/70 p-7 shadow-[0_24px_80px_rgba(109,63,85,0.13)] backdrop-blur">
          <h2 className="text-xl font-semibold">Application Foundation 状态</h2>
          <dl className="mt-6 grid gap-4 text-sm">
            <StatusRow label="Web 应用" value="运行中" />
            <StatusRow
              label="API Live"
              value={isLive ? "available" : "unavailable"}
            />
            <StatusRow
              label="API Ready"
              value={isReady ? "ready" : (ready?.status ?? "unavailable")}
            />
            <StatusRow
              label="PostgreSQL"
              value={ready?.dependencies.database ?? "unknown"}
            />
            <StatusRow
              label="Redis"
              value={ready?.dependencies.redis ?? "unknown"}
            />
            <StatusRow label="版本" value={live?.version ?? "—"} />
            <StatusRow label="真实人脸处理" value="未启用" />
            <StatusRow label="真实支付" value="未启用" />
          </dl>
        </aside>
      </section>
    </main>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-black/10 pb-3 last:border-0">
      <dt className="text-black/55">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
