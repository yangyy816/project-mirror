import { expect, test } from "@playwright/test";

test("synthetic ImageVersion history shell remains local, responsive and keyboard-operable", async ({
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
  await expect(page.getByText("D11 IMAGEVERSION HISTORY")).toBeVisible();
  const slider = page.getByRole("slider", { name: /对比滑杆/ });
  await slider.focus();
  await page.keyboard.press("ArrowRight");
  await expect(slider).toHaveAttribute("aria-valuetext", "当前对比位置 51%");

  await page.getByRole("button", { name: "恢复到所选版本" }).click();
  await expect(page.getByText(/恢复请求待确认/)).toBeVisible();
  await page.getByRole("button", { name: "取消", exact: true }).click();
  await expect(page.getByText(/操作已取消/)).toBeVisible();

  await page.getByRole("button", { name: "恢复到所选版本" }).click();
  await page.getByRole("button", { name: "确认完成" }).click();
  await expect(page.getByText(/恢复已显示为完成/)).toBeVisible();

  await page.getByRole("button", { name: "不支持的执行请求" }).click();
  await expect(page.getByText(/没有获批执行能力/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "恢复到所选版本" }),
  ).toBeDisabled();
  expect(browserAuthorization).toEqual([]);
  await expect(page.locator("body")).not.toContainText(
    "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  );
});
