import { describe, expect, it } from "vitest";

import { parseWebAuthConfig, WebAuthConfigError } from "./web-auth-config";

const policyManifest = JSON.stringify([
  {
    document_code: "privacy",
    document_version: "v1",
    document_digest: "a".repeat(64),
    title: "隐私政策",
    content_url: "http://127.0.0.1:3000/policies/privacy-v1",
    status: "approved",
  },
]);

function input(overrides: Record<string, string | undefined> = {}) {
  return {
    appEnv: "development",
    apiBaseUrl: "http://127.0.0.1:8000",
    appOrigin: "http://127.0.0.1:3000",
    policyManifest,
    ageProviderStatus: "unconfigured",
    ...overrides,
  };
}

describe("web authentication config", () => {
  it("parses only an approved exact policy manifest", () => {
    const config = parseWebAuthConfig(input());

    expect(config.policyManifest).toHaveLength(1);
    expect(config.ageProvider.status).toBe("unconfigured");
  });

  it.each([
    input({ policyManifest: "[]" }),
    input({ policyManifest: "not-json" }),
    input({ ageProviderStatus: "approved" }),
    input({ ageProviderStatus: "mock" }),
  ])("fails closed for incomplete or dangerous public config", (candidate) => {
    expect(() => parseWebAuthConfig(candidate)).toThrow(WebAuthConfigError);
  });

  it("keeps development buildable with no manifest while exposing no usable policy", () => {
    expect(
      parseWebAuthConfig(input({ policyManifest: undefined })).policyManifest,
    ).toEqual([]);
  });

  it("requires approved HTTPS policy and age configuration in production", () => {
    const productionManifest = JSON.stringify([
      {
        document_code: "privacy",
        document_version: "v1",
        document_digest: "b".repeat(64),
        title: "隐私政策",
        content_url: "https://mirror.example/policies/privacy-v1",
        status: "approved",
      },
    ]);
    const production = input({
      appEnv: "production",
      apiBaseUrl: "https://api.mirror.example",
      appOrigin: "https://mirror.example",
      policyManifest: productionManifest,
      ageProviderStatus: "approved",
      ageProviderPublicUrl: "https://age.example/verify",
      ageProviderOrigin: "https://age.example",
    });

    expect(parseWebAuthConfig(production).ageProvider.origin).toBe(
      "https://age.example",
    );
    expect(() =>
      parseWebAuthConfig({ ...production, ageProviderStatus: "unconfigured" }),
    ).toThrow(WebAuthConfigError);
    expect(() =>
      parseWebAuthConfig({
        ...production,
        apiBaseUrl: "http://api.mirror.example",
      }),
    ).toThrow(WebAuthConfigError);
  });
});
