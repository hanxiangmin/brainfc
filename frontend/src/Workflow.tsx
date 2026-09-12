import RawPreparation from "./NativePreparation";
import { useEffect, useRef, useState } from "react";

async function request(path: string, body?: any) {
  const r = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const data = await r.json();
  if (!r.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
type Props = {
  job: any;
  busy: boolean;
  onJob: (job: any) => void;
  onError: (e: any) => void;
};
const kinds = [
  ["auto", "已处理影像 / ROI 时序（自动识别）"],
  ["raw-bids", "原始 NIfTI / BIDS"],
  ["raw-dicom", "原始 DICOM"],
];
const defaultConfig = {
  t_r: "",
  high_pass: "",
  low_pass: "",
  discard: "0",
  fd_threshold: "",
  min_samples: "20",
  method: "pearson",
  data_space: "",
  atlas_space: "",
  preprocessed: false,
  detrend: true,
  standardize: true,
  table_header: true,
  transpose: false,
  variable: "",
  confound_columns: "",
};

export default function Workflow({ job, busy, onJob, onError }: Props) {
  const [catalog, setCatalog] = useState<any>(null),
    [dataset, setDataset] = useState("custom"),
    [variant, setVariant] = useState("custom"),
    [kind, setKind] = useState("auto");
  const [step, setStep] = useState(0),
    [highest, setHighest] = useState(0),
    [paths, setPaths] = useState<Record<string, string>>({}),
    [config, setConfig] = useState(defaultConfig),
    [info, setInfo] = useState<any>(null),
    [review, setReview] = useState<any>(null),
    [accepted, setAccepted] = useState(false),
    [localBusy, setLocalBusy] = useState(false);
  const [referenceDecision, setReferenceDecision] = useState("skip"),
    [roiDecision, setRoiDecision] = useState("skip"),
    [denoiseDecision, setDenoiseDecision] = useState(""),
    [sourceConfirmed, setSourceConfirmed] = useState(false),
    [rawQc, setRawQc] = useState(false),
    [rawReady, setRawReady] = useState(false),
    [atlasName, setAtlasName] = useState("schaefer100"),
    [atlasJob, setAtlasJob] = useState(""),
    [trNotice, setTrNotice] = useState("");
  const [autoNotes, setAutoNotes] = useState<string[]>([]),
    [tableEdited, setTableEdited] = useState(false);
  const session = useRef(crypto.randomUUID());
  const preset = catalog?.datasets
    .find((d: any) => d.id === dataset)
    ?.variants.find((v: any) => v.id === variant);
  const disabled = busy || localBusy;
  const effectiveKind =
    kind === "auto"
      ? info?.format === "timeseries-table"
        ? "table"
        : info?.format ||
          (/\.(csv|tsv|txt|1d|npy|npz|mat)$/i.test(paths.source || "")
            ? "table"
            : "volume")
      : kind;
  const isRaw = kind.startsWith("raw"),
    isTable = effectiveKind === "table",
    volume = effectiveKind === "volume" || isRaw;
  useEffect(() => {
    request("/api/presets").then(setCatalog).catch(onError);
  }, []);
  useEffect(() => {
    if (job?.id === atlasJob && job?.status === "complete" && job.atlas) {
      setPaths((p) => ({ ...p, atlas: job.atlas.atlas, rois: job.atlas.rois }));
      setConfig((c) => ({ ...c, atlas_space: job.atlas.space }));
    }
  }, [job?.id, job?.status, atlasJob]);
  function invalidate() {
    setHighest(step);
    setReview(null);
    setAccepted(false);
  }
  function setValue(key: string, value: any) {
    if (["table_header", "transpose", "variable"].includes(key))
      setTableEdited(true);
    invalidate();
    setConfig((c) => ({ ...c, [key]: value }));
  }
  function setPath(key: string, value: string) {
    invalidate();
    setPaths((p) =>
      key === "source" ? { source: value } : { ...p, [key]: value },
    );
    if (key === "source") {
      setInfo(null);
      setSourceConfirmed(false);
      setTrNotice("");
      setAutoNotes([]);
      setTableEdited(false);
      setReferenceDecision("skip");
      setRoiDecision("skip");
      setDenoiseDecision("");
      setConfig({
        ...defaultConfig,
        t_r: preset?.t_r ? String(preset.t_r) : "",
      });
    }
  }
  function chooseDataset(d: any, v: any) {
    setDataset(d.id);
    setVariant(v.id);
    setKind(v.input_kind.startsWith("raw") ? v.input_kind : "auto");
    setConfig({ ...defaultConfig, t_r: v.t_r === null ? "" : String(v.t_r) });
    setPaths({});
    setInfo(null);
    setRawReady(false);
    setRawQc(false);
    setSourceConfirmed(false);
    setHighest(0);
    setReview(null);
    setDenoiseDecision("");
    setReferenceDecision("skip");
    setRoiDecision("skip");
    setTrNotice("");
    setAutoNotes([]);
    setTableEdited(false);
  }
  async function action(fn: () => Promise<any>) {
    setLocalBusy(true);
    try {
      await fn();
    } catch (e) {
      onError(e);
    } finally {
      setLocalBusy(false);
    }
  }
  function payload() {
    return {
      ...paths,
      config: {
        ...config,
        t_r: config.t_r ? Number(config.t_r) : null,
        high_pass: config.high_pass ? Number(config.high_pass) : null,
        low_pass: config.low_pass ? Number(config.low_pass) : null,
        discard: Number(config.discard),
        fd_threshold: config.fd_threshold ? Number(config.fd_threshold) : null,
        min_samples: Number(config.min_samples),
        data_space: config.data_space || null,
        atlas_space: config.atlas_space || null,
        variable: config.variable || null,
        confound_columns: config.confound_columns
          ? config.confound_columns.split(",").map((c) => c.trim())
          : null,
      },
    };
  }
  async function advance() {
    if (step === 0) {
      const suggestion = await request("/api/input-suggestions", {
        source: paths.source,
        overrides: tableEdited
          ? {
              table_header: config.table_header,
              transpose: config.transpose,
              variable: config.variable || null,
            }
          : undefined,
      });
      const d = suggestion.info;
      if (isRaw && d.format !== "volume")
        throw new Error("原始数据流程需选择预处理后的 4D BOLD。");
      setInfo(d);
      setAutoNotes(suggestion.notes);
      setPaths((p) => ({ ...p, ...suggestion.paths }));
      setConfig((c) => ({
        ...c,
        ...suggestion.config,
        confound_columns: Array.isArray(suggestion.config.confound_columns)
          ? suggestion.config.confound_columns.join(",")
          : suggestion.config.confound_columns ?? c.confound_columns,
        discard: String(suggestion.config.discard ?? c.discard),
        data_space: d.space || suggestion.config.data_space || c.data_space,
        atlas_space: suggestion.config.atlas_space || c.atlas_space,
      }));
      setReferenceDecision(
        suggestion.paths.reference || paths.reference ? "supply" : "skip",
      );
      setRoiDecision(suggestion.paths.rois || paths.rois ? "supply" : "skip");
      if (suggestion.paths.confounds || paths.confounds)
        setDenoiseDecision("regress");
      if (d.t_r) {
        setTrNotice(
          preset?.t_r && Math.abs(preset.t_r - d.t_r) > 1e-4
            ? `方案参考 TR ${preset.t_r} s 与扫描 ${d.t_r} s 不同。已使用${d.tr_source}中的 ${d.t_r} s；请确认站点 / 序列。`
            : `TR ${d.t_r} s，读取自${d.tr_source}。`,
        );
        setConfig((c) => ({
          ...c,
          t_r: String(d.t_r),
          data_space: d.space || c.data_space,
        }));
      }
    }
    if (step === 2)
      await request("/api/preflight", { ...payload(), stage: "spatial" });
    if (step === 2) setReview(await request("/api/preflight", payload()));
    setHighest(step + 2);
    setStep(step + 2);
    setAccepted(false);
  }
  function decision(v: string) {
    setDenoiseDecision(v);
    invalidate();
    if (v !== "regress") {
      setPaths((p) => ({ ...p, confounds: "" }));
      setConfig((c) => ({
        ...c,
        confound_columns: "",
        fd_threshold: "",
        ...(v === "upstream"
          ? {
              detrend: false,
              standardize: false,
              high_pass: "",
              low_pass: "",
              discard: "0",
            }
          : {}),
      }));
    }
  }
  async function submit() {
    if (!accepted || !review || highest !== 4) return;
    const p = {
      ...payload(),
      guidance: {
        dataset,
        variant,
        input_kind: isRaw ? kind : effectiveKind,
        source_confirmed: true,
        spatial_confirmed: true,
        denoise_confirmed: true,
        review_confirmed: true,
        raw_qc_confirmed: rawQc,
        confounds_decision: denoiseDecision,
        reference_decision: referenceDecision,
        roi_decision: roiDecision,
        metadata_notice: trNotice,
      },
    };
    onJob(await request("/api/jobs", p));
  }
  function field(key: string, label: string, hint = "完整本地路径") {
    const source = key === "source";
    const chooser = (
      <label className={source ? "source-picker" : "upload"}>
        {source ? (paths.source ? "重新选择数据文件" : "选择数据文件") : "选择"}
        <input
          type="file"
          multiple={source}
          aria-label={`选择${label}`}
          onChange={(e) => {
            const chosen = Array.from(e.target.files || []);
            if (chosen.length)
              action(async () => {
                const uploaded: { name: string; path: string }[] = [];
                for (const file of chosen) {
                  const form = new FormData();
                  form.append("file", file);
                  form.append("session", session.current);
                  const r = await fetch("/api/upload", {
                    method: "POST",
                    body: form,
                  });
                  const d = await r.json();
                  if (!r.ok) throw new Error(d.detail);
                  uploaded.push({ name: file.name, path: d.path });
                }
                if (source) {
                  const primary = uploaded.filter(
                    (f) =>
                      !/\.json$/i.test(f.name) &&
                      !/(confounds|brain_mask|_T1w|_dseg|\.dlabel\.|\.label\.)/i.test(
                        f.name,
                      ),
                  );
                  if (primary.length !== 1)
                    throw new Error(
                      "请一次选择一个 BOLD / ROI 时序，可同时附带其 JSON、confounds 和脑掩膜。",
                    );
                  setPath("source", primary[0].path);
                } else if (key !== "sidecar") setPath(key, uploaded[0].path);
                else {
                  setInfo(null);
                  setSourceConfirmed(false);
                }
              });
          }}
        />
      </label>
    );
    if (source && isRaw)
      return (
        <div className="chosen-file">
          已选择预处理输出：{paths.source?.split(/[\\/]/).pop()}
        </div>
      );
    if (source)
      return (
        <div className="source-choice">
          {chooser}
          <p className="muted">可同时选择本次扫描的 JSON、混杂变量和脑掩膜。</p>
          {paths.source && (
            <p className="chosen-file">{paths.source.split(/[\\/]/).pop()}</p>
          )}
          <details>
            <summary>使用本地路径（大文件免上传）</summary>
            <label>
              {label}
              <input
                aria-label={label}
                value={paths[key] || ""}
                placeholder={hint}
                onChange={(e) => setPath(key, e.target.value)}
              />
            </label>
          </details>
        </div>
      );
    return (
      <label className="file-field">
        {label}
        <div className="file-row">
          <input
            aria-label={label}
            value={paths[key] || ""}
            placeholder={hint}
            onChange={(e) => setPath(key, e.target.value)}
          />
          {chooser}
        </div>
      </label>
    );
  }
  const text = (
    key: keyof typeof defaultConfig,
    label: string,
    type = "text",
    placeholder = "",
  ) => (
    <label>
      {label}
      <input
        aria-label={label}
        type={type}
        step="any"
        value={String(config[key])}
        placeholder={placeholder}
        onChange={(e) => setValue(key, e.target.value)}
      />
    </label>
  );
  const check = (key: keyof typeof defaultConfig, label: string) => (
    <label className="check">
      <input
        type="checkbox"
        checked={!!config[key]}
        onChange={(e) => setValue(key, e.target.checked)}
      />
      {label}
    </label>
  );
  const canNext =
    step === 0
      ? !!preset && !!paths.source && sourceConfirmed && (!isRaw || rawReady)
      : step === 2
        ? referenceDecision !== "" &&
          (!isTable || roiDecision !== "") &&
          (info?.format === "timeseries-table" || config.preprocessed) &&
          !!denoiseDecision &&
          (denoiseDecision !== "regress" || !!paths.confounds)
        : false;

  return (
    <div className="guided-workflow">
      <div className="section-heading">
        <h2>处理引导</h2>
        <button
          className="link"
          disabled={disabled}
          onClick={() =>
            action(async () => onJob(await request("/api/demo", {})))
          }
        >
          真实样例 ↗
        </button>
      </div>
      <p className="muted">
        选文件后自动填写能确认的信息。高级选项可保持默认；缺失信息才需补充。
      </p>
      <nav className="workflow-steps" aria-label="处理步骤">
        {["选择数据", "确认处理方案", "开始处理"].map((s, index) => {
          const i = index * 2;
          return (
            <button
              key={s}
              disabled={i > highest || disabled}
              className={i === step ? "active" : i < step ? "done" : ""}
              onClick={() => {
                setStep(i);
                setHighest(i);
                setReview(null);
                setAccepted(false);
              }}
            >
              <span>{i < step ? "✓" : index + 1}</span>
              {s}
            </button>
          );
        })}
      </nav>
      <fieldset disabled={disabled}>
        {step === 0 && (
          <>
            <h3>选择要处理的数据</h3>
            <label>
              数据来源（可不选）
              <select
                aria-label="公开数据集"
                value={dataset}
                onChange={(e) => {
                  const d = catalog.datasets.find(
                    (d: any) => d.id === e.target.value,
                  );
                  chooseDataset(d, d.variants[0]);
                }}
              >
                {catalog?.datasets.map((d: any) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
            {dataset !== "custom" && (
              <label>
                采集方案 / 处理版本
                <select
                  aria-label="采集方案"
                  value={variant}
                  onChange={(e) => {
                    const d = catalog.datasets.find(
                      (d: any) => d.id === dataset,
                    );
                    chooseDataset(
                      d,
                      d.variants.find((v: any) => v.id === e.target.value),
                    );
                  }}
                >
                  {catalog?.datasets
                    .find((d: any) => d.id === dataset)
                    ?.variants.map((v: any) => (
                      <option key={v.id} value={v.id}>
                        {v.name}
                      </option>
                    ))}
                </select>
              </label>
            )}
            {preset && dataset !== "custom" && (
              <div className="preset-note">
                <b>
                  {preset.t_r
                    ? `方案参考 TR · ${preset.t_r} 秒`
                    : "TR · 从实际扫描读取"}
                </b>
                <details><summary>来源与适用范围</summary><p>{preset.notes}</p>
                {preset.upstream && <p>{preset.upstream}</p>}
                {preset.source && (
                  <a href={preset.source} target="_blank" rel="noreferrer">
                    查看官方说明 ↗
                  </a>
                )}
                <small>
                  仅作待确认预填；采集元数据优先。滤波、FD、图谱不会被冒充为数据集官方默认。
                </small>
                </details>
              </div>
            )}
            <label>
              本次输入类别
              <select
                aria-label="本次输入类别"
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value);
                  setPaths({});
                  setInfo(null);
                  setRawReady(false);
                  setRawQc(false);
                  setSourceConfirmed(false);
                  setConfig((c) => ({ ...defaultConfig, t_r: c.t_r }));
                  setDenoiseDecision("");
                  setRoiDecision("skip");
                  setReferenceDecision("skip");
                  setTableEdited(false);
                  setAutoNotes([]);
                }}
              >
                {kinds.map(([v, t]) => (
                  <option key={v} value={v}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            {isRaw && <p className="workflow-route">
              {kind === "raw-dicom"
                ? "Python 转换 → 预处理 → 质控 → ROI 提取"
                : kind === "raw-bids"
                  ? "BOLD + T1 → Python 预处理 → 质控 → ROI 提取"
                  : isTable
                    ? "核对时序方向与列顺序 → 去噪复核 → 连接矩阵"
                    : effectiveKind === "cifti"
                      ? "检查时序轴 → 匹配 BrainModel / Parcels → 去噪 → 连接矩阵"
                      : effectiveKind === "gifti"
                        ? "检查半球与顶点顺序 → 匹配 label.gii → 去噪 → 连接矩阵"
                        : "检查 4D BOLD → 确认配准与图谱 → 去噪 → 连接矩阵"}
            </p>}
          </>
        )}
        {step === 0 && (
          <>
            {isRaw && <h3>先完成原始数据预处理</h3>}
            {isRaw && !rawReady ? (
              <RawPreparation
                key={kind}
                kind={kind}
                job={job}
                busy={busy}
                onJob={onJob}
                onError={onError}
                onReady={(r) => {
                  setPaths({
                    source: r.bold,
                    confounds: r.confounds || "",
                    mask: r.mask || "",
                  });
                  setConfig((c) => ({
                    ...c,
                    data_space: r.space || "",
                    t_r: String(r.t_r || c.t_r),
                    preprocessed: true,
                    confound_columns: r.confound_columns?.join(",") || "",
                    discard: String(r.discard || 0),
                  }));
                  setRawReady(true);
                  setRawQc(true);
                  setSourceConfirmed(true);
                  setDenoiseDecision(r.confounds ? "regress" : "");
                }}
              />
            ) : (
              <>
                {field("source", "fMRI / ROI 时序")}
                {volume && (
                  <details>
                    <summary>采集 JSON（与 BOLD 同名，可选上传）</summary>
                    {field(
                      "sidecar",
                      "采集 JSON",
                      "上传后与 BOLD 保存在同一目录",
                    )}
                    <p className="muted">
                      本地路径模式请把 JSON 放在 BOLD 旁。文件夹层级继承的 BIDS
                      元数据需在预处理时正确解析。
                    </p>
                  </details>
                )}
                {isTable && (
                  <details>
                    <summary>时序表选项（自动识别表头；通常无需修改）</summary>
                    <p>
                      仅当原文件为 ROI × 时间，或包含多个 MAT / NPZ 数组时修改。
                    </p>
                    {check("table_header", "文本首行是脑区名称")}
                    {check("transpose", "原文件为 ROI × 时间，需要转置")}
                    {text(
                      "variable",
                      "MAT / NPZ 变量名",
                      "text",
                      "只有一个二维数组时可留空",
                    )}
                  </details>
                )}
                {isRaw && (
                  <p className="success-note">
                    预处理与质控已确认，接下来核对所选输出。
                  </p>
                )}
                <label className="check">
                  <input
                    type="checkbox"
                    checked={sourceConfirmed}
                    onChange={(e) => setSourceConfirmed(e.target.checked)}
                  />
                  {isTable
                    ? "我确认这是单次扫描的 ROI 时序，方向和列含义正确"
                    : "我确认这是主 BOLD 时序，不是 T1、场图或反向短序列"}
                </label>
              </>
            )}
          </>
        )}
        {step === 2 && (
          <>
            <h3>{isTable ? "核对脑区顺序与可选坐标" : "确认空间与脑区图谱"}</h3>
            <div className="input-facts">
              {info?.format} · {info?.n_frames} 个时间点
              {info?.n_rois ? ` · ${info.n_rois} 个脑区` : ""}
            </div>
            {trNotice && <p className="preset-note">{trNotice}</p>}
            {autoNotes.map((note, i) => (
              <p className="muted" key={i}>
                {note}
              </p>
            ))}
            {paths.atlas && (
              <div className="auto-summary">
                <b>已匹配脑区图谱</b>
                <p>{paths.atlas.split(/[\\/]/).pop()}</p>
                <small>
                  {config.data_space || "空间待确认"} ·{" "}
                  {paths.reference ? "已匹配解剖参考" : "使用图谱包络"}
                </small>
              </div>
            )}
            {!isTable && (
              <>
                <p>
                  {volume
                    ? "使用已完成头动校正和配准的 BOLD。图谱必须位于相同模板或个体空间。"
                    : effectiveKind === "cifti"
                      ? "dtseries 需要匹配 BrainModelAxis 的 dlabel；ptseries 已分区，无需再次添加图谱。"
                      : "func.gii 与 label.gii 必须属于同一半球、表面和顶点顺序；当前按单半球提取。"}
                </p>
                {check(
                  "preprocessed",
                  "已检查预处理报告，影像完成头动校正与空间配准",
                )}
                <details
                  open={
                    !config.data_space || (info?.needs_atlas && !paths.atlas)
                  }
                >
                  <summary>
                    {!config.data_space || (info?.needs_atlas && !paths.atlas)
                      ? "需要补充空间 / 图谱"
                      : "更换图谱或空间（高级）"}
                  </summary>
                  {volume && (
                    <div className="file-row">
                      <select
                        aria-label="标准脑区图谱"
                        value={atlasName}
                        onChange={(e) => setAtlasName(e.target.value)}
                      >
                        {[
                          "schaefer100",
                          "schaefer200",
                          "schaefer400",
                          "aal116",
                        ].map((n) => (
                          <option key={n}>{n}</option>
                        ))}
                      </select>
                      <button
                        onClick={() =>
                          action(async () => {
                            const j = await request("/api/atlas", {
                              name: atlasName,
                            });
                            setAtlasJob(j.id);
                            onJob(j);
                          })
                        }
                      >
                        载入图谱
                      </button>
                    </div>
                  )}
                  {info?.needs_atlas &&
                    field(
                      "atlas",
                      "分区图谱",
                      volume
                        ? "整数分区 NIfTI"
                        : effectiveKind === "cifti"
                          ? "匹配的 dlabel.nii"
                          : "同半球 label.gii",
                    )}
                  <div className="two-fields">
                    {text("data_space", "数据空间")}
                    {info?.needs_atlas && text("atlas_space", "图谱空间")}
                  </div>
                  {field(
                    "rois",
                    "脑区标签表（可选）",
                    "roi_id、name，可含 x/y/z",
                  )}
                </details>
              </>
            )}
            {isTable && (
              <>
                <label>
                  脑区信息
                  <select
                    aria-label="脑区信息"
                    value={roiDecision}
                    onChange={(e) => {
                      setRoiDecision(e.target.value);
                      invalidate();
                      if (e.target.value === "skip")
                        setPaths((p) => ({ ...p, rois: "", reference: "" }));
                    }}
                  >
                    <option value="">请选择</option>
                    <option value="supply">提供标签 / 坐标表</option>
                    <option value="skip">跳过坐标，仅生成矩阵</option>
                  </select>
                </label>
                {roiDecision === "supply" && (
                  <>
                    {field(
                      "rois",
                      "脑区标签表",
                      "与时序列完全同序；roi_id/name/x/y/z",
                    )}
                    {text("data_space", "坐标空间")}
                    <p className="muted">
                      坐标缺失时保留矩阵，三维与八视图无法启用。
                    </p>
                  </>
                )}
              </>
            )}
            <details>
              <summary>解剖参考与掩膜（可选，已自动匹配或跳过）</summary>
              <label>
                解剖参考（可选）
                <select
                  aria-label="解剖参考选择"
                  value={referenceDecision}
                  onChange={(e) => {
                    setReferenceDecision(e.target.value);
                    invalidate();
                    if (e.target.value === "skip")
                      setPaths((p) => ({ ...p, reference: "" }));
                  }}
                >
                  <option value="">请选择或明确跳过</option>
                  <option value="supply">提供同空间脑掩膜 / 去颅骨 T1</option>
                  <option value="skip">跳过，使用图谱包络或坐标视图</option>
                </select>
              </label>
              {referenceDecision === "supply" && field("reference", "解剖参考")}
              {volume && (
                <details>
                  <summary>限制提取范围的脑掩膜（可不选）</summary>
                  {field("mask", "脑掩膜")}
                </details>
              )}
              <p className="muted">
                显示的包络只作解剖参考；重采样不会完成配准。
              </p>
            </details>
          </>
        )}
        {step === 2 && (
          <>
            <h3>本次去噪选择</h3>
            {preset?.upstream && (
              <p className="preset-note">{preset.upstream}</p>
            )}
            <label>
              混杂回归与去噪
              <select
                aria-label="去噪选择"
                value={denoiseDecision}
                onChange={(e) => decision(e.target.value)}
              >
                <option value="">请选择</option>
                <option value="regress">本次进行混杂回归</option>
                <option value="upstream">上游已去噪，本次保留</option>
                <option value="skip">明确跳过混杂回归</option>
              </select>
            </label>
            {denoiseDecision === "upstream" && (
              <p className="muted">
                已将滤波、初始帧剔除、去趋势和标准化关闭，以保留上游时序。需要再次处理时请逐项开启并复核。
              </p>
            )}
            {denoiseDecision === "skip" && (
              <p className="warning">
                将记录“本次未进行混杂回归”。请确认上游记录或研究方案允许这样处理。
              </p>
            )}
            {denoiseDecision === "regress" && (
              <details open={!paths.confounds}>
                <summary>
                  {paths.confounds
                    ? "已匹配混杂变量（查看 / 更换）"
                    : "需要提供混杂变量"}
                </summary>
                {field("confounds", "混杂变量", "与原始时序等长的 TSV / CSV")}
                {text(
                  "confound_columns",
                  "回归列名（逗号分隔）",
                  "text",
                  "fMRIPrep 默认 motion6 + 可用 WM/CSF",
                )}
                <p className="muted">
                  这是软件提供的基础选择，不代表任何数据集官方的通用去噪方案。其他模型需明确提供列名。
                </p>
              </details>
            )}
            <div className="auto-summary">
              TR {config.t_r || "待确认"} 秒 ·{" "}
              {config.method === "pearson"
                ? "Pearson 相关"
                : config.method === "spearman"
                  ? "Spearman 相关"
                  : "收缩偏相关"}
              <br />
              滤波：
              {config.high_pass || config.low_pass
                ? `${config.high_pass || "无高通"} — ${config.low_pass || "无低通"} Hz`
                : "关闭"}
              ；可在下方调整。
            </div>
            <details>
              <summary>高级处理参数（通常无需填写）</summary>
              <div className="two-fields">
                {text("t_r", "TR（秒）", "number", "未找到时手动确认")}
                {text("discard", "丢弃初始帧", "number")}
                {text("high_pass", "高通（Hz）", "number", "留空关闭")}
                {text("low_pass", "低通（Hz）", "number", "留空关闭")}
                {denoiseDecision === "regress" &&
                  text("fd_threshold", "FD 阈值（mm）", "number", "留空不剔除")}
                {text("min_samples", "至少保留帧数", "number")}
              </div>
              {check("detrend", "去除线性趋势")}
              {check("standardize", "时序标准化")}
              <label>
                连接算法
                <select
                  aria-label="连接算法"
                  value={config.method}
                  onChange={(e) => setValue("method", e.target.value)}
                >
                  <option value="pearson">Pearson 相关</option>
                  <option value="spearman">Spearman 相关</option>
                  <option value="partial">收缩偏相关</option>
                </select>
              </label>
            </details>
          </>
        )}
        {step === 4 && review && (
          <>
            <h3>确认本次处理</h3>
            <dl className="review-list">
              <dt>数据来源</dt>
              <dd>
                {catalog?.datasets.find((d: any) => d.id === dataset)?.name} ·{" "}
                {preset?.name}
              </dd>
              <dt>输入</dt>
              <dd>{paths.source}</dd>
              <dt>空间 / 图谱</dt>
              <dd>
                {config.data_space || "未提供坐标"} /{" "}
                {paths.atlas || "使用已有 ROI 分区"}
              </dd>
              <dt>TR</dt>
              <dd>
                {review.effective_tr
                  ? `${review.effective_tr} s`
                  : "未提供；不计算秒级滤波"}
              </dd>
              <dt>帧数</dt>
              <dd>
                {review.n_retained} / {review.n_frames}
              </dd>
              <dt>回归</dt>
              <dd>
                {review.confound_columns?.join(", ") ||
                  (denoiseDecision === "upstream"
                    ? "保留上游去噪"
                    : "明确跳过")}
              </dd>
              <dt>滤波</dt>
              <dd>
                {config.high_pass || "关闭"} — {config.low_pass || "关闭"} Hz
              </dd>
              <dt>其他</dt>
              <dd>
                去趋势 {config.detrend ? "开" : "关"} · 标准化{" "}
                {config.standardize ? "开" : "关"} · 丢弃 {config.discard} 帧
              </dd>
              <dt>连接方法</dt>
              <dd>{config.method}</dd>
            </dl>
            {trNotice && <p className="preset-note">{trNotice}</p>}
            <p className="muted">
              来源、官方方案参考、确认与跳过的选项会写入结果记录。提取时还会核对每个脑区覆盖、时序有效性与空间匹配。
            </p>
            <label className="check">
              <input
                type="checkbox"
                checked={accepted}
                onChange={(e) => setAccepted(e.target.checked)}
              />
              我已核对本次扫描参数与上游处理记录
            </label>
            <button
              className="primary extract"
              disabled={!accepted || disabled}
              onClick={() => action(submit)}
            >
              开始处理并提取矩阵 →
            </button>
          </>
        )}
        <div className="wizard-actions">
          {step > 0 && (
            <button
              onClick={() => {
                setStep(step - 2);
                setHighest(step - 2);
                setReview(null);
                setAccepted(false);
              }}
            >
              ← 上一步
            </button>
          )}
          {step < 4 && (
            <button
              className="primary"
              disabled={
                !canNext ||
                disabled ||
                (step === 2 &&
                  ((referenceDecision === "supply" && !paths.reference) ||
                    (isTable && roiDecision === "supply" && !paths.rois)))
              }
              onClick={() => action(advance)}
            >
              {step === 0 ? "识别文件并继续" : "核对方案，进入复核"} →
            </button>
          )}
        </div>
      </fieldset>
    </div>
  );
}
