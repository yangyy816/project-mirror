import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type HealthResponse = components["schemas"]["HealthResponse"];
export type VersionResponse = components["schemas"]["VersionResponse"];
export type ErrorEnvelope = components["schemas"]["ErrorEnvelope"];

export const API_VERSION = "v1" as const;

export function createMirrorApiClient(baseUrl: string) {
  return createClient<paths>({ baseUrl });
}
