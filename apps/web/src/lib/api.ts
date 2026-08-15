import { serverEnv } from "@mirror/config/server";
import type { HealthResponse } from "@mirror/contracts";

async function fetchHealth(path: string): Promise<HealthResponse | null> {
  try {
    const response = await fetch(`${serverEnv.API_BASE_URL}${path}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(2_000),
    });
    return (await response.json()) as HealthResponse;
  } catch {
    return null;
  }
}

export async function getApiStatus(): Promise<{
  live: HealthResponse | null;
  ready: HealthResponse | null;
}> {
  const [live, ready] = await Promise.all([
    fetchHealth("/health/live"),
    fetchHealth("/health/ready"),
  ]);
  return { live, ready };
}
