import { expect, test } from "@playwright/test";

const apiOrigin = "http://localhost:4400";

test.beforeEach(async ({ request }) => {
  await request.post(`${apiOrigin}/__test/reset`);
});

test("real questionnaire remains keyboard-operable without the obsolete ImageVersion fixture", async ({
  page,
}) => {
  const browserAuthorization: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/demo/")) {
      browserAuthorization.push(request.headers().authorization ?? "");
    }
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/demo");
  await expect(page.getByText("Before / After 与版本历史")).toHaveCount(0);
  await page.getByRole("button", { name: "开始 Demo" }).press("Enter");
  await expect(page.getByRole("button", { name: "开始偏好问卷" })).toBeVisible({
    timeout: 6_000,
  });
  await page.getByRole("button", { name: "开始偏好问卷" }).press("Enter");
  const choice = page.getByRole("button", { name: "更偏好左侧" });
  await choice.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("img", { name: "左侧方案" })).toBeVisible();
  expect(browserAuthorization).not.toContain(expect.stringMatching(/.+/));
});
