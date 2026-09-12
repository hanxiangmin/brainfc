"""Bundled OpenAPI reader: no CDN, external fonts, or downloaded scripts."""

REFERENCE_HTML = r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>BrainFC Networks · 本地 API 参考</title>
<style>
body{font:16px/1.7 system-ui,sans-serif;color:#18354a;background:#f5fafc;margin:0;padding:32px}
main{max-width:1050px;margin:auto}a{color:#007da3}h1{line-height:1.3}section{background:white;border:1px solid #c8dfe9;border-radius:12px;margin:18px 0;padding:22px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eaf5fa;padding:18px;border-radius:8px;font-size:13px}
code{font-family:ui-monospace,monospace}summary{cursor:pointer}h2{font-size:18px}.method{color:#007da3;margin-right:14px}
</style><main>
<a href="/">← 返回分析工作区</a><h1>BrainFC Networks 本地 API</h1>
<p>所有路由调用同一份 Python 分析核心。服务地址为当前页面所在的回环地址。</p>
<p><a href="./openapi.json" download="hicbrain-openapi.json">下载 OpenAPI JSON</a> · 本页面全部资源保存在本机。</p>
<section><h2>上传 → 分析 → 结果</h2><pre>POST /api/v1/uploads     multipart/form-data，files 字段可重复
POST /api/v1/jobs        提交上传文件 ID、读取选项与分析参数
GET  /api/v1/jobs/{id}   查询进度、错误与结果 ID
GET  /api/v1/results/{id}
GET  /api/v1/results/{id}/export?format=zip
POST /api/v1/jobs/{id}/cancel
POST /api/v1/jobs/{id}/retry</pre>
<p>提交任务示例（将 file_ids 替换为上传返回的 ID）：</p>
<pre>{
  "file_ids": ["UPLOAD_ID"],
  "input": {"kind": "timeseries", "variable": "ROISignals", "roi_columns": "0:116"},
  "analysis": {"connectivity_method": "pearson", "graph_method": "density", "density": 0.1,
               "hypergraph_method": "multiscale", "hypergraph_ks": [5, 10]}
}</pre>
<p>input 支持 kind、variable、roi_columns、matrix_kind、preset、roi_ids、labels、coordinates、metadata。
矩阵类型 matrix_kind 为 correlation、fisher_z 或 covariance；ROI 时序采用时间点 × 脑区方向。</p>
<p>导出格式：zip、json、csv（多表 ZIP）、html、png、svg、pdf、graphml、hyperedges。
批量任务中的 errors 按文件记录；completed 仍需检查 errors 判断每个文件是否成功。</p></section>
<section><h2>队列统计</h2><pre>POST /api/v1/statistics
{"rows": [{"subject_id": "p01", "group": "A", "feature": 0.42}],
 "subject_column": "subject_id", "group_column": "group", "feature_columns": ["feature"],
 "covariates": []}</pre><p>上例仅展示表结构。比较需要两组、每组至少两个独立受试者；重复受试者 ID 会被拒绝。
协变量字段使用数值列，类别协变量请先按研究设计编码。</p></section>
<h2>当前版本的路由与数据结构</h2><div id="routes">正在读取本地接口描述…</div>
<script>
fetch('./openapi.json').then(r=>{if(!r.ok)throw Error('接口描述不可用');return r.json()}).then(schema=>{
const root=document.getElementById('routes');root.replaceChildren();
for(const [path, methods] of Object.entries(schema.paths))for(const [method,operation] of Object.entries(methods)){
const section=document.createElement('section'), title=document.createElement('h2'), badge=document.createElement('span');
badge.className='method';badge.textContent=method.toUpperCase();title.append(badge,document.createTextNode(path));section.append(title);
const details=document.createElement('details'), summary=document.createElement('summary'), pre=document.createElement('pre');
summary.textContent=operation.summary||'请求与响应';pre.textContent=JSON.stringify(operation,null,2);details.append(summary,pre);section.append(details);root.append(section);
}
const section=document.createElement('section'), details=document.createElement('details'), summary=document.createElement('summary'), pre=document.createElement('pre');
summary.textContent='共享 JSON schemas';pre.textContent=JSON.stringify(schema.components||{},null,2);details.append(summary,pre);section.append(details);root.append(section);
}).catch(e=>{document.getElementById('routes').textContent=e.message});
</script></main></html>'''
