# Python API and local HTTP API

## Shared data objects

`BrainDataset(data, kind, roi_ids=[], labels=[], coordinates=None, matrix_kind='correlation', metadata={}, warnings=[])` holds a numeric T×R timeseries or R×R connectivity array. `coordinates`, when present, is R×3, with the coordinate space named in metadata. ROI IDs must be unique.

`AnalysisConfig` contains connectivity_method (`pearson`, `spearman`, `partial`); graph_method (`weighted`, `threshold`, `density`, `knn`, `mst`); threshold, density and k; hypergraph_method (`knn`, `multiscale`, `custom`, `template`); hypergraph_ks; custom_edges; groups; compute_graph and compute_hypergraph. Defaults: Pearson, graph density 0.1, hypergraph kNN k=5. Both analyses enabled.

`AnalysisResult` stores correlation, ROI identities, labels, anatomical coordinates, native graph/hypergraph payloads, config, metadata, warnings and software version. `layouts.graph_2d` separately stores a deterministic circular display layout by ROI ID, with unitless coordinates and `coordinate_space='display'`. `to_dict()` is JSON-safe; `from_dict()` restores an exported result (including older results without saved layouts).

## Read and validate

```python
from brainfc.network.io import inspect_file, load_data, validate_dataset

print(inspect_file("subject.mat"))
data = load_data("subject.mat", kind="timeseries", variable="ROISignals",
                roi_columns="0:116", metadata={"tr": 2.0})
warnings = validate_dataset(data)
```

`roi_columns` accepts a zero-based integer list or a half-open Python slice string. Multi-array MAT/NPZ requires a variable. `matrix_kind` is `auto`, `correlation`, `fisher_z`, or `covariance`. Presets are `generic`, `abide1`, `abide2`, `adhd`, `mdd`, `adni`; they never infer diagnosis or anatomical labels.

## Construct structures directly

```python
from brainfc.network.connectivity import compute_connectivity, fisher_z, inverse_fisher_z
from brainfc.network.graph import build_graph, analyze_graph
from brainfc.network.hypergraph import build_hypergraph, to_payload

fc = compute_connectivity(data.data, method="pearson")
graph = build_graph(fc, data.roi_ids, method="density", density=0.1)
metrics = analyze_graph(graph)
hypergraph = build_hypergraph(fc, data.roi_ids, method="custom",
    custom_edges=[{"id": "network-A", "members": data.roi_ids[:3], "weight": 1}])
native = to_payload(hypergraph)
```

Graph functions return NetworkX Graph objects; hypergraph construction returns an XGI Hypergraph. `to_payload` retains native hyperedge IDs and membership. kNN-generated duplicate member sets are consolidated with their originating scales/centers retained.

## Cohort statistics

```python
import pandas as pd
from brainfc.network.statistics import compare_groups

table = pd.read_csv("participant_metrics.csv")
comparison = compare_groups(table, group_column="group", subject_column="subject_id",
    feature_columns=["efficiency", "mean_hyperdegree"], covariates=["age", "mean_fd"])
```

Two groups and independent subject IDs are required. With covariates, categorical covariates are encoded by the documented implementation; consult returned design and exclusions. Missing rows, tested families and group order are reported. ROI rows or repeated scans must not be presented as independent participants.

## Exports

`export_result(result, path, format=None)` supports json, html, svg, png, pdf, graphml, hyperedges, zip, csv. `csv` is a ZIP of complete labeled tables. `zip` adds the JSON source of truth, standalone HTML, GraphML, native hyperedges, and figures. Spreadsheet values that resemble formulas are escaped; JSON preserves exact identifiers.

## Local HTTP

### Atlas and independent view state (0.2)

```python
from brainfc.network import AtlasRegistry, AtlasSpec, ViewConfig

registry = AtlasRegistry("./my-analysis/atlases")
catalog = registry.list()                   # includes uninstalled standard entries
spec = registry.install("aal-spm12-116")   # explicit first-use download
# Supply your independently verified, ordered atlas IDs, one per matrix row.
mapped = registry.bind(result, spec["id"], ordered_roi_ids, confirmed=True)
view = ViewConfig(style="envelope", theme="midnight", layer="both", opacity=0.2)

custom = registry.import_atlas("atlas.nii.gz", "labels.tsv",
    name="My parcellation", space="my-reference-v1", version="1.0",
    reference="aligned_brain_only_reference.nii.gz", space_confirmed=True)
surface_path = registry.asset(custom["id"], "geometry.json")
```

`AtlasSpec` records version, exact space, labels / names / hemispheres / representative coordinates, source URLs, license and source/content hashes. `bind` returns a copy, retaining source ROI IDs, connectivity, graph IDs, native hyperedges and analysis parameters. Its added `metadata.roi_metadata` maps source ROI IDs to atlas ROI IDs. Anatomical coordinates use RAS+ millimetres; display layouts stay separate. Installation and custom-import details: [atlas guide](viewer-atlases.md).

`ViewConfig` fields are `style`, `theme`, `layer`, `opacity`, `labels`, `only_selected`, `selection`, `camera`, `schema_version`. Camera contains `position`, `target`, `up` as finite XYZ vectors. Selection is `{kind: 'node'|'edge'|'hyperedge', id: stable_string_key}`; native hyperedge IDs are encoded with type in the view only, e.g. `'["number",1]'` and `'["string","1"]'`. `to_dict` / `from_dict` validates independent view JSON.

| Method / endpoint | Action |
|---|---|
| GET `/api/v1/atlases` | List standard catalogue and locally installed atlases |
| POST `/api/v1/atlases/{id}/install` | Download official resources and generate local geometry |
| GET `/api/v1/atlases/{id}` | Return installed AtlasSpec |
| POST `/api/v1/atlases` | Multipart `parcellation`, `labels`, optional `reference`, JSON string `metadata` |
| GET `/api/v1/atlases/{id}/assets/{name}` | Read allowlisted geometry, labels, parcellation or reference |
| POST `/api/v1/results/{id}/atlas` | Bind explicit `atlas_id`, `ordered_roi_ids`, `confirmed: true` |
| GET `/api/v1/results/{id}/mapped` | Read result plus verified atlas binding, leaving original result unchanged |
| GET / PUT `/api/v1/results/{id}/view` | Read / validate and save ViewConfig |

Atlas upload metadata requires `name`, exact `space`, and `space_confirmed: true`; optional `version`, `sources`, `license`. Custom spaces require their own reference brain. Standard spaces can use their matched installed/downloaded reference when omitted. An invalid import returns 422; a failed upstream installation returns 502 with retry context. Atlas generation runs outside the HTTP event loop; analysis jobs retain their process queue.

### Existing analysis endpoints

The web extra provides FastAPI and interactive OpenAPI documentation at `/docs`. Endpoints are `/api/v1/uploads`, `/api/v1/jobs`, `/api/v1/jobs/{id}`, `/api/v1/jobs/{id}/cancel`, `/api/v1/jobs/{id}/retry`, `/api/v1/results/{id}`, `/api/v1/results/{id}/export`, `/api/v1/statistics` and `/api/v1/template`.

Uploads use multipart field `files`. Job JSON has `file_ids`, `input` (load_data options except path), and `analysis` (AnalysisConfig). File IDs are opaque; arbitrary server file paths are not accepted. Local service access from a foreign browser origin is rejected.

```json
{"file_ids":["returned-upload-id"],"input":{"kind":"timeseries","variable":"ROISignals","roi_columns":"0:116"},"analysis":{"graph_method":"density","density":0.1,"hypergraph_method":"knn","k":5}}
```

Jobs are durable across restarts. Running/queued work is marked interrupted on restart; retry creates a new job rather than silently overwriting results. One subprocess runs at a time. Batch failures are isolated and explicitly listed beside successful results.
