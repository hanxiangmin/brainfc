/* Real browser captures. Run after examples/prepare_gallery.py; requires Playwright Chromium. */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const base = process.env.HYPERBRAIN_URL || 'http://127.0.0.1:8765';
const root = path.resolve(__dirname, '../..');
const fixtures = JSON.parse(fs.readFileSync(path.join(root, '.work/gallery-fixtures.json')));
const out = path.join(root, 'website/public/gallery');
fs.mkdirSync(out, { recursive: true });
let browser;
(async () => {
  browser = await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  const page = await browser.newPage({viewport:{width:1600,height:1000}, deviceScaleFactor:1, baseURL:base});
  const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  const gallery=[];
  async function shot(id, en, zh, {n=116,style='envelope',theme='midnight',layer='hypergraph',selected=null,panel=null,full=false}={}) {
    const fixture=fixtures.find(x=>x.n===n);
    const data=await (await page.request.get(`/api/v1/results/${fixture.result_id}/mapped`)).json();
    const view={style,theme,layer,opacity:.2,labels:true,only_selected:false,selection:selected?{kind:'hyperedge',id:JSON.stringify(['string',selected])}:null,camera:{},schema_version:1};
    assert.ok((await page.request.put(`/api/v1/results/${fixture.result_id}/view`,{data:view})).ok());
    await page.goto(`/?result=${fixture.result_id}`);
    const scene=page.getByTestId('brain-scene'); await scene.waitFor();
    await page.waitForFunction(()=>Number(document.querySelector('[data-testid="brain-scene"]')?.dataset.labelCount)>0);
    await page.waitForTimeout(500);
    assert.equal(await page.locator('.style-tabs button').count(),3);
    if(panel==='node'||panel==='edge'){
      await page.getByLabel('查找脑区',{exact:true}).fill(n===116?'PreCG.L':data.metadata.roi_metadata[0].abbreviation);
      await page.locator('.roi-search-list button').first().click();
      if(panel==='edge')await page.locator('.viewer-details .edge-item').first().click();
    }else if(panel) {
      await page.getByRole('button',{name:panel,exact:true}).click();
      if(panel==='连接热图')await page.locator('.js-plotly-plot').waitFor();
      if(panel==='图谱切片核查')await page.waitForTimeout(1800);
    }
    await page.mouse.move(10,10);await page.waitForTimeout(400);
    const file=id+'.png'; await (full?page:scene).screenshot({path:path.join(out,file)});
    const state=await scene.evaluate(e=>({...e.dataset}));
    const selectionText=await page.locator('.viewer-details').innerText();
    if(selected)assert.ok(selectionText.includes(selected));
    if(selected)assert.equal(state.contextNodeAlpha,'0.025');
    const memberIds=selected?data.hypergraph.edges.find(h=>h.id===selected).members:[];
    gallery.push({id,file,en,zh,n,style,theme,layer,selected,panel,full,
      members:memberIds,atlas:fixture.atlas_id,space:fixture.space,version:'0.3.0',
      sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(out,file))).digest('hex'),
      matrix_sha256:fixture.matrix_sha256,rendered:state});
    console.log(`Captured ${id}`);
  }
  for(const [style,en,zh] of [['ballstick','Node-link','节点连线'],['envelope','Envelope','透明包络'],['parcels','Parcel surfaces','分区表面']]){
    for(const [theme,te,tz] of [['midnight','Midnight','深夜蓝'],['paper','Paper','论文白']]){
      await shot(`${style}-${theme}`,`${en} / ${te}`,`${zh} / ${tz}`,{style,theme,selected:'H06'});
    }
  }
  for(const [key,en,zh] of [['H03','Three members: triangle','三成员：三角面'],['H04','Four members: envelope','四成员：空间包络'],['H08','Eight members: envelope','八成员：空间包络'],['H12','Twelve members: envelope','十二成员：空间包络']]){
    await shot('envelope-'+key.toLowerCase(),en,zh,{selected:key});
    await shot('anchor-'+key.toLowerCase(),en+' / H anchor',zh+' / H 锚点',{style:'ballstick',selected:key});
  }
  await shot('hero','Native hyperedges, in anatomical space','解剖空间中的原生超边',{selected:'H06',full:true,style:'ballstick'});
  await shot('global-hypergraph','Complete synthetic hypergraph','合成超图全局视图');
  await shot('graph-global','Signed pairwise connections','有符号普通图',{layer:'graph',style:'ballstick'});
  await shot('overlay','Graph and hypergraph overlay','普通图与超图叠加',{layer:'both',style:'ballstick'});
  await shot('node-focus','Select a region and its memberships','选择脑区及其关联结构',{style:'ballstick',layer:'both',panel:'node',full:true});
  await shot('edge-focus','Inspect a signed connection','查看一条有符号连接',{style:'ballstick',layer:'both',panel:'edge',full:true});
  await shot('linked-heatmap','Selection linked to the connectivity matrix','选择与连接矩阵联动',{selected:'H06',panel:'连接热图',full:true});
  await shot('members','Native hyperedge IDs and complete members','原生超边 ID 与完整成员表',{selected:'H04-repeat',panel:'脑区与超边成员表',full:true});
  await shot('atlas-slices','Verify parcellation against its reference','分割图谱与参考脑切片核查',{panel:'图谱切片核查',full:true});
  for(const n of [90,200,400])await shot(`atlas-${n}`,`${n} regions / complete structure`,`${n} 脑区 / 完整结构`,{n,style:'parcels',layer:'hypergraph',theme:'paper'});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify({data:'Synthetic demonstrations; no patient data. Custom sets illustrate rendering, not biological systems.',
    generation:'examples/prepare_gallery.py',capture:'frontend/scripts/capture-gallery.cjs',fixtures:fixtures.map(({result_id,...f})=>f),gallery},null,2)+'\n');
  console.log(JSON.stringify({screenshots:gallery.length,errors}));await browser.close();
})().catch(async e=>{console.error(e);await browser?.close();process.exitCode=1;});
