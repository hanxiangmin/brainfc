/* Actual application screenshots during a continuous OrbitControls drag. */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..');
const out = path.join(root, '.work/orbit-frames');
fs.mkdirSync(out, { recursive: true });
const fixture = JSON.parse(fs.readFileSync(path.join(root, '.work/gallery-fixtures.json'))).find(x => x.n === 116);
const id = fixture.result_id;
const frameCount = 72;
let browser, page, originalView;
const hashes = value => crypto.createHash('sha256').update(value).digest('hex');
(async () => {
  browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1, baseURL: process.env.HYPERBRAIN_URL || 'http://127.0.0.1:8765' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const response = await page.request.get(`/api/v1/results/${id}/mapped`);
  assert.ok(response.ok());
  const data = await response.json();
  originalView = await (await page.request.get(`/api/v1/results/${id}/view`)).json();
  const view = { style: 'ballstick', theme: 'midnight', layer: 'hypergraph', opacity: .2, labels: true,
    only_selected: false, selection: { kind: 'hyperedge', id: JSON.stringify(['string', 'H06']) }, camera: {}, schema_version: 1 };
  assert.ok((await page.request.put(`/api/v1/results/${id}/view`, { data: view })).ok());
  await page.goto(`/?result=${id}`);
  const scene = page.getByTestId('brain-scene');
  await scene.waitFor();
  await page.waitForFunction(() => document.querySelector('[data-testid="brain-scene"]')?.dataset.anchorCount === '7');
  await page.waitForTimeout(900);
  assert.match(await page.locator('.selection-identity').innerText(), /H06/);
  assert.equal(await page.locator('.viewer-details .roi-item').count(), 6);
  const box = await scene.boundingBox();
  const width = box.width, height = box.height;
  assert.ok(width > height + 70, 'Drag should stay inside the scene for the complete orbit.');
  const startX = box.x + width - 38, y = box.y + 92;
  const captures = [];
  async function capture(i, angle) {
    const filename = `rotation-${String(i).padStart(3, '0')}.png`;
    await page.screenshot({ path: path.join(out, filename) });
    assert.match(await page.locator('.selection-identity').innerText(), /H06/);
    assert.equal(await page.locator('.viewer-details .roi-item').count(), 6);
    captures.push({ file: filename, commanded_azimuth_degrees: angle,
      sha256: hashes(fs.readFileSync(path.join(out, filename))) });
  }
  await page.mouse.move(startX, y);
  await capture(0, 0);
  await page.mouse.down();
  for (let i = 1; i <= frameCount; i++) {
    const t = i / frameCount;
    const ease = t * t * (3 - 2 * t);
    // OrbitControls maps one element-height horizontal drag to one azimuth revolution.
    await page.mouse.move(startX - height * ease, y);
    await page.waitForTimeout(110);
    await capture(i, 360 * ease);
    if (i % 12 === 0) console.log(`Rotation: ${i}/${frameCount}`);
  }
  await page.mouse.up();
  await page.mouse.move(10, 10);
  await page.waitForTimeout(1200);
  await capture(frameCount + 1, 360);
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await page.waitForTimeout(250);
  const finalView = await (await page.request.get(`/api/v1/results/${id}/view`)).json();
  assert.deepEqual(finalView.selection, view.selection);
  const after = await (await page.request.get(`/api/v1/results/${id}/mapped`)).json();
  assert.deepEqual(after, data);
  assert.deepEqual(errors, []);
  const members = data.hypergraph.edges.find(edge => edge.id === 'H06').members;
  fs.writeFileSync(path.join(out, 'manifest.json'), JSON.stringify({
    data: 'Synthetic demonstration; actual application rendering.', viewport: [1600, 1000],
    interaction: 'One continuous horizontal drag in the 3D viewer; same selected hyperedge in every frame.',
    style: 'ballstick', theme: 'midnight', selection: 'H06', members,
    atlas: fixture.atlas_id, space: fixture.space, matrix_sha256: fixture.matrix_sha256,
    data_unchanged: true, errors, frames: captures,
  }, null, 2) + '\n');
  console.log(JSON.stringify({ captured: captures.length, hyperedge: 'H06', members: members.length, dataUnchanged: true, errors }));
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
  if (page && originalView) await page.request.put(`/api/v1/results/${id}/view`, { data: originalView });
  await browser?.close();
});
