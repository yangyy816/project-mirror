import { Badge } from "@mirror/ui";

import type { DemoCapabilityReadResult } from "@/lib/demo-capabilities";

type DemoShellProps = Readonly<{
  result: DemoCapabilityReadResult;
}>;

function capabilityTone(status: string): "success" | "warning" {
  return status === "AVAILABLE" ? "success" : "warning";
}

export function DemoShell({ result }: DemoShellProps) {
  const data = result.kind === "AVAILABLE" ? result.data : null;
  const connectionLabel =
    result.kind === "AVAILABLE"
      ? "已连接"
      : result.kind === "AUTH_REQUIRED"
        ? "DEMO_AUTH_REQUIRED"
        : "unavailable";

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-8 md:px-10">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-plum">
            Project Mirror
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            Demo 能力概览
          </h1>
        </div>
        <Badge tone="warning">DEMO_PROTOTYPE · 非生产环境</Badge>
      </header>

      <section className="mt-8 rounded-[2rem] border border-black/10 bg-white/70 p-7 shadow-[0_24px_80px_rgba(109,63,85,0.13)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold">真实 API capability 状态</h2>
            <p className="mt-1 text-sm text-black/60">
              唯一读取来源：GET /api/v1/demo/capabilities
            </p>
          </div>
          <Badge tone={data ? "success" : "warning"}>{connectionLabel}</Badge>
        </div>

        {data ? (
          <ul className="mt-6 grid gap-3 sm:grid-cols-2">
            {data.capabilities.map((capability) => (
              <li
                className="rounded-2xl border border-black/10 bg-white p-4"
                key={capability.code}
              >
                <div className="flex items-start justify-between gap-3">
                  <code className="text-sm font-semibold text-plum">
                    {capability.code}
                  </code>
                  <Badge tone={capabilityTone(capability.status)}>
                    {capability.status}
                  </Badge>
                </div>
                {capability.reason ? (
                  <p className="mt-3 text-sm leading-6 text-black/60">
                    {capability.reason}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : result.kind === "AUTH_REQUIRED" ? (
          <p className="mt-6 rounded-2xl border border-dashed border-black/20 p-4 text-sm leading-6 text-black/65">
            API 已明确要求 Demo
            Bearer，当前能力状态未验证。此页面不会请求、存储或向浏览器暴露 Demo
            Bearer。
          </p>
        ) : (
          <p className="mt-6 rounded-2xl border border-dashed border-black/20 p-4 text-sm leading-6 text-black/65">
            当前无法验证 capability 状态。页面不会以缓存、fixture
            或推测结果替代真实 API 响应。
          </p>
        )}
      </section>
    </main>
  );
}
