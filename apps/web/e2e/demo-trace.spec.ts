import { expect, test } from "@playwright/test";

test("real Demo page rejects browser authority overrides and removes obsolete trace fixtures", async ({
  page,
}) => {
  await page.goto("/demo");
  await expect(page.getByText("UI_CONTRACT_ONLY")).toHaveCount(0);
  await expect(page.getByText("REAL_D02_INTEGRATION_PENDING")).toHaveCount(0);
  await expect(page.getByText("Context 与 Trace 回放")).toHaveCount(0);
  const denied = await page.evaluate(
    async () =>
      (
        await fetch("/api/demo/session", {
          method: "POST",
          headers: { Authorization: "Bearer browser-must-not-send" },
        })
      ).status,
  );
  expect(denied).toBe(403);
  const override = await page.evaluate(
    async () =>
      (await fetch("/api/demo/session?session_id=override", { method: "POST" }))
        .status,
  );
  expect(override).toBe(403);
});
