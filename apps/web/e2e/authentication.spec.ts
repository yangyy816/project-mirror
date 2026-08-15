import { expect, test, type Page } from "@playwright/test";

const apiOrigin = "http://127.0.0.1:4400";

test.beforeEach(async ({ request }) => {
  await request.post(`${apiOrigin}/__test/reset`);
});

async function completeAuthentication(page: Page, inviteCode?: string) {
  await page.goto("/join");
  await page.getByLabel("手机号").fill("synthetic-phone");
  if (inviteCode !== undefined) {
    await page.getByLabel("邀请码（如有）").fill(inviteCode);
  }
  await page.getByRole("button", { name: "获取验证码" }).click();
  await page.getByLabel("验证码").fill("123456");
  await page.getByRole("button", { name: "继续" }).click();
  await expect(
    page.getByRole("heading", { name: "完成账号开通" }),
  ).toBeVisible();
}

async function activateAccount(page: Page) {
  await page.getByRole("button", { name: "开始年龄核验" }).click();
  await expect(page.getByRole("link", { name: "隐私政策" })).toBeVisible();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "确认并继续" }).click();
  await expect(page).toHaveURL(/\/account$/);
  await expect(
    page.getByRole("heading", { name: "账号基础已就绪" }),
  ).toBeVisible();
}

test("new invited user completes pending onboarding, reload recovery and logout", async ({
  page,
  request,
}) => {
  await completeAuthentication(page, "synthetic-invite");

  await page.getByRole("button", { name: "开始年龄核验" }).click();
  await expect(page.getByRole("link", { name: "隐私政策" })).toBeVisible();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "确认并继续" }).click();
  await expect(page).toHaveURL(/\/account$/);
  await expect(
    page.getByRole("heading", { name: "账号基础已就绪" }),
  ).toBeVisible();

  const state = await (await request.get(`${apiOrigin}/__test/state`)).json();
  expect(state).toMatchObject({ active: true, last_invite_present: true });

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "账号基础已就绪" }),
  ).toBeVisible();
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  expect(page.url()).not.toContain("token");
  expect(page.url()).not.toContain("credential");

  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/join$/);
  await page.goto("/account");
  await expect(page).toHaveURL(/\/join$/);
  await expect(page.getByText("账号基础已就绪")).toHaveCount(0);
});

test("existing login omits invite and recovers from a wrong OTP", async ({
  page,
  request,
}) => {
  await page.goto("/join");
  await page.getByLabel("手机号").fill("synthetic-existing-phone");
  await page.getByRole("button", { name: "获取验证码" }).click();
  await page.getByLabel("验证码").fill("000000");
  await page.getByRole("button", { name: "继续" }).click();
  await expect(page.getByText("认证请求未完成，请检查后重试。")).toBeVisible();

  await page.getByLabel("验证码").fill("123456");
  await page.getByRole("button", { name: "继续" }).click();
  await expect(
    page.getByRole("heading", { name: "完成账号开通" }),
  ).toBeVisible();

  const state = await (await request.get(`${apiOrigin}/__test/state`)).json();
  expect(state).toMatchObject({
    last_invite_present: false,
    challenge_count: 1,
  });
});

test("missing CSRF and revoked refresh fail closed without account-content flash", async ({
  page,
  request,
}) => {
  await completeAuthentication(page, "synthetic-invite");
  await activateAccount(page);

  await page.evaluate(() => {
    document.cookie = "mirror_csrf=; Max-Age=0; Path=/";
  });
  await page.reload();
  await expect(page).toHaveURL(/\/join$/);
  await expect(
    page.getByRole("heading", { name: "加入 Project Mirror 私测" }),
  ).toBeVisible();
  await expect(page.getByText("账号基础已就绪")).toHaveCount(0);

  await request.post(`${apiOrigin}/__test/reset`);
  await page.goto("/account");
  await expect(page).toHaveURL(/\/join$/);
  await expect(page.getByText("账号基础已就绪")).toHaveCount(0);
});
