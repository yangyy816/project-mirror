import { expect, test } from "@playwright/test";

const apiOrigin = "http://localhost:4400";
const demoBearer = "x".repeat(32);
const demoSessionId = "1".repeat(32);

test.beforeEach(async ({ request }) => {
  await request.post(`${apiOrigin}/__test/reset`);
});

test("browser uses the same-origin BFF without exposing the Demo bearer", async ({
  page,
  request,
}) => {
  const browserRequests: string[] = [];
  page.on("request", (route) => {
    if (route.url().includes("/api/demo/")) {
      browserRequests.push(route.headers().authorization ?? "");
    }
  });

  await page.goto("/demo");
  const recallResponse = page.waitForResponse("**/api/demo/recall?*");
  await page.getByRole("button", { name: "读取 Context 与 Trace" }).click();
  expect((await recallResponse).status()).toBe(200);
  await expect(page.getByText("只读回放完成。")).toBeVisible();
  await expect(page.getByText("11111111111111111111111111111111")).toHaveCount(
    0,
  );
  await expect(page.getByText("DETERMINISTIC_READ_ONLY")).toBeVisible();
  expect(browserRequests).toEqual(["", ""]);
  const demoCookie = (await page.context().cookies()).find(
    (cookie) => cookie.name === "mirror_demo_session",
  );
  expect(demoCookie).toMatchObject({
    httpOnly: true,
    sameSite: "Strict",
    path: "/api/demo",
  });
  expect(demoCookie?.value).toMatch(/^[a-f0-9]{64}$/);
  expect(demoCookie?.value).not.toBe(demoBearer);
  expect(demoCookie?.value).not.toBe(demoSessionId);
  expect(page.url()).not.toContain(demoBearer);
  expect(await page.content()).not.toContain(demoBearer);
  expect(await page.content()).not.toContain(demoSessionId);
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);

  const state = await (await request.get(`${apiOrigin}/__test/state`)).json();
  expect(state).toMatchObject({
    demo_recall_ats: ["2099-01-01T00:00:00.000Z", "2099-01-01T00:00:00.000Z"],
    demo_request_count: 2,
    demo_session_create_count: 1,
  });
});

test("BFF fails closed for a client Authorization header and invalid timestamps", async ({
  page,
}) => {
  await page.goto("/demo");
  const denied = await page.evaluate(async () => {
    const response = await fetch("/api/demo/session", {
      method: "POST",
      headers: { Authorization: "Bearer browser-must-not-send" },
    });
    return response.status;
  });
  expect(denied).toBe(403);

  const override = await page.evaluate(async () => {
    const response = await fetch("/api/demo/session?session_id=override", {
      method: "POST",
    });
    return response.status;
  });
  expect(override).toBe(403);

  await page.getByLabel("回放时间（显式、带时区）").fill("2099-01-01T00:00:00");
  await page.getByRole("button", { name: "读取 Context 与 Trace" }).click();
  await expect(
    page.getByText("回放时间必须是带时区的 ISO-8601 时间。"),
  ).toBeVisible();
});

test("digest mismatch fails closed without displaying an authority projection", async ({
  page,
  request,
}) => {
  await request.post(`${apiOrigin}/__test/fail-next`, {
    data: { target: "demo-digest-mismatch" },
  });
  await page.goto("/demo");
  await page.getByRole("button", { name: "读取 Context 与 Trace" }).click();
  await expect(page.getByText(/权威 digest 不一致/)).toBeVisible();
  await expect(page.getByText("compilation digest")).toHaveCount(0);
});
