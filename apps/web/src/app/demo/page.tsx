import { DemoShell } from "@/components/demo/DemoShell";
import { DemoTraceWorkspace } from "@/components/demo/DemoTraceWorkspace";
import { DemoVersionHistoryWorkspace } from "@/components/demo/DemoVersionHistoryWorkspace";
import { getDemoCapabilities } from "@/lib/demo-capabilities";

export default async function DemoPage() {
  const result = await getDemoCapabilities();
  return (
    <>
      <DemoShell result={result} />
      <div className="mx-auto max-w-6xl px-6 pb-8 md:px-10">
        <DemoTraceWorkspace />
        <DemoVersionHistoryWorkspace />
      </div>
    </>
  );
}
