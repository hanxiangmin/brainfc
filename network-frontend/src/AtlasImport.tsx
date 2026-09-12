import { useState } from "react";
import { LoaderCircle, X } from "lucide-react";
import { api } from "./types";
import { downloadBlob, type Atlas } from "./viewerTypes";
export default function AtlasImport({
  onClose,
  onDone,
}: {
  onClose: () => void;
  onDone: (id: string) => Promise<void>;
}) {
  const [name, setName] = useState(""),
    [space, setSpace] = useState("MNIColin27"),
    [customSpace, setCustomSpace] = useState(""),
    [version, setVersion] = useState("custom-1"),
    [confirmed, setConfirmed] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [files, setFiles] = useState<Record<string, File>>({});
  async function submit() {
    setError("");
    setBusy(true);
    try {
      const body = new FormData();
      Object.entries(files).forEach(([k, v]) => body.append(k, v));
      body.append(
        "metadata",
        JSON.stringify({
          name,
          space: space === "custom" ? customSpace : space,
          version,
          space_confirmed: confirmed,
        }),
      );
      const atlas = await api<Atlas>("/atlases", { method: "POST", body });
      await onDone(atlas.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="viewer-modal-backdrop">
      <div
        className="viewer-modal"
        role="dialog"
        aria-modal="true"
        aria-label="导入我的图谱"
      >
        <div className="panel-title">
          <h2>导入我的脑图谱</h2>
          <button aria-label="关闭导入" onClick={onClose} disabled={busy}>
            <X size={19} />
          </button>
        </div>
        <p>上传整数分区影像与标签表，生成真实分区表面。数据只保存在本机。</p>
        <div className="import-grid">
          <label>
            图谱名称
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            版本
            <input
              value={version}
              onChange={(e) => setVersion(e.target.value)}
            />
          </label>
        </div>
        <label>
          兼容参考空间
          <select
            aria-label="兼容参考空间"
            value={space}
            onChange={(e) => setSpace(e.target.value)}
          >
            <option value="MNIColin27">MNIColin27</option>
            <option value="MNI152NLin6Asym">MNI152NLin6Asym</option>
            <option value="custom">自定义空间</option>
          </select>
        </label>
        {space === "custom" && (
          <label>
            空间名称与说明
            <input
              value={customSpace}
              onChange={(e) => setCustomSpace(e.target.value)}
              placeholder="明确命名、版本和空间说明，不能只写 MNI / native"
            />
          </label>
        )}
        {[
          ["parcellation", "整数分区影像（必需）", ".nii,.nii.gz"],
          ["labels", "标签表 CSV / TSV（必需）", ".csv,.tsv"],
          [
            "reference",
            `已去颅骨、已对齐的参考脑${space === "custom" ? "（必需）" : "（可选，留空使用上述标准参考脑）"}`,
            ".nii,.nii.gz",
          ],
        ].map(([key, label, accept]) => (
          <label key={key} className="import-file">
            {label}
            <input
              type="file"
              accept={accept}
              onChange={(e) => {
                const f = e.target.files?.[0];
                setFiles((old) => {
                  const next = { ...old };
                  if (f) next[key] = f;
                  else delete next[key];
                  return next;
                });
              }}
            />
          </label>
        ))}
        <div className="import-schema">
          <strong>标签表必需列</strong>
          <code>label_value, roi_id, abbreviation, name, hemisphere</code>
          <p>
            英文缩写和全名由图谱字典提供；半球填写 L / R / M / B。可另加
            network、color。0 为背景，标签值不等于矩阵行号。
          </p>
          <button
            className="text-button"
            onClick={() =>
              downloadBlob(
                new Blob(
                  [
                    "label_value,roi_id,abbreviation,name,hemisphere,network,color\n",
                  ],
                  { type: "text/csv" },
                ),
                "atlas-labels-header.csv",
              )
            }
          >
            下载标签表表头
          </button>
        </div>
        <label className="check-row">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          我确认分区与参考脑已在声明空间中对齐，空间单位为
          mm。系统只检查，不执行配准。
        </label>
        {error && <div className="viewer-notice error">{error}</div>}
        <button
          className="accent-button full"
          disabled={
            busy ||
            !name ||
            !confirmed ||
            !files.parcellation ||
            !files.labels ||
            (space === "custom" && (!customSpace || !files.reference))
          }
          onClick={submit}
        >
          {busy ? (
            <>
              <LoaderCircle className="spin" size={16} />
              验证并生成表面中…
            </>
          ) : (
            "验证并导入图谱"
          )}
        </button>
      </div>
    </div>
  );
}
