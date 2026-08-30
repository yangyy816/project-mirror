import { DemoShell } from "@/components/demo/DemoShell";
import { getDemoCapabilities } from "@/lib/demo-capabilities";

export default async function DemoPage() {
  const data = await getDemoCapabilities();
  return <DemoShell data={data} />;
}
