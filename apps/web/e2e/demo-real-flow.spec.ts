import { expect, test } from "@playwright/test";

const apiOrigin = "http://localhost:4400";
const forbidden = [
  "x".repeat(32),
  "1".repeat(32),
  "b".repeat(32),
  "c".repeat(32),
  "d".repeat(64),
  "f".repeat(64),
  "e".repeat(32),
  "0".repeat(32),
  "9".repeat(32),
  "5".repeat(32),
  "7".repeat(32),
  "6".repeat(64),
  "7".repeat(64),
  "8".repeat(64),
  "9".repeat(64),
];

test.beforeEach(async ({ request }) => {
  await request.post(`${apiOrigin}/__test/reset`);
});

test("completes the same-origin synthetic preference flow without browser authority leakage", async ({
  page,
}) => {
  const authorization: string[] = [];
  const browserPaths: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/demo/")) {
      authorization.push(request.headers().authorization ?? "");
      browserPaths.push(new URL(request.url()).pathname);
    }
  });
  await page.goto("/demo");
  await page.getByRole("button", { name: "开始 Demo" }).click();
  await expect(page.getByRole("button", { name: "开始偏好问卷" })).toBeVisible({
    timeout: 6_000,
  });
  const demoCookie = (await page.context().cookies()).find(
    (cookie) => cookie.name === "mirror_demo_session",
  );
  expect(demoCookie).toMatchObject({
    httpOnly: true,
    sameSite: "Strict",
    path: "/api/demo",
  });
  expect(demoCookie?.value).toMatch(/^[a-f0-9]{64}$/);
  for (const value of forbidden) expect(demoCookie?.value).not.toBe(value);
  await page.getByRole("button", { name: "开始偏好问卷" }).click();
  await expect(page.getByRole("img", { name: "左侧方案" })).toHaveAttribute(
    "src",
    /\/api\/demo\/questionnaire\/media\//,
  );
  await expect(page.getByRole("img", { name: "右侧方案" })).toHaveAttribute(
    "src",
    /\/api\/demo\/questionnaire\/media\//,
  );
  await page.getByRole("button", { name: "更偏好左侧" }).click();
  await page.getByRole("button", { name: "跳过此题" }).click();
  await expect(page.getByText("偏好档案已准备完成。")).toBeVisible({
    timeout: 6_000,
  });
  await page.getByRole("button", { name: "生成档案引导的几何预览" }).click();
  const accept = page.getByRole("button", { name: "最终保存并用作参考" });
  await expect(page.getByRole("img", { name: "编辑前合成图" })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByRole("img", { name: "编辑后合成图" })).toBeVisible();
  await expect(accept).toBeEnabled({ timeout: 8_000 });
  await accept.click();
  await expect(page.getByText("已保存，参考档案待恢复")).toBeVisible();
  await expect(page.getByText("已保存并更新参考档案")).toBeVisible({
    timeout: 8_000,
  });
  expect(
    browserPaths.filter((path) => path === "/api/demo/self-transfer/accept"),
  ).toHaveLength(1);
  expect(authorization).not.toContain(expect.stringMatching(/.+/));
  const content = await page.content();
  for (const value of forbidden) expect(content).not.toContain(value);
  expect(page.url()).not.toMatch(/bearer|digest|locator/i);
  expect(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
  ).toBe(0);
});

test("projects no-compatible geometry safely and invalidates old preview media after logout", async ({
  page,
  request,
}) => {
  await request.post(`${apiOrigin}/__test/fail-next`, {
    data: { target: "demo-geometry-no-compatible" },
  });
  await page.goto("/demo");
  await page.getByRole("button", { name: "开始 Demo" }).click();
  await page.getByRole("button", { name: "开始偏好问卷" }).click({
    timeout: 8_000,
  });
  await page.getByRole("button", { name: "更偏好左侧" }).click({
    timeout: 8_000,
  });
  await page.getByRole("button", { name: "跳过此题" }).click();
  await page
    .getByRole("button", { name: "生成档案引导的几何预览" })
    .click({ timeout: 8_000 });
  await expect(page.getByText("当前档案暂无可用的安全几何步骤")).toBeVisible({
    timeout: 8_000,
  });
  await page.getByRole("button", { name: "结束 Demo" }).click();
  await expect(page.getByRole("button", { name: "开始 Demo" })).toBeVisible();
  expect(
    await page.evaluate(
      async () =>
        (await fetch(`/api/demo/self-transfer/media/${"a".repeat(64)}/INPUT`))
          .status,
    ),
  ).toBe(404);
});

test("recovers from a redacted analysis failure", async ({ page, request }) => {
  await request.post(`${apiOrigin}/__test/fail-next`, {
    data: { target: "demo-analysis" },
  });
  await page.goto("/demo");
  await page.getByRole("button", { name: "开始 Demo" }).click();
  await expect(page.getByText(/服务暂时不可用/)).toBeVisible({
    timeout: 6_000,
  });
  await expect(
    page.getByRole("button", { name: "重试当前步骤" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "重试当前步骤" }).click();
  await expect(page.getByRole("button", { name: "开始偏好问卷" })).toBeVisible({
    timeout: 6_000,
  });
});

test("serializes logout after a pending Session response and clears the cookie", async ({
  page,
  request,
}) => {
  await request.post(`${apiOrigin}/__test/fail-next`, {
    data: { target: "demo-session-delay" },
  });
  await page.goto("/demo");
  await page.getByRole("button", { name: "开始 Demo" }).click();
  await expect(page.getByText("正在建立 Demo 会话。")).toBeVisible();
  await page.getByRole("button", { name: "结束 Demo" }).click();
  await expect(page.getByText("正在安全结束 Demo 会话。")).toBeVisible();
  await expect(page.getByRole("button", { name: "开始 Demo" })).toBeVisible({
    timeout: 6_000,
  });
  expect(
    (await page.context().cookies()).find(
      (cookie) => cookie.name === "mirror_demo_session",
    ),
  ).toBeUndefined();
  expect(
    await page.evaluate(
      async () =>
        (await fetch("/api/demo/analysis", { method: "POST" })).status,
    ),
  ).toBe(403);
});
