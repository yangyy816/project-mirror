export type DemoPublishedImageVersion = Readonly<{
  kind: "IMAGE_VERSION";
  entryId: string;
  id: string;
  label: string;
  parentId: string | null;
  operation: string;
  verifier: "PASS";
  execution: "COMPLETED";
  digest: string;
  lineage: string;
  status: "CURRENT" | "VERIFIED";
}>;

export type DemoExecutionEvent = Readonly<{
  kind: "EXECUTION_EVENT";
  entryId: string;
  label: string;
  operation: string;
  verifier: "CANCELLED" | "FAILED" | "UNSUPPORTED";
  execution: "CANCELLED" | "FAILED" | "NOT_SUPPORTED";
  digest: string;
  status: "CANCELLED" | "FAILED" | "UNSUPPORTED";
}>;

export type DemoVersionHistoryEntry =
  | DemoPublishedImageVersion
  | DemoExecutionEvent;

export const demoVersionHistoryFixture = [
  {
    kind: "IMAGE_VERSION",
    entryId: "timeline-version-004",
    id: "iv-demo-004",
    label: "当前版本 v4",
    parentId: "iv-demo-003",
    operation: "局部明暗调整 · synthetic operation summary",
    verifier: "PASS",
    execution: "COMPLETED",
    digest: "4d5a8f3ce1b7d9a2",
    lineage: "synthetic-lineage-004",
    status: "CURRENT",
  },
  {
    kind: "IMAGE_VERSION",
    entryId: "timeline-version-003",
    id: "iv-demo-003",
    label: "父版本 v3",
    parentId: null,
    operation: "轮廓参数预览 · synthetic operation summary",
    verifier: "PASS",
    execution: "COMPLETED",
    digest: "3c1e6a8bd2f40579",
    lineage: "synthetic-lineage-003",
    status: "VERIFIED",
  },
  {
    kind: "EXECUTION_EVENT",
    entryId: "execution-demo-cancelled",
    label: "已取消执行 v2",
    operation: "未完成的局部调整",
    verifier: "CANCELLED",
    execution: "CANCELLED",
    digest: "2aa943f0e74c61bd",
    status: "CANCELLED",
  },
  {
    kind: "EXECUTION_EVENT",
    entryId: "execution-demo-failed",
    label: "失败执行 v1",
    operation: "验证未通过的变更请求",
    verifier: "FAILED",
    execution: "FAILED",
    digest: "1baf07d91e2c88f4",
    status: "FAILED",
  },
  {
    kind: "EXECUTION_EVENT",
    entryId: "execution-demo-unsupported",
    label: "不支持的执行请求",
    operation: "尚无已批准的执行能力",
    verifier: "UNSUPPORTED",
    execution: "NOT_SUPPORTED",
    digest: "0f0e11a29c77d3be",
    status: "UNSUPPORTED",
  },
] as const satisfies readonly DemoVersionHistoryEntry[];

export function abbreviateDemoAuthority(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}
