const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const code = ts.transpileModule(fs.readFileSync('src/viewerTypes.ts','utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const context = { exports: {} }; vm.runInNewContext(code, context);
const { edgesOf, hyperedgesOf, selectionMembers, related } = context.exports;
const plain = value => JSON.parse(JSON.stringify(value));

test('compact atlas names preserve hemisphere and parcel number without changing originals',()=>{
 const roi={roi_id:'7',abbreviation:'7Networks_LH_Vis_7',name:'7Networks_LH_Vis_7'};
 assert.equal(context.exports.shortRoiName(roi),'L · Vis 7');
 assert.equal(context.exports.shortRoiName({...roi,abbreviation:'7Networks_RH_Vis_7'}),'R · Vis 7');
 assert.equal(roi.name,'7Networks_LH_Vis_7');
});

test('legacy ordinary edge identifiers are invariant under endpoint order', () => {
 const one = edgesOf({graph:{edges:[{source:'left',target:'right',weight:-.3}]}});
 const two = edgesOf({graph:{edges:[{source:'right',target:'left',weight:-.3}]}});
 assert.equal(one[0].id,two[0].id);
 assert.equal(one[0].weight,-.3);
});
test('mixed numeric/string hyperedge IDs and duplicate memberships remain independently selectable', () => {
 const original={hypergraph:{edges:[{id:1,members:['a','b','c'],weight:.2},{id:'1',members:['a','b','c'],weight:-.4}]}};
 const before=JSON.stringify(original), h=hyperedgesOf(original);
 assert.notEqual(h[0].id,h[1].id);
 assert.equal(h[0].source_id,1); assert.equal(h[1].source_id,'1');
 for(const e of h)assert.deepEqual([...selectionMembers({kind:'hyperedge',id:e.id},[],h)],['a','b','c']);
 assert.equal(JSON.stringify(original),before);
});
test('hyperedge selection excludes nonmembers even if a geometry envelope surrounds them',()=>{
 const h=hyperedgesOf({hypergraph:{edges:[{id:'set',members:['a','b','c']}]}});
 const focus=related({kind:'hyperedge',id:h[0].id},[{id:'pair',source:'a',target:'inside-but-not-member'}],h);
 assert.deepEqual([...focus.nodes],['a','b','c']); assert.equal(focus.edgeIds.size,0);
 assert.equal(focus.hyperIds.size,1);
});
test('node selection follows ordinary adjacency and complete hyperedge memberships',()=>{
 const edges=[{id:'e1',source:'a',target:'b'},{id:'e2',source:'d',target:'e'}];
 const hypers=[{id:'h1',members:['a','c','d']},{id:'h2',members:['e']}];
 const focus=related({kind:'node',id:'a'},edges,hypers);
 assert.deepEqual([...focus.nodes].sort(),['a','b','c','d']);
 assert.deepEqual([...focus.edgeIds],['e1']); assert.deepEqual([...focus.hyperIds],['h1']);
});
test('normalizing graph and hypergraph display records preserves source data',()=>{
 const result={graph:{edges:[{id:'stable',source:'a',target:'b',weight:.8}]},hypergraph:{edges:[{id:'h',members:['a','b']}]}};
 const before=plain(result);edgesOf(result);hyperedgesOf(result);assert.deepEqual(result,before);
});

const appearanceContext = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync('src/viewerAppearance.ts','utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, appearanceContext);
const { emphasis, objectAlpha, labelAlpha } = appearanceContext.exports;

test('a selected hyperedge emphasizes only its own identity and complete members',()=>{
 const selected={kind:'hyperedge',id:'h1'},focus=related(selected,[],[{id:'h1',members:['a','b','c']},{id:'h2',members:['a','b','c']}]);
 assert.equal(emphasis({kind:'hyperedge',id:'h1'},selected,focus),'primary');
 assert.equal(emphasis({kind:'hyperedge',id:'h2'},selected,focus),'context');
 for(const id of ['a','b','c'])assert.equal(emphasis({kind:'node',id},selected,focus),'primary');
 assert.equal(emphasis({kind:'node',id:'inside-but-not-member'},selected,focus),'context');
 assert.ok(objectAlpha('context','node')<=.03);
 assert.ok(objectAlpha('context','surface')<=.003);
});
test('a selected node stays stronger than its neighbors and their labels',()=>{
 const selected={kind:'node',id:'a'},focus=related(selected,[{id:'ab',source:'a',target:'b'}],[]);
 assert.equal(emphasis({kind:'node',id:'a'},selected,focus),'primary');
 assert.equal(emphasis({kind:'node',id:'b'},selected,focus),'related');
 assert.equal(emphasis({kind:'node',id:'c'},selected,focus),'context');
 assert.ok(labelAlpha.primary>labelAlpha.related&&labelAlpha.related>labelAlpha.context);
 assert.ok(objectAlpha('primary','node')>=3*objectAlpha('related','node'));
});
test('dense global envelopes reduce ink without hiding any structure',()=>{
 const small=objectAlpha('global','surface',10),large=objectAlpha('global','surface',400);
 assert.ok(large>0&&large<small);
 assert.ok(objectAlpha('global','outline',400)>0);
 assert.ok(objectAlpha('global','edge',400,true)<objectAlpha('global','edge',400,false));
});
