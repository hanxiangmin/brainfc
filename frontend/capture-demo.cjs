const { chromium } = require('playwright');
const path = require('node:path');
const fs = require('node:fs');
const root = path.resolve(__dirname, '..');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.FMRI_TEST_CHROMIUM || undefined, args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage({viewport:{width:1500,height:1280},deviceScaleFactor:1});
    const errors=[]; page.on('pageerror', e => errors.push(e.message));
    await page.goto('http://127.0.0.1:8766/?job='+process.env.FMRI_TEST_JOB);
    await page.getByRole('heading',{name:'连接分析结果',exact:true}).waitFor();
    await page.getByTestId('brain-scene').waitFor();
    await page.getByRole('button',{name:'右前斜',exact:true}).click();
    await page.screenshot({path:path.join(root,'docs','interface-preview.png')});
    await page.getByRole('button',{name:'脑区八视图',exact:true}).click();
    await page.waitForFunction(()=>{const img=document.querySelector('.eight-views');return img?.complete&&img.naturalWidth>0});
    await page.screenshot({path:path.join(root,'.work/browser-qa','07-standard-atlas.png')});
    await page.setViewportSize({width:390,height:844});
    await page.getByRole('button',{name:'功能连接矩阵',exact:true}).click();
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1);
    if(overflow)throw new Error('Mobile viewport has horizontal overflow');
    if(errors.length)throw new Error(errors.join('\n'));
    fs.writeFileSync(path.join(root,'.work/browser-qa','standard-atlas.json'),JSON.stringify({job:process.env.FMRI_TEST_JOB,standard_atlas:100,query_link:true,mobile_overflow:false,page_errors:errors},null,2));
    console.log('Standard atlas view, direct result link and mobile width passed');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1)});
