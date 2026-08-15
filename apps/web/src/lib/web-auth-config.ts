import { z } from "zod";

const runtimeSchema = z.enum(["development", "test", "ci", "production"]);
const sha256Schema = z.string().regex(/^[a-f0-9]{64}$/);
const absoluteUrlSchema = z.string().url();

const policySchema = z
  .object({
    document_code: z.string().min(1).max(64),
    document_version: z.string().min(1).max(64),
    document_digest: sha256Schema,
    title: z.string().min(1).max(200),
    content_url: absoluteUrlSchema,
    status: z.literal("approved"),
  })
  .strict();

const ageProviderStatusSchema = z.enum(["unconfigured", "approved"]);

export type WebPolicyManifest = z.infer<typeof policySchema>;

export type WebAuthConfig = Readonly<{
  appEnv: z.infer<typeof runtimeSchema>;
  apiBaseUrl: string;
  appOrigin: string;
  policyManifest: readonly WebPolicyManifest[];
  ageProvider: Readonly<{
    status: z.infer<typeof ageProviderStatusSchema>;
    publicUrl: string | null;
    origin: string | null;
  }>;
}>;

export class WebAuthConfigError extends Error {
  constructor() {
    super("浏览器认证配置不可用。");
    this.name = "WebAuthConfigError";
  }
}

export type WebAuthConfigInput = Readonly<{
  appEnv?: string;
  apiBaseUrl?: string;
  appOrigin?: string;
  policyManifest?: string;
  ageProviderStatus?: string;
  ageProviderPublicUrl?: string;
  ageProviderOrigin?: string;
}>;

function parseUrl(value: string): URL {
  try {
    const parsed = new URL(value);
    if (parsed.username || parsed.password || parsed.search || parsed.hash) {
      throw new Error("unsafe URL");
    }
    return parsed;
  } catch {
    throw new WebAuthConfigError();
  }
}

function requireSecureUrl(url: URL, appEnv: WebAuthConfig["appEnv"]): void {
  if (
    appEnv === "production" &&
    (url.protocol !== "https:" ||
      url.hostname === "localhost" ||
      url.hostname === "127.0.0.1")
  ) {
    throw new WebAuthConfigError();
  }
}

function parsePolicyManifest(
  value: string | undefined,
  appEnv: WebAuthConfig["appEnv"],
): readonly WebPolicyManifest[] {
  if (value === undefined) {
    if (appEnv === "production") {
      throw new WebAuthConfigError();
    }
    return [];
  }
  try {
    const parsed = z.array(policySchema).min(1).parse(JSON.parse(value));
    const unique = new Set(
      parsed.map((policy) =>
        [
          policy.document_code,
          policy.document_version,
          policy.document_digest,
        ].join("\u0000"),
      ),
    );
    if (unique.size !== parsed.length) {
      throw new WebAuthConfigError();
    }
    return parsed;
  } catch (error) {
    if (error instanceof WebAuthConfigError) {
      throw error;
    }
    throw new WebAuthConfigError();
  }
}

export function parseWebAuthConfig(input: WebAuthConfigInput): WebAuthConfig {
  try {
    const appEnv = runtimeSchema.parse(input.appEnv ?? "development");
    const apiBaseUrl = absoluteUrlSchema.parse(input.apiBaseUrl);
    const appOrigin = absoluteUrlSchema.parse(input.appOrigin);
    const apiUrl = parseUrl(apiBaseUrl);
    const originUrl = parseUrl(appOrigin);
    requireSecureUrl(apiUrl, appEnv);
    requireSecureUrl(originUrl, appEnv);

    const policyManifest = parsePolicyManifest(input.policyManifest, appEnv);
    for (const policy of policyManifest) {
      requireSecureUrl(parseUrl(policy.content_url), appEnv);
    }

    const status = ageProviderStatusSchema.parse(
      input.ageProviderStatus ?? "unconfigured",
    );
    const publicUrl = input.ageProviderPublicUrl ?? null;
    const origin = input.ageProviderOrigin ?? null;
    if (status === "approved") {
      if (publicUrl === null || origin === null) {
        throw new WebAuthConfigError();
      }
      const providerUrl = parseUrl(absoluteUrlSchema.parse(publicUrl));
      const providerOrigin = parseUrl(absoluteUrlSchema.parse(origin));
      requireSecureUrl(providerUrl, appEnv);
      requireSecureUrl(providerOrigin, appEnv);
      if (providerUrl.origin !== providerOrigin.origin) {
        throw new WebAuthConfigError();
      }
    } else if (publicUrl !== null || origin !== null) {
      throw new WebAuthConfigError();
    }
    if (appEnv === "production" && status !== "approved") {
      throw new WebAuthConfigError();
    }

    return {
      appEnv,
      apiBaseUrl: apiUrl.toString().replace(/\/$/, ""),
      appOrigin: originUrl.origin,
      policyManifest,
      ageProvider: { status, publicUrl, origin },
    };
  } catch (error) {
    if (error instanceof WebAuthConfigError) {
      throw error;
    }
    throw new WebAuthConfigError();
  }
}

export function getWebAuthConfig(): WebAuthConfig {
  const appEnv = process.env.NEXT_PUBLIC_APP_ENV ?? "development";
  return parseWebAuthConfig({
    appEnv,
    apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000",
    appOrigin:
      process.env.NEXT_PUBLIC_APP_ORIGIN ??
      (appEnv === "production" ? undefined : "http://127.0.0.1:3000"),
    policyManifest: process.env.NEXT_PUBLIC_POLICY_MANIFEST,
    ageProviderStatus: process.env.NEXT_PUBLIC_AGE_PROVIDER_STATUS,
    ageProviderPublicUrl: process.env.NEXT_PUBLIC_AGE_PROVIDER_PUBLIC_URL,
    ageProviderOrigin: process.env.NEXT_PUBLIC_AGE_PROVIDER_ORIGIN,
  });
}
