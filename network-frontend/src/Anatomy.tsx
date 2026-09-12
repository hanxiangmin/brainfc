import { useEffect, useRef, useState } from "react";
import { Brain, LoaderCircle } from "lucide-react";
import type { Niivue } from "@niivue/niivue";
import type { Result } from "./types";
import { apiUrl } from "./types";

export default function Anatomy({
  result,
  selected,
  members,
  onSelect,
}: {
  result: Result;
  selected: string | null;
  members: string[];
  onSelect: (id: string) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null),
    nv = useRef<Niivue | null>(null),
    select = useRef(onSelect);
  select.current = onSelect;
  const [error, setError] = useState(""),
    [ready, setReady] = useState(false);
  const mapped =
    !!result.coordinates && result.metadata.coordinate_space === "MNI";
  useEffect(() => {
    if (!mapped || !canvas.current) return;
    let active = true;
    let viewer: Niivue | null = null;
    setError("");
    setReady(false);
    (async () => {
      const { Niivue, SLICE_TYPE } = await import("@niivue/niivue");
      if (!active) return;
      viewer = new Niivue({
        backColor: [0.065, 0.11, 0.14, 1],
        show3Dcrosshair: true,
        isResizeCanvas: true,
        textHeight: 0.025,
        isColorbar: false,
        isOrientCube: true,
      });
      nv.current = viewer;
      await viewer.attachToCanvas(canvas.current!);
      if (!active) return;
      await viewer.loadVolumes([
        {
          url: apiUrl("/template"),
          name: "MNI152_reference.nii.gz",
          colormap: "gray",
          opacity: 0.28,
        },
      ]);
      if (!active) return;
      viewer.setSliceType(SLICE_TYPE.MULTIPLANAR);
      viewer.onLocationChange = (location) => {
        const mm = (location as { mm?: number[] }).mm;
        if (!mm) return;
        let nearest = -1,
          distance = Infinity;
        result.coordinates!.forEach((xyz, i) => {
          const d = xyz.reduce((sum, v, j) => sum + (v - mm[j]) ** 2, 0);
          if (d < distance) {
            distance = d;
            nearest = i;
          }
        });
        if (nearest >= 0 && distance < 225)
          select.current(result.roi_ids[nearest]);
      };
      setReady(true);
    })().catch((e) => {
      if (active) setError(String(e.message || e));
    });
    return () => {
      active = false;
      viewer?.cleanup();
      nv.current = null;
    };
  }, [result, mapped]);
  useEffect(() => {
    const viewer = nv.current;
    if (!ready || !viewer || !result.coordinates) return;
    const marked = new Set(members);
    if (selected) marked.add(selected);
    viewer.loadConnectome({
      name: "ROI mapping",
      nodeScale: 2.1,
      nodeColormap: "viridis",
      nodeMinColor: 0,
      nodeMaxColor: 1,
      nodeColormapNegative: "cool",
      edgeColormap: "warm",
      edgeColormapNegative: "cool",
      edgeMin: 0,
      edgeMax: 1,
      edgeScale: 0,
      showLegend: false,
      nodes: result.coordinates.map((xyz, i) => ({
        name: result.labels[i],
        x: xyz[0],
        y: xyz[1],
        z: xyz[2],
        colorValue: marked.has(result.roi_ids[i]) ? 1 : 0.4,
        sizeValue: marked.has(result.roi_ids[i]) ? 2.1 : 0.8,
      })),
      edges: [],
    });
    if (selected) {
      const index = result.roi_ids.indexOf(selected);
      if (index >= 0) {
        viewer.scene.crosshairPos = viewer.mm2frac(
          result.coordinates[index] as [number, number, number],
        );
        viewer.drawScene();
      }
    }
  }, [ready, result, selected, members]);
  if (!mapped)
    return (
      <div className="anatomy-empty">
        <div className="anatomy-orbit">
          <Brain size={66} strokeWidth={0.9} />
        </div>
        <strong>添加脑区映射以启用解剖定位</strong>
        <p>
          上传 ROI 标签与 MNI 坐标后，
          <br />
          在参考脑影像中定位每一个脑区。
        </p>
        <span className="badge">当前可使用矩阵与抽象网络视图</span>
      </div>
    );
  return (
    <div className="anatomy">
      <canvas ref={canvas} aria-label="MNI 参考脑影像及脑区定位" />
      {!ready && !error && (
        <div className="canvas-status">
          <LoaderCircle className="spin" /> 正在加载本地参考影像
        </div>
      )}
      {error && <div className="canvas-status">解剖视图暂不可用：{error}</div>}
      <div className="anatomy-caption">
        MNI 参考影像 · 滚轮切片 / 拖动旋转 · 点击切片邻近脑区联动
      </div>
    </div>
  );
}
