import { describe, expect, it } from "vitest";

import {
  abbreviateDemoAuthority,
  demoVersionHistoryFixture,
} from "./demo-version-history";

describe("demo version history fixture", () => {
  it("is typed, deterministic, synthetic-only, and includes every terminal projection", () => {
    expect(demoVersionHistoryFixture.map((item) => item.status)).toEqual([
      "CURRENT",
      "VERIFIED",
      "CANCELLED",
      "FAILED",
      "UNSUPPORTED",
    ]);
    expect(demoVersionHistoryFixture[0].kind).toBe("IMAGE_VERSION");
    expect(demoVersionHistoryFixture[0].parentId).toBe("iv-demo-003");
    expect(
      demoVersionHistoryFixture
        .slice(2)
        .every((item) => item.kind === "EXECUTION_EVENT"),
    ).toBe(true);
    expect(demoVersionHistoryFixture[0].digest).toHaveLength(16);
    expect(abbreviateDemoAuthority("synthetic-lineage-004")).toBe(
      "syntheti…-004",
    );
  });
});
