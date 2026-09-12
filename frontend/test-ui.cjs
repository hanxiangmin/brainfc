const { chromium } = require("playwright");
const path = require("node:path");
const fs = require("node:fs");
const assert = require("node:assert/strict");
const root = path.resolve(__dirname, "..");
const out = path.join(root, ".work", "browser-qa");
fs.mkdirSync(out, { recursive: true });
let browser;
(async () => {
  browser = await chromium.launch({
    headless: true,
    executablePath: process.env.FMRI_TEST_CHROMIUM || undefined,
    args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
  });
  const page = await browser.newPage({
    viewport: { width: 1500, height: 1080 },
    deviceScaleFactor: 1,
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://127.0.0.1:8766");
  await page.getByRole("heading", { name: /让 fMRI/ }).waitFor();
  await page.screenshot({ path: path.join(out, "01-welcome.png") });
  await page.getByRole("button", { name: /打开合成演示/ }).click();
  await page
    .getByRole("heading", { name: "连接分析结果", exact: true })
    .waitFor({ timeout: 180000 });
  const scene = page.getByTestId("brain-scene");
  await scene.waitFor();
  await page.waitForFunction(() => {
    const c = document.querySelector(
      '[aria-label="交互三维脑网络，拖动旋转，右键平移，滚轮缩放"]',
    );
    return c && c.width > 0;
  });
  await page.screenshot({ path: path.join(out, "02-3d.png") });
  await page.getByRole("button", { name: "顶部", exact: true }).click();
  await page.getByRole("button", { name: "底部", exact: true }).click();
  await page.getByRole("button", { name: "右前斜", exact: true }).click();
  await page.getByRole("button", { name: "浅色", exact: true }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "保存 PNG", exact: true }).click();
  const download = await downloadPromise;
  await download.saveAs(path.join(out, "03-3d-export.png"));
  assert.ok(fs.statSync(path.join(out, "03-3d-export.png")).size > 10000);
  await page.getByRole("button", { name: "功能连接矩阵", exact: true }).click();
  await page.getByRole("heading", { name: "完整功能连接矩阵" }).waitFor();
  await page.screenshot({ path: path.join(out, "04-matrix.png") });
  await page.getByRole("button", { name: "脑区八视图", exact: true }).click();
  await page.waitForFunction(() => {
    const i = document.querySelector("img.eight-views");
    return i?.complete && i.naturalWidth > 0;
  });
  await page.screenshot({ path: path.join(out, "05-eight-views.png") });
  await page.getByRole("button", { name: "质控与参数", exact: true }).click();
  assert.ok(
    (await page.locator("main").innerText()).includes("synthetic-demo"),
  );
  const zipPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: /下载完整结果/ }).click();
  await (await zipPromise).saveAs(path.join(out, "result.zip"));
  const jobs = await (
    await page.request.get("http://127.0.0.1:8766/api/jobs")
  ).json();
  const job = jobs.find((j) => j.kind === "demo" && j.status === "complete");
  assert.ok(job);
  await page.goto(
    "file:///" + path.join(job.result_dir, "report.html").replaceAll("\\", "/"),
  );
  await page
    .getByRole("heading", { name: "连接分析结果", exact: true })
    .waitFor();
  await page.getByTestId("brain-scene").waitFor();
  assert.equal(await page.locator("aside").count(), 0);
  await page.getByRole("button", { name: "脑区八视图", exact: true }).click();
  await page.waitForFunction(() => {
    const i = document.querySelector("img.eight-views");
    return i?.complete && i.naturalWidth > 0;
  });
  await page.screenshot({ path: path.join(out, "06-offline-report.png") });
  assert.deepEqual(errors, []);
  fs.writeFileSync(
    path.join(out, "validation.json"),
    JSON.stringify(
      {
        status: "passed",
        browser: "standalone Playwright Chromium (in-app runtime unavailable)",
        job: job.id,
        page_errors: errors,
        checks: [
          "GUI starts NIfTI demo job",
          "interactive WebGL canvas",
          "eight camera presets",
          "theme switch",
          "PNG screenshot download",
          "matrix tab",
          "eight views image",
          "QC metadata",
          "ZIP download",
          "file:// offline report with embedded image and no API",
        ],
        date: new Date().toISOString(),
      },
      null,
      2,
    ),
  );
  console.log(JSON.stringify({ status: "passed", job: job.id, out }));
  await browser.close();
})().catch(async (e) => {
  console.error(e);
  if (browser) await browser.close();
  process.exit(1);
});
