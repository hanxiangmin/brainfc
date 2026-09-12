// Portable release smoke: isolated workspace/server and newly generated inputs.
const { chromium } = require("playwright");
const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const net = require("node:net");
const assert = require("node:assert/strict");
const root = path.resolve(__dirname, "..");
const output = path.join(root, ".work", "release-browser", String(Date.now()));
fs.mkdirSync(output, { recursive: true });
const localPython = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const python = process.env.FMRI_TEST_PYTHON || (fs.existsSync(localPython) ? localPython : "python");
let child, browser, page, logfile;
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function freePort() {
  return new Promise((resolve) => {
    const socket = net.createServer();
    socket.listen(0, "127.0.0.1", () => {
      const port = socket.address().port;
      socket.close(() => resolve(port));
    });
  });
}
async function main() {
  const port = await freePort();
  const base = `http://127.0.0.1:${port}`;
  logfile = fs.openSync(path.join(output, "server.log"), "w");
  child = spawn(python, ["-m", "brainfc", "serve", "--port", String(port), "--workspace", path.join(output, "workspace"), "--no-browser"], { cwd: root, stdio: ["ignore", logfile, logfile], windowsHide: true, env: { ...process.env, PYTHONUTF8: "1" } });
  child.on("error", (error) => console.error(error));
  let ready = false;
  for (let i = 0; i < 100; i++) {
    try { ready = (await fetch(base + "/api/health")).ok; } catch {}
    if (ready) break;
    await delay(200);
  }
  assert.ok(ready, "Temporary server did not start");
  browser = await chromium.launch({ headless: true, executablePath: process.env.FMRI_TEST_CHROMIUM || undefined, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
  page = await browser.newPage({ baseURL: base, viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  assert.equal(await page.locator(".primary").first().evaluate(el => getComputedStyle(el).backgroundColor), "rgb(0, 125, 163)");
  await page.screenshot({ path: path.join(output, "extraction-home.png"), fullPage: true });
  assert.ok(await page.getByRole("navigation", { name: "处理步骤" }).getByRole("button").nth(1).isDisabled());
  // UI-only native workflow fixture: numerical algorithms are tested separately.
  const rawDir = path.join(output, "raw-fixture");
  const prepared = spawnSync(python, ["-c", `from pathlib import Path; import nibabel as n, numpy as np; p=Path(${JSON.stringify(rawDir)}); p.mkdir(); a=np.diag([2.,2.,2.,1.])\nfor name,shape in [('bold',(12,14,16,30)),('t1w',(12,14,16))]:\n im=n.Nifti1Image(np.random.default_rng(7).random(shape).astype('float32'),a); im.header.set_xyzt_units('mm','sec'); n.save(im,p/(name+'.nii.gz'))`], { cwd: root, encoding: "utf8", windowsHide: true });
  assert.equal(prepared.status, 0, prepared.stderr);
  await page.getByLabel("本次输入类别", { exact: true }).selectOption("raw-bids");
  await page.getByLabel("静息态 BOLD", { exact: true }).fill(path.join(rawDir, "bold.nii.gz"));
  await page.getByLabel("T1 结构像", { exact: true }).fill(path.join(rawDir, "t1w.nii.gz"));
  await page.getByRole("button", { name: "检查并生成方案" }).click();
  await page.getByText(/缺少切片采集时间/).waitFor();
  assert.ok(await page.getByRole("button", { name: "确认方案，开始 Python 处理" }).isDisabled());
  assert.equal(await page.getByLabel("FreeSurfer license.txt").count(), 0);
  await page.getByRole("checkbox", { name: /明确跳过层间时间校正/ }).check();
  await page.getByRole("button", { name: "检查并生成方案" }).click();
  await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent.includes('确认方案，开始 Python 处理') && !b.disabled));
  const fakeId = "f".repeat(32);
  const fake = { id: fakeId, kind: "python-preprocess", status: "complete", message: "UI fixture", run: {
    bold: path.join(rawDir, "bold.nii.gz"), mask: "", confounds: "", t_r: 1,
    space: "MNI152NLin6Asym", discard: 0, confound_columns: ["motion_matrix_00", "csf"],
  }};
  await page.route("**/api/python/preprocess", r => r.fulfill({ json: fake }));
  await page.getByRole("button", { name: "确认方案，开始 Python 处理" }).click();
  await page.getByRole("link", { name: /打开完整质控报告/ }).waitFor();
  assert.ok(await page.getByRole("button", { name: "继续提取功能连接 →" }).isDisabled());
  await page.getByRole("checkbox", { name: /我已检查配准、脑覆盖/ }).check();
  assert.ok(await page.getByRole("button", { name: "继续提取功能连接 →" }).isEnabled());
  await page.locator(".raw-guide").screenshot({ path: path.join(output, "native-qc-gate.png") });
  await page.getByRole("button", { name: "继续提取功能连接 →" }).click();
  await page.getByText("已选择预处理输出：bold.nii.gz", { exact: true }).waitFor();
  await page.unroute("**/api/python/preprocess");
  await page.goto(base);
  await page.getByRole("button", { name: "打开真实样例" }).click();
  await page.getByTestId("brain-scene").waitFor({ timeout: 120000 });
  await page.waitForFunction(() => document.querySelector('[data-testid="brain-scene"]')?.dataset.renderMs);
  const jobs = await (await page.request.get("/api/jobs")).json();
  const demo = jobs.find((job) => job.kind === "demo" && job.status === "complete");
  assert.ok(demo);
  const result = await (await page.request.get(`/api/jobs/${demo.id}/files/result.json`)).json();
  assert.equal(demo.example_kind, "rest01");
  assert.equal(result.qc.n_rois, 100);
  assert.equal(result.sample_indices.length, 145);
  assert.equal(result.provenance.synthetic, false);
  assert.equal(result.provenance.example.sample_id, "rest01");
  await page.getByText("真实静息态样例 · rest01 · 已脱敏", { exact: false }).waitFor();
  await page.locator(".viewer-card").screenshot({ path: path.join(output, "brain.png") });
  await page.getByRole("button", { name: "功能连接矩阵", exact: true }).click();
  const matrix = page.locator(".matrix-wrap canvas");
  const box = await matrix.boundingBox();
  await matrix.click({ position: { x: box.width * .5 / 100, y: box.height * .5 / 100 } });
  await page.getByTestId("brain-scene").waitFor();
  const threshold = page.getByRole("slider", { name: "显示连接阈值" });
  await threshold.fill("0.2");
  await threshold.dispatchEvent("input");
  const ids = await page.locator(".scene-shell").getAttribute("data-edge-ids");
  assert.ok(ids.length > 0);
  await page.getByRole("button", { name: "脑区八视图", exact: true }).click();
  await page.waitForFunction(() => { const img = document.querySelector("img.eight-views"); return img?.complete && img.naturalWidth > 0; });
  assert.equal(await page.getByTestId("synced-views").getAttribute("data-edge-ids"), ids);
  await page.getByTestId("synced-views").screenshot({ path: path.join(output, "eight-views.png") });
  const svgUrl = await page.getByRole("link", { name: "SVG ↓", exact: true }).getAttribute("href");
  assert.equal((await page.request.get(svgUrl)).status(), 200);
  // Continue from a real extraction result without any file upload or ROI re-entry.
  await page.getByRole("link", { name: "进入网络分析 →", exact: true }).click();
  await page.getByText("已从 BrainFC 提取结果自动接入", { exact: false }).waitFor();
  assert.equal(await page.getByRole("button", { name: "开始建模分析", exact: true }).evaluate(el => getComputedStyle(el).backgroundColor), "rgb(0, 125, 163)");
  await page.screenshot({ path: path.join(output, "network-config.png"), fullPage: true });
  assert.equal(await page.locator(".connectivity-config").count(), 0);
  await page.getByRole("button", { name: "开始建模分析", exact: true }).click();
  let networkJob;
  for (let i = 0; i < 180; i++) {
    const queue = await (await page.request.get("/networks/api/v1/jobs")).json();
    networkJob = queue.jobs[0];
    if (networkJob && !["queued", "running"].includes(networkJob.status)) break;
    await delay(500);
  }
  assert.equal(networkJob.status, "completed", JSON.stringify(networkJob));
  assert.deepEqual(networkJob.errors, []);
  const networkId = networkJob.results[0].id;
  const network = await (await page.request.get(`/networks/api/v1/results/${networkId}`)).json();
  assert.deepEqual(network.connectivity, result.connectivity);
  assert.deepEqual(network.roi_ids, result.rois.map(r => r.roi_id));
  assert.deepEqual(network.metadata.sample_indices, result.sample_indices);
  assert.deepEqual(network.metadata.brainfc_geometry, result.geometry);
  await page.goto(`/networks/?result=${networkId}`);
  await page.getByTestId("brain-workbench").waitFor({ timeout: 60000 });
  await page.getByText("● 已验证脑区顺序", { exact: true }).waitFor();
  await page.getByTestId("brain-scene").waitFor();
  assert.equal(await page.getByLabel("图谱", { exact: true }).inputValue(), "brainfc-result");
  assert.ok((await page.getByTestId("brain-workbench").getAttribute("class")).includes("paper"));
  await page.getByRole("button", { name: "超图", exact: true }).click();
  await page.getByRole("button", { name: /透明包络/ }).click();
  await delay(500);
  await page.getByTestId("brain-workbench").screenshot({ path: path.join(output, "network-workbench.png") });
  const networkExport = await page.request.get(`/networks/api/v1/results/${networkId}/export?format=json`);
  assert.equal(networkExport.status(), 200);
  assert.deepEqual((await networkExport.json()).connectivity, result.connectivity);
  const report = await page.request.get(`/api/jobs/${demo.id}/files/report.html`);
  const offline = path.join(output, "report.html");
  fs.writeFileSync(offline, await report.body());
  await page.goto(require("node:url").pathToFileURL(offline).href);
  await page.getByTestId("brain-scene").waitFor();
  await page.getByRole("button", { name: "脑区八视图", exact: true }).click();
  await page.waitForFunction(() => { const img = document.querySelector("img.eight-views"); return img?.complete && img.naturalWidth > 0; });
  // Upload a headerless ROI table and complete the documented three-step workflow.
  const fixture = path.join(output, "signals.1D");
  fs.writeFileSync(fixture, Array.from({ length: 60 }, (_, t) => [Math.sin(t / 3), Math.cos(t / 5), Math.sin(t / 4)].join(" ")).join("\n"));
  await page.goto(base);
  await page.getByLabel("选择fMRI / ROI 时序", { exact: true }).setInputFiles(fixture);
  await page.locator(".chosen-file").waitFor();
  await page.getByRole("checkbox", { name: /我确认这是单次扫描的 ROI 时序/ }).check();
  await page.getByRole("button", { name: "识别文件并继续 →", exact: true }).click();
  await page.getByRole("heading", { name: "核对脑区顺序与可选坐标" }).waitFor();
  assert.ok((await page.locator(".input-facts").innerText()).includes("60 个时间点"));
  await page.getByLabel("去噪选择", { exact: true }).selectOption("upstream");
  await page.getByRole("button", { name: "核对方案，进入复核 →", exact: true }).click();
  await page.getByRole("checkbox", { name: /我已核对本次扫描参数/ }).check();
  await page.getByRole("button", { name: "开始处理并提取矩阵 →" }).click();
  await page.getByRole("heading", { name: "连接分析结果", exact: true }).waitFor({ timeout: 60000 });
  const tableJobs = await (await page.request.get(base + "/api/jobs")).json();
  const table = tableJobs.find((job) => job.kind === "extract" && job.status === "complete");
  assert.ok(table);
  assert.equal(table.qc.n_input, 60);
  await page.goto(base + "/reference/");
  await page.getByRole("heading", { name: "BrainFC 文档", exact: true }).waitFor();
  await page.screenshot({ path: path.join(output, "manual.png"), fullPage: true });
  await page.getByRole("link", { name: "全部函数与参数", exact: true }).first().click();
  await page.getByRole("heading", { name: "extract_connectome", exact: true }).waitFor();
  await page.setViewportSize({ width: 390, height: 900 });
  const mobile = await page.evaluate(() => ({
    fits: document.documentElement.scrollWidth <= innerWidth + 2,
    overflow: Array.from(document.querySelectorAll("main h1,main h2,main h3,main p,main pre,main table")).filter(el => el.getBoundingClientRect().right > innerWidth + 2).map(el => ({tag: el.tagName, text: el.textContent.slice(0, 100)})),
  }));
  assert.ok(mobile.fits, JSON.stringify(mobile));
  assert.deepEqual(errors, []);
  fs.writeFileSync(path.join(output, "validation.json"), JSON.stringify({ status: "passed", demo: demo.id, table: table.id, network: networkId, checks: ["isolated server", "demo extraction", "matrix selection", "3D/eight exact edge synchronization", "SVG", "extraction to network handoff", "unchanged matrix and ROI order", "inherited geometry without downloads", "hypergraph envelope", "network export", "offline HTML", "headerless upload wizard", "bundled manual navigation", "mobile manual"], errors }, null, 2));
  console.log(JSON.stringify({ status: "passed", evidence: output }));
}
main().catch(async (error) => {
  console.error(error);
  if (page) await page.screenshot({ path: path.join(output, "failure.png"), fullPage: true }).catch(() => {});
  process.exitCode = 1;
}).finally(async () => {
  if (browser) await browser.close();
  // Terminate only the process tree created above, never an existing user server.
  if (child?.pid) {
    if (process.platform === "win32") spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
    else child.kill("SIGTERM");
  }
  if (logfile !== undefined) fs.closeSync(logfile);
});
