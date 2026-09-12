import { lazy, Suspense, useEffect, useRef, useState } from "react";
import Papa from "papaparse";
import {
  Activity,
  ArrowRight,
  BarChart3,
  BookOpen,
  Brain,
  Check,
  CheckCircle2,
  ChevronRight,
  Circle,
  Clock3,
  Database,
  FileCheck2,
  FileUp,
  FolderOpen,
  Layers3,
  LoaderCircle,
  Network,
  Play,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Square,
  Upload,
  X,
  AlertCircle,
} from "lucide-react";
import {
  api,
  post,
  type Upload as UploadRecord,
  type Job,
  type Result,
} from "./types";
const Results = lazy(() => import("./Results"));
import Statistics from "./Statistics";
declare const __NETWORK_VERSION__: string;

const statuses: Record<string, string> = {
  queued: "等待运行",
  running: "计算中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  interrupted: "已中断",
};
const presets = [
  ["generic", "通用格式"],
  ["abide1", "ABIDE I · ASD"],
  ["abide2", "ABIDE II · ASD"],
  ["adhd", "ADHD-200"],
  ["mdd", "MDD"],
  ["adni", "ADNI · 认知障碍"],
];
export default function App() {
  const [page, setPage] = useState<
      "upload" | "jobs" | "results" | "statistics" | "guide"
    >("upload"),
    [step, setStep] = useState(1),
    [uploads, setUploads] = useState<UploadRecord[]>([]),
    [chosen, setChosen] = useState<string[]>([]),
    [jobs, setJobs] = useState<Job[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [connection, setConnection] = useState<"loading" | "online" | "offline">(
      "loading",
    ),
    [dragging, setDragging] = useState(false),
    [result, setResult] = useState<Result | null>(null),
    [resultId, setResultId] = useState(""),
    [resultName, setResultName] = useState(""),
    [resultBusy, setResultBusy] = useState(false),
    [toast, setToast] = useState("");
  const [imported, setImported] = useState(false);
  const [kind, setKind] = useState("auto"),
    [variable, setVariable] = useState(""),
    [roiColumns, setRoiColumns] = useState(""),
    [matrixKind, setMatrixKind] = useState("auto"),
    [preset, setPreset] = useState("generic"),
    [roiTable, setRoiTable] = useState(""),
    [coordinateSpace, setCoordinateSpace] = useState("unknown"),
    [tr, setTr] = useState(""),
    [atlas, setAtlas] = useState(""),
    [preprocessing, setPreprocessing] = useState(""),
    [gsr, setGsr] = useState("unknown");
  const [connectivity, setConnectivity] = useState("pearson"),
    [graphMethod, setGraphMethod] = useState("density"),
    [hypergraphMethod, setHypergraphMethod] = useState("knn"),
    [threshold, setThreshold] = useState("0.2"),
    [density, setDensity] = useState("0.1"),
    [k, setK] = useState("5"),
    [ks, setKs] = useState("5,10"),
    [graphEnabled, setGraphEnabled] = useState(true),
    [hyperEnabled, setHyperEnabled] = useState(true),
    [customEdges, setCustomEdges] = useState(""),
    [groups, setGroups] = useState("");
  const inputRef = useRef<HTMLInputElement>(null),
    polling = useRef(false);
  const selectedFiles = uploads.filter((u) => chosen.includes(u.id)),
    first = selectedFiles[0],
    activeJobs = jobs.filter(
      (j) => j.status === "running" || j.status === "queued",
    ),
    completed = jobs.flatMap((j) => j.results || []);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get("result");
    if (id && /^[a-f0-9]{32}$/.test(id)) void openResult(id, "");
    const source = params.get("source_job");
    if (!id && source && /^[a-f0-9]{32}$/.test(source)) {
      setBusy(true);
      fetch(`/api/jobs/${source}/network-input`, post())
        .then(async response => {
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail || "读取提取结果失败");
          setUploads(prev => [data.file, ...prev.filter(item => item.id !== data.file.id)]);
          setChosen([data.file.id]);
          setKind("connectivity");
          setMatrixKind("correlation");
          setImported(true);
          setStep(3);
          setToast(`已接入 ${data.n_rois} 个脑区；矩阵、脑区顺序与处理记录已自动保留`);
        })
        .catch(e => setError(e.message))
        .finally(() => setBusy(false));
    }
  }, []);
  useEffect(() => {
    let active = true;
    api("/health")
      .then(() => active && setConnection("online"))
      .catch(() => active && setConnection("offline"));
    api<{ files: UploadRecord[] }>("/uploads")
      .then((data) => active && setUploads(prev => [...prev, ...data.files.filter(item => !prev.some(p => p.id === item.id))]))
      .catch(() => {});
    const refresh = async () => {
      if (polling.current) return;
      polling.current = true;
      try {
        const data = await api<{ jobs: Job[] }>("/jobs");
        if (active) {
          setJobs(data.jobs);
          setConnection("online");
        }
      } catch {
        if (active) setConnection("offline");
      } finally {
        polling.current = false;
      }
    };
    void refresh();
    const timer = setInterval(refresh, 1800);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 3500);
    return () => clearTimeout(timer);
  }, [toast]);
  async function upload(files: FileList | File[]) {
    if (!files.length) return;
    setBusy(true);
    setError("");
    setImported(false);
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));
    try {
      const data = await api<{
        files: UploadRecord[];
        errors?: { name: string; message: string }[];
      }>("/uploads", { method: "POST", body: form });
      setUploads((prev) => [
        ...data.files,
        ...prev.filter((p) => !data.files.some((f) => f.id === p.id)),
      ]);
      setChosen(data.files.map((f) => f.id));
      setVariable("");
      setKind("auto");
      setMatrixKind("auto");
      setStep(2);
      if (data.errors?.length)
        setError(
          data.errors
            .map((item) => item.name + ": " + item.message)
            .join(" / "),
        );
      setToast(`已上传 ${data.files.length} 个文件`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }
  function metadataInput() {
    if (imported) return {kind: "connectivity", matrix_kind: "correlation"};
    const metadata: Record<string, unknown> = {
      coordinate_space: coordinateSpace,
      atlas: atlas || "unknown",
      preprocessing: preprocessing || "unknown",
      gsr,
    };
    if (tr) {
      const value = Number(tr);
      if (!Number.isFinite(value) || value <= 0)
        throw new Error("TR 必须是大于 0 的秒数。");
      metadata.tr = value;
    }
    const mapping: Record<string, unknown> = {};
    if (roiTable.trim()) {
      const parsed = Papa.parse<Record<string, string>>(roiTable.trim(), {
        header: true,
        skipEmptyLines: true,
      });
      if (parsed.errors.length) throw new Error(parsed.errors[0].message);
      if (!parsed.meta.fields?.includes("id"))
        throw new Error("脑区表必须包含 id 表头，可选 label,x,y,z。");
      mapping.roi_ids = parsed.data.map((row) => row.id?.trim());
      mapping.labels = parsed.data.map(
        (row) => row.label?.trim() || row.id?.trim(),
      );
      const coordinateHeaders = ["x", "y", "z"];
      if (coordinateHeaders.some((c) => parsed.meta.fields?.includes(c))) {
        if (!coordinateHeaders.every((c) => parsed.meta.fields?.includes(c)))
          throw new Error("坐标需要同时提供 x、y、z 三列。");
        mapping.coordinates = parsed.data.map((row, i) =>
          coordinateHeaders.map((c) => {
            if (!row[c]?.trim() || !Number.isFinite(Number(row[c])))
              throw new Error(`脑区表第 ${i + 2} 行的 ${c} 不是有效坐标。`);
            return Number(row[c]);
          }),
        );
      }
    }
    return {
      kind,
      variable: variable || null,
      roi_columns: roiColumns || null,
      matrix_kind: matrixKind,
      preset,
      metadata,
      ...mapping,
    };
  }
  async function run() {
    setBusy(true);
    setError("");
    try {
      const input = metadataInput(),
        analysis = {
          connectivity_method: connectivity,
          graph_method: graphMethod,
          threshold: Number(threshold),
          density: Number(density),
          k: Number(k),
          hypergraph_method: hypergraphMethod,
          hypergraph_ks:
            hypergraphMethod === "knn"
              ? [Number(k)]
              : ks.split(",").map((v) => Number(v.trim())),
          custom_edges:
            hypergraphMethod === "custom"
              ? JSON.parse(customEdges || "[]")
              : [],
          groups:
            hypergraphMethod === "template" ? JSON.parse(groups || "{}") : {},
          compute_graph: graphEnabled,
          compute_hypergraph: hyperEnabled,
        };
      const job = await api<Job>(
        "/jobs",
        post({ file_ids: chosen, input, analysis }),
      );
      setJobs((prev) => [job, ...prev]);
      setPage("jobs");
      setToast("分析任务已加入队列");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function openResult(id: string, name: string) {
    setResultBusy(true);
    setPage("results");
    setError("");
    try {
      const data = await api<Result>(`/results/${id}`);
      setResult(data);
      setResultId(id);
      setResultName(name || String(data.metadata.source_name || "分析结果"));
      const url = new URL(window.location.href);
      url.searchParams.set("result", id);
      window.history.replaceState(null, "", url);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setResultBusy(false);
    }
  }
  async function jobAction(id: string, action: "cancel" | "retry") {
    setError("");
    try {
      await api(`/jobs/${id}/${action}`, post());
      const data = await api<{ jobs: Job[] }>("/jobs");
      setJobs(data.jobs);
      setToast(action === "cancel" ? "任务已取消" : "已建立新的重跑任务");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const goUpload = () => {
    const url = new URL(window.location.href);
    url.searchParams.delete("result");
    url.searchParams.delete("source_job");
    window.history.replaceState(null, "", url);
    setPage("upload");
    setStep(1);
    setImported(false);
    setError("");
  };
  return (
    <div
      className={`app-shell ${page === "results" && result ? "viewer-active" : ""}`}
    >
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            goUpload();
          }}
        >
          <div className="brand-icon">
            <Brain size={26} strokeWidth={1.55} />
          </div>
          <div>
            <strong>
              Brain<span>FC</span>
            </strong>
            <small>网络与超图分析</small>
          </div>
        </a>
        <div className="workspace-tag">
          <span className="dot teal" /> 本地研究工作区 <span>01</span>
        </div>
        <div className="nav-label">工作台</div>
        <nav>
          <a href="/" className="text-button" style={{display: "flex", padding: "12px 14px"}}><Brain size={18} /> 返回影像与时序提取</a>
          <button
            onClick={goUpload}
            className={page === "upload" ? "active" : ""}
          >
            <FileUp size={18} />
            上传与分析
            <Plus size={14} className="nav-end" />
          </button>
          <button
            onClick={() => {
              setPage("jobs");
              setError("");
            }}
            className={page === "jobs" ? "active" : ""}
          >
            <Activity size={18} />
            分析任务
            {activeJobs.length > 0 && (
              <span className="nav-counter">{activeJobs.length}</span>
            )}
          </button>
          <button
            onClick={() => {
              if (resultId) setPage("results");
              else if (completed.length)
                void openResult(completed[0].id, completed[0].name);
              else setPage("results");
              setError("");
            }}
            className={page === "results" ? "active" : ""}
          >
            <Network size={18} />
            结果探索
            <span className="nav-counter muted">{completed.length}</span>
          </button>
          <button
            onClick={() => {
              setPage("statistics");
              setError("");
            }}
            className={page === "statistics" ? "active" : ""}
          >
            <BarChart3 size={18} />
            队列统计
          </button>
        </nav>
        <div className="sidebar-rule" />
        <div className="nav-label">研究资源</div>
        <nav>
          <button
            className={page === "guide" ? "active" : ""}
            onClick={() => setPage("guide")}
          >
            <BookOpen size={18} />
            使用指南与 Python API
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className="privacy-icon">
            <ShieldCheck size={21} />
          </div>
          <strong>数据留在本机</strong>
          <p>
            上传、计算与结果保存
            <br />
            均在此设备上完成。
          </p>
          <div className="version">
            BRAINFC NETWORKS <span>v{__NETWORK_VERSION__}</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            研究工作台
            <ChevronRight size={14} />
            <strong>
              {
                {
                  upload: "上传与分析",
                  jobs: "分析任务",
                  results: "结果探索",
                  statistics: "队列统计",
                  guide: "使用指南",
                }[page]
              }
            </strong>
          </div>
          <div className="service-status">
            <span
              className={`dot ${connection === "online" ? "teal" : connection === "offline" ? "coral" : "amber"}`}
            />
            {connection === "online"
              ? "本地服务已连接"
              : connection === "offline"
                ? "本地服务未连接"
                : "正在连接"}
            <span className="topbar-separator" />
            <span className="mode-badge">LOCAL</span>
          </div>
        </header>
        <main>
          {error && (
            <div className="error" role="alert">
              <AlertCircle size={18} />
              <span>{error}</span>
              <button aria-label="关闭错误提示" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {page === "upload" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">FROM DATA TO NETWORK</div>
                  <h1>开始一次脑网络探索</h1>
                  <p>
                    从功能连接矩阵或 ROI 时序出发，在图与超图中理解脑区关系。
                  </p>
                </div>
                <div className="analysis-badge">
                  <span className="badge-icon">
                    <Network size={21} />
                  </span>
                  <span>
                    统一分析核心<small>Python API ↔ 本地网页</small>
                  </span>
                </div>
              </div>
              <div className="steps">
                {[
                  ["上传数据", Upload],
                  ["确认内容", FileCheck2],
                  ["配置分析", Settings2],
                  ["查看结果", Network],
                  ["导出结果", FolderOpen],
                ].map(([label, Icon], i) => {
                  const I = Icon as typeof Upload;
                  return (
                    <button
                      key={i}
                      disabled={i > 2 || (i > 0 && !chosen.length)}
                      className={`step ${step === i + 1 ? "current" : ""} ${step > i + 1 ? "done" : ""}`}
                      onClick={() => setStep(i + 1)}
                    >
                      <span className="step-marker">
                        {step > i + 1 ? <Check size={15} /> : <I size={16} />}
                      </span>
                      <span>
                        <small>0{i + 1}</small>
                        {String(label)}
                      </span>
                      {i < 4 && (
                        <ChevronRight size={14} className="step-arrow" />
                      )}
                    </button>
                  );
                })}
              </div>
              {step === 1 && (
                <div className="upload-layout">
                  <section className="panel upload-panel">
                    <div className="section-heading">
                      <div>
                        <h2>上传脑网络数据</h2>
                        <p>支持单个受试者或同一格式的批量文件</p>
                      </div>
                      <span className="badge">本机计算</span>
                    </div>
                    <div
                      className={`dropzone ${dragging ? "dragging" : ""} ${busy ? "loading" : ""}`}
                      onDragOver={(e) => {
                        e.preventDefault();
                        setDragging(true);
                      }}
                      onDragLeave={() => setDragging(false)}
                      onDrop={(e) => {
                        e.preventDefault();
                        setDragging(false);
                        if (!busy) void upload(e.dataTransfer.files);
                      }}
                    >
                      <div className="upload-orbit">
                        <div className="upload-symbol">
                          {busy ? (
                            <LoaderCircle size={34} className="spin" />
                          ) : (
                            <Upload size={34} strokeWidth={1.5} />
                          )}
                        </div>
                        <span className="orbit-node a" />
                        <span className="orbit-node b" />
                        <span className="orbit-node c" />
                      </div>
                      <h3>
                        {busy ? "正在读取与检查文件…" : "将数据文件拖放到这里"}
                      </h3>
                      <p>或从你的设备中选择文件</p>
                      <button
                        className="button primary"
                        disabled={busy}
                        onClick={() => inputRef.current?.click()}
                      >
                        <Plus size={16} /> 选择数据文件
                      </button>
                      <input
                        ref={inputRef}
                        hidden
                        type="file"
                        multiple
                        accept=".csv,.tsv,.txt,.1d,.1D,.npy,.npz,.mat"
                        onChange={(e) =>
                          e.target.files && void upload(e.target.files)
                        }
                      />
                      <div className="file-formats">
                        CSV <span>·</span> TSV <span>·</span> TXT / 1D{" "}
                        <span>·</span> NPY / NPZ <span>·</span> MAT
                      </div>
                    </div>
                    <div className="data-type-cards">
                      <div>
                        <GridIcon />
                        <strong>功能连接矩阵</strong>
                        <p>N × N · 相关系数或 Fisher-z</p>
                      </div>
                      <div>
                        <Activity size={23} />
                        <strong>ROI 时间序列</strong>
                        <p>T × N · 时间点 × 脑区</p>
                      </div>
                    </div>
                  </section>
                  <div className="upload-aside">
                    <section className="panel workflow-note">
                      <span className="eyebrow">YOUR RESEARCH, CONNECTED</span>
                      <h2>
                        一个入口，
                        <br />
                        两种网络视角。
                      </h2>
                      <div className="mini-network" aria-hidden="true">
                        <svg viewBox="0 0 220 145">
                          <path
                            d="M49 91L75 36L126 45L167 99L116 117Z M49 91L126 45L116 117L75 36L167 99"
                            stroke="#86b9cd"
                            strokeWidth="1"
                            fill="none"
                          />
                          <path
                            d="M67 26Q104 7 136 30L181 93Q197 120 162 125L106 123Q83 116 90 91Z"
                            fill="#eaf5fa"
                            stroke="#86b9cd"
                            strokeDasharray="4 4"
                          />
                          {[
                            [49, 91],
                            [75, 36],
                            [126, 45],
                            [167, 99],
                            [116, 117],
                          ].map(([x, y], i) => (
                            <circle
                              key={i}
                              cx={x}
                              cy={y}
                              r={i === 2 ? 9 : 6}
                              fill={i === 2 ? "#007da3" : "#0096c3"}
                              stroke="white"
                              strokeWidth="3"
                            />
                          ))}
                        </svg>
                      </div>
                      <p>
                        普通图描述两两连接。
                        <br />
                        超图保留多个脑区的共同成员关系。
                      </p>
                      <div className="note-divider" />
                      <div className="method-label">
                        <CheckCircle2 size={15} /> 参数、结构与来源一并记录
                      </div>
                      <div className="method-label">
                        <CheckCircle2 size={15} /> 同一套可复现 Python API
                      </div>
                    </section>
                    <section className="panel cohort-note">
                      <Database size={20} />
                      <div>
                        <strong>通用数据，统一流程</strong>
                        <p>ABIDE · ADHD-200 · MDD · ADNI</p>
                        <small>数据预设辅助解析，分析方法由你选择。</small>
                      </div>
                    </section>
                  </div>
                </div>
              )}
              {step === 1 && uploads.length > 0 && (
                <section className="panel recent-files">
                  <div className="panel-title">
                    <span>
                      工作区文件 <span className="count">{uploads.length}</span>
                    </span>
                    <button
                      className="text-button"
                      disabled={!chosen.length}
                      onClick={() => setStep(2)}
                    >
                      继续已选文件 <ArrowRight size={14} />
                    </button>
                  </div>
                  {uploads.slice(0, 12).map((file) => (
                    <label className="file-row" key={file.id}>
                      <input
                        type="checkbox"
                        checked={chosen.includes(file.id)}
                        onChange={(e) =>
                          setChosen(
                            e.target.checked
                              ? [...chosen, file.id]
                              : chosen.filter((id) => id !== file.id),
                          )
                        }
                      />
                      <FileCheck2 size={19} />
                      <div>
                        <strong>{file.name}</strong>
                        <small>
                          {file.variables
                            .map((v) => `${v.name} · ${v.shape.join(" × ")}`)
                            .join(" / ")}
                        </small>
                      </div>
                      <span className="badge">
                        {file.format?.toUpperCase()}
                      </span>
                    </label>
                  ))}
                </section>
              )}
              {step === 2 && (
                <>
                  <div className="two-column">
                    <section className="panel form-panel">
                      <h2>
                        01 <span>确认文件与格式</span>
                      </h2>
                      <div className="selected-files">
                        {selectedFiles.map((file) => (
                          <div key={file.id}>
                            <FileCheck2 size={19} />
                            <span>
                              <strong>{file.name}</strong>
                              <small>
                                {file.variables
                                  .map(
                                    (v) => `${v.name}: ${v.shape.join(" × ")}`,
                                  )
                                  .join(" / ")}
                              </small>
                            </span>
                            <button
                              className="icon-button"
                              aria-label={`移除 ${file.name}`}
                              onClick={() =>
                                setChosen(chosen.filter((id) => id !== file.id))
                              }
                            >
                              <X size={15} />
                            </button>
                          </div>
                        ))}
                      </div>
                      <div className="form-grid">
                        <label className="field">
                          <span>数据预设</span>
                          <select
                            value={preset}
                            onChange={(e) => setPreset(e.target.value)}
                          >
                            {presets.map(([value, label]) => (
                              <option value={value} key={value}>
                                {label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="field">
                          <span>数据类型</span>
                          <select
                            value={kind}
                            onChange={(e) => setKind(e.target.value)}
                          >
                            <option value="auto">自动识别</option>
                            <option value="connectivity">功能连接矩阵</option>
                            <option value="timeseries">ROI 时间序列</option>
                          </select>
                        </label>
                        <label className="field">
                          <span>数组 / MAT 变量</span>
                          <select
                            value={variable}
                            onChange={(e) => setVariable(e.target.value)}
                          >
                            <option value="">自动选择（仅单一数组）</option>
                            {first?.variables.map((v) => (
                              <option key={v.name} value={v.name}>
                                {v.name} · {v.shape.join(" × ")}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="field">
                          <span>连接矩阵数值类型</span>
                          <select
                            value={matrixKind}
                            onChange={(e) => setMatrixKind(e.target.value)}
                          >
                            <option value="auto">
                              自动识别 / 需确认时提示
                            </option>
                            <option value="correlation">相关系数 r</option>
                            <option value="fisher_z">
                              Fisher-z（分析前还原 r）
                            </option>
                          </select>
                        </label>
                      </div>
                      <label className="field">
                        <span>ROI 列范围（可选）</span>
                        <input
                          value={roiColumns}
                          onChange={(e) => setRoiColumns(e.target.value)}
                          placeholder="例如 0:116，索引从 0 开始，右端不含"
                        />
                        <small>
                          用于时序脑区选择。MDD 多图谱数组需明确范围；ADHD
                          辅助列按表头自动排除。
                        </small>
                      </label>
                      {selectedFiles.flatMap((f) => f.warnings || []).length >
                        0 && (
                        <div className="notice">
                          {Array.from(
                            new Set(
                              selectedFiles.flatMap((f) => f.warnings || []),
                            ),
                          ).map((w, i) => (
                            <p key={i}>{w}</p>
                          ))}
                        </div>
                      )}
                      <p className="hint">
                        批量分析共用当前解析设置；不同变量或图谱请分别提交。
                      </p>
                    </section>
                    <section className="panel form-panel">
                      <h2>
                        02 <span>记录脑区与处理信息</span>
                      </h2>
                      <div className="form-grid">
                        <label className="field">
                          <span>图谱及版本</span>
                          <input
                            value={atlas}
                            onChange={(e) => setAtlas(e.target.value)}
                            placeholder="例如 AAL 116 · 明确版本"
                          />
                        </label>
                        <label className="field">
                          <span>TR（秒，可选）</span>
                          <input
                            type="number"
                            min="0.01"
                            step="0.01"
                            value={tr}
                            onChange={(e) => setTr(e.target.value)}
                            placeholder="2.0"
                          />
                        </label>
                        <label className="field">
                          <span>坐标空间</span>
                          <select
                            value={coordinateSpace}
                            onChange={(e) => setCoordinateSpace(e.target.value)}
                          >
                            <option value="unknown">未指定</option>
                            <option value="MNI">MNI（毫米，已确认）</option>
                            <option value="native">个体空间</option>
                          </select>
                        </label>
                        <label className="field">
                          <span>全局信号回归 GSR</span>
                          <select
                            value={gsr}
                            onChange={(e) => setGsr(e.target.value)}
                          >
                            <option value="unknown">未知</option>
                            <option value="yes">已执行</option>
                            <option value="no">未执行</option>
                          </select>
                        </label>
                      </div>
                      <label className="field">
                        <span>预处理说明（可选）</span>
                        <input
                          value={preprocessing}
                          onChange={(e) => setPreprocessing(e.target.value)}
                          placeholder="处理流程、删帧、滤波及来源"
                        />
                      </label>
                      <label className="field">
                        <span>脑区映射表（可选，CSV）</span>
                        <textarea
                          rows={5}
                          value={roiTable}
                          onChange={(e) => setRoiTable(e.target.value)}
                          placeholder={
                            "id,label,x,y,z\nROI_001,Frontal_L,-38,24,46\nROI_002,Frontal_R,38,24,46"
                          }
                        />
                        <small>
                          按矩阵 / 时序列顺序逐行填写；id 必填。坐标需要完整
                          x,y,z 三列，明确 MNI 后启用解剖视图。
                        </small>
                      </label>
                      <div className="method-note">
                        缺少图谱时仍可分析矩阵和抽象网络。系统不会根据矩阵大小猜测脑区解剖位置。
                      </div>
                    </section>
                  </div>
                  <div className="form-footer">
                    <button
                      className="button secondary"
                      onClick={() => setStep(1)}
                    >
                      返回上传
                    </button>
                    <button
                      className="button primary"
                      disabled={!chosen.length}
                      onClick={() => {
                        try {
                          metadataInput();
                          setError("");
                          setStep(3);
                        } catch (e) {
                          setError((e as Error).message);
                        }
                      }}
                    >
                      配置分析 <ArrowRight size={16} />
                    </button>
                  </div>
                </>
              )}
              {step === 3 && (
                <>
                  {imported && <div className="config-intro"><FileCheck2 size={18} />
                    已从 BrainFC 提取结果自动接入。保留完整矩阵、脑区顺序和处理记录；确认下面的分析方法即可。
                  </div>}
                  <div className="config-intro">
                    <span>
                      <FileCheck2 size={18} />
                      {chosen.length} 个文件已选定
                    </span>
                    <span>
                      原始连接的正负符号保留 · 路径类指标基于正连接计算
                    </span>
                  </div>
                  {!imported && kind !== "connectivity" && <section className="panel form-panel connectivity-config">
                    <div>
                      <h2>连接估计</h2>
                      <p className="hint">
                        仅对 ROI 时序生效；连接矩阵直接进入结构分析。
                      </p>
                    </div>
                    <label className="field">
                      <span>估计方法</span>
                      <select
                        value={connectivity}
                        disabled={imported || kind === "connectivity"}
                        onChange={(e) => setConnectivity(e.target.value)}
                      >
                        <option value="pearson">Pearson 相关</option>
                        <option value="spearman">Spearman 相关</option>
                        <option value="partial">收缩协方差偏相关</option>
                      </select>
                    </label>
                  </section>}
                  <div className="two-column">
                    <section
                      className={`panel form-panel ${!graphEnabled ? "disabled-panel" : ""}`}
                    >
                      <div className="config-heading">
                        <div className="config-icon">
                          <Network size={23} />
                        </div>
                        <div>
                          <h2>普通图分析</h2>
                          <p>连接、拓扑与节点指标</p>
                        </div>
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={graphEnabled}
                            onChange={(e) => setGraphEnabled(e.target.checked)}
                          />
                          <span />
                        </label>
                      </div>
                      <label className="field">
                        <span>构图方法</span>
                        <select
                          disabled={!graphEnabled}
                          value={graphMethod}
                          onChange={(e) => setGraphMethod(e.target.value)}
                        >
                          <option value="density">固定连接密度</option>
                          <option value="threshold">固定绝对阈值</option>
                          <option value="weighted">完整加权图</option>
                          <option value="knn">k 近邻图</option>
                          <option value="mst">最大生成树</option>
                        </select>
                      </label>
                      {graphMethod === "density" && (
                        <label className="field">
                          <span>保留密度（0–1）</span>
                          <input
                            type="number"
                            min="0.001"
                            max="1"
                            step="0.01"
                            value={density}
                            onChange={(e) => setDensity(e.target.value)}
                          />
                        </label>
                      )}
                      {graphMethod === "threshold" && (
                        <label className="field">
                          <span>绝对相关阈值</span>
                          <input
                            type="number"
                            min="0"
                            max="1"
                            step="0.05"
                            value={threshold}
                            onChange={(e) => setThreshold(e.target.value)}
                          />
                        </label>
                      )}
                      {graphMethod === "knn" && (
                        <label className="field">
                          <span>近邻数量 k</span>
                          <input
                            type="number"
                            min="1"
                            step="1"
                            value={k}
                            onChange={(e) => setK(e.target.value)}
                          />
                        </label>
                      )}
                      <div className="feature-tags">
                        <span>连接强度</span>
                        <span>聚类系数</span>
                        <span>全局效率</span>
                        <span>中心性</span>
                        <span>社区</span>
                      </div>
                    </section>
                    <section
                      className={`panel form-panel ${!hyperEnabled ? "disabled-panel" : ""}`}
                    >
                      <div className="config-heading">
                        <div className="config-icon gold">
                          <Layers3 size={23} />
                        </div>
                        <div>
                          <h2>超图分析</h2>
                          <p>原生超边与高阶结构表征</p>
                        </div>
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={hyperEnabled}
                            onChange={(e) => setHyperEnabled(e.target.checked)}
                          />
                          <span />
                        </label>
                      </div>
                      <label className="field">
                        <span>超图构建方法</span>
                        <select
                          disabled={!hyperEnabled}
                          value={hypergraphMethod}
                          onChange={(e) => setHypergraphMethod(e.target.value)}
                        >
                          <option value="knn">FC-profile k 近邻</option>
                          <option value="multiscale">多尺度 k 近邻</option>
                          <option value="custom">自定义超边</option>
                          <option value="template">功能系统模板</option>
                        </select>
                      </label>
                      {hypergraphMethod === "knn" && (
                        <label className="field">
                          <span>近邻数量 k</span>
                          <input
                            type="number"
                            min="1"
                            step="1"
                            value={k}
                            onChange={(e) => setK(e.target.value)}
                          />
                        </label>
                      )}
                      {hypergraphMethod === "multiscale" && (
                        <label className="field">
                          <span>近邻尺度（逗号分隔）</span>
                          <input
                            value={ks}
                            onChange={(e) => setKs(e.target.value)}
                            placeholder="5,10"
                          />
                        </label>
                      )}
                      {hypergraphMethod === "custom" && (
                        <label className="field">
                          <span>超边 JSON</span>
                          <textarea
                            rows={4}
                            value={customEdges}
                            onChange={(e) => setCustomEdges(e.target.value)}
                            placeholder={
                              '[{"id":"edge_1","members":["ROI_001","ROI_002"],"weight":1}]'
                            }
                          />
                        </label>
                      )}
                      {hypergraphMethod === "template" && (
                        <label className="field">
                          <span>功能系统 → ROI 成员（JSON）</span>
                          <textarea
                            rows={4}
                            value={groups}
                            onChange={(e) => setGroups(e.target.value)}
                            placeholder={
                              '{"DMN":["ROI_001","ROI_002","ROI_003"]}'
                            }
                          />
                        </label>
                      )}
                      <div className="feature-tags">
                        <span>超度</span>
                        <span>成员参与</span>
                        <span>超边重叠</span>
                        <span>连通性</span>
                        <span>关联矩阵</span>
                      </div>
                      <p className="hint">
                        FC
                        构建的超图是一种结构表征，不等同于不可约高阶相互作用证据。
                      </p>
                    </section>
                  </div>
                  <div className="form-footer">
                    <button
                      className="button secondary"
                      onClick={() => setStep(2)}
                    >
                      返回确认内容
                    </button>
                    <button
                      className="button primary"
                      disabled={
                        busy ||
                        !chosen.length ||
                        (!graphEnabled && !hyperEnabled)
                      }
                      onClick={() => void run()}
                    >
                      {busy ? (
                        <LoaderCircle size={16} className="spin" />
                      ) : (
                        <Play size={16} />
                      )}{" "}
                      开始建模分析
                    </button>
                  </div>
                </>
              )}
            </>
          )}
          {page === "jobs" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">ANALYSIS QUEUE</div>
                  <h1>分析任务</h1>
                  <p>计算在独立进程中运行，结果和运行记录保存在本机。</p>
                </div>
                <button className="button primary" onClick={goUpload}>
                  <Plus size={16} /> 新建分析
                </button>
              </div>
              <div className="queue-summary">
                <span>
                  <LoaderCircle size={17} />
                  {activeJobs.length} 个任务进行中
                </span>
                <span>
                  <CheckCircle2 size={17} />
                  {completed.length} 份结果可探索
                </span>
              </div>
              {!jobs.length ? (
                <div className="panel empty-state">
                  <Clock3 size={44} />
                  <h3>还没有分析任务</h3>
                  <p>上传一份连接矩阵或 ROI 时序，开始第一个分析。</p>
                  <button className="button primary" onClick={goUpload}>
                    上传数据 <ArrowRight size={16} />
                  </button>
                </div>
              ) : (
                jobs.map((job) => (
                  <section className="panel job-card" key={job.id}>
                    <div className="job-header">
                      <div className={`job-state-icon ${job.status}`}>
                        {job.status === "completed" ? (
                          <CheckCircle2 size={22} />
                        ) : job.status === "running" ? (
                          <LoaderCircle size={22} className="spin" />
                        ) : job.status === "failed" ? (
                          <AlertCircle size={22} />
                        ) : (
                          <Clock3 size={22} />
                        )}
                      </div>
                      <div>
                        <h3>
                          {job.results?.[0]?.name ||
                            `分析任务 ${job.id.slice(0, 8)}`}
                        </h3>
                        <p>
                          {new Date(job.created_at).toLocaleString("zh-CN")} ·{" "}
                          {job.files?.length || 0} 个文件
                        </p>
                      </div>
                      <span className={`status-badge ${job.status}`}>
                        {statuses[job.status] || job.status}
                      </span>
                      {["queued", "running"].includes(job.status) ? (
                        <button
                          className="button secondary small"
                          onClick={() => void jobAction(job.id, "cancel")}
                        >
                          <Square size={13} /> 取消
                        </button>
                      ) : (
                        <button
                          className="button secondary small"
                          onClick={() => void jobAction(job.id, "retry")}
                        >
                          <RefreshCw size={13} /> 重跑
                        </button>
                      )}
                    </div>
                    <div className="job-progress">
                      <div style={{ width: `${job.progress || 0}%` }} />
                    </div>
                    <p className="job-message">
                      {job.message || "等待处理"}{" "}
                      <span>{job.progress || 0}%</span>
                    </p>
                    {job.errors?.map((e, i) => (
                      <div className="error compact" key={i}>
                        <AlertCircle size={15} />
                        {e.name}: {e.message}
                      </div>
                    ))}
                    {job.results?.length > 0 && (
                      <div className="job-results">
                        {job.results.map((r) => (
                          <button
                            key={r.id}
                            onClick={() => void openResult(r.id, r.name)}
                          >
                            <FileCheck2 size={17} />
                            <span>{r.name}</span>探索结果{" "}
                            <ArrowRight size={15} />
                          </button>
                        ))}
                      </div>
                    )}
                  </section>
                ))
              )}
            </>
          )}
          {page === "results" &&
            (resultBusy ? (
              <div className="panel empty-state">
                <LoaderCircle size={40} className="spin" />
                <h3>正在载入分析结果</h3>
                <p>连接矩阵、网络结构与来源记录正在读取。</p>
              </div>
            ) : result ? (
              <>
                <div className="result-picker">
                  <label>
                    切换分析结果{" "}
                    <select
                      value={resultId}
                      onChange={(e) => {
                        const r = completed.find(
                          (v) => v.id === e.target.value,
                        );
                        if (r) void openResult(r.id, r.name);
                      }}
                    >
                      {completed.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name} · {r.id.slice(0, 6)}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <Suspense
                  fallback={
                    <div className="panel empty-state">
                      <LoaderCircle className="spin" />
                      <p>正在载入本地可视化组件</p>
                    </div>
                  }
                >
                  <Results
                    key={resultId}
                    result={result}
                    resultId={resultId}
                    name={resultName}
                    datasets={completed}
                    onDataset={(id) => {
                      const r = completed.find((v) => v.id === id);
                      if (r) void openResult(r.id, r.name);
                    }}
                    onBack={goUpload}
                  />
                </Suspense>
              </>
            ) : (
              <div className="panel empty-state">
                <Network size={48} />
                <h3>结果将在这里呈现</h3>
                <p>完成一次分析后，探索脑区、连接矩阵与原生超边。</p>
                <button className="button primary" onClick={goUpload}>
                  开始分析 <ArrowRight size={16} />
                </button>
              </div>
            ))}
          {page === "statistics" && <Statistics />}
          {page === "guide" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">GETTING STARTED</div>
                  <h1>把分析接入你的研究</h1>
                  <p>网页操作与 Python API 使用同一份输入约定与分析核心。</p>
                </div>
                <BookOpen size={39} className="heading-icon" />
              </div>
              <div className="two-column">
                <section className="panel form-panel">
                  <h2>本地网页工作流</h2>
                  <ol className="guide-list">
                    <li>上传矩阵或 ROI 时序，批量文件需要相同解析设置。</li>
                    <li>
                      确认数组变量、连接类型及 ROI 顺序。Fisher-z
                      需显式选择或按文件元信息识别。
                    </li>
                    <li>按需补充图谱、MNI 坐标、TR 和预处理信息。</li>
                    <li>
                      配置图 / 超图，启动任务。在结果中点击脑区或超边联动探索。
                    </li>
                    <li>下载可复用结构、指标、图像及方法报告。</li>
                  </ol>
                  <div className="notice">
                    首版用于科研描述与队列分析，不输出单人疾病诊断。原始 fMRI
                    预处理与预测训练留待后续版本。
                  </div>
                </section>
                <section className="panel form-panel">
                  <h2>Python API</h2>
                  <pre className="code-block">
                    {
                      'from brainfc.network import load_data, analyze, AnalysisConfig\nfrom brainfc.network.export import export_result\n\ndataset = load_data(\n    "subject.csv",\n    kind="connectivity",\n    matrix_kind="correlation",\n)\nresult = analyze(dataset, AnalysisConfig(\n    graph_method="density", density=0.1,\n    hypergraph_method="multiscale",\n    hypergraph_ks=[5, 10],\n))\nexport_result(result, "analysis-output.zip", "zip")'
                    }
                  </pre>
                  <p className="hint">完整参数与路由说明见本地接口文档。</p>
                  <a
                    className="button secondary"
                    href="/networks/docs"
                    target="_blank"
                    rel="noreferrer"
                  >
                    打开 API 文档 <ArrowRight size={15} />
                  </a>
                </section>
              </div>
              <section className="panel form-panel">
                <h2>数据与计算约定</h2>
                <div className="guide-grid">
                  <div>
                    <strong>输入</strong>
                    <p>
                      矩阵 N × N，时序 T × N。MAT / NPZ
                      多变量需明确选择；辅助列不属于脑区。
                    </p>
                  </div>
                  <div>
                    <strong>统计单位</strong>
                    <p>
                      独立受试者。同一人的多次扫描先指定一次，避免将重复扫描当作独立样本。
                    </p>
                  </div>
                  <div>
                    <strong>可追溯性</strong>
                    <p>
                      导出记录包含输入校验值、算法参数与版本。原生超边保留独立
                      ID 和完整成员。
                    </p>
                  </div>
                </div>
              </section>
            </>
          )}
        </main>
        <footer>
          <span>
            BrainFC Networks <span className="footer-dot">·</span> 本地脑网络分析
          </span>
          <span>图 · 超图 · 可复现研究</span>
        </footer>
      </div>
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={17} />
          {toast}
        </div>
      )}
    </div>
  );
}
function GridIcon() {
  return (
    <svg
      width="23"
      height="23"
      viewBox="0 0 23 23"
      fill="none"
      aria-hidden="true"
    >
      {[0, 1, 2].map((y) =>
        [0, 1, 2].map((x) => (
          <rect
            key={`${x}-${y}`}
            x={x * 7 + 1}
            y={y * 7 + 1}
            width="5"
            height="5"
            rx="1"
            fill={x === y ? "#0096c3" : "#c8dfe9"}
          />
        )),
      )}
    </svg>
  );
}
