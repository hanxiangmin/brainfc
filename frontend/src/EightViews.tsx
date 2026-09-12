import { useEffect, useRef, useState } from "react";
import BrainScene, { type SceneHandle } from "./vendor/BrainScene";
import {
  downloadBlob,
  type ROI,
  type Edge,
  type AtlasGeometry,
  type ViewConfig,
} from "./vendor/viewerTypes";
const EMPTY: any[] = [];
const noop = () => {};
export const cameras = [
  ["left", "左侧"],
  ["right", "右侧"],
  ["anterior", "前侧"],
  ["posterior", "后侧"],
  ["superior", "顶部"],
  ["inferior", "底部"],
  ["left-oblique", "左前斜"],
  ["right-oblique", "右前斜"],
];
export default function EightViews({
  rois,
  edges,
  geometry,
  view,
  threshold,
  maxEdges,
  jobId,
}: {
  rois: ROI[];
  edges: Edge[];
  geometry: AtlasGeometry;
  view: ViewConfig;
  threshold: number;
  maxEdges: number;
  jobId?: string;
}) {
  const scene = useRef<SceneHandle>(null),
    [image, setImage] = useState(""),
    [error, setError] = useState(""),
    [rendering, setRendering] = useState(true);
  const title = `|r| ≥ ${threshold.toFixed(2)} · 最多 ${maxEdges} 条 · 当前 ${edges.length} 条连接${view.selection ? " · 已筛选" : ""}`;
  useEffect(() => {
    let live = true,
      url = "";
    setRendering(true);
    setError("");
    setImage("");
    // BrainScene effects apply the new graph/materials before this scheduled capture.
    const timer = setTimeout(
      () =>
        scene.current
          ?.views(cameras, title)
          .then((blob) => {
            if (!live) return;
            url = URL.createObjectURL(blob);
            setImage(url);
            setRendering(false);
          })
          .catch((e) => {
            if (live) {
              setError(String(e));
              setRendering(false);
            }
          }),
      120,
    );
    return () => {
      live = false;
      clearTimeout(timer);
      if (url) URL.revokeObjectURL(url);
    };
  }, [rois, edges, geometry, view, title]);
  const params = new URLSearchParams({
    threshold: String(threshold),
    max_edges: String(maxEdges),
    opacity: String(view.opacity),
    theme: view.theme,
  });
  if (view.selection) {
    params.set("selection_kind", view.selection.kind);
    params.set("selection_id", view.selection.id);
  }
  return (
    <div
      className={`white-card synced-views ${view.theme}`}
      data-edge-ids={edges.map((e) => e.id).join(",")}
      data-testid="synced-views"
    >
      <div className="card-head">
        <h2>与三维同步的八个视角</h2>
        <div>
          <button
            disabled={!image || rendering}
            onClick={() =>
              fetch(image)
                .then((r) => r.blob())
                .then((b) => downloadBlob(b, "eight-views-current.png"))
            }
          >
            保存 PNG
          </button>
          {jobId && !rendering && (
            <>
              <a href={`/api/jobs/${jobId}/views?${params}&format=svg`}>
                SVG ↓
              </a>
              <a href={`/api/jobs/${jobId}/views?${params}&format=pdf`}>
                PDF ↓
              </a>
            </>
          )}
        </div>
      </div>
      <p className="muted">{title} · 解剖轮廓、颜色和选中内容跟随三维设置</p>
      <div className="capture-scene" aria-hidden="true">
        <BrainScene
          compact
          ref={scene}
          rois={rois}
          edges={edges}
          hypers={EMPTY}
          geometry={geometry}
          view={view}
          onSelect={noop}
          onCandidates={noop}
          onStatus={noop}
          onSlow={noop}
        />
      </div>
      {rendering && <p role="status">正在更新八个视角…</p>}
      {error && <p role="alert">{error}</p>}
      {image && (
        <img
          className="eight-views"
          src={image}
          alt="同步脑区球棍八视图：左、右、前、后、顶、底、左前斜、右前斜"
        />
      )}
      <p className="muted">
        八个视角使用完全相同的连接集合。PNG 保留当前三维材质；SVG / PDF
        为相同筛选结果的可编辑矢量投影。
      </p>
    </div>
  );
}
