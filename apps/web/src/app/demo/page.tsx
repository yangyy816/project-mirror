import { DemoShell } from "@/components/demo/DemoShell";
import { getDemoCapabilities } from "@/lib/demo-capabilities";

export default async function DemoPage() {
  const result = await getDemoCapabilities();
  return <DemoShell result={result} />;
}
