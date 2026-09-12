// Capture the actual report viewer and Archify's clean diagram exports.
// Usage: node capture-readme.cjs /absolute/path/to/report.html
// Set FMRI_TEST_CHROMIUM when using an existing Chromium installation.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const assets = path.join(root, 'docs/assets');

async function main() {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.FMRI_TEST_CHROMIUM || undefined,
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1050}, deviceScaleFactor: 1});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    if (process.argv[2]) {
      await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);
      await page.getByTestId('brain-scene').waitFor();
      await page.waitForFunction(() => document.querySelector('[data-testid="brain-scene"]')?.dataset.renderMs);
      const theme = page.getByRole('button', {name: '深色', exact: true});
      if (await theme.count()) await theme.click();
      const limit = page.locator('.shared-controls select');
      await limit.selectOption('200');
      await page.locator('.viewer-card').screenshot({path: path.join(assets, 'viewer.png')});
      const ids = await page.locator('.scene-shell').getAttribute('data-edge-ids');
      await page.getByRole('button', {name: '脑区八视图', exact: true}).click();
      await page.waitForFunction(() => {const img=document.querySelector('img.eight-views');return img?.complete && img.naturalWidth>0;});
      assert.equal(await page.getByTestId('synced-views').getAttribute('data-edge-ids'), ids);
      await page.locator('img.eight-views').screenshot({path: path.join(assets, 'eight-views.png')});
    }
    await page.goto(pathToFileURL(path.join(assets, 'processing.html')).href);
    await page.waitForFunction(() => document.querySelector('svg'));
    // Use the viewer's export API through its visible controls. Excludes all UI chrome.
    for (const format of ['svg', 'png']) {
      await page.locator('#btn-export').click();
      const pending = page.waitForEvent('download');
      await page.locator(`button[data-format="${format}"]`).click();
      const download = await pending;
      await download.saveAs(path.join(assets, `processing.${format}`));
      if (format === 'svg') {
        const file = path.join(assets, 'processing.svg');
        fs.writeFileSync(file, fs.readFileSync(file, 'utf8').replace(/[ \t]+$/gm, ''));
      }
    }
    assert.equal(errors.length, 0, errors.join('\n'));
    console.log('Captured actual viewer, synchronized eight views, and clean workflow PNG/SVG.');
  } finally { await browser.close(); }
}
main().catch(error => {console.error(error); process.exitCode=1;});
