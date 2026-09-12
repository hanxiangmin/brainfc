# Hyper-Brain local web UI

The Chinese React interface uses the same `/api/v1` API as local Python analysis workers. It contains no external CDN, hosted authentication, remote fonts or runtime analytics. NiiVue loads the local `/api/v1/template` only when a supplied ROI mapping explicitly uses MNI coordinates.

```powershell
npm ci
npm run check
npm run build
```

The Vite build writes bundled assets into `../src/hicbrain/web/static`, included in the Python wheel. Python package users do not need Node.js. To develop the interface alongside `hicbrain serve --no-browser`, run `npm run dev`; Vite proxies `/api` to `127.0.0.1:8765`.

Builds also run the offline license generator and include `THIRD_PARTY_NOTICES.txt` in the static output. It verifies lockfile/runtime SPDX and version agreement, retains installed LICENSE files, and adds checked-in upstream notices from `licenses/`. Run `npm run licenses` to regenerate notices without rebuilding JavaScript. Supplemental source refresh is a separate maintainer action and is never part of a normal build.

The UI supports uploads, inspect/parse settings, optional ROI CSV mapping, graph and native hypergraph configuration, persisted job progress/cancel/retry, result selection, ROI-linked visualizations, exports, and participant-table statistics. The graph visualization displays at most the strongest 650 connections; the hyperedge list displays 150 matches and incidence view the first 80 edges. Full structures and metrics remain in exports. Ring positions are explicitly abstract, never anatomical coordinates.

NiiVue 0.67 API use was verified against its installed TypeScript declarations and source (`attachToCanvas`, `loadVolumes`, `loadConnectome`, `onLocationChange`, `mm2frac`, `cleanup`). WebGL failures have an inline recovery message and do not disable matrix/network analysis.
