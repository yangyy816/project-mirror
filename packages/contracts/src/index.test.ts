import { describe, expect, it } from "vitest";

import { API_VERSION } from "./index";

describe("contract constants", () => {
  it("pins the public API version", () => {
    expect(API_VERSION).toBe("v1");
  });
});
