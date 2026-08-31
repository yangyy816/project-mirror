import { expect, test, type Page } from "@playwright/test";

const apiOrigin = "http://localhost:4400";

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

test("active user manages assets and a real asynchronous data export without persisting grants", async ({
  page,
  request,
}) => {
  await completeAuthentication(page, "synthetic-invite");
  await page.getByRole("button", { name: "开始年龄核验" }).click();
  await page.getByRole("checkbox").check();
  await request.post(`${apiOrigin}/__test/fail-next`, {
    data: { target: "assets" },
  });
  await page.getByRole("button", { name: "确认并继续" }).click();
  await expect(page).toHaveURL(/\/account$/);

  await expect(page.getByText("请求未完成，请稍后重试。")).toBeVisible();
  await page.getByRole("button", { name: "重试读取资产" }).click();
  await expect(page.getByText("32 × 24")).toBeVisible();

  await page.getByRole("button", { name: "查看详情" }).click();
  await expect(page.getByLabel("资产详情")).toContainText("image/jpeg");

  const assetDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载", exact: true }).click();
  await expect((await assetDownload).suggestedFilename()).toMatch(
    /^mirror-asset-[a-f0-9]{32}\.jpg$/,
  );

  await page.getByRole("button", { name: "删除", exact: true }).click();
  await expect(page.getByText("删除请求状态：处理中")).toBeVisible();
  await expect(page.getByText("暂无可访问资产。")).toBeVisible();

  await page.getByRole("button", { name: "申请数据导出" }).click();
  await expect(page.getByText("导出状态：准备中")).toBeVisible();
  await expect(page.getByText("导出状态：可下载")).toBeVisible();
  const exportDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载数据导出" }).click();
  await expect((await exportDownload).suggestedFilename()).toBe(
    "project-mirror-data-export.zip",
  );

  expect(await page.evaluate(() => localStorage.length)).toBe(0);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  expect(page.url()).not.toContain("grant");
  expect(page.url()).not.toContain("token");
});

test("guarded account deletion hides ordinary content and only polls deletion status", async ({
  page,
  request,
}) => {
  await completeAuthentication(page, "synthetic-invite");
  await activateAccount(page);
  await expect(
    page.getByRole("button", { name: "永久删除账号" }),
  ).toBeDisabled();
  await page.getByLabel("输入“删除我的账号”确认").fill("删除我的账号");
  await page.getByRole("button", { name: "永久删除账号" }).click();

  await expect(
    page.getByRole("heading", { name: "账号删除处理中" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "我的图片资产" })).toHaveCount(
    0,
  );
  await expect(page).toHaveURL(/\/join$/);
  await expect(
    page.getByRole("heading", { name: "加入 Project Mirror 私测" }),
  ).toBeVisible();

  const state = await (await request.get(`${apiOrigin}/__test/state`)).json();
  expect(state).toMatchObject({
    session: false,
    account_deletion_status: "completed",
  });
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
});
