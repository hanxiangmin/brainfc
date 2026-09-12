import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ArrowLeft,
  Brain,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Focus,
  LoaderCircle,
  Moon,
  RotateCcw,
  Save,
  Sun,
  Upload,
  X,
} from "lucide-react";
import Papa from "papaparse";
import BrainScene, { type SceneHandle } from "./BrainScene";
import { api, post, pretty, type Result } from "./types";
import {
  categoryColor,
  defaultView,
  downloadBlob,
  edgesOf,
  hyperedgesOf,
  related,
  roiColor,
  selectionMembers,
  styles,
  type Atlas,
  type AtlasGeometry,
  type ROI,
  type Selection,
  type ViewConfig,
} from "./viewerTypes";
import AtlasImport from "./AtlasImport";
import "./viewer.css";
const Plot = lazy(() => import("./Plot"));
const AtlasSlices = lazy(() => import("./AtlasSlices"));
type Props = {
  result: Result;
  resultId: string;
  name: string;
  datasets?: { id: string; name: string }[];
  onDataset?: (id: string) => void;
  onBack?: () => void;
};
const hemiNames: Record<string, string> = {
  L: "左半球 · Left",
  R: "右半球 · Right",
  M: "中线 · Midline",
  B: "双侧 · Bilateral",
};
export default function Results({
  result: initial,
  resultId,
  name,
  datasets = [],
  onDataset,
  onBack,
}: Props) {
  const [result, setResult] = useState(initial),
    [view, setView] = useState<ViewConfig>(defaultView),
    [catalog, setCatalog] = useState<Atlas[]>([]),
    [atlasId, setAtlasId] = useState("");
  const [atlas, setAtlas] = useState<Atlas | null>(null),
    [geometry, setGeometry] = useState<AtlasGeometry | null>(null),
    [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [toast, setToast] = useState("");
  const [left, setLeft] = useState(true),
    [bottom, setBottom] = useState<"" | "matrix" | "members" | "slices">(""),
    [candidates, setCandidates] = useState<Selection[]>([]),
    [importOpen, setImportOpen] = useState(false),
    [exportOpen, setExportOpen] = useState(false);
  const [mapping, setMapping] = useState(""),
    [confirmed, setConfirmed] = useState(false),
    [search, setSearch] = useState(""),
    [status, setStatus] = useState({ fallback: 0, lod: false, fps: 0 });
  const scene = useRef<SceneHandle>(null),
    restoreFile = useRef<HTMLInputElement>(null);
  const [slow, setSlow] = useState(false);
  const reportSlow = useCallback(() => setSlow(true), []);
  const bind = result.metadata.atlas_binding as
    | { atlas_id: string; ordered_roi_ids: string[]; atlas_sha256: string }
    | undefined;
  const inheritedGeometry = result.metadata.brainfc_geometry as AtlasGeometry | undefined;
  const inherited = !bind && atlasId === "brainfc-result" && !!inheritedGeometry;
  const mapped = (!!bind && bind.atlas_id === atlasId) || inherited;
  const allEdges = useMemo(() => edgesOf(result), [result]),
    allHypers = useMemo(() => hyperedgesOf(result), [result]);
  const rois = useMemo(
    () =>
      (mapped ? result.metadata.roi_metadata : atlas?.labels || []) as ROI[],
    [mapped, result, atlas],
  );
  const sceneEdges = useMemo(
      () => (mapped ? allEdges : []),
      [mapped, allEdges],
    ),
    sceneHypers = useMemo(() => (mapped ? allHypers : []), [mapped, allHypers]);
  const roiById = useMemo(
    () => new Map(rois.map((r) => [r.source_roi_id || r.roi_id, r])),
    [rois],
  );
  const resultRoiById = useMemo(
    () =>
      new Map(
        ((result.metadata.roi_metadata || []) as ROI[]).map((r) => [
          r.source_roi_id || r.roi_id,
          r,
        ]),
      ),
    [result],
  );
  const focus = useMemo(
    () => related(view.selection, sceneEdges, sceneHypers),
    [view.selection, sceneEdges, sceneHypers],
  );
  const members = useMemo(
    () => selectionMembers(view.selection, sceneEdges, sceneHypers),
    [view.selection, sceneEdges, sceneHypers],
  );
  const selectedNode =
    view.selection?.kind === "node"
      ? roiById.get(view.selection.id)
      : undefined;
  const selectedEdge =
    view.selection?.kind === "edge"
      ? sceneEdges.find((e) => e.id === view.selection!.id)
      : undefined;
  const selectedHyper =
    view.selection?.kind === "hyperedge"
      ? sceneHypers.find((e) => e.id === view.selection!.id)
      : undefined;
  const patch = (p: Partial<ViewConfig>) => setView((v) => ({ ...v, ...p }));
  const select = useCallback(
    (s: Selection | null) =>
      setView((v) => ({
        ...v,
        selection: s,
        only_selected: s ? v.only_selected : false,
      })),
    [],
  );
  const reportStatus = useCallback((s: typeof status) => setStatus(s), []);
  const global = () => {
    select(null);
    setCandidates([]);
    setSearch("");
  };
  const notify = (s: string) => {
    setToast(s);
    setTimeout(() => setToast(""), 4000);
  };
  useEffect(() => {
    let live = true;
    Promise.all([
      api<Result>(`/results/${resultId}/mapped`),
      api<ViewConfig>(`/results/${resultId}/view`),
      api<{ atlases: Atlas[] }>("/atlases"),
    ])
      .then(([data, state, list]) => {
        if (!live) return;
        setResult(data);
        setView(state);
        const inherited = data.metadata.brainfc_geometry as AtlasGeometry | undefined;
        const inheritedAtlas: Atlas | null = inherited ? {
          id: "brainfc-result", name: "提取结果的脑区与参考表面", space: inherited.space,
          version: data.version, n_rois: data.roi_ids.length, installed: true, custom: true,
          labels: data.metadata.roi_metadata as ROI[], sources: [],
        } : null;
        setCatalog(inheritedAtlas ? [inheritedAtlas, ...list.atlases] : list.atlases);
        const b = data.metadata.atlas_binding as
          { atlas_id: string } | undefined;
        setAtlasId(
          b?.atlas_id ||
            inheritedAtlas?.id ||
            list.atlases.find((a) => a.installed)?.id ||
            list.atlases[0]?.id ||
            "",
        );
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [resultId]);
  useEffect(() => {
    const entry = catalog.find((a) => a.id === atlasId);
    setAtlas(entry || null);
    setGeometry(null);
    setMapping("");
    setConfirmed(false);
    if (entry?.id === "brainfc-result" && inheritedGeometry) {
      setGeometry(inheritedGeometry);
      setBusy("");
      return;
    }
    if (!entry?.installed) return;
    const controller = new AbortController();
    setBusy("正在读取脑表面与分区");
    Promise.all([
      api<Atlas>(`/atlases/${atlasId}`, { signal: controller.signal }),
      api<AtlasGeometry>(`/atlases/${atlasId}/assets/geometry.json`, {
        signal: controller.signal,
      }),
    ])
      .then(([a, g]) => {
        if (controller.signal.aborted) return;
        setAtlas(a);
        setGeometry(g);
        setBusy("");
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          setError(e.message);
          setBusy("");
        }
      });
    return () => controller.abort();
  }, [atlasId, catalog, inheritedGeometry]);
  async function install() {
    setError("");
    setBusy("正在下载并生成图谱表面，首次安装需要几分钟");
    try {
      await api(`/atlases/${atlasId}/install`, post());
      const list = await api<{ atlases: Atlas[] }>("/atlases");
      setCatalog(list.atlases);
      notify("图谱已安装，可离线使用");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function applyMapping() {
    setError("");
    setBusy("正在验证脑区顺序");
    try {
      const ids = mapping
        .split(/[\n,\t]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      const data = await api<Result>(
        `/results/${resultId}/atlas`,
        post({ atlas_id: atlasId, ordered_roi_ids: ids, confirmed }),
      );
      setResult(data);
      global();
      notify("脑区映射已验证并保存");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function readOrder(file?: File) {
    if (!file) return;
    try {
      const parsed = Papa.parse<Record<string, string>>(await file.text(), {
        header: true,
        skipEmptyLines: true,
      });
      if (parsed.errors.length || !parsed.meta.fields?.includes("roi_id"))
        throw new Error("顺序表需要 roi_id 列，每行对应一行矩阵。");
      setMapping(parsed.data.map((r) => r.roi_id).join("\n"));
      setConfirmed(false);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function saveView() {
    if (!mapped) {
      notify("先确认脑区映射，或返回已绑定图谱，再保存分析视图");
      return;
    }
    try {
      const state = { ...view, camera: scene.current?.camera() || view.camera };
      await api(`/results/${resultId}/view`, { ...post(state), method: "PUT" });
      setView(state);
      notify("视角与选择已保存，下次打开自动恢复");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function exportImage() {
    try {
      downloadBlob(
        await scene.current!.image(),
        `hic-brain-${view.style}-${view.theme}.png`,
      );
      setExportOpen(false);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  function exportBundle() {
    if (!mapped) {
      notify("先确认脑区映射，或返回已绑定图谱，再导出数据与视图");
      return;
    }
    const bundle = {
      format: "hicbrain-view-1",
      result_id: resultId,
      name,
      result,
      atlas: mapped ? atlas : null,
      view: { ...view, camera: scene.current?.camera() || view.camera },
    };
    downloadBlob(
      new Blob([JSON.stringify(bundle)], { type: "application/json" }),
      `hic-brain-${resultId.slice(0, 8)}-view.json`,
    );
    setExportOpen(false);
  }
  async function restore(file?: File) {
    if (!file) return;
    try {
      const bundle = JSON.parse(await file.text());
      if (
        bundle.format !== "hicbrain-view-1" ||
        bundle.result_id !== resultId ||
        JSON.stringify(bundle.result?.connectivity) !==
          JSON.stringify(result.connectivity) ||
        JSON.stringify(bundle.result?.roi_ids) !==
          JSON.stringify(result.roi_ids) ||
        JSON.stringify(bundle.result?.graph) !== JSON.stringify(result.graph) ||
        JSON.stringify(bundle.result?.hypergraph) !==
          JSON.stringify(result.hypergraph) ||
        JSON.stringify(bundle.result?.config) !==
          JSON.stringify(result.config) ||
        JSON.stringify(bundle.result?.metadata?.atlas_binding) !==
          JSON.stringify(result.metadata.atlas_binding)
      )
        throw new Error("视图文件与当前分析结果不一致，请先选择对应的数据集。");
      if (
        bundle.atlas?.sha256?.content !==
        (mapped ? atlas?.sha256?.content : undefined)
      )
        throw new Error("图谱版本或映射不一致，不能恢复到不同的解剖空间。");
      const state = await api<ViewConfig>(`/results/${resultId}/view`, {
        ...post(bundle.view),
        method: "PUT",
      });
      setView(state);
      scene.current?.restore(state.camera);
      notify("已恢复相机、风格、图层和选择");
    } catch (e) {
      setError((e as Error).message);
    }
    if (restoreFile.current) restoreFile.current.value = "";
  }
  const count = (kind: "node" | "edge" | "hyperedge") => {
    const total =
      kind === "node"
        ? rois.length
        : kind === "edge"
          ? sceneEdges.length
          : sceneHypers.length;
    const enabled =
      kind === "node" ||
      (kind === "edge" ? view.layer !== "hypergraph" : view.layer !== "graph");
    const visible = !enabled
      ? 0
      : view.only_selected && view.selection
        ? kind === "node"
          ? focus.nodes.size
          : kind === "edge"
            ? focus.edgeIds.size
            : focus.hyperIds.size
        : total;
    return `${visible.toLocaleString()} / ${total.toLocaleString()}`;
  };
  const matrixIndices = [...members]
    .map((id) => result.roi_ids.indexOf(id))
    .filter((i) => i >= 0);
  const nodeName = (id: string) => roiById.get(id)?.abbreviation || id;
  const nodeRow = (id: string) => {
    const r = roiById.get(id);
    return (
      <button
        key={id}
        className="roi-item"
        onClick={() => select({ kind: "node", id })}
      >
        <span
          className="color-dot"
          style={{ background: r ? roiColor(r) : "#aaa" }}
        />
        <span>
          <strong>{r?.abbreviation || id}</strong>
          <small>{r?.name || "尚未映射英文全名"}</small>
        </span>
        <ChevronRight size={12} />
      </button>
    );
  };
  return (
    <section
      className={`brain-workbench ${view.theme}`}
      data-testid="brain-workbench"
    >
      <header className="viewer-top">
        <button
          className="viewer-brand"
          onClick={onBack}
          title="返回上传与分析"
        >
          <Brain size={25} />
          <span>
            Brain<span className="brand-dot">FC</span>
              <small>NETWORK EXPLORER</small>
          </span>
        </button>
        <label className="dataset-switch">
          <span>数据集</span>
          <select
            aria-label="数据集"
            value={resultId}
            onChange={(e) => onDataset?.(e.target.value)}
          >
            {datasets.length ? (
              datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))
            ) : (
              <option value={resultId}>{name}</option>
            )}
          </select>
        </label>
        <label className="atlas-switch">
          <span>图谱 / 参考空间</span>
          <select
            aria-label="图谱"
            value={atlasId}
            onChange={(e) => {
              setAtlasId(e.target.value);
              global();
            }}
          >
            {catalog.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
                {a.installed ? "" : " · 未安装"}
              </option>
            ))}
          </select>
        </label>
        <div className="viewer-actions">
          <button
            onClick={() =>
              patch({ theme: view.theme === "midnight" ? "paper" : "midnight" })
            }
            aria-label={view.theme === "midnight" ? "切换论文白" : "切换深夜蓝"}
          >
            {view.theme === "midnight" ? <Moon size={16} /> : <Sun size={16} />}
            <span>{view.theme === "midnight" ? "深夜蓝" : "论文白"}</span>
          </button>
          <button onClick={saveView} title="保存视角与选择">
            <Save size={16} />
            <span>保存</span>
          </button>
          <div className="export-menu">
            <button
              className="accent-button"
              onClick={() => setExportOpen(!exportOpen)}
            >
              <Download size={16} />
              导出
              <ChevronDown size={12} />
            </button>
            {exportOpen && (
              <div className="export-options">
                <button disabled={!geometry} onClick={exportImage}>
                  当前视角 PNG
                </button>
                <button onClick={exportBundle}>数据与视图 JSON</button>
                <button
                  onClick={() => {
                    downloadBlob(
                      new Blob(
                        [
                          Papa.unparse(
                            allHypers.flatMap((h) =>
                              h.members.map((m) => ({
                                hyperedge_id: h.source_id,
                                hyperedge_id_type: typeof h.source_id,
                                roi_id: m,
                                abbreviation:
                                  resultRoiById.get(m)?.abbreviation || "",
                                name: resultRoiById.get(m)?.name || "",
                                weight: h.weight ?? "",
                              })),
                            ),
                            { escapeFormulae: true },
                          ),
                        ],
                        { type: "text/csv;charset=utf-8" },
                      ),
                      "hyperedge-members.csv",
                    );
                    setExportOpen(false);
                  }}
                >
                  完整超边成员 CSV
                </button>
                <button
                  onClick={() => {
                    downloadBlob(
                      new Blob(
                        [
                          Papa.unparse(
                            [result.roi_ids, ...result.connectivity],
                            { escapeFormulae: true },
                          ),
                        ],
                        { type: "text/csv;charset=utf-8" },
                      ),
                      "connectivity.csv",
                    );
                    setExportOpen(false);
                  }}
                >
                  连接矩阵 CSV
                </button>
                <button
                  onClick={() => {
                    restoreFile.current?.click();
                    setExportOpen(false);
                  }}
                >
                  恢复视图 JSON…
                </button>
              </div>
            )}
          </div>
        </div>
        <input
          ref={restoreFile}
          type="file"
          accept=".json"
          hidden
          onChange={(e) => void restore(e.target.files?.[0])}
        />
      </header>
      <div className="viewer-stylebar">
        <div className="style-tabs" role="group" aria-label="可视化风格">
          {styles.map(([id, label, description], i) => (
            <button
              key={id}
              title={description}
              disabled={inherited && id === "parcels" && !Object.keys(geometry?.parcels || {}).length}
              className={view.style === id ? "active" : ""}
              onClick={() => patch({ style: id })}
            >
              <span className="style-number">0{i + 1}</span>
              {label}
            </button>
          ))}
        </div>
        <span className="local-indicator">
          <span />
          本机计算 · 已安装图谱可离线
        </span>
      </div>
      {error && (
        <div className="viewer-notice error" role="alert">
          {error}
          <button aria-label="关闭错误" onClick={() => setError("")}>
            <X size={16} />
          </button>
        </div>
      )}
      {toast && (
        <div className="viewer-toast" role="status">
          {toast}
        </div>
      )}
      <div className={`viewer-body ${left ? "" : "left-closed"}`}>
        {left && (
          <aside className="viewer-left">
            <div className="panel-title">
              <span>数据与显示</span>
              <button onClick={() => setLeft(false)} aria-label="收起左侧面板">
                <ChevronLeft size={16} />
              </button>
            </div>
            <section>
              <div className="micro-heading">当前输入</div>
              <strong className="file-name" title={name}>
                {name}
              </strong>
              <div className="data-facts">
                <span>{result.roi_ids.length} 脑区</span>
                <span>
                  {String(
                    result.metadata.matrix_kind ||
                      result.metadata.connectivity_kind ||
                      result.config.connectivity_method ||
                      "连接矩阵",
                  )}
                </span>
              </div>
              <p className="muted">
                普通边 {allEdges.length.toLocaleString()} · 超边{" "}
                {allHypers.length.toLocaleString()}
              </p>
              <button className="text-button" onClick={onBack}>
                <ArrowLeft size={12} />
                上传 / 分析其他数据
              </button>
            </section>
            <section>
              <div className="micro-heading">解剖映射</div>
              <div className={`mapping-state ${mapped ? "valid" : ""}`}>
                {mapped ? "● 已验证脑区顺序" : "○ 图谱预览 · 数据尚未叠加"}
              </div>
              <p className="muted">
                {atlas?.space || "选择图谱"} · {atlas?.version || ""}
              </p>
              {!atlas?.installed && (
                <>
                  <p>首次使用需下载图谱和参考脑，并生成脑区表面。</p>
                  <button
                    className="accent-button full"
                    disabled={!!busy || !atlasId}
                    onClick={install}
                  >
                    <Download size={14} />
                    安装所选图谱
                  </button>
                </>
              )}
              {atlas?.installed && !mapped && (
                <>
                  {bind ? (
                    <>
                      <p>当前结果绑定了另一分区。预览不会改变数据映射。</p>
                      <button
                        className="accent-button full"
                        onClick={() => {
                          setAtlasId(bind.atlas_id);
                          global();
                        }}
                      >
                        返回已绑定图谱
                      </button>
                    </>
                  ) : (
                    <details className="mapping-form" open>
                      <summary>确认矩阵每行对应的脑区</summary>
                      <p>
                        图谱有 {atlas.n_rois} 区，数据有 {result.roi_ids.length}{" "}
                        行。数量一致也需要核实顺序。
                      </p>
                      <button
                        className="outline-button full"
                        onClick={() => {
                          setMapping(
                            (atlas.labels || [])
                              .map((r) => r.roi_id)
                              .join("\n"),
                          );
                          setConfirmed(false);
                        }}
                      >
                        填入图谱标准顺序
                      </button>
                      <label className="upload-small">
                        导入顺序表 CSV / TSV
                        <input
                          type="file"
                          accept=".csv,.tsv"
                          onChange={(e) => void readOrder(e.target.files?.[0])}
                        />
                      </label>
                      <textarea
                        aria-label="矩阵脑区顺序"
                        rows={5}
                        value={mapping}
                        onChange={(e) => {
                          setMapping(e.target.value);
                          setConfirmed(false);
                        }}
                        placeholder="每行一个图谱 roi_id，与矩阵行顺序一致"
                      />
                      <small>
                        {
                          mapping.split(/[\n,\t]+/).filter((s) => s.trim())
                            .length
                        }{" "}
                        / {result.roi_ids.length} 行 · 首行数据 ID：
                        {result.roi_ids[0]}
                      </small>
                      <label className="check-row">
                        <input
                          type="checkbox"
                          checked={confirmed}
                          onChange={(e) => setConfirmed(e.target.checked)}
                        />
                        我已核实数据使用该分区及上述顺序
                      </label>
                      <button
                        className="accent-button full"
                        disabled={!confirmed || !!busy}
                        onClick={applyMapping}
                      >
                        验证并叠加连接
                      </button>
                    </details>
                  )}
                </>
              )}
              <button
                className="text-button"
                onClick={() => setImportOpen(true)}
              >
                <Upload size={13} />
                导入我的 NIfTI 图谱
              </button>
              {atlas?.installed && !inherited && (
                <button
                  className="text-button"
                  onClick={() => setBottom(bottom === "slices" ? "" : "slices")}
                >
                  核查图谱切片与参考脑
                </button>
              )}
            </section>
            <section>
              <div className="micro-heading">显示结构</div>
              <div className="layer-switch">
                {[
                  ["graph", "普通图"],
                  ["hypergraph", "超图"],
                  ["both", "叠加"],
                ].map(([id, label]) => (
                  <button
                    key={id}
                    className={view.layer === id ? "active" : ""}
                    onClick={() => patch({ layer: id as ViewConfig["layer"] })}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <label className="opacity-label">
                全局脑表面不透明度{" "}
                <strong>{Math.round(view.opacity * 100)}%</strong>
              </label>
              <input
                aria-label="脑表面不透明度"
                type="range"
                min="0"
                max="1"
                step=".01"
                value={view.opacity}
                onChange={(e) => patch({ opacity: +e.target.value })}
              />
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={view.labels}
                  onChange={(e) => patch({ labels: e.target.checked })}
                />
                显示全部英文缩写
              </label>
              <label className="check-row">
                <input
                  type="checkbox"
                  disabled={!view.selection}
                  checked={view.only_selected}
                  onChange={(e) => patch({ only_selected: e.target.checked })}
                />
                仅看所选及其关联结构
              </label>
              <p className="muted">
                选择时背景自动淡出；恢复全局可查看全部结构。
              </p>
            </section>
            <section>
              <div className="micro-heading">查找脑区</div>
              <input
                aria-label="查找脑区"
                placeholder="缩写 / 英文名称 / ROI ID"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              {search && (
                <div className="roi-search-list">
                  {rois
                    .filter((r) =>
                      `${r.abbreviation} ${r.name} ${r.roi_id}`
                        .toLowerCase()
                        .includes(search.toLowerCase()),
                    )
                    .map((r) => nodeRow(r.source_roi_id || r.roi_id))}
                </div>
              )}
            </section>
          </aside>
        )}
        <main className={`viewer-center${bottom ? " bottom-open" : ""}`}>
          <div className="scene-tools">
            {!left && (
              <button aria-label="展开左侧面板" onClick={() => setLeft(true)}>
                <ChevronRight size={16} />
              </button>
            )}
            <div className="scene-heading">
              <strong>{styles.find((s) => s[0] === view.style)?.[1]}</strong>
              <span>{mapped ? "已映射的脑网络" : "图谱预览"}</span>
            </div>
            <div className="camera-buttons">
              <select
                aria-label="标准视角"
                defaultValue=""
                onChange={(e) => {
                  scene.current?.orient(e.target.value);
                  e.target.value = "";
                }}
              >
                <option value="" disabled>
                  标准方向
                </option>
                <option value="anterior">前 · A</option>
                <option value="posterior">后 · P</option>
                <option value="left">左 · L</option>
                <option value="right">右 · R</option>
                <option value="superior">顶 · S</option>
              </select>
              <button
                aria-label="视角复位"
                title="视角复位"
                onClick={() => scene.current?.orient("reset")}
              >
                <RotateCcw size={16} />
              </button>
            </div>
          </div>
          <div className="scene-stage">
            {geometry && rois.length ? (
              <BrainScene
                ref={scene}
                rois={rois}
                edges={sceneEdges}
                hypers={sceneHypers}
                geometry={geometry}
                view={view}
                onSelect={select}
                onCandidates={setCandidates}
                onStatus={reportStatus}
                onSlow={reportSlow}
              />
            ) : (
              <div className="viewer-empty">
                <Brain size={64} strokeWidth={1} />
                <h2>{busy ? "正在准备三维脑" : "选择并安装一个标准图谱"}</h2>
                <p>真实参考脑与脑区分割将在这里显示</p>
              </div>
            )}
            {busy && (
              <div className="scene-loading" role="status">
                <LoaderCircle size={17} className="spin" />
                {busy}
              </div>
            )}
            {!mapped && geometry && (
              <div className="preview-badge">
                仅预览图谱。确认左侧脑区映射后显示连接。
              </div>
            )}
            {view.selection && (
              <button className="reset-selection" onClick={global}>
                <Focus size={14} />
                恢复全局
              </button>
            )}
          </div>
          <div className="scene-status">
            <span>
              脑区 <b>{count("node")}</b>
            </span>
            <span>
              普通边 <b>{count("edge")}</b>
            </span>
            <span>
              超边 <b>{count("hyperedge")}</b>
            </span>
            <span className="scene-help">拖动旋转 · 右键平移 · 滚轮缩放</span>
          </div>
          {(slow ||
            status.lod ||
            sceneEdges.length > 10000 ||
            sceneHypers.length > 1000) && (
            <div className="viewer-resource">
              结构较密，已保留全部连接。
              {status.lod ? "普通边使用低精度线段。" : ""}
              可点击对象并开启“仅看所选”改善交互。
            </div>
          )}
          {status.fallback > 0 && (
            <div className="viewer-resource">
              {status.fallback} 条超边无法形成稳定包络，已用骨架保留全部成员。
            </div>
          )}
          <div className="bottom-tabs">
            {[
              ["matrix", "连接热图"],
              ["members", "脑区与超边成员表"],
              ["slices", "图谱切片核查"],
            ].filter(([id]) => !inherited || id !== "slices").map(([id, label]) => (
              <button
                key={id}
                className={bottom === id ? "active" : ""}
                onClick={() =>
                  setBottom(bottom === id ? "" : (id as typeof bottom))
                }
              >
                {label}
                <ChevronDown
                  size={13}
                  style={{ transform: bottom === id ? "rotate(180deg)" : "" }}
                />
              </button>
            ))}
            <span>{view.selection ? "与当前选择联动" : "按需展开"}</span>
          </div>
          {bottom && (
            <div className="bottom-content">
              {bottom === "matrix" && (
                <>
                  <div className="table-caption">
                    完整矩阵 · 点击单元格选择已有普通边，点击对角线选择脑区
                    {!mapped && " · 未映射时沿用原始数据标签"}
                  </div>
                  <Suspense fallback={<p>正在加载热图</p>}>
                    <Plot
                      height={330}
                      data={[
                        {
                          type: "heatmap",
                          z: result.connectivity,
                          x: result.labels,
                          y: result.labels,
                          colorscale: [
                            [0, "#438dd3"],
                            [
                              0.5,
                              view.theme === "midnight" ? "#111d2e" : "#ffffff",
                            ],
                            [1, "#e69950"],
                          ],
                          zmin: -Math.max(
                            ...result.connectivity.map((row) =>
                              Math.max(...row.map(Math.abs)),
                            ),
                          ),
                          zmax: Math.max(
                            ...result.connectivity.map((row) =>
                              Math.max(...row.map(Math.abs)),
                            ),
                          ),
                          hovertemplate:
                            "%{y} ↔ %{x}<br>%{z:.4f}<extra></extra>",
                        },
                      ]}
                      layout={{
                        font: {
                          color:
                            view.theme === "midnight" ? "#c7d8ec" : "#24374b",
                          size: 10,
                        },
                        margin: { l: 80, r: 45, t: 10, b: 60 },
                        xaxis: { tickangle: -45, nticks: 16 },
                        yaxis: { autorange: "reversed", nticks: 16 },
                        shapes: matrixIndices.flatMap((i) => [
                          {
                            type: "rect" as const,
                            x0: i - 0.5,
                            x1: i + 0.5,
                            y0: -0.5,
                            y1: result.roi_ids.length - 0.5,
                            line: { color: "#66ccb8", width: 1 },
                            fillcolor: "transparent",
                          },
                          {
                            type: "rect" as const,
                            x0: -0.5,
                            x1: result.roi_ids.length - 0.5,
                            y0: i - 0.5,
                            y1: i + 0.5,
                            line: { color: "#66ccb8", width: 1 },
                            fillcolor: "transparent",
                          },
                        ]),
                      }}
                      onClick={(e) => {
                        if (!mapped) {
                          notify("请先确认脑区映射，以联动三维脑");
                          return;
                        }
                        const point = e.points[0],
                          i = result.labels.indexOf(String(point.y)),
                          j = result.labels.indexOf(String(point.x));
                        if (i < 0 || j < 0) return;
                        if (i === j)
                          select({ kind: "node", id: result.roi_ids[i] });
                        else {
                          const edge = allEdges.find(
                            (a) =>
                              (a.source === result.roi_ids[i] &&
                                a.target === result.roi_ids[j]) ||
                              (a.source === result.roi_ids[j] &&
                                a.target === result.roi_ids[i]),
                          );
                          if (edge) {
                            patch({
                              layer:
                                view.layer === "hypergraph"
                                  ? "both"
                                  : view.layer,
                            });
                            select({ kind: "edge", id: edge.id });
                          } else notify("该矩阵单元未在当前分析中构成普通边");
                        }
                      }}
                    />
                  </Suspense>
                </>
              )}
              {bottom === "members" && (
                <div className="member-tables">
                  <div>
                    <div className="table-caption">脑区 · {rois.length}</div>
                    <div className="scroll-table">
                      <table>
                        <thead>
                          <tr>
                            <th>缩写 / 全名</th>
                            <th>半球</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rois.map((r) => (
                            <tr
                              key={r.roi_id}
                              className={
                                members.has(r.source_roi_id || r.roi_id)
                                  ? "selected"
                                  : ""
                              }
                              onClick={() =>
                                select({
                                  kind: "node",
                                  id: r.source_roi_id || r.roi_id,
                                })
                              }
                            >
                              <td>
                                <strong>{r.abbreviation}</strong>
                                <small>{r.name}</small>
                              </td>
                              <td>{r.hemisphere}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div>
                    <div className="table-caption">
                      超边完整成员 · {sceneHypers.length} 条（独立 ID）
                    </div>
                    <div className="scroll-table">
                      <table>
                        <thead>
                          <tr>
                            <th>超边</th>
                            <th>成员</th>
                            <th>数量</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sceneHypers.map((h) => (
                            <tr
                              key={h.id}
                              className={
                                focus.hyperIds.has(h.id) ? "selected" : ""
                              }
                              onClick={() => {
                                patch({
                                  layer:
                                    view.layer === "graph"
                                      ? "both"
                                      : view.layer,
                                });
                                select({ kind: "hyperedge", id: h.id });
                              }}
                            >
                              <td>
                                <i
                                  className="color-dot"
                                  style={{ background: categoryColor(h.id) }}
                                />
                                {h.display_id}
                              </td>
                              <td>{h.members.map(nodeName).join(" · ")}</td>
                              <td>{h.members.length}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
              {bottom === "slices" && atlas?.installed && !inherited && (
                <Suspense fallback={<p>正在加载切片核查</p>}>
                  <AtlasSlices
                    atlas={atlas}
                    coordinate={selectedNode?.coordinates}
                  />
                </Suspense>
              )}
            </div>
          )}
        </main>
        <aside className="viewer-details">
          <div className="panel-title">
            <span>{view.selection ? "当前选择" : "图谱与图例"}</span>
            {view.selection && (
              <button aria-label="清除选择" onClick={global}>
                <X size={15} />
              </button>
            )}
          </div>
          {candidates.length > 1 && (
            <section className="overlap-list">
              <div className="micro-heading">
                此位置有 {candidates.length} 个候选对象
              </div>
              <select
                aria-label="重叠对象候选"
                value={`${view.selection?.kind}:${view.selection?.id}`}
                onChange={(e) => {
                  const s = candidates.find(
                    (c) => `${c.kind}:${c.id}` === e.target.value,
                  );
                  if (s) select(s);
                }}
              >
                {candidates.map((s) => (
                  <option key={`${s.kind}:${s.id}`} value={`${s.kind}:${s.id}`}>
                    {s.kind === "node"
                      ? "脑区 " + nodeName(s.id)
                      : s.kind === "edge"
                        ? "普通边 " + s.id
                        : "超边 " +
                          (sceneHypers.find((h) => h.id === s.id)?.display_id ||
                            s.id)}
                  </option>
                ))}
              </select>
            </section>
          )}
          {selectedNode ? (
            <>
              <section className="selection-identity">
                <div className="micro-heading">BRAIN REGION</div>
                <h2>{selectedNode.abbreviation}</h2>
                <p>{selectedNode.name}</p>
                <span className="detail-tag">
                  {hemiNames[selectedNode.hemisphere]}
                </span>
                <dl>
                  <dt>图谱 ID</dt>
                  <dd>{selectedNode.roi_id}</dd>
                  <dt>图像标签值</dt>
                  <dd>{selectedNode.label_value}</dd>
                  <dt>参考坐标 / mm</dt>
                  <dd>
                    {selectedNode.coordinates
                      .map((x) => x.toFixed(1))
                      .join(", ")}
                  </dd>
                  {selectedNode.network && (
                    <>
                      <dt>分区归属</dt>
                      <dd>{selectedNode.network}</dd>
                    </>
                  )}
                </dl>
              </section>
              <section>
                <div className="micro-heading">
                  相连普通边 · {focus.edgeIds.size}
                </div>
                <div className="detail-scroll">
                  {sceneEdges
                    .filter((e) => focus.edgeIds.has(e.id))
                    .map((e) => (
                      <button
                        key={e.id}
                        className="edge-item"
                        onClick={() => select({ kind: "edge", id: e.id })}
                      >
                        <span>
                          {nodeName(
                            e.source === view.selection!.id
                              ? e.target
                              : e.source,
                          )}
                        </span>
                        <b
                          style={{
                            color: e.weight < 0 ? "#438dd3" : "#e69950",
                          }}
                        >
                          {e.weight.toFixed(4)}
                        </b>
                      </button>
                    ))}
                </div>
              </section>
              <section>
                <div className="micro-heading">
                  所属超边 · {focus.hyperIds.size}
                </div>
                <div className="detail-scroll">
                  {sceneHypers
                    .filter((h) => focus.hyperIds.has(h.id))
                    .map((h) => (
                      <button
                        key={h.id}
                        className="edge-item"
                        onClick={() => {
                          patch({
                            layer: view.layer === "graph" ? "both" : view.layer,
                          });
                          select({ kind: "hyperedge", id: h.id });
                        }}
                      >
                        <span>
                          <i
                            className="color-dot"
                            style={{ background: categoryColor(h.id) }}
                          />
                          {h.display_id}
                        </span>
                        <span>{h.members.length} 区</span>
                      </button>
                    ))}
                </div>
              </section>
            </>
          ) : selectedEdge ? (
            <>
              <section className="selection-identity">
                <div className="micro-heading">PAIRWISE CONNECTION</div>
                <h2>
                  {nodeName(selectedEdge.source)}
                  <span className="connection-symbol">↔</span>
                  {nodeName(selectedEdge.target)}
                </h2>
                <div
                  className="weight-value"
                  style={{
                    color: selectedEdge.weight < 0 ? "#438dd3" : "#e69950",
                  }}
                >
                  {selectedEdge.weight.toFixed(5)}
                </div>
                <p>
                  {selectedEdge.weight < 0 ? "负连接" : "正连接"} ·{" "}
                  {String(
                    result.metadata.output_matrix_kind ||
                      result.config.connectivity_method ||
                      "连接值",
                  )}
                </p>
                <dl>
                  <dt>普通边 ID</dt>
                  <dd>{selectedEdge.id}</dd>
                  <dt>构建方式</dt>
                  <dd>{String(result.config.graph_method)}</dd>
                </dl>
              </section>
              <section>
                <div className="micro-heading">两个端点</div>
                {nodeRow(selectedEdge.source)}
                {nodeRow(selectedEdge.target)}
              </section>
            </>
          ) : selectedHyper ? (
            <>
              <section className="selection-identity">
                <div className="micro-heading">HYPEREDGE</div>
                <h2>
                  <i
                    className="color-dot"
                    style={{ background: categoryColor(selectedHyper.id) }}
                  />
                  {selectedHyper.display_id}
                </h2>
                <p>{selectedHyper.members.length} 个成员 · 完整成员集合</p>
                <dl>
                  <dt>构建方式</dt>
                  <dd>{String(result.config.hypergraph_method)}</dd>
                  <dt>超边权重</dt>
                  <dd>{pretty(selectedHyper.weight)}</dd>
                </dl>
              </section>
              <section>
                <div className="micro-heading">成员缩写与英文全名</div>
                {selectedHyper.members.map(nodeRow)}
              </section>
              <section>
                <p className="muted">
                  包络与曲线只表达成员关系，不表示纤维束。包络内其他脑区不属于该超边；空心六边形
                  H 是超边锚点，不是脑区。
                </p>
              </section>
            </>
          ) : (
            <>
              <section className="selection-identity">
                <div className="micro-heading">ANATOMICAL REFERENCE</div>
                <h2>{atlas?.name || "未选择图谱"}</h2>
                <p>{atlas?.space || ""}</p>
                <div className="detail-tag">
                  {atlas?.n_rois || 0} parcels · {atlas?.version || ""}
                </div>
                <p className="muted" style={{ marginTop: 15 }}>
                  点击脑区、连接或超边，查看与当前对象有关的信息。
                </p>
              </section>
              <section>
                <div className="micro-heading">普通连接</div>
                <div className="legend-row">
                  <i
                    className="legend-line"
                    style={{ background: "#e69950" }}
                  />
                  正连接
                </div>
                <div className="legend-row">
                  <i
                    className="legend-line"
                    style={{ background: "#438dd3" }}
                  />
                  负连接
                </div>
                <p className="muted">
                  同一分析中，线粗随连接绝对值变化；低精度模式使用等宽线。
                </p>
              </section>
              <section>
                <div className="micro-heading">脑区颜色</div>
                {view.style === "parcels" && (
                  <p className="muted">
                    分区表面使用图谱颜色；未提供时按脑区 ID
                    配色。下方图例对应定位球，点击表面查看确切分区。
                  </p>
                )}
                {Array.from(
                  new Map(
                    rois.map((r) => [
                      r.network && r.network !== "AAL anatomical region"
                        ? r.network
                        : hemiNames[r.hemisphere],
                      r,
                    ]),
                  ).entries(),
                ).map(([label, r]) => (
                  <div className="legend-row" key={label}>
                    <i
                      className="color-dot"
                      style={{ background: roiColor(r) }}
                    />
                    {label}
                  </div>
                ))}
              </section>
              <section>
                <div className="micro-heading">超边颜色与成员</div>
                <p>
                  颜色用于区分超边，不表示疾病或显著性。不同 ID
                  可能共用颜色，点击后以 ID 和完整成员表确认。
                </p>
                <p className="muted">
                  ⬡ H 超边锚点 · 非脑区
                  <br />
                  透明面 / 包络 · 非脑组织或纤维束
                </p>
              </section>
              <section>
                <details>
                  <summary>来源与许可</summary>
                  {atlas?.sources?.map((url) => (
                    <a key={url} href={url} target="_blank" rel="noreferrer">
                      {new URL(url).hostname} ↗
                    </a>
                  ))}
                  <p className="muted">
                    {atlas?.license || "安装后查看资源来源和许可"}
                  </p>
                </details>
              </section>
            </>
          )}
        </aside>
      </div>
      {importOpen && (
        <AtlasImport
          onClose={() => setImportOpen(false)}
          onDone={async (id) => {
            const list = await api<{ atlases: Atlas[] }>("/atlases");
            setCatalog(list.atlases);
            setAtlasId(id);
            setImportOpen(false);
            global();
            notify("自定义图谱已验证，表面已生成");
          }}
        />
      )}
    </section>
  );
}
