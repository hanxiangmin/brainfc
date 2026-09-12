import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createRoot } from "react-dom/client";
import BrainScene, { type SceneHandle } from "./vendor/BrainScene";
import {
  defaultView,
  downloadBlob,
  type ROI,
  type Edge,
  type AtlasGeometry,
  type ViewConfig,
  type Selection,
} from "./vendor/viewerTypes";
import "./style.css";
import Workflow from "./Workflow";
import EightViews from "./EightViews";
import { displayEdges } from "./display";
declare const __FMRI_VERSION__: string;

type Result = {
  rois: ROI[];
  connectivity: number[][];
  sample_indices: number[];
  qc: Record<string, any>;
  provenance: Record<string, any>;
  geometry: (AtlasGeometry & { source?: string }) | null;
  views_image?: string;
};
type Job = {
  id: string;
  status: string;
  message: string;
  kind: string;
  atlas?: any;
  result_dir?: string;
};
declare global {
  interface Window {
    __FMRI_REPORT__?: Result;
  }
}
const offline = !!window.__FMRI_REPORT__;
async function api(path: string, body?: any) {
  const response = await fetch(
    path,
    body !== undefined
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
const cameras = [
  ["left", "左侧"],
  ["right", "右侧"],
  ["anterior", "前侧"],
  ["posterior", "后侧"],
  ["superior", "顶部"],
  ["inferior", "底部"],
  ["left-oblique", "左前斜"],
  ["right-oblique", "右前斜"],
];
const EMPTY: any[] = [];

function Matrix({
  result,
  onSelect,
}: {
  result: Result;
  onSelect: (s: Selection | null) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null),
    [tip, setTip] = useState(
      "移动到矩阵单元格查看脑区连接；点击可在三维视图中定位。",
    );
  useEffect(() => {
    const ctx = canvas.current!.getContext("2d")!,
      n = result.rois.length,
      size = 720;
    ctx.clearRect(0, 0, size, size);
    result.connectivity.forEach((row, i) =>
      row.forEach((v, j) => {
        const t = Math.abs(v),
          col = v >= 0 ? [177, 71, 54] : [41, 106, 157];
        ctx.fillStyle = `rgb(${col.map((c) => Math.round(244 + (c - 244) * t)).join(",")})`;
        const x = (j * size) / n,
          y = (i * size) / n;
        ctx.fillRect(x, y, Math.ceil(size / n), Math.ceil(size / n));
      }),
    );
  }, [result]);
  function cell(e: React.MouseEvent<HTMLCanvasElement>) {
    const box = e.currentTarget.getBoundingClientRect(),
      n = result.rois.length;
    return [
      Math.min(n - 1, Math.floor(((e.clientY - box.top) / box.height) * n)),
      Math.min(n - 1, Math.floor(((e.clientX - box.left) / box.width) * n)),
    ];
  }
  return (
    <div className="matrix-panel">
      <div className="matrix-wrap">
        <span className="axis-y">ROI 行</span>
        <canvas
          aria-label="功能连接矩阵，蓝色为负相关，红色为正相关"
          width={720}
          height={720}
          ref={canvas}
          onMouseMove={(e) => {
            const [i, j] = cell(e);
            setTip(
              `${result.rois[i].name} ↔ ${result.rois[j].name}  ·  r = ${result.connectivity[i][j].toFixed(4)}`,
            );
          }}
          onClick={(e) => {
            const [i, j] = cell(e);
            onSelect(
              i === j
                ? { kind: "node", id: result.rois[i].roi_id }
                : { kind: "edge", id: `${i}:${j}` },
            );
          }}
        />
        <span>ROI 列 · 与导出文件顺序一致</span>
      </div>
      <div className="color-scale">
        <span>−1</span>
        <i />
        <span>+1</span>
      </div>
      <p className="matrix-tip">{tip}</p>
    </div>
  );
}

function App() {
  const [result, setResult] = useState<Result | null>(
      window.__FMRI_REPORT__ || null,
    ),
    [job, setJob] = useState<Job | null>(null),
    [jobs, setJobs] = useState<Job[]>([]),
    [error, setError] = useState(""),
    [workspace, setWorkspace] = useState(""),
    [tab, setTab] = useState("3d"),
    [threshold, setThreshold] = useState(0.3),
    [maxEdges, setMaxEdges] = useState(200),
    [view, setView] = useState<ViewConfig>({ ...defaultView, labels: true }),
    [fps, setFps] = useState(0);
  const [busy, setBusy] = useState(false);
  const [resultJob, setResultJob] = useState<Job | null>(null);
  const scene = useRef<SceneHandle>(null),
    busyJob = job && ["queued", "running"].includes(job.status);
  const handleError = (e: any) => setError(e.message || String(e));
  useEffect(() => {
    if (!offline) {
      api("/api/health")
        .then((d) => setWorkspace(d.workspace))
        .catch(handleError);
      api("/api/jobs").then(setJobs).catch(handleError);
      const requestedJob = new URLSearchParams(window.location.search).get(
        "job",
      );
      if (requestedJob) void loadJob(requestedJob);
    }
  }, []);
  useEffect(() => {
    if (!busyJob || !job) return;
    let stopped = false;
    const timer = setInterval(async () => {
      try {
        const next: Job = await api(`/api/jobs/${job.id}`);
        if (stopped) return;
        if (next.status === "complete") {
          if (["extract", "demo"].includes(next.kind)) {
            const data = await api(`/api/jobs/${next.id}/files/result.json`);
            if (!stopped) {
              setResult(data);
              setResultJob(next);
              setView({ ...defaultView, labels: true });
              setTab("3d");
            }
          }
          api("/api/jobs").then(setJobs).catch(handleError);
        } else if (["failed", "interrupted"].includes(next.status)) {
          setError(next.message);
          api("/api/jobs").then(setJobs).catch(handleError);
        }
        if (!stopped) setJob(next);
      } catch (e) {
        if (!stopped) handleError(e);
      }
    }, 1500);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [job?.id, busyJob]);
  const edges: Edge[] = useMemo(
    () =>
      result
        ? displayEdges(
            result.connectivity,
            result.rois,
            threshold,
            maxEdges,
            view.selection,
          )
        : [],
    [result, threshold, maxEdges, view.selection],
  );
  const onSelect = useCallback(
    (s: Selection | null) => setView((v) => ({ ...v, selection: s })),
    [],
  );
  const onStatus = useCallback((s: { fps: number }) => setFps(s.fps), []);
  const onSlow = useCallback(() => {}, []),
    onCandidates = useCallback(() => {}, []);
  const currentResultJob = resultJob;
  const fileUrl = (name: string) =>
    currentResultJob ? `/api/jobs/${currentResultJob.id}/files/${name}` : "";
  async function start(path: string, payload: any = {}) {
    setError("");
    setBusy(true);
    try {
      setJob(await api(path, payload));
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(false);
    }
  }
  async function loadJob(id: string) {
    setError("");
    try {
      const next = await api(`/api/jobs/${id}`);
      setJob(next);
      if (
        next.status === "complete" &&
        ["demo", "extract"].includes(next.kind)
      ) {
        setResult(await api(`/api/jobs/${id}/files/result.json`));
        setResultJob(next);
        setView({ ...defaultView, labels: true });
      }
    } catch (e) {
      handleError(e);
    }
  }
  const selectedROI = result?.rois.find(
    (r) => view.selection?.kind === "node" && r.roi_id === view.selection.id,
  );
  const can3d = result?.geometry && result.rois.every((r) => r.coordinates);
  return (
    <div className={`app ${offline ? "offline" : ""}`}>
      <header className="top">
        <a className="brand" href={offline ? "#" : "/"}>
          <span className="brand-icon">◎</span>
          <div>
            Brain<strong>FC</strong>
            <small>从脑影像到功能连接</small>
          </div>
        </a>
        <div className="top-meta">
          {!offline && <a href="/networks/">网络与超图分析</a>}
          <span className="local-dot" />
          {offline ? "离线分析报告" : "本地工作台"}
          <span className="version">v{__FMRI_VERSION__}</span>
        </div>
      </header>
      <div className="layout">
        {!offline && (
          <aside>
            <Workflow
              job={job}
              busy={busy || !!busyJob}
              onJob={setJob}
              onError={handleError}
            />
            {jobs.length > 0 && (
              <details className="history">
                <summary>历史任务 · {jobs.length}</summary>
                {jobs.map((j) => (
                  <button
                    key={j.id}
                    className="run-item"
                    onClick={() => loadJob(j.id)}
                  >
                    {j.kind === "demo" ? "合成演示" : j.kind} · {j.status}
                    <small>{j.id.slice(0, 10)}</small>
                  </button>
                ))}
              </details>
            )}
            <p className="workspace">工作目录：{workspace}</p>
          </aside>
        )}
        <main>
          {error && (
            <div className="error" role="alert">
              <strong>请检查输入</strong>
              <p>{error}</p>
              <button onClick={() => setError("")}>关闭</button>
            </div>
          )}
          {job && (
            <div className={`job ${job.status}`} role="status">
              <span className={busyJob ? "spinner" : ""} />
              <strong>
                {busyJob
                  ? "处理中"
                  : job.status === "complete"
                    ? "已完成"
                    : job.status === "failed"
                      ? "处理失败"
                      : job.status}
              </strong>
              <span>{job.message}</span>
              {["preprocess", "dicom"].includes(job.kind) && (
                <a
                  href={`/api/jobs/${job.id}/files/preprocessing.log`}
                  target="_blank"
                >
                  查看日志
                </a>
              )}
            </div>
          )}
          {!offline && result && resultJob && (
            <div className="network-next">
              <div><strong>继续分析脑网络</strong><p>矩阵、脑区顺序、坐标与处理记录会自动带入。选择图或超图方法，即可计算网络指标。</p></div>
              <a href={`/networks/?source_job=${resultJob.id}`} className="primary">进入网络分析 →</a>
            </div>
          )}
          {!result ? (
            <div className="welcome">
              <div className="eyebrow">LOCAL · REPRODUCIBLE · PYTHON</div>
              <h1>
                让 fMRI，成为
                <br />
                <em>可探索的脑连接。</em>
              </h1>
              <p>
                从影像提取脑区时序，生成可追溯的功能连接矩阵。
                <br />
                用八个固定视角与交互三维，查看同一张脑网络。
              </p>
              <div className="flow">
                <span>
                  4D 影像<small>NIfTI / CIFTI / GIFTI</small>
                </span>
                <i>→</i>
                <span>
                  ROI 时序<small>分区 · 去噪 · 质控</small>
                </span>
                <i>→</i>
                <span>
                  功能连接<small>矩阵 · 八视图 · 三维</small>
                </span>
              </div>
              <button
                className="primary"
                disabled={busy || !!busyJob}
                onClick={() => start("/api/demo")}
              >
                打开合成演示 <span>↗</span>
              </button>
              <small>无需下载数据。演示为固定种子的合成信号。</small>
              <div className="data-notes">
                <b>你的数据可以来自</b>
                <p>ABIDE · ADHD-200 · ADNI · REST-meta-MDD · HCP · 自有队列</p>
                <p>
                  不同数据源通过影像或 ROI 时序入口接入。原始影像先完成预处理。
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="result-title">
                <div>
                  <div className="eyebrow">FUNCTIONAL CONNECTIVITY</div>
                  <h1>连接分析结果</h1>
                  <p>
                    {result.provenance.synthetic
                      ? "合成演示 · 无受试者数据"
                      : result.provenance.inputs?.source?.path
                          ?.split(/[\\/]/)
                          .pop() || "导出的连接结果"}{" "}
                    <span>· {result.provenance.method}</span>
                  </p>
                </div>
                {currentResultJob && (
                  <a className="primary" href={fileUrl("result.zip")}>
                    下载完整结果 ↓
                  </a>
                )}
              </div>
              <div className="metrics">
                <div>
                  <strong>{result.qc.n_rois}</strong>
                  <span>脑区</span>
                </div>
                <div>
                  <strong>
                    {result.qc.n_retained}
                    <small> / {result.qc.n_input}</small>
                  </strong>
                  <span>保留时间点</span>
                </div>
                <div>
                  <strong>
                    {result.qc.t_r ?? "—"}
                    <small> s</small>
                  </strong>
                  <span>重复时间 TR</span>
                </div>
                <div>
                  <strong>{result.qc.fd_mean?.toFixed(3) ?? "—"}</strong>
                  <span>平均 FD（mm）</span>
                </div>
              </div>
              <div className="result-tabs">
                {[
                  ["3d", "三维脑网络"],
                  ["matrix", "功能连接矩阵"],
                  ["views", "脑区八视图"],
                  ["qc", "质控与参数"],
                ].map(([k, label]) => (
                  <button
                    key={k}
                    className={tab === k ? "active" : ""}
                    onClick={() => setTab(k)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {(tab === "3d" || tab === "views") && (
                <div className="shared-controls">
                  {" "}
                  <div className="view-controls">
                    <label>
                      显示阈值 |r| ≥ {threshold.toFixed(2)}
                      <input
                        aria-label="显示连接阈值"
                        type="range"
                        min="0"
                        max="1"
                        step=".01"
                        value={threshold}
                        onChange={(e) => setThreshold(Number(e.target.value))}
                      />
                    </label>
                    <label>
                      最多显示连接
                      <select
                        value={maxEdges}
                        onChange={(e) => setMaxEdges(Number(e.target.value))}
                      >
                        {[50, 100, 200, 500, 1000].map((n) => (
                          <option key={n}>{n}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      脑壳可见度
                      <input
                        aria-label="脑壳可见度"
                        type="range"
                        min="0"
                        max=".5"
                        step=".01"
                        value={view.opacity}
                        onChange={(e) =>
                          setView((v) => ({
                            ...v,
                            opacity: Number(e.target.value),
                          }))
                        }
                      />
                    </label>
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={view.labels}
                        onChange={(e) =>
                          setView((v) => ({ ...v, labels: e.target.checked }))
                        }
                      />
                      悬停名称（仅前方）
                    </label>
                    <button onClick={() => onSelect(null)}>清除选择</button>
                  </div>
                  <p className="selection-summary">
                    {view.selection
                      ? `当前筛选：${selectedROI?.name || (view.selection.kind === "edge" ? "选中的连接" : view.selection.id)} · ${edges.length} 条连接${edges.length === 0 ? "（当前阈值下无连接，可降低阈值或清除选择）" : ""}`
                      : `全部脑区 · 按 |r| 从大到小显示 ${edges.length} 条连接`}
                  </p>
                </div>
              )}
              {tab === "3d" && (
                <div className={`viewer-card ${view.theme}`}>
                  <div className="viewer-toolbar">
                    <div>
                      {cameras.map(([key, label]) => (
                        <button
                          key={key}
                          onClick={() => scene.current?.orient(key)}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    <div>
                      <button
                        onClick={() =>
                          setView((v) => ({
                            ...v,
                            theme:
                              v.theme === "midnight" ? "paper" : "midnight",
                          }))
                        }
                      >
                        {view.theme === "midnight" ? "浅色" : "深色"}
                      </button>
                      <button
                        onClick={() =>
                          scene.current
                            ?.image()
                            .then((b) => downloadBlob(b, "brain-3d.png"))
                            .catch(handleError)
                        }
                      >
                        保存 PNG
                      </button>
                    </div>
                  </div>
                  {can3d ? (
                    <div
                      className="scene-shell"
                      data-edge-ids={edges.map((e) => e.id).join(",")}
                    >
                      <BrainScene
                        key={result.provenance.created_utc}
                        ref={scene}
                        rois={result.rois}
                        edges={edges}
                        hypers={EMPTY}
                        geometry={result.geometry!}
                        view={view}
                        onSelect={onSelect}
                        onCandidates={onCandidates}
                        onStatus={onStatus}
                        onSlow={onSlow}
                      />
                      <div className="scene-caption">
                        <span>
                          {result.provenance.config.data_space} · RAS+ / mm
                        </span>
                        <span>
                          {edges.length} 条显示连接 · 橙色正相关 / 蓝色负相关
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="no-geometry">
                      请提供与时序列逐一匹配的脑区 x/y/z
                      坐标，启用三维和八视图。
                    </div>
                  )}
                  <div className="viewer-foot">
                    {selectedROI
                      ? `${selectedROI.name} · ${selectedROI.roi_id} · ${selectedROI.coordinates?.map((v) => v.toFixed(1)).join(", ")} mm`
                      : "拖动旋转 · 滚轮缩放 · 悬停前方脑区查看名称 · 点击筛选相关连接"}
                    <span>{fps ? `${Math.round(fps)} FPS` : ""}</span>
                  </div>
                </div>
              )}
              {tab === "matrix" && (
                <div className="white-card">
                  <div className="card-head">
                    <h2>完整功能连接矩阵</h2>
                    {currentResultJob && (
                      <div>
                        <a href={fileUrl("connectivity.csv")}>CSV ↓</a>
                        <a href={fileUrl("connectivity.npy")}>NPY ↓</a>
                        <a href={fileUrl("matrix.svg")}>SVG ↓</a>
                      </div>
                    )}
                  </div>
                  <Matrix
                    result={result}
                    onSelect={(s) => {
                      if (s?.kind === "edge") {
                        const [a, b] = s.id.split(":").map(Number);
                        s.id = `${Math.min(a, b)}:${Math.max(a, b)}`;
                      }
                      onSelect(s);
                      setTab("3d");
                    }}
                  />
                  <p className="muted">
                    完整矩阵保留所有正负连接。三维显示阈值不改变矩阵；Fisher-z
                    单独导出，对角线设为 0。
                  </p>
                </div>
              )}
              {tab === "views" &&
                (can3d ? (
                  <EightViews
                    rois={result.rois}
                    edges={edges}
                    geometry={result.geometry!}
                    view={view}
                    threshold={threshold}
                    maxEdges={maxEdges}
                    jobId={currentResultJob?.id}
                  />
                ) : (
                  <div className="white-card">
                    需要与时序列匹配的脑区坐标，才能启用八视图。
                  </div>
                ))}
              {tab === "qc" && (
                <div className="white-card">
                  <h2>质控与可复现参数</h2>
                  {result.qc.warnings?.map((w: string, i: number) => (
                    <p className="warning" key={i}>
                      {w}
                    </p>
                  ))}
                  <div className="qc-grid">
                    <div>
                      <h3>保留的原始帧号（从 0 开始）</h3>
                      <pre>{result.sample_indices.join(", ")}</pre>
                      <h3>参数</h3>
                      <pre>
                        {JSON.stringify(result.provenance.config, null, 2)}
                      </pre>
                    </div>
                    <div>
                      <h3>质量记录</h3>
                      <pre>{JSON.stringify(result.qc, null, 2)}</pre>
                    </div>
                  </div>
                  <details>
                    <summary>文件来源、SHA-256 与软件版本</summary>
                    <pre>{JSON.stringify(result.provenance, null, 2)}</pre>
                  </details>
                </div>
              )}
              <p className="result-note">
                导出保留 ROI
                顺序、原始帧号、输入校验值与处理参数。球棍表示功能连接，不表示纤维束。
              </p>
            </>
          )}
        </main>
      </div>
      <footer>
        BrainFC <span>Python API + 本地界面</span>
        <span>3D viewer adapted from Hyper-Brain · Apache-2.0</span>
      </footer>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
