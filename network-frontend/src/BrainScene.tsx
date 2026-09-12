import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import * as T from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { ConvexGeometry } from "three/addons/geometries/ConvexGeometry.js";
import { emphasis, objectAlpha, labelAlpha } from "./viewerAppearance";
import {
  categoryColor,
  related,
  roiColor,
  type AtlasGeometry,
  type CameraState,
  type Edge,
  type Hyperedge,
  type ROI,
  type Selection,
  type Surface,
  type ViewConfig,
} from "./viewerTypes";

export type SceneHandle = {
  image: () => Promise<Blob>;
  camera: () => CameraState;
  orient: (view: string) => void;
  restore: (c: CameraState) => void;
};
type Props = {
  rois: ROI[];
  edges: Edge[];
  hypers: Hyperedge[];
  geometry: AtlasGeometry;
  view: ViewConfig;
  onSelect: (s: Selection | null) => void;
  onCandidates: (s: Selection[]) => void;
  onStatus: (s: { fallback: number; lod: boolean; fps: number }) => void;
  onSlow: () => void;
};
type Instance = {
  mesh: T.InstancedMesh;
  selections: Selection[];
  colors: T.Color[];
  matrices: T.Matrix4[];
};
type Lines = {
  mesh: T.LineSegments;
  selections: Selection[];
  colors: T.Color[];
  original: Float32Array;
};
type Solid = {
  mesh: T.Mesh | T.LineSegments;
  selection: Selection;
  color: T.Color;
  opacity: number;
  part: "surface" | "outline" | "parcel" | "parcel-outline";
};
type Runtime = {
  renderer: T.WebGLRenderer;
  camera: T.PerspectiveCamera;
  controls: OrbitControls;
  scene: T.Scene;
  group: T.Group;
  instances: Instance[];
  lines: Lines[];
  solids: Solid[];
  pickables: T.Object3D[];
  focusGroup: T.Group;
  focusPaths: { id: string; color: T.Color; paths: T.Curve<T.Vector3>[] }[];
  anchors: { id: string; position: number[]; color: string }[];
  anchorHits: {
    x: number;
    y: number;
    radius: number;
    id: string;
    alpha: number;
  }[];
  brain?: T.Mesh;
  dirty: boolean;
  hovered?: string;
  labelHits: { x: number; y: number; w: number; id: string; alpha: number }[];
  render: () => void;
  restore: (c: CameraState) => void;
  orient: (v: string) => void;
};
const zero = new T.Matrix4().makeScale(0, 0, 0);
// Per-instance / per-vertex alpha: dim objects remain transparent instead of
// becoming opaque background-colored geometry that still hides the selection.
function transparentMaterial<M extends T.Material>(material: M): M {
  material.transparent = true;
  material.depthWrite = false;
  material.onBeforeCompile = (shader) => {
    shader.vertexShader =
      "attribute float visualAlpha; varying float vVisualAlpha;\n" +
      shader.vertexShader;
    shader.vertexShader = shader.vertexShader.replace(
      "#include <color_vertex>",
      "#include <color_vertex>\nvVisualAlpha = visualAlpha;",
    );
    shader.fragmentShader =
      "varying float vVisualAlpha;\n" + shader.fragmentShader;
    shader.fragmentShader = shader.fragmentShader.replace(
      "#include <color_fragment>",
      "#include <color_fragment>\ndiffuseColor.a *= vVisualAlpha;",
    );
  };
  material.customProgramCacheKey = () => "hyperbrain-visual-alpha-1";
  return material;
}
function meshGeometry(s: Surface) {
  const g = new T.BufferGeometry();
  g.setAttribute("position", new T.Float32BufferAttribute(s.positions, 3));
  g.setIndex(s.indices);
  g.computeVertexNormals();
  return g;
}
function isSolid(points: T.Vector3[]) {
  if (points.length < 3) return false;
  const a = points[0],
    b = points.find((p) => p.distanceToSquared(a) > 1e-8);
  if (!b) return false;
  const ab = b.clone().sub(a),
    c = points.find(
      (p) => ab.clone().cross(p.clone().sub(a)).lengthSq() > 1e-6,
    );
  if (!c) return false;
  if (points.length === 3) return true;
  const normal = ab.cross(c.clone().sub(a)).normalize();
  return points.some((p) => Math.abs(normal.dot(p.clone().sub(a))) > 1e-3);
}
function dispose(group: T.Group) {
  const gs = new Set<T.BufferGeometry>(),
    ms = new Set<T.Material>();
  group.traverse((o) => {
    const m = o as T.Mesh;
    if (m.geometry) gs.add(m.geometry);
    if (m.material)
      (Array.isArray(m.material) ? m.material : [m.material]).forEach((x) =>
        ms.add(x),
      );
  });
  gs.forEach((g) => g.dispose());
  ms.forEach((m) => m.dispose());
  group.clear();
}

const BrainScene = forwardRef<SceneHandle, Props>(
  function BrainScene(props, ref) {
    const host = useRef<HTMLDivElement>(null),
      overlay = useRef<HTMLCanvasElement>(null),
      runtime = useRef<Runtime | null>(null),
      current = useRef(props);
    current.current = props;
    const [error, setError] = useState(""),
      [hover, setHover] = useState<{
        text: string;
        x: number;
        y: number;
      } | null>(null);
    useImperativeHandle(ref, () => ({
      image: async () => {
        const r = runtime.current;
        if (!r || !overlay.current) throw new Error("三维场景尚未就绪");
        r.render();
        const c = document.createElement("canvas");
        c.width = r.renderer.domElement.width;
        c.height = r.renderer.domElement.height;
        const ctx = c.getContext("2d")!;
        ctx.drawImage(r.renderer.domElement, 0, 0);
        ctx.drawImage(overlay.current, 0, 0, c.width, c.height);
        return new Promise((resolve, reject) =>
          c.toBlob(
            (b) => (b ? resolve(b) : reject(new Error("图片导出失败"))),
            "image/png",
          ),
        );
      },
      camera: () => {
        const r = runtime.current;
        return r
          ? {
              position: r.camera.position.toArray(),
              target: r.controls.target.toArray(),
              up: r.camera.up.toArray(),
            }
          : {};
      },
      orient: (v) => runtime.current?.orient(v),
      restore: (c) => runtime.current?.restore(c),
    }));
    useEffect(() => {
      if (!host.current || !overlay.current) return;
      const element = host.current,
        labels = overlay.current;
      let renderer: T.WebGLRenderer;
      try {
        renderer = new T.WebGLRenderer({
          antialias: true,
          alpha: false,
          preserveDrawingBuffer: true,
        });
      } catch (e) {
        setError(`无法创建三维画布：${String(e)}。请启用浏览器硬件加速。`);
        return;
      }
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.outputColorSpace = T.SRGBColorSpace;
      element.prepend(renderer.domElement);
      renderer.domElement.setAttribute(
        "aria-label",
        "交互三维脑网络，拖动旋转，右键平移，滚轮缩放",
      );
      const scene = new T.Scene(),
        camera = new T.PerspectiveCamera(37, 1, 0.1, 3000),
        group = new T.Group();
      const bounds = new T.Box3().setFromArray(
          current.current.geometry.brain.positions,
        ),
        center = bounds.getCenter(new T.Vector3()),
        extent = bounds.getSize(new T.Vector3());
      let radius = 1;
      const vertices = current.current.geometry.brain.positions;
      for (let i = 0; i < vertices.length; i += 3)
        radius = Math.max(
          radius,
          Math.hypot(
            vertices[i] - center.x,
            vertices[i + 1] - center.y,
            vertices[i + 2] - center.z,
          ),
        );
      const defaultDistance = radius * 3.15;
      camera.near = radius / 1000;
      camera.far = radius * 50;
      camera.up.set(0, 0, 1);
      camera.position
        .copy(center)
        .add(
          new T.Vector3(0.56, 0.72, 0.46)
            .normalize()
            .multiplyScalar(defaultDistance),
        );
      const controls = new OrbitControls(camera, renderer.domElement);
      controls.target.copy(center);
      controls.enableDamping = true;
      controls.dampingFactor = 0.12;
      controls.minDistance = radius * 0.25;
      controls.maxDistance = radius * 25;
      scene.add(group);
      scene.add(new T.AmbientLight(0xffffff, 1.8));
      const sun = new T.DirectionalLight(0xffffff, 2.6);
      sun.position
        .copy(center)
        .add(new T.Vector3(-radius, radius * 2, radius * 3));
      sun.target.position.copy(center);
      scene.add(sun.target);
      scene.add(sun);
      const fill = new T.DirectionalLight(0x91b8db, 1);
      fill.position
        .copy(center)
        .add(new T.Vector3(radius, -radius * 2, radius));
      fill.target.position.copy(center);
      scene.add(fill.target);
      scene.add(fill);
      const r: Runtime = {
        renderer,
        camera,
        controls,
        scene,
        group,
        instances: [],
        lines: [],
        solids: [],
        pickables: [],
        focusGroup: new T.Group(),
        focusPaths: [],
        anchors: [],
        anchorHits: [],
        labelHits: [],
        dirty: true,
        render: () => {},
        restore: (c) => {
          if (c.position?.length === 3) camera.position.fromArray(c.position);
          if (c.target?.length === 3) controls.target.fromArray(c.target);
          if (c.up?.length === 3) camera.up.fromArray(c.up);
          controls.update();
          r.dirty = true;
        },
        orient: (view) => {
          const target = center.clone(),
            d = defaultDistance;
          controls.target.copy(center);
          const v: Record<string, number[]> = {
            anterior: [0, 1, 0],
            posterior: [0, -1, 0],
            left: [-1, 0, 0],
            right: [1, 0, 0],
            superior: [0, 0, 1],
            reset: [0.56, 0.72, 0.46],
          };
          camera.up.set(
            0,
            view === "superior" ? 1 : 0,
            view === "superior" ? 0 : 1,
          );
          camera.position.copy(target).add(
            new T.Vector3()
              .fromArray(v[view] || v.reset)
              .normalize()
              .multiplyScalar(d),
          );
          controls.update();
          r.dirty = true;
        },
      };
      runtime.current = r;
      r.restore(current.current.view.camera);
      const resize = () => {
        const w = element.clientWidth,
          h = element.clientHeight;
        renderer.setSize(w, h);
        camera.aspect = w / Math.max(h, 1);
        camera.updateProjectionMatrix();
        labels.width = w * renderer.getPixelRatio();
        labels.height = h * renderer.getPixelRatio();
        labels.style.width = `${w}px`;
        labels.style.height = `${h}px`;
        r.dirty = true;
      };
      const observer = new ResizeObserver(resize);
      observer.observe(element);
      resize();
      const drawLabels = () => {
        const p = current.current,
          ctx = labels.getContext("2d")!,
          w = element.clientWidth,
          h = element.clientHeight,
          ratio = renderer.getPixelRatio();
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        ctx.clearRect(0, 0, w, h);
        r.labelHits = [];
        r.anchorHits = [];
        const dark = p.view.theme === "midnight",
          focus = related(p.view.selection, p.edges, p.hypers),
          occupied = new Map<string, { x: number; y: number; w: number }[]>();
        const cellsFor = (x: number, y: number, width: number) => {
          const keys: string[] = [];
          for (
            let a = Math.floor(x / 60);
            a <= Math.floor((x + width) / 60);
            a++
          )
            for (
              let b = Math.floor((y - 11) / 14);
              b <= Math.floor((y + 11) / 14);
              b++
            )
              keys.push(`${a},${b}`);
          return keys;
        };
        const collides = (x: number, y: number, width: number) =>
          cellsFor(x, y, width).some((key) =>
            occupied
              .get(key)
              ?.some(
                (a) =>
                  Math.abs(a.y - y) < 11 && x < a.x + a.w && x + width > a.x,
              ),
          );
        const project = (xyz: number[]) => {
          const v = new T.Vector3().fromArray(xyz).project(camera);
          return { x: ((v.x + 1) * w) / 2, y: ((1 - v.y) * h) / 2, z: v.z };
        };
        const labelLevel = (id: string) =>
          r.hovered === id
            ? "primary"
            : emphasis({ kind: "node", id }, p.view.selection, focus);
        const ordered = [...p.rois].sort(
          (a, b) =>
            labelAlpha[labelLevel(b.source_roi_id || b.roi_id)] -
            labelAlpha[labelLevel(a.source_roi_id || a.roi_id)],
        );
        if (p.view.labels)
          for (const roi of ordered) {
            const id = roi.source_roi_id || roi.roi_id,
              level = labelLevel(id);
            if (
              p.view.only_selected &&
              p.view.selection &&
              !focus.nodes.has(id)
            )
              continue;
            const v = project(roi.coordinates);
            if (v.z < -1 || v.z > 1) continue;
            ctx.font = `${level === "primary" ? "600 11" : p.rois.length > 200 ? "8.5" : "10"}px Inter,Segoe UI,sans-serif`;
            const tw = ctx.measureText(roi.abbreviation).width + 7;
            let x = Math.max(4, Math.min(w - tw - 4, v.x + 7)),
              y = Math.max(20, Math.min(h - 50, v.y - 5));
            // Screen-space displacement only; the underlying anatomical coordinates never move.
            for (let attempt = 0; attempt < 400; attempt++) {
              if (!collides(x, y, tw)) break;
              const angle = attempt * 2.39996323,
                radius = Math.sqrt(attempt + 1) * 18;
              x = Math.max(
                6,
                Math.min(w - tw - 6, v.x + Math.cos(angle) * radius),
              );
              y = Math.max(
                20,
                Math.min(h - 50, v.y + Math.sin(angle) * radius),
              );
            }
            for (const key of cellsFor(x, y, tw)) {
              const cell = occupied.get(key) || [];
              cell.push({ x, y, w: tw });
              occupied.set(key, cell);
            }
            ctx.globalAlpha = labelAlpha[level];
            const accent =
              p.view.selection?.kind === "hyperedge"
                ? categoryColor(p.view.selection.id)
                : dark
                  ? "#9ce3d2"
                  : "#257b72";
            ctx.strokeStyle =
              level === "primary" ? accent : dark ? "#50647e" : "#a2afbe";
            ctx.lineWidth = level === "primary" ? 0.85 : 0.4;
            if (Math.hypot(x - v.x, y - v.y) > 13) {
              ctx.beginPath();
              ctx.moveTo(v.x, v.y);
              ctx.lineTo(x, y - 3);
              ctx.stroke();
            }
            if (level === "primary") {
              ctx.lineWidth = 1.5;
              ctx.beginPath();
              ctx.arc(v.x, v.y, 7, 0, Math.PI * 2);
              ctx.stroke();
            }
            ctx.fillStyle = dark ? "#111e30" : "#ffffff";
            ctx.beginPath();
            ctx.roundRect(x - 3, y - 10, tw + 2, 14, 3);
            ctx.fill();
            ctx.fillStyle =
              p.view.selection?.id === id && p.view.selection.kind === "node"
                ? dark
                  ? "#ffffff"
                  : "#162738"
                : dark
                  ? "#deebf7"
                  : "#23364b";
            ctx.fillText(roi.abbreviation, x, y);
            if (r.hovered === id) {
              ctx.strokeStyle = dark ? "#ffffff" : "#163850";
              ctx.lineWidth = 2;
              ctx.beginPath();
              ctx.arc(v.x, v.y, 7, 0, Math.PI * 2);
              ctx.stroke();
            }
            r.labelHits.push({ x, y, w: tw, id, alpha: labelAlpha[level] });
          }
        // A flat, fixed-screen-size H badge is an auxiliary set marker. It has
        // no sphere shading or anatomical identity and stays readable on rotation.
        const orderedAnchors = [...r.anchors].sort(
          (a, b) =>
            Number(a.id === p.view.selection?.id) -
            Number(b.id === p.view.selection?.id),
        );
        for (const anchor of orderedAnchors) {
          const level = emphasis(
            { kind: "hyperedge", id: anchor.id },
            p.view.selection,
            focus,
          );
          if (
            p.view.only_selected &&
            p.view.selection &&
            !focus.hyperIds.has(anchor.id)
          )
            continue;
          const v = project(anchor.position);
          if (v.z < -1 || v.z > 1) continue;
          const radius = level === "primary" ? 15 : 9;
          const alpha =
            level === "primary"
              ? 1
              : level === "context"
                ? 0.009
                : level === "related"
                  ? 0.3
                  : 0.7;
          ctx.globalAlpha = alpha;
          ctx.beginPath();
          for (let i = 0; i < 6; i++) {
            const angle = (i * Math.PI) / 3;
            const x = v.x + Math.cos(angle) * radius,
              y = v.y + Math.sin(angle) * radius;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          ctx.closePath();
          ctx.fillStyle = dark ? "#111e30" : "#ffffff";
          ctx.fill();
          ctx.strokeStyle = anchor.color;
          ctx.lineWidth = level === "primary" ? 2.3 : 1.3;
          ctx.stroke();
          ctx.font = `700 ${level === "primary" ? 15 : 10}px Inter,Segoe UI,sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillStyle = anchor.color;
          ctx.fillText("H", v.x, v.y + 0.5);
          ctx.textAlign = "start";
          ctx.textBaseline = "alphabetic";
          r.anchorHits.push({ ...v, radius, id: anchor.id, alpha });
        }
        element.dataset.anchorCount = String(r.anchors.length);
        ctx.globalAlpha = 1;
        ctx.font = "bold 12px Inter,Segoe UI,sans-serif";
        for (const [label, xyz] of [
          ["L", [center.x - extent.x * 0.66, center.y, center.z]],
          ["R", [center.x + extent.x * 0.66, center.y, center.z]],
          ["A", [center.x, center.y + extent.y * 0.66, center.z]],
          ["P", [center.x, center.y - extent.y * 0.66, center.z]],
          ["S", [center.x, center.y, center.z + extent.z * 0.66]],
          ["I", [center.x, center.y, center.z - extent.z * 0.66]],
        ] as [string, number[]][]) {
          const v = project(xyz);
          ctx.fillStyle = dark ? "#8496ae" : "#697c91";
          ctx.fillText(label, v.x, v.y);
        }
        ctx.font = "10px Inter,Segoe UI,sans-serif";
        ctx.fillStyle = dark ? "#90a3bb" : "#566b80";
        ctx.fillText(
          `${p.geometry.space} · RAS+ · mm   |   ${p.rois.length} ROI   |   BrainFC Networks`,
          18,
          h - 18,
        );
        element.dataset.labelCount = String(r.labelHits.length);
      };
      r.render = () => {
        renderer.render(scene, camera);
        drawLabels();
      };
      let frame = 0,
        alive = true,
        slowFrames = 0,
        warned = false;
      const animate = () => {
        if (!alive) return;
        frame = requestAnimationFrame(animate);
        const changed = controls.update();
        if (changed || r.dirty) {
          const start = performance.now();
          r.render();
          r.dirty = false;
          element.dataset.renderMs = String(
            Math.round(performance.now() - start),
          );
          slowFrames =
            performance.now() - start > 110
              ? slowFrames + 1
              : Math.max(0, slowFrames - 1);
          if (slowFrames >= 3 && !warned) {
            warned = true;
            current.current.onSlow();
          }
        }
      };
      animate();
      const ray = new T.Raycaster();
      ray.params.Line!.threshold = 1.2;
      const hits = (e: PointerEvent) => {
        const box = renderer.domElement.getBoundingClientRect(),
          x = e.clientX - box.left,
          y = e.clientY - box.top;
        const anchors = [...r.anchorHits]
          .reverse()
          .filter(
            (a) =>
              a.alpha >= 0.1 && Math.hypot(x - a.x, y - a.y) <= a.radius + 2,
          );
        if (anchors.length)
          return anchors.map(
            (a) => ({ kind: "hyperedge", id: a.id }) as Selection,
          );
        const label = [...r.labelHits]
          .reverse()
          .find(
            (a) =>
              a.alpha >= 0.1 &&
              x >= a.x &&
              x <= a.x + a.w &&
              Math.abs(y - (a.y - 4)) < 7,
          );
        if (label) return [{ kind: "node", id: label.id } as Selection];
        ray.setFromCamera(
          new T.Vector2((x / box.width) * 2 - 1, -(y / box.height) * 2 + 1),
          camera,
        );
        const found: Selection[] = [];
        const v = current.current.view,
          focus = related(
            v.selection,
            current.current.edges,
            current.current.hypers,
          );
        for (const hit of ray.intersectObjects(r.pickables, false)) {
          if (!hit.object.visible) continue;
          const data = hit.object.userData;
          const s: Selection | undefined =
            data.selection ||
            (hit.instanceId !== undefined
              ? data.selections?.[hit.instanceId]
              : data.selections?.[Math.floor((hit.index || 0) / 2)]);
          if (
            s &&
            v.only_selected &&
            v.selection &&
            !(s.kind === "node"
              ? focus.nodes.has(s.id)
              : s.kind === "edge"
                ? focus.edgeIds.has(s.id)
                : focus.hyperIds.has(s.id))
          )
            continue;
          if (s && !found.some((a) => a.kind === s.kind && a.id === s.id))
            found.push(s);
        }
        const priority = (s: Selection) => {
          const level = emphasis(s, v.selection, focus);
          const rank =
            level === "primary"
              ? 0
              : level === "related"
                ? 2
                : level === "context"
                  ? 4
                  : 0;
          return rank + (s.kind === "node" ? 0 : 1);
        };
        return found.sort((a, b) => priority(a) - priority(b));
      };
      let down = { x: 0, y: 0 },
        throttle = 0;
      const pointerDown = (e: PointerEvent) => {
        down = { x: e.clientX, y: e.clientY };
      };
      const pointerUp = (e: PointerEvent) => {
        if (
          Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5 ||
          e.button !== 0
        )
          return;
        const candidates = hits(e);
        current.current.onCandidates(candidates);
        current.current.onSelect(candidates[0] || null);
      };
      const move = (e: PointerEvent) => {
        if (e.buttons || performance.now() - throttle < 100) return;
        throttle = performance.now();
        const s = hits(e)[0];
        const p = current.current;
        const hovered = s?.kind === "node" ? s.id : undefined;
        if (r.hovered !== hovered) {
          r.hovered = hovered;
          r.dirty = true;
        }
        if (!s) {
          setHover(null);
          return;
        }
        const text =
          s.kind === "node"
            ? p.rois.find((r) => (r.source_roi_id || r.roi_id) === s.id)
                ?.abbreviation || s.id
            : s.kind === "hyperedge"
              ? `超边 ${p.hypers.find((h) => h.id === s.id)?.display_id}`
              : `普通边 · ${p.edges.find((a) => a.id === s.id)?.weight.toFixed(4)}`;
        const b = element.getBoundingClientRect();
        setHover({
          text,
          x: Math.min(e.clientX - b.left + 12, b.width - 180),
          y: e.clientY - b.top + 14,
        });
      };
      const leave = () => {
        setHover(null);
        r.hovered = undefined;
        r.dirty = true;
      };
      renderer.domElement.addEventListener("pointerdown", pointerDown);
      renderer.domElement.addEventListener("pointerup", pointerUp);
      renderer.domElement.addEventListener("pointermove", move);
      renderer.domElement.addEventListener("pointerleave", leave);
      return () => {
        alive = false;
        cancelAnimationFrame(frame);
        observer.disconnect();
        controls.dispose();
        dispose(group);
        renderer.dispose();
        renderer.domElement.remove();
        runtime.current = null;
      };
    }, []);
    useEffect(() => {
      const r = runtime.current;
      if (!r) return;
      const { rois, edges, hypers, geometry, view } = props;
      dispose(r.group);
      r.instances = [];
      r.lines = [];
      r.solids = [];
      r.pickables = [];
      r.focusPaths = [];
      r.anchors = [];
      r.focusGroup = new T.Group();
      r.group.add(r.focusGroup);
      const lookup = new Map(
        rois.map((n) => [
          n.source_roi_id || n.roi_id,
          new T.Vector3().fromArray(n.coordinates),
        ]),
      );
      const add = (mesh: T.Object3D, pick = true) => {
        r.group.add(mesh);
        if (pick) r.pickables.push(mesh);
      };
      const brain = new T.Mesh(
        meshGeometry(geometry.brain),
        new T.MeshStandardMaterial({
          color: "#d3dbe4",
          transparent: true,
          opacity: view.opacity,
          depthWrite: false,
          roughness: 0.78,
          side: T.FrontSide,
        }),
      );
      brain.renderOrder = 3;
      add(brain, false);
      r.brain = brain;
      if (view.style === "parcels")
        for (const roi of rois) {
          const s = geometry.parcels[roi.roi_id];
          if (!s) continue;
          const color = new T.Color(roi.color || categoryColor(roi.roi_id)),
            selection: Selection = {
              kind: "node",
              id: roi.source_roi_id || roi.roi_id,
            };
          const mesh = new T.Mesh(
            meshGeometry(s),
            new T.MeshStandardMaterial({
              color,
              transparent: true,
              opacity: 0.62,
              roughness: 0.78,
              depthWrite: false,
            }),
          );
          mesh.userData.selection = selection;
          add(mesh);
          r.solids.push({
            mesh,
            selection,
            color,
            opacity: 0.62,
            part: "parcel",
          });
          const outline = new T.LineSegments(
            new T.EdgesGeometry(mesh.geometry, 32),
            new T.LineBasicMaterial({
              color,
              transparent: true,
              opacity: 0.24,
              depthWrite: false,
            }),
          );
          add(outline, false);
          r.solids.push({
            mesh: outline,
            selection,
            color,
            opacity: 0.24,
            part: "parcel-outline",
          });
        }
      const sphere = new T.SphereGeometry(1, rois.length > 200 ? 10 : 16, 10),
        nodeMesh = new T.InstancedMesh(
          sphere,
          transparentMaterial(
            new T.MeshStandardMaterial({ roughness: 0.4, metalness: 0.05 }),
          ),
          rois.length,
        );
      const nodeData: Instance = {
          mesh: nodeMesh,
          selections: [],
          colors: [],
          matrices: [],
        },
        transform = new T.Object3D();
      sphere.setAttribute(
        "visualAlpha",
        new T.InstancedBufferAttribute(
          new Float32Array(rois.length).fill(1),
          1,
        ),
      );
      rois.forEach((roi, i) => {
        transform.position.fromArray(roi.coordinates);
        transform.scale.setScalar(
          view.style === "ballstick"
            ? 2.35
            : view.style === "parcels"
              ? 1.6
              : 1.65,
        );
        transform.updateMatrix();
        nodeData.matrices.push(transform.matrix.clone());
        nodeData.colors.push(new T.Color(roiColor(roi)));
        nodeData.selections.push({
          kind: "node",
          id: roi.source_roi_id || roi.roi_id,
        });
        nodeMesh.setMatrixAt(i, transform.matrix);
        nodeMesh.setColorAt(i, nodeData.colors[i]);
      });
      nodeMesh.userData.selections = nodeData.selections;
      r.instances.push(nodeData);
      add(nodeMesh);
      const linePositions: number[] = [],
        lineColors: T.Color[] = [],
        lineSelections: Selection[] = [];
      const segment = (
        a: T.Vector3,
        b: T.Vector3,
        selection: Selection,
        color: T.Color,
      ) => {
        linePositions.push(...a.toArray(), ...b.toArray());
        lineSelections.push(selection);
        lineColors.push(color);
      };
      const lod = edges.length > 18000 || rois.length > 400;
      if (view.layer !== "hypergraph" && edges.length) {
        if (lod)
          edges.forEach((e) => {
            const a = lookup.get(e.source),
              b = lookup.get(e.target);
            if (a && b)
              segment(
                a,
                b,
                { kind: "edge", id: e.id },
                new T.Color(e.weight < 0 ? "#438dd3" : "#e69950"),
              );
          });
        else {
          const edgeMesh = new T.InstancedMesh(
            new T.CylinderGeometry(1, 1, 1, view.style === "ballstick" ? 6 : 4),
            transparentMaterial(
              new T.MeshStandardMaterial({
                roughness: 0.65,
              }),
            ),
            edges.length,
          );
          edgeMesh.geometry.setAttribute(
            "visualAlpha",
            new T.InstancedBufferAttribute(
              new Float32Array(edges.length).fill(1),
              1,
            ),
          );
          const data: Instance = {
              mesh: edgeMesh,
              selections: [],
              colors: [],
              matrices: [],
            },
            axis = new T.Vector3(0, 1, 0);
          let max = 0;
          edges.forEach((e) => {
            max = Math.max(max, Math.abs(e.weight));
          });
          edges.forEach((e, i) => {
            const a = lookup.get(e.source)!,
              b = lookup.get(e.target)!;
            const d = b.clone().sub(a);
            transform.position.copy(a).add(b).multiplyScalar(0.5);
            transform.quaternion.setFromUnitVectors(
              axis,
              d.clone().normalize(),
            );
            const radius =
              (view.style === "ballstick" ? 0.22 : 0.11) *
              (1 + Math.abs(e.weight) / (max || 1));
            transform.scale.set(radius, d.length(), radius);
            transform.updateMatrix();
            data.matrices.push(transform.matrix.clone());
            data.colors.push(new T.Color(e.weight < 0 ? "#438dd3" : "#e69950"));
            data.selections.push({ kind: "edge", id: e.id });
            edgeMesh.setMatrixAt(i, transform.matrix);
            edgeMesh.setColorAt(i, data.colors[i]);
          });
          edgeMesh.userData.selections = data.selections;
          edgeMesh.renderOrder = view.style === "parcels" ? 4 : 0;
          r.instances.push(data);
          add(edgeMesh);
        }
      }
      let fallback = 0;
      if (view.layer !== "graph")
        for (const h of hypers) {
          const points = h.members.map((m) => lookup.get(m)!).filter(Boolean),
            color = new T.Color(categoryColor(h.id)),
            selection: Selection = { kind: "hyperedge", id: h.id };
          if (!points.length) continue;
          let surface: T.BufferGeometry | undefined;
          if (
            (view.style === "envelope" || view.style === "parcels") &&
            isSolid(points)
          ) {
            try {
              surface =
                points.length === 3
                  ? new T.BufferGeometry().setFromPoints(points)
                  : new ConvexGeometry(points);
              surface.computeVertexNormals();
            } catch {
              surface = undefined;
            }
          }
          if (surface) {
            if (view.style === "envelope") {
              const mesh = new T.Mesh(
                surface,
                new T.MeshBasicMaterial({
                  color,
                  transparent: true,
                  opacity: objectAlpha("global", "surface", hypers.length),
                  side: points.length === 3 ? T.DoubleSide : T.FrontSide,
                  depthWrite: false,
                }),
              );
              mesh.userData.selection = selection;
              mesh.renderOrder = 1;
              add(mesh);
              r.solids.push({
                mesh,
                selection,
                color,
                opacity: 0.17,
                part: "surface",
              });
            }
            const outline = new T.LineSegments(
              new T.EdgesGeometry(surface, 10),
              new T.LineBasicMaterial({
                color,
                transparent: true,
                opacity: 0.62,
                depthWrite: false,
              }),
            );
            outline.userData.selection = selection;
            outline.renderOrder = view.style === "parcels" ? 4 : 1;
            add(outline);
            r.solids.push({
              mesh: outline,
              selection,
              color,
              opacity: 0.62,
              part: "outline",
            });
            const boundary = outline.geometry.getAttribute("position");
            const paths: T.Curve<T.Vector3>[] = [];
            for (let i = 0; i < boundary.count; i += 2)
              paths.push(
                new T.LineCurve3(
                  new T.Vector3().fromBufferAttribute(boundary, i),
                  new T.Vector3().fromBufferAttribute(boundary, i + 1),
                ),
              );
            r.focusPaths.push({ id: h.id, color, paths });
            if (view.style === "parcels") surface.dispose();
          } else {
            if (view.style === "envelope" || view.style === "parcels")
              fallback++;
            const center = points
              .reduce((sum, p) => sum.add(p), new T.Vector3())
              .multiplyScalar(1 / points.length);
            const paths: T.Curve<T.Vector3>[] = [];
            points.forEach((p) => {
              const direction = p.clone().sub(center);
              const normal = new T.Vector3(0, 0, 1);
              if (Math.abs(direction.clone().normalize().dot(normal)) > 0.9)
                normal.set(0, 1, 0);
              const bend = direction
                .clone()
                .cross(normal)
                .normalize()
                .multiplyScalar(direction.length() * 0.08);
              const path = new T.QuadraticBezierCurve3(
                center.clone(),
                center.clone().lerp(p, 0.5).add(bend),
                p.clone(),
              );
              paths.push(path);
              const samples = path.getPoints(10);
              for (let i = 1; i < samples.length; i++)
                segment(samples[i - 1], samples[i], selection, color);
            });
            r.focusPaths.push({ id: h.id, color, paths });
            r.anchors.push({
              id: h.id,
              position: center.toArray(),
              color: categoryColor(h.id),
            });
          }
        }
      if (linePositions.length) {
        const original = new Float32Array(linePositions),
          g = new T.BufferGeometry();
        g.setAttribute("position", new T.BufferAttribute(original.slice(), 3));
        g.setAttribute(
          "visualAlpha",
          new T.Float32BufferAttribute(
            new Float32Array(lineSelections.length * 2).fill(1),
            1,
          ),
        );
        g.setAttribute(
          "color",
          new T.Float32BufferAttribute(
            lineColors.flatMap((c) => [...c.toArray(), ...c.toArray()]),
            3,
          ),
        );
        const mesh = new T.LineSegments(
          g,
          transparentMaterial(
            new T.LineBasicMaterial({
              vertexColors: true,
            }),
          ),
        );
        mesh.userData.selections = lineSelections;
        mesh.renderOrder = view.style === "parcels" ? 4 : 0;
        r.lines.push({
          mesh,
          selections: lineSelections,
          colors: lineColors,
          original,
        });
        add(mesh);
      }
      props.onStatus({ fallback, lod, fps: 0 });
      r.group.userData.built = true;
      if (host.current) {
        host.current.dataset.nodeCount = String(rois.length);
        host.current.dataset.edgeCount = String(
          view.layer === "hypergraph" ? 0 : edges.length,
        );
        host.current.dataset.hyperedgeCount = String(
          view.layer === "graph" ? 0 : hypers.length,
        );
      }
    }, [
      props.rois,
      props.edges,
      props.hypers,
      props.geometry,
      props.view.style,
      props.view.layer,
    ]);
    useEffect(() => {
      const r = runtime.current;
      if (!r) return;
      const { view, edges, hypers } = props,
        dark = view.theme === "midnight",
        bg = new T.Color(dark ? "#111d2e" : "#f8fafc");
      r.scene.background = bg;
      const focus = related(view.selection, edges, hypers),
        levelFor = (s: Selection) => emphasis(s, view.selection, focus);
      if (r.brain) {
        (r.brain.material as T.MeshStandardMaterial).opacity = view.selection
          ? Math.min(view.opacity, 0.065)
          : view.opacity;
        r.brain.visible = view.opacity > 0;
      }
      for (const data of r.instances) {
        const alpha = data.mesh.geometry.getAttribute("visualAlpha");
        data.selections.forEach((s, i) => {
          const level = levelFor(s);
          data.mesh.setColorAt(i, data.colors[i]);
          alpha.setX(
            i,
            objectAlpha(
              level,
              s.kind === "node" ? "node" : "edge",
              hypers.length,
              view.layer === "both",
            ),
          );
          data.mesh.setMatrixAt(
            i,
            level === "context" && view.only_selected ? zero : data.matrices[i],
          );
        });
        alpha.needsUpdate = true;
        data.mesh.instanceMatrix.needsUpdate = true;
        if (data.mesh.instanceColor) data.mesh.instanceColor.needsUpdate = true;
      }
      for (const data of r.lines) {
        const attr = data.mesh.geometry.getAttribute("color"),
          pos = data.mesh.geometry.getAttribute("position"),
          alpha = data.mesh.geometry.getAttribute("visualAlpha");
        data.selections.forEach((s, i) => {
          const level = levelFor(s),
            color = data.colors[i];
          for (let k = 0; k < 2; k++) {
            attr.setXYZ(i * 2 + k, color.r, color.g, color.b);
            alpha.setX(
              i * 2 + k,
              objectAlpha(
                level,
                s.kind === "hyperedge" ? "membership" : "edge",
                hypers.length,
                view.layer === "both",
              ),
            );
            const j = i * 6 + k * 3;
            pos.setXYZ(
              i * 2 + k,
              level === "context" && view.only_selected
                ? 1e6
                : data.original[j],
              data.original[j + 1],
              data.original[j + 2],
            );
          }
        });
        attr.needsUpdate = true;
        alpha.needsUpdate = true;
        pos.needsUpdate = true;
        data.mesh.geometry.computeBoundingSphere();
      }
      for (const data of r.solids) {
        const level = levelFor(data.selection),
          material = data.mesh.material as T.MeshStandardMaterial;
        material.opacity = objectAlpha(level, data.part, hypers.length);
        data.mesh.visible = !(view.only_selected && level === "context");
      }
      dispose(r.focusGroup);
      if (view.selection?.kind === "hyperedge") {
        const selected = r.focusPaths.find((p) => p.id === view.selection!.id);
        if (selected) {
          const material = new T.MeshBasicMaterial({
            color: selected.color,
            transparent: true,
            opacity: 0.92,
            depthWrite: false,
          });
          for (const path of selected.paths) {
            const mesh = new T.Mesh(
              new T.TubeGeometry(path, 16, 0.19, 5, false),
              material,
            );
            mesh.renderOrder = 5;
            r.focusGroup.add(mesh);
          }
        }
      }
      if (host.current) {
        host.current.dataset.focusMode = view.selection?.kind || "global";
        host.current.dataset.contextNodeAlpha = String(
          view.selection
            ? objectAlpha("context", "node")
            : objectAlpha("global", "node"),
        );
      }
      r.dirty = true;
    }, [props.view, props.rois, props.edges, props.hypers, props.geometry]);
    return (
      <div className="brain-scene" ref={host} data-testid="brain-scene">
        <canvas className="brain-labels" ref={overlay} aria-hidden="true" />
        {hover && (
          <div className="brain-hover" style={{ left: hover.x, top: hover.y }}>
            {hover.text}
          </div>
        )}
        {error && <div className="viewer-empty">{error}</div>}
      </div>
    );
  },
);
export default BrainScene;
