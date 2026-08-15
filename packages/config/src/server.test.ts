import { describe, expect, it } from "vitest";

import { serverSchema } from "./server";

describe("server environment", () => {
  it("rejects an invalid API URL", () => {
    expect(() => serverSchema.parse({ API_BASE_URL: "not-a-url" })).toThrow();
  });
});
