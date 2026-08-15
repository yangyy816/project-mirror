import { describe, expect, it } from "vitest";

describe("web foundation", () => {
  it("uses a non-public server API URL by default", () => {
    expect(process.env.NEXT_PUBLIC_TENCENT_SECRET_KEY).toBeUndefined();
  });
});
