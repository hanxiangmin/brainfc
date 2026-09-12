import type { Edge, ROI, Selection } from "./vendor/viewerTypes";

export function displayEdges(
  matrix: number[][],
  rois: ROI[],
  threshold: number,
  limit: number,
  selection: Selection | null,
): Edge[] {
  const candidates: Edge[] = [];
  matrix.forEach((row, i) =>
    row.forEach((weight, j) => {
      const id = `${i}:${j}`,
        source = rois[i].roi_id,
        target = rois[j]?.roi_id;
      if (j <= i || weight === 0 || Math.abs(weight) < threshold) return;
      if (
        selection?.kind === "node" &&
        source !== selection.id &&
        target !== selection.id
      )
        return;
      if (selection?.kind === "edge" && id !== selection.id) return;
      candidates.push({ id, source, target, weight });
    }),
  );
  return candidates
    .sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight))
    .slice(0, limit);
}

export function shortROI(name: string) {
  // Remove only the atlas-wide prefix; hemisphere, network and parcel ID stay unique.
  return name.replace(/^\d+Networks_/, "").replaceAll("_", " · ");
}
