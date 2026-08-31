import { defineConfig } from "@playwright/test";

const next =
  process.platform === "win32"
    ? ".\\node_modules\\.bin\\next.CMD"
    : "./node_modules/.bin/next";
const appOrigin = "http://localhost:4300";
const apiOrigin = "http://localhost:4400";
const policyManifest = JSON.stringify([
  {
    document_code: "privacy",
    document_version: "e2e-v1",
    document_digest: "a".repeat(64),
    title: "隐私政策",
    content_url: `${apiOrigin}/policies/privacy`,
    status: "approved",
  },
]);
const webCommand =
  process.platform === "win32"
    ? `${next} build && ${next} start`
    : `${next} build && node e2e/prepare-standalone.mjs && node .next/standalone/apps/web/server.js`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["line"], ["html", { open: "never" }]] : "line",
  use: {
    baseURL: appOrigin,
    channel: process.platform === "win32" ? "msedge" : undefined,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  webServer: [
    {
      command: "node e2e/fake-api.mjs",
      cwd: ".",
      url: `${apiOrigin}/health`,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: webCommand,
      cwd: ".",
      url: `${appOrigin}/demo`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        NEXT_PUBLIC_APP_ENV: "test",
        NEXT_PUBLIC_API_BASE_URL: apiOrigin,
        API_BASE_URL: apiOrigin,
        DEMO_BEARER_TOKEN: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        DEMO_SESSION_ID: "11111111111111111111111111111111",
        DEMO_SESSION_TTL_SECONDS: "900",
        NEXT_PUBLIC_APP_ORIGIN: appOrigin,
        NEXT_PUBLIC_POLICY_MANIFEST: policyManifest,
        NEXT_PUBLIC_AGE_PROVIDER_STATUS: "approved",
        NEXT_PUBLIC_AGE_PROVIDER_PUBLIC_URL: `${apiOrigin}/age/verify`,
        NEXT_PUBLIC_AGE_PROVIDER_ORIGIN: apiOrigin,
        HOSTNAME: "localhost",
        PORT: "4300",
      },
    },
  ],
});
