import type { Selection } from "./viewerTypes";

export type Emphasis = "global" | "primary" | "related" | "context";
type Focus = {
  nodes: Set<string>;
  edgeIds: Set<string>;
  hyperIds: Set<string>;
};

export function emphasis(
  object: Selection,
  selection: Selection | null,
  focus: Focus,
): Emphasis {
  if (!selection) return "global";
  if (object.kind === selection.kind && object.id === selection.id)
    return "primary";
  const associated =
    object.kind === "node"
      ? focus.nodes.has(object.id)
      : object.kind === "edge"
        ? focus.edgeIds.has(object.id)
        : focus.hyperIds.has(object.id);
  if (!associated) return "context";
  return selection.kind === "node" ? "related" : "primary";
}

export function objectAlpha(
  level: Emphasis,
  part:
    | "node"
    | "edge"
    | "membership"
    | "surface"
    | "outline"
    | "parcel"
    | "parcel-outline",
  count = 0,
  overlay = false,
) {
  if (level === "context")
    return part === "node"
      ? 0.025
      : part === "surface" || part === "parcel"
        ? 0.002
        : 0.009;
  if (level === "related")
    return part === "node"
      ? 0.95
      : part === "surface"
        ? 0.015
        : part === "parcel"
          ? 0.08
          : 0.72;
  if (level === "primary")
    return part === "surface"
      ? 0.12
      : part === "parcel"
        ? 0.65
        : part === "parcel-outline"
          ? 0.65
          : 1;
  if (part === "surface")
    return Math.max(0.022, 0.1 / Math.sqrt(1 + count / 16));
  if (part === "outline")
    return Math.max(0.09, 0.28 / Math.sqrt(1 + count / 24));
  if (part === "node") return 0.92;
  if (part === "edge") return overlay ? 0.2 : 0.54;
  if (part === "membership")
    return Math.max(0.18, 0.45 / Math.sqrt(1 + count / 60));
  return part === "parcel" ? 0.62 : 0.24;
}

export const labelAlpha: Record<Emphasis, number> = {
  primary: 1,
  related: 0.26,
  context: 0.025,
  global: 0.82,
};
