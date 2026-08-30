import { serverEnv } from "@mirror/config/server";
import { z } from "zod";

const capabilitySchema = z
  .object({
    code: z.enum([
      "P3_FACE_ANALYSIS",
      "P4_QUESTIONNAIRE",
      "P5_COMPILER",
      "P6_DETERMINISTIC_RASTER",
      "P6_GEOMETRY",
      "P6_MAKEUP",
      "P6_GENERATIVE_EDITOR",
      "P7_PREFERENCE_MEMORY",
    ]),
    status: z.enum([
      "AVAILABLE",
      "NOT_IMPLEMENTED",
      "DEFERRED_WITH_EXPLICIT_REASON",
      "CAPABILITY_UNAVAILABLE",
    ]),
    reason: z.string().min(1).max(256).nullable().optional(),
  })
  .strict();

const responseSchema = z
  .object({
    track: z.literal("DEMO_PROTOTYPE"),
    capabilities: z.array(capabilitySchema),
  })
  .strict();

export type DemoCapability = z.infer<typeof capabilitySchema>;
export type DemoCapabilitiesResponse = z.infer<typeof responseSchema>;
export type DemoCapabilityReadResult =
  | Readonly<{ kind: "AVAILABLE"; data: DemoCapabilitiesResponse }>
  | Readonly<{ kind: "AUTH_REQUIRED"; data: null }>
  | Readonly<{ kind: "UNAVAILABLE"; data: null }>;

export async function getDemoCapabilities(): Promise<DemoCapabilityReadResult> {
  try {
    const response = await fetch(
      `${serverEnv.API_BASE_URL}/api/v1/demo/capabilities`,
      {
        cache: "no-store",
        signal: AbortSignal.timeout(2_000),
      },
    );
    if (response.status === 401) return { kind: "AUTH_REQUIRED", data: null };
    if (!response.ok) return { kind: "UNAVAILABLE", data: null };
    return {
      kind: "AVAILABLE",
      data: responseSchema.parse(await response.json()),
    };
  } catch {
    return { kind: "UNAVAILABLE", data: null };
  }
}
