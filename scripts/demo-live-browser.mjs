// Real-service operator: JSON lines on stdin, redacted observations on stdout.
// This driver never starts a service, injects a credential, or retries an action.
import { createRequire } from "node:module";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";

const repo = fileURLToPath(new URL("../", import.meta.url));
const requireWeb = createRequire(resolve(repo, "apps/web/package.json"));
const { chromium } = requireWeb("@playwright/test");
const driverTask = process.env.MIRROR_DEMO_DRIVER_TASK;
if (!driverTask || !/^[A-Za-z0-9_-]{1,96}$/.test(driverTask))
  throw new Error("DRIVER_TASK_ID_REQUIRED");
const checkpointRoot = resolve(repo, ".private-handoff", driverTask);
const checkpointFile = resolve(checkpointRoot, "browser-state.json");
const receiptFile = resolve(checkpointRoot, "NAME_RECEIPT.json");
mkdirSync(checkpointRoot, { recursive: true });
if (!existsSync(receiptFile))
  writeFileSync(
    receiptFile,
    JSON.stringify({
      task: driverTask,
      purpose: "BROWSER_SESSION_RECOVERY_ONLY",
    }),
    { flag: "wx", mode: 0o600 },
  );
if (JSON.parse(readFileSync(receiptFile, "utf8")).task !== driverTask)
  throw new Error("DRIVER_CHECKPOINT_OWNER_MISMATCH");
const origin = new URL(process.argv[2] ?? "http://localhost:48000");
if (
  origin.protocol !== "http:" ||
  !["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname) ||
  origin.username ||
  origin.password ||
  origin.search ||
  origin.hash ||
  origin.pathname !== "/"
)
  throw new Error("LOOPBACK_ORIGIN_REQUIRED");

const allowedButtons = new Set([
  "重试当前步骤",
  "开始 Demo",
  "开始偏好问卷",
  "更偏好左侧",
  "更偏好右侧",
  "难以区分",
  "跳过此题",
  "生成档案引导的几何预览",
  "最终保存并用作参考",
  "结束 Demo",
]);
const counters = { authorizationHeaders: 0, pageErrors: 0, failedRequests: 0 };
const requests = [];
const responses = [];
const processed = new Set();
let browser;
let page;
let checkpointWork = Promise.resolve();
function checkpoint() {
  checkpointWork = checkpointWork
    .catch(() => {})
    .then(async () => {
      if (!page || page.isClosed()) return;
      const state = await page.context().storageState();
      writeFileSync(checkpointFile + ".tmp", JSON.stringify(state), {
        mode: 0o600,
      });
      renameSync(checkpointFile + ".tmp", checkpointFile);
    });
  return checkpointWork;
}
const emit = (value) => process.stdout.write(JSON.stringify(value) + "\n");
if (process.argv.includes("--checkpoint-status")) {
  const stored = existsSync(checkpointFile)
    ? JSON.parse(readFileSync(checkpointFile, "utf8"))
    : {};
  const cookie = stored.cookies?.find(
    (item) => item.name === "mirror_demo_session",
  );
  emit({
    hasDemoCookie: Boolean(cookie),
    secondsRemaining: cookie
      ? Math.floor(cookie.expires - Date.now() / 1000)
      : null,
  });
  process.exit(0);
}
const routeName = (url) =>
  new URL(url).pathname.replace(/\/media\/[a-f0-9]{64}\//g, "/media/:token/");

async function snapshot() {
  if (!page) return { opened: false };
  await checkpoint();
  return {
    opened: !page.isClosed(),
    ...(await page.evaluate(() => {
      const regions = [...document.querySelectorAll("[aria-live]")];
      const text = regions.map((n) => n.textContent ?? "").join(" ");
      const known = [
        ["正在建立 Demo 会话", "SESSION_CREATING"],
        ["分析完成，可以开始偏好问卷", "ANALYSIS_READY"],
        ["偏好档案已准备完成", "PROFILE_READY"],
        ["请确认编辑前后合成图", "PREVIEW_READY"],
        ["正在最终保存", "SAVING"],
        ["已保存，参考档案待恢复", "REFERENCE_PENDING"],
        ["已保存并更新参考档案", "REFERENCE_READY"],
        ["当前档案暂无可用的安全几何步骤", "NO_COMPATIBLE_CASE"],
        ["请求被拒绝", "DENIED"],
        ["服务暂时不可用", "UNAVAILABLE"],
        ["处理未完成", "FAILED"],
      ];
      const buttons = [...document.querySelectorAll("button")];
      return {
        states: known
          .filter(([needle]) => text.includes(needle))
          .map(([, state]) => state),
        startEnabled: buttons.some(
          (b) => b.textContent?.trim() === "开始 Demo" && !b.disabled,
        ),
        questionnaireEnabled: buttons.some(
          (b) => b.textContent?.trim() === "开始偏好问卷" && !b.disabled,
        ),
        answerEnabled: buttons.some(
          (b) => b.textContent?.trim() === "更偏好左侧" && !b.disabled,
        ),
        previewEnabled: buttons.some(
          (b) =>
            b.textContent?.trim() === "生成档案引导的几何预览" && !b.disabled,
        ),
        saveEnabled: buttons.some(
          (b) => b.textContent?.trim() === "最终保存并用作参考" && !b.disabled,
        ),
        images: [...document.querySelectorAll("img")]
          .filter((i) => ["编辑前合成图", "编辑后合成图"].includes(i.alt))
          .map((i) => ({
            side: i.alt === "编辑前合成图" ? "INPUT" : "RESULT",
            loaded: i.complete && i.naturalWidth > 0,
            width: i.naturalWidth,
            height: i.naturalHeight,
          })),
        storageEntries: localStorage.length + sessionStorage.length,
      };
    })),
    counters: { ...counters },
    requests: requests.slice(-12),
    responses: responses.slice(-12),
  };
}

async function command(input) {
  if (input.op === "open") {
    if (browser) throw new Error("BROWSER_ALREADY_OPEN");
    browser = await chromium.launch({
      executablePath:
        process.platform === "win32"
          ? "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
          : undefined,
      headless: true,
    });
    const context = await browser.newContext({
      serviceWorkers: "block",
      storageState: existsSync(checkpointFile) ? checkpointFile : undefined,
    });
    page = await context.newPage();
    page.setDefaultTimeout(10000);
    page.on("pageerror", () => counters.pageErrors++);
    page.on("requestfinished", () => {
      void checkpoint().catch(() => {});
    });
    page.on("requestfailed", () => counters.failedRequests++);
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (
        url.origin !== origin.origin ||
        !url.pathname.startsWith("/api/demo/")
      )
        return;
      if (request.headers().authorization) counters.authorizationHeaders++;
      requests.push({
        method: request.method(),
        route: routeName(request.url()),
      });
    });
    page.on("response", async (response) => {
      const url = new URL(response.url());
      if (
        url.origin !== origin.origin ||
        !url.pathname.startsWith("/api/demo/")
      )
        return;
      const item = {
        route: routeName(response.url()),
        status: response.status(),
      };
      // Do not read media or forward arbitrary response content.
      if (response.headers()["content-type"]?.includes("application/json")) {
        const body = await response.json().catch(() => null);
        for (const key of ["status", "code"]) {
          if (
            typeof body?.[key] === "string" &&
            /^[A-Z_]{1,80}$/.test(body[key])
          )
            item[key + "Value"] = body[key];
        }
      }
      responses.push(item);
    });
    const navigation = await page.goto(new URL("/demo", origin).href, {
      waitUntil: "networkidle",
      timeout: 20000,
    });
    return { pageStatus: navigation?.status(), ...(await snapshot()) };
  }
  if (input.op === "status") return snapshot();
  if (input.op === "reload-media") {
    if (!page) throw new Error("UNSUPPORTED_ACTION");
    await page.locator("img").evaluateAll((nodes) => {
      for (const image of nodes) {
        const source = image.getAttribute("src");
        if (source?.startsWith("/api/demo/")) {
          image.removeAttribute("src");
          image.setAttribute("src", source);
        }
      }
    });
    return snapshot();
  }
  if (input.op === "click") {
    if (!page || !allowedButtons.has(input.name))
      throw new Error("UNSUPPORTED_ACTION");
    if (input.name === "最终保存并用作参考") {
      const state = await snapshot();
      if (
        state.images.length !== 2 ||
        !state.images.every((i) => i.loaded) ||
        !state.saveEnabled
      )
        throw new Error("LOADED_BEFORE_AFTER_REQUIRED");
    }
    emit({ id: input.id, phase: "ACTION_STARTING", action: input.name });
    await page.getByRole("button", { name: input.name, exact: true }).click();
    return snapshot();
  }
  if (input.op === "close") {
    await checkpointWork.catch(() => {});
    await browser?.close();
    browser = undefined;
    page = undefined;
    return { closed: true };
  }
  throw new Error("UNSUPPORTED_COMMAND");
}

emit({ status: "DRIVER_READY", browserStarted: false });
for await (const line of createInterface({
  input: process.stdin,
  crlfDelay: Infinity,
})) {
  try {
    const input = JSON.parse(line);
    if (typeof input.id !== "string" || !/^[a-z0-9-]{1,64}$/.test(input.id))
      throw new Error("COMMAND_ID_REQUIRED");
    if (processed.has(input.id)) {
      emit({ id: input.id, status: "ALREADY_ATTEMPTED_NO_RETRY" });
      continue;
    }
    processed.add(input.id);
    emit({ id: input.id, result: await command(input) });
  } catch (error) {
    const known =
      /^(?:LOADED_BEFORE_AFTER_REQUIRED|BROWSER_ALREADY_OPEN|UNSUPPORTED_ACTION|UNSUPPORTED_COMMAND|COMMAND_ID_REQUIRED)$/;
    emit({
      status: "DRIVER_ERROR",
      error:
        error?.name === "TimeoutError"
          ? "TIMEOUT_OUTCOME_REQUIRES_OBSERVATION"
          : known.test(error?.message)
            ? error.message
            : "OPERATION_ERROR_DETAILS_WITHHELD",
    });
  }
}
await browser?.close();
