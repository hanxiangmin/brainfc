import { useState } from "react";
import Papa from "papaparse";
import {
  BarChart3,
  Upload,
  Play,
  LoaderCircle,
  ArrowDownToLine,
} from "lucide-react";
import { api, post, pretty } from "./types";
export default function Statistics() {
  const [raw, setRaw] = useState(""),
    [rows, setRows] = useState<Record<string, unknown>[]>([]),
    [subject, setSubject] = useState(""),
    [group, setGroup] = useState(""),
    [features, setFeatures] = useState<string[]>([]),
    [covariates, setCovariates] = useState<string[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [result, setResult] = useState<unknown>(null);
  const columns = rows.length ? Object.keys(rows[0]) : [];
  function parse(text: string) {
    try {
      let parsed: Record<string, unknown>[];
      if (text.trim().startsWith("[")) {
        parsed = JSON.parse(text);
      } else {
        const data = Papa.parse<Record<string, unknown>>(text, {
          header: true,
          dynamicTyping: true,
          skipEmptyLines: true,
        });
        if (data.errors.length) throw new Error(data.errors[0].message);
        parsed = data.data;
      }
      if (
        !Array.isArray(parsed) ||
        !parsed.length ||
        typeof parsed[0] !== "object"
      )
        throw new Error("需要包含表头和数据行的 CSV 或 JSON 对象数组。");
      setRows(parsed);
      const keys = Object.keys(parsed[0]);
      setSubject(
        keys.find((k) => /subject|participant|^id$/i.test(k)) || keys[0],
      );
      setGroup(keys.find((k) => /group|diagnosis/i.test(k)) || keys[1] || "");
      setFeatures([]);
      setCovariates([]);
      setResult(null);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function calculate() {
    setError("");
    setBusy(true);
    try {
      setResult(
        await api(
          "/statistics",
          post({
            rows,
            subject_column: subject,
            group_column: group,
            feature_columns: features,
            covariates,
          }),
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const resultRows = Array.isArray(result)
    ? result
    : result && typeof result === "object"
      ? (result as { results?: unknown[] }).results
      : null;
  function download() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "hic-brain-statistics.json";
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <div className="statistics-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">COHORT ANALYSIS</div>
          <h1>从个体走向队列</h1>
          <p>导入参与者与特征表，比较组间差异并报告效应量。</p>
        </div>
        <BarChart3 className="heading-icon" size={42} />
      </div>
      <div className="two-column">
        <section className="panel form-panel">
          <h2>
            01 <span>导入研究表</span>
          </h2>
          <p className="hint">
            每行对应一位受试者。包含匿名 ID、分组、数值特征及可选协变量。重复 ID
            会被拒绝。
          </p>
          <label className="button secondary">
            <Upload size={16} /> 选择 CSV / JSON
            <input
              hidden
              type="file"
              accept=".csv,.tsv,.json"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (file) {
                  const text = await file.text();
                  setRaw(text);
                  parse(text);
                }
              }}
            />
          </label>
          <label className="field">
            <span>或粘贴表格内容</span>
            <textarea
              rows={8}
              value={raw}
              onChange={(e) => setRaw(e.target.value)}
              placeholder={
                "subject_id,group,age,efficiency\nS001,HC,24,0.42\nS002,ASD,27,0.35"
              }
            />
          </label>
          <button
            className="button secondary"
            onClick={() => parse(raw)}
            disabled={!raw.trim()}
          >
            检查表格
          </button>
          {rows.length > 0 && (
            <div className="success-note">
              已读取 {rows.length} 行 × {columns.length} 列
            </div>
          )}
        </section>
        <section className="panel form-panel">
          <h2>
            02 <span>定义比较</span>
          </h2>
          <div className="form-grid">
            <label className="field">
              <span>受试者 ID 列</span>
              <select
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                disabled={!rows.length}
              >
                {columns.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>分组列（两个独立组）</span>
              <select
                value={group}
                onChange={(e) => setGroup(e.target.value)}
                disabled={!rows.length}
              >
                {columns.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="field">
            <span>待检验特征</span>
            <div className="check-list">
              {columns
                .filter((c) => c !== subject && c !== group)
                .map((c) => (
                  <label key={c}>
                    <input
                      type="checkbox"
                      checked={features.includes(c)}
                      onChange={(e) => {
                        setFeatures(
                          e.target.checked
                            ? [...features, c]
                            : features.filter((v) => v !== c),
                        );
                        if (e.target.checked)
                          setCovariates(covariates.filter((v) => v !== c));
                      }}
                    />
                    {c}
                  </label>
                ))}
            </div>
          </div>
          <div className="field">
            <span>协变量（可选，数值列）</span>
            <div className="check-list">
              {columns
                .filter(
                  (c) => c !== subject && c !== group && !features.includes(c),
                )
                .map((c) => (
                  <label key={c}>
                    <input
                      type="checkbox"
                      checked={covariates.includes(c)}
                      onChange={(e) =>
                        setCovariates(
                          e.target.checked
                            ? [...covariates, c]
                            : covariates.filter((v) => v !== c),
                        )
                      }
                    />
                    {c}
                  </label>
                ))}
            </div>
          </div>
          <div className="method-note">
            无协变量使用 Welch 比较；有协变量使用 OLS 与 HC3
            稳健标准误。统一进行 BH-FDR 校正。
          </div>
          <button
            className="button primary"
            disabled={busy || !features.length || subject === group}
            onClick={calculate}
          >
            {busy ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <Play size={16} />
            )}
            运行队列统计
          </button>
        </section>
      </div>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {result !== null && (
        <section className="panel">
          <div className="panel-title">
            <span>统计结果</span>
            <button className="button secondary small" onClick={download}>
              <ArrowDownToLine size={14} /> JSON
            </button>
          </div>
          {Array.isArray(resultRows) &&
          resultRows.length > 0 &&
          typeof resultRows[0] === "object" ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    {Object.keys(resultRows[0]).map((k) => (
                      <th key={k}>{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {resultRows.map((row, i) => (
                    <tr key={i}>
                      {Object.values(row as Record<string, unknown>).map(
                        (v, j) => (
                          <td key={j}>{pretty(v)}</td>
                        ),
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <pre className="json-output">{JSON.stringify(result, null, 2)}</pre>
          )}
          <details className="metadata-panel">
            <summary>完整统计输出</summary>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </details>
        </section>
      )}
    </div>
  );
}
