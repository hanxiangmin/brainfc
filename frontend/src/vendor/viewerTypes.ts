import type { Result } from "./types";
export type Selection = { kind: "node" | "edge" | "hyperedge"; id: string };
export type CameraState = {
  position?: number[];
  target?: number[];
  up?: number[];
};
export type ViewConfig = {
  style: "ballstick" | "envelope" | "parcels";
  theme: "midnight" | "paper";
  layer: "graph" | "hypergraph" | "both";
  opacity: number;
  labels: boolean;
  only_selected: boolean;
  selection: Selection | null;
  camera: CameraState;
  schema_version: 1;
};
export const defaultView: ViewConfig = {
  style: "ballstick",
  theme: "paper",
  layer: "graph",
  opacity: 0.28,
  labels: true,
  only_selected: true,
  selection: null,
  camera: {},
  schema_version: 1,
};
export type ROI = {
  roi_id: string;
  source_roi_id?: string;
  label_value: number;
  abbreviation: string;
  name: string;
  hemisphere: string;
  network?: string;
  color?: string;
  coordinates: number[];
};
export type Atlas = {
  id: string;
  name: string;
  space: string;
  version: string;
  n_rois: number;
  installed: boolean;
  custom: boolean;
  labels?: ROI[];
  sources?: string[];
  license?: string;
  sha256?: { content: string };
};
export type Surface = { positions: number[]; indices: number[] };
export type AtlasGeometry = {
  space: string;
  units: string;
  orientation: string;
  brain: Surface;
  parcels: Record<string, Surface>;
};
export type Edge = {
  id: string;
  source: string;
  target: string;
  weight: number;
};
export type Hyperedge = {
  id: string;
  source_id: string | number;
  display_id: string;
  members: string[];
  weight?: number;
  [key: string]: unknown;
};
export const styles = [
  ["ballstick", "节点连线", "球形脑区、普通连接与 H 标记的超边成员连线"],
  ["envelope", "透明包络", "观察超边成员与空间重叠"],
  ["parcels", "脑区分区表面", "观察真实分割的脑区范围"],
] as const;
export function edgesOf(result: Result): Edge[] {
  return result.graph.edges.map((e) => ({
    ...e,
    id: e.id || `edge:${JSON.stringify([e.source, e.target].sort())}`,
  }));
}
export function hyperedgesOf(result: Result): Hyperedge[] {
  return result.hypergraph.edges.map((e) => ({
    ...e,
    source_id: e.id,
    display_id:
      String(e.id) + (typeof e.id === "number" ? " (numeric ID)" : ""),
    id: JSON.stringify([typeof e.id, e.id]),
  }));
}
export function selectionMembers(
  s: Selection | null,
  edges: Edge[],
  hypers: Hyperedge[],
): Set<string> {
  if (!s) return new Set();
  if (s.kind === "node") return new Set([s.id]);
  if (s.kind === "edge") {
    const e = edges.find((e) => e.id === s.id);
    return new Set(e ? [e.source, e.target] : []);
  }
  return new Set(hypers.find((e) => e.id === s.id)?.members || []);
}
export function related(
  s: Selection | null,
  edges: Edge[],
  hypers: Hyperedge[],
) {
  const nodes = selectionMembers(s, edges, hypers),
    edgeIds = new Set<string>(),
    hyperIds = new Set<string>();
  if (s?.kind === "node") {
    edges.forEach((e) => {
      if (e.source === s.id || e.target === s.id) {
        edgeIds.add(e.id);
        nodes.add(e.source);
        nodes.add(e.target);
      }
    });
    hypers.forEach((h) => {
      if (h.members.includes(s.id)) {
        hyperIds.add(h.id);
        h.members.forEach((m) => nodes.add(m));
      }
    });
  } else if (s?.kind === "edge") edgeIds.add(s.id);
  else if (s?.kind === "hyperedge") hyperIds.add(s.id);
  return { nodes, edgeIds, hyperIds };
}
const palette = [
  "#52b9c9",
  "#b0a0e9",
  "#e5b66c",
  "#81c79b",
  "#e58caa",
  "#739edc",
  "#c0c77d",
  "#bca899",
];
export function categoryColor(id: string) {
  let h = 2166136261;
  for (const c of id) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return palette[(h >>> 0) % palette.length];
}
export function roiColor(r: ROI) {
  return r.color && /^#[\da-f]{6}$/i.test(r.color)
    ? r.color
    : categoryColor(
        r.network && r.network !== "AAL anatomical region"
          ? r.network
          : r.hemisphere,
      );
}
export function downloadBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
