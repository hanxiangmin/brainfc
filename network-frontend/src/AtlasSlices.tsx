import { useEffect, useRef, useState } from "react";
import type { Niivue } from "@niivue/niivue";
import type { Atlas } from "./viewerTypes";
import { apiUrl } from "./types";
export default function AtlasSlices({
  atlas,
  coordinate,
}: {
  atlas: Atlas;
  coordinate?: number[];
}) {
  const canvas = useRef<HTMLCanvasElement>(null),
    instance = useRef<Niivue | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    let viewer: Niivue | null = null;
    setError("");
    (async () => {
      const { Niivue, SLICE_TYPE } = await import("@niivue/niivue");
      if (!active || !canvas.current) return;
      viewer = new Niivue({
        backColor: [0.065, 0.11, 0.18, 1],
        isColorbar: false,
        isResizeCanvas: true,
        textHeight: 0.025,
      });
      instance.current = viewer;
      await viewer.attachToCanvas(canvas.current);
      if (!active) return;
      await viewer.loadVolumes([
        {
          url: apiUrl(`/atlases/${atlas.id}/assets/reference.nii.gz`),
          name: atlas.space + ".nii.gz",
          colormap: "gray",
        },
        {
          url: apiUrl(`/atlases/${atlas.id}/assets/parcellation.nii.gz`),
          name: atlas.name + ".nii.gz",
          colormap: "random",
          opacity: 0.35,
        },
      ]);
      if (!active) return;
      viewer.setSliceType(SLICE_TYPE.MULTIPLANAR);
      if (coordinate) {
        viewer.scene.crosshairPos = viewer.mm2frac(
          coordinate as [number, number, number],
        );
        viewer.drawScene();
      }
    })().catch((e) => {
      if (active) setError(e.message);
    });
    return () => {
      active = false;
      viewer?.cleanup();
      instance.current = null;
    };
  }, [atlas.id]);
  useEffect(() => {
    const v = instance.current;
    if (v && coordinate && v.volumes.length) {
      v.scene.crosshairPos = v.mm2frac(coordinate as [number, number, number]);
      v.drawScene();
    }
  }, [coordinate]);
  return (
    <div className="atlas-slices">
      <div className="table-caption">
        {atlas.space} · 原始分区叠加参考脑 · 十字定位当前脑区 · 滚轮切片
      </div>
      {error ? (
        <p role="alert">{error}</p>
      ) : (
        <canvas ref={canvas} aria-label="图谱与参考脑切片核查" />
      )}
    </div>
  );
}
