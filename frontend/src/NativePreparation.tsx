import { useEffect, useState } from "react";

async function request(path: string, body: any) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
  return data;
}

export default function NativePreparation({ kind, job, busy, onJob, onError, onReady }: {
  kind: string; job: any; busy: boolean; onJob: (job: any) => void;
  onError: (error: any) => void; onReady: (run: any) => void;
}) {
  const [paths, setPaths] = useState({ bold: "", t1w: "", sidecar: "" });
  const [config, setConfig] = useState({ slice_timing: "auto", slice_axis: "", t_r: "", discard: 0, smoothing_fwhm: 0 });
  const [source, setSource] = useState("");
  const [series, setSeries] = useState<any[]>([]);
  const [selection, setSelection] = useState({ bold_series: "", t1_series: "" });
  const [plan, setPlan] = useState<any>(null);
  const [active, setActive] = useState("");
  const [phase, setPhase] = useState(0);
  const [localBusy, setLocalBusy] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [converted, setConverted] = useState(false);
  const [session] = useState(() => crypto.randomUUID().replaceAll("-", ""));
  const [bids, setBids] = useState("");
  const [runs, setRuns] = useState<any[]>([]);
  const disabled = busy || localBusy;
  const ownJob = job?.id === active ? job : null;
  const body = () => ({ ...paths, sidecar: paths.sidecar || null,
    config: { ...config, t_r: config.t_r ? Number(config.t_r) : null,
      slice_axis: config.slice_axis === "" ? null : Number(config.slice_axis) } });
  const change = (key: string, value: string) => {
    setPaths(p => ({ ...p, [key]: value })); setPlan(null); setReviewed(false);
  };
  const action = async (fn: () => Promise<void>) => {
    setLocalBusy(true);
    try { await fn(); } catch (error) { onError(error); } finally { setLocalBusy(false); }
  };
  useEffect(() => {
    if (!active && job && ["queued", "running", "complete"].includes(job.status) &&
        (job.kind === "python-preprocess" || (kind === "raw-dicom" && job.kind === "python-dicom"))) {
      setActive(job.id);
      if (job.kind === "python-preprocess") setPhase(job.status === "complete" ? 2 : 1);
    }
  }, [job?.id, job?.status, kind, active]);
  useEffect(() => {
    if (ownJob?.status === "complete") {
      if (ownJob.kind === "python-dicom") {
        setPaths({ bold: ownJob.converted.bold.image, t1w: ownJob.converted.t1w.image, sidecar: ownJob.converted.bold.sidecar });
        setConverted(true); setPlan(null); setPhase(0);
      } else if (ownJob.kind === "python-preprocess") setPhase(2);
    }
    if (ownJob?.status === "failed") setPhase(0);
  }, [ownJob?.id, ownJob?.status]);

  const fileField = (key: keyof typeof paths, title: string) => <label>{title}
    <input aria-label={title} value={paths[key]} placeholder="本机文件路径" onChange={e => change(key, e.target.value)} />
    <input aria-label={`选择${title}`} type="file" accept={key === "sidecar" ? ".json" : ".nii,.gz"}
      onChange={e => { const file = e.target.files?.[0]; if (!file) return;
        action(async () => { const form = new FormData(); form.append("session", session); form.append("file", file);
          const response = await fetch("/api/upload", { method: "POST", body: form }); const data = await response.json();
          if (!response.ok) throw new Error(data.detail); change(key, data.path); }); e.target.value = ""; }} />
  </label>;
  return <div className="raw-guide">
    <p className="workflow-route">选择影像 → 确认处理方案 → 检查质控 → 提取功能连接</p>
    <div className="raw-stages">{["影像与方案", "Python 预处理", "质量检查"].map((name, i) =>
      <span key={name} className={phase === i ? "active" : ""}>{i + 1}. {name}</span>)}</div>
    {phase === 0 && <fieldset disabled={disabled}>
      {kind === "raw-dicom" && !converted ? <>
        <label>DICOM 文件夹<input value={source} onChange={e => { setSource(e.target.value); setSeries([]); }} /></label>
        <button disabled={!source} onClick={() => action(async () => {
          const found = await request("/api/python/dicom/scan", { path: source }); setSeries(found);
          const one = (name: string) => { const matches = found.filter((s: any) => s.candidate === name); return matches.length === 1 ? matches[0].series_id : ""; };
          setSelection({ bold_series: one("bold"), t1_series: one("t1w") });
        })}>识别扫描序列</button>
        {series.length > 0 && <>
          <p className="muted">已按扫描说明推荐序列，请确认 BOLD 与 T1 属于同一次检查。</p>
          {(["bold_series", "t1_series"] as const).map(key => <label key={key}>{key === "bold_series" ? "静息态 BOLD" : "T1 结构像"}
            <select value={selection[key]} onChange={e => setSelection({ ...selection, [key]: e.target.value })}>
              <option value="">选择序列</option>{series.map((s, i) => <option key={s.series_id} value={s.series_id}>
                序列 {i + 1} · {s.candidate} · {s.file_count} 文件{s.t_r ? ` · TR ${s.t_r} s` : ""}</option>)}
            </select></label>)}
          <button className="primary" disabled={!selection.bold_series || !selection.t1_series || selection.bold_series === selection.t1_series}
            onClick={() => action(async () => { const j = await request("/api/python/dicom/run", { source, ...selection }); setActive(j.id); onJob(j); })}>
            转换所选影像</button>
        </>}
      </> : <>
        <p>选择同一次检查的静息态 BOLD 和 T1，采集参数会自动读取。输出位置自动安排。</p>
        {!converted && <details><summary>从 BIDS 文件夹自动查找</summary>
          <label>BIDS 文件夹<input value={bids} onChange={e => setBids(e.target.value)} /></label>
          <button disabled={!bids} onClick={() => action(async () => setRuns(await request("/api/python/discover", { path: bids })))}>查找扫描</button>
          {runs.map(r => <button key={r.bold} onClick={() => { setPaths({ bold: r.bold, t1w: r.t1w, sidecar: r.sidecar || "" }); setPlan(null); }}>
            {r.label}</button>)}
        </details>}
        {fileField("bold", "静息态 BOLD")}{fileField("t1w", "T1 结构像")}
        <details><summary>采集 JSON 与高级设置（通常自动读取）</summary>
          {fileField("sidecar", "采集 JSON")}
          <label>TR（秒；留空自动读取）<input type="number" min="0" step="any" value={config.t_r}
            onChange={e => { setConfig({ ...config, t_r: e.target.value }); setPlan(null); }} /></label>
          <label>切片维度<select value={config.slice_axis} onChange={e => { setConfig({ ...config, slice_axis: e.target.value }); setPlan(null); }}>
            <option value="">从 JSON / 影像头读取</option><option value="0">i（第 1 维）</option><option value="1">j（第 2 维）</option><option value="2">k（第 3 维）</option>
          </select></label>
          <label>去除开头帧数<input type="number" min="0" step="1" value={config.discard}
            onChange={e => { setConfig({ ...config, discard: Number(e.target.value) }); setPlan(null); }} /></label>
          <label>空间平滑 FWHM（mm；0 表示不做）<input type="number" min="0" value={config.smoothing_fwhm}
            onChange={e => { setConfig({ ...config, smoothing_fwhm: Number(e.target.value) }); setPlan(null); }} /></label>
        </details>
        <label className="check"><input type="checkbox" checked={config.slice_timing === "skip"}
          onChange={e => { setConfig({ ...config, slice_timing: e.target.checked ? "skip" : "auto" }); setPlan(null); }} />
          明确跳过层间时间校正（例如缺少可靠采集时间）</label>
        <button disabled={!paths.bold || !paths.t1w} onClick={() => action(async () => setPlan(await request("/api/python/inspect", body())))}>检查并生成方案</button>
        {plan && <div className="decision-panel">
          <p>{plan.shape[3]} 帧 · TR {plan.t_r} 秒 · {plan.space} · 2 mm</p>
          <p>{plan.steps.join(" → ")}</p>
          {plan.missing.map((message: string) => <p className="warning" key={message}>{message}</p>)}
          <p className="muted">请确认两幅影像来自同一人、BOLD 为单回波静息态，且成人模板适合本次数据。此流程不做场图畸变校正。</p>
          <button className="primary" disabled={!plan.ready} onClick={() => action(async () => {
            const j = await request("/api/python/preprocess", body()); setActive(j.id); setReviewed(false); setPhase(1); onJob(j);
          })}>确认方案，开始 Python 处理</button>
        </div>}
      </>}
    </fieldset>}
    {phase === 1 && <p>正在处理，完成后自动进入质量检查。{ownJob?.message}</p>}
    {phase === 2 && ownJob?.run && <fieldset disabled={disabled}>
      <p>检查脑提取、脑室与皮层对齐、组织位置及头动，再继续计算功能连接。</p>
      <a href={`/api/jobs/${active}/preprocessing/qc.html`} target="_blank" rel="noreferrer">打开完整质控报告 ↗</a>
      <img style={{ width: "100%", borderRadius: 12 }} src={`/api/jobs/${active}/preprocessing/alignment.png`} alt="配准与组织分割质控" />
      <img style={{ width: "100%", borderRadius: 12 }} src={`/api/jobs/${active}/preprocessing/motion.png`} alt="头动和 DVARS" />
      <label className="check"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />
        我已检查配准、脑覆盖、组织分割和头动，确认可继续</label>
      <button className="primary" disabled={!reviewed} onClick={() => onReady(ownJob.run)}>继续提取功能连接 →</button>
      <button onClick={() => { setPhase(0); setPlan(null); setReviewed(false); }}>调整设置并重新处理</button>
    </fieldset>}
  </div>;
}
