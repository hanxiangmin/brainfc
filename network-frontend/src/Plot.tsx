import { useEffect, useRef, useState } from "react";
import type * as P from "plotly.js";
import Plotly from "plotly.js-dist-min";
export default function Plot({
  data,
  layout,
  onClick,
  height = 360,
}: {
  data: P.Data[];
  layout?: Partial<P.Layout>;
  onClick?: (e: P.PlotMouseEvent) => void;
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    let live = true;
    Plotly.react(
      node,
      data,
      {
        font: {
          family: "Inter, Segoe UI, Microsoft YaHei, sans-serif",
          color: "#53636b",
          size: 11,
        },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        margin: { l: 45, r: 15, b: 45, t: 15 },
        autosize: true,
        ...layout,
      },
      {
        responsive: true,
        displaylogo: false,
        modeBarButtonsToRemove: ["sendDataToCloud"] as never,
        toImageButtonOptions: {
          format: "svg",
          filename: "hic-brain-figure",
          width: 1200,
          height: 900,
        },
      },
    )
      .then(() => {
        if (live && onClick)
          (node as unknown as P.PlotlyHTMLElement).on("plotly_click", onClick);
      })
      .catch((reason: Error) => {
        if (live) setError(reason.message || String(reason));
      });
    const observer = new ResizeObserver(() => {
      if (live) Plotly.Plots.resize(node);
    });
    observer.observe(node);
    return () => {
      live = false;
      observer.disconnect();
      (node as unknown as P.PlotlyHTMLElement).removeAllListeners?.(
        "plotly_click",
      );
    };
  }, [data, layout, onClick]);
  useEffect(() => {
    const node = ref.current;
    return () => {
      if (node) Plotly.purge(node);
    };
  }, []);
  return (
    <>
      {error && <div className="notice">图表暂时无法显示：{error}</div>}
      <div ref={ref} style={{ width: "100%", height }} />
    </>
  );
}
