# Implementation contract — 0.1

This document describes the shared API used by the implementation teams. No historical experiment is imported.

## Numerical API

- `connectivity.compute_connectivity(timeseries, method='pearson') -> ndarray`; `fisher_z(matrix)` / `inverse_fisher_z(matrix)`; explicit finite handling on the diagonal.
- `graph.build_graph(matrix, roi_ids=None, method='density', threshold=.2, density=.1, k=5) -> networkx.Graph` retains signed edges, deterministic ties without index-based top-k loss. `graph.analyze_graph(graph) -> {'global': dict, 'nodes': list[dict]}`. Node rows have `id`; `graph.to_payload(graph)` returns `{'edges': [{'source','target','weight'}], 'metrics': ...}`. Global network length metrics use positive weights and document inverse-weight lengths.
- `hypergraph.build_hypergraph(matrix, roi_ids=None, method='knn', ks=None, custom_edges=None, groups=None) -> xgi.Hypergraph`. Custom edges have `id`, `members` (ROI IDs), optional `weight`; preserve explicit edge identity. Template groups map group ID to ROI members. `hypergraph.to_payload(H) -> {'edges': [{'id','members','weight', ...}], 'metrics': {'global': dict, 'nodes': list[dict]}}`.

## IO API

- `inspect_file(path) -> {'name', 'format', 'variables': [{'name', 'shape', 'dtype'}], 'suggested_kind', 'suggested_variable', 'suggested_matrix_kind', 'warnings'}`; no full path in user payload. CSV/TXT/1D variable name is `data`.
- `load_data(path, kind='auto', variable=None, roi_columns=None, matrix_kind='auto', roi_ids=None, labels=None, coordinates=None, metadata=None, preset='generic') -> BrainDataset`. roi_columns is either a list of zero-based ints or a Python-style slice string e.g. `0:116`; MAT/NPZ multiple arrays require explicit choice. ADHD helper columns must be discarded by header names, MDD >1000 columns must require explicit selection.
- `validate_dataset(dataset) -> list[str]` throws ValidationError for bad shapes, non-finite values, constant time channels, mismatched ROI IDs/labels/coordinates, nonsymmetric FC. Max 1000 ROIs, 100000 timepoints, 5000000 cells. Missing TR is a warning for static FC, not a block.
- `statistics.describe(values)`; `compare_groups(data, group_column, subject_column, feature_columns, covariates=None)` accepts dataframe, returns JSON-safe effect/p/q rows, detects repeated IDs and invalid group/feature/covariate values, uses statsmodels OLS HC3 or scipy Welch as appropriate, BH-FDR. Public API only unless UI explicitly supplies a participant table.

## Browser REST API

- `GET /api/v1/health -> {'version','local_only':true}`
- `POST /api/v1/uploads` multipart field `files` (multiple) -> `{'files':[{'id','name', ...inspection}]}`. Server assigns opaque file IDs, never accepts external paths.
- `GET /api/v1/uploads -> {'files':[...]}`
- `POST /api/v1/jobs` JSON `{file_ids:[...], input:{kind, variable, roi_columns, matrix_kind, preset, roi_ids, labels, coordinates, metadata}, analysis:{...AnalysisConfig}} -> job`.
- `GET /api/v1/jobs -> {'jobs':[...]}`; `GET /api/v1/jobs/{id} -> job`.
- Job fields: `id`, `status` queued/running/completed/failed/cancelled/interrupted, `progress` 0..100, `message`, `created_at`, `files`, `results` [{id,name}], `errors` [{name,message}]. Batch failures are isolated; if any succeed job is completed with errors.
- `POST /api/v1/jobs/{id}/cancel`; `POST /api/v1/jobs/{id}/retry -> new job`.
- `GET /api/v1/results/{id} -> AnalysisResult.to_dict()`.
- `GET /api/v1/results/{id}/export?format=zip|json|csv|html|svg|png|pdf|graphml|hyperedges` returns download. ZIP includes all artifacts.
- `POST /api/v1/statistics` JSON `{rows:[...], group_column, subject_column, feature_columns:[...], covariates:[]}` -> statistics output.

## Frontend

React + Vite, installed static files under `src/hicbrain/web/static`. No CDN. Main upload workflow, queue/result list, metadata input (ROI table optional), analysis configuration, results with linked selection via ROI ID. Native hyperedge set/incidence view; FC Plotly heatmap, optional anatomical NiiVue scene only when explicit valid MNI coordinates exist. Never invent brain anatomy for unknown labels. NiiVue volume can use a packaged public template or supplied local NIfTI; no network requests required. 3D coordinate scatter may accompany but must not be falsely described as anatomical surface.
