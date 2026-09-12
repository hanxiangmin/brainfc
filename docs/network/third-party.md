# Third-party components

Hyper-Brain original source is Apache-2.0. This does not relicense external software or datasets.

| Component | Main license | Role |
|---|---|---|
| NumPy, SciPy, pandas | BSD-3-Clause | numerical arrays, computation, tables |
| Nilearn, scikit-learn | BSD-3-Clause | connectivity and neuroimaging resources |
| NiBabel | MIT | neuroimaging file IO |
| scikit-image | BSD-3-Clause | surfaces from validated label volumes |
| NetworkX, XGI | BSD-3-Clause | graph and native hypergraph structures |
| Matplotlib | Matplotlib license | export figures |
| statsmodels | BSD-3-Clause | statistical estimation |
| FastAPI, Starlette, Uvicorn, python-multipart | MIT/BSD/Apache terms per distribution | optional local HTTP |
| React, React DOM, Plotly.js, lucide-react | MIT / ISC per component | bundled frontend |
| NiiVue | BSD-2-Clause | local anatomy display |
| Three.js | MIT | unified 3D scene, camera, picking and hyperedge geometry |
| Vite / TypeScript | MIT / Apache-2.0 | frontend build tools |

Exact installed Python dependency notices are retained by their distributions.

## Bundled frontend notices

Every `npm run build` ends with `npm run licenses`, which generates `src/hicbrain/web/static/THIRD_PARTY_NOTICES.txt` for inclusion in the Python wheel. Generation is offline and records the lockfile SHA-256, package versions, registry integrity, declared SPDX license, full license texts and original copyright notices.

The generator checks each installed non-development runtime package against `frontend/package-lock.json` and fails if a version, license declaration, required text or supplemental-source checksum differs. The 0.2 inventory has 21 runtime packages, including Three.js, React, React DOM, scheduler, Plotly.js, NiiVue, lucide-react, Papa Parse and the NiiVue/Zarr/compression dependency chain. NiiVue's optional native Rollup compiler is explicitly excluded because it is not shipped in the browser bundle. Tree-shaking may omit parts of the conservatively included runtime inventory.

Prebundled dependencies require more than top-level npm metadata: original Plotly embedded notices, MapLibre's BSD terms and embedded attributions, NiiVue's author-attributed utility code, Roboto/Apache portions, and the Blosc/LZ4/Zstandard libraries compiled by numcodecs are also retained. `frontend/licenses/sources.json` records the supplemental source URLs and SHA-256 hashes. NiiVue 0.67.0 omits its root LICENSE from its npm tarball, so its BSD-2-Clause license was retrieved at the exact npm `gitHead` commit `7021c439133ea9f63836f48cbdbbddea26e411ef`.

Maintainers may refresh supplemental texts with `node frontend/scripts/fetch-license-sources.mjs`, then review the changed content and checksums before building. Normal users and ordinary builds make no license-download network requests. These notices preserve third-party terms; they do not relicense those components as Apache-2.0.

The compatibility `/api/v1/template` endpoint retains Nilearn's installed MNI152 reference. The 0.2 atlas viewer instead uses exact matched MNIColin27 or MNI152NLin6Asym assets from TemplateFlow. Downloaded T1w, brain mask and template metadata remain under the local atlas source cache. Colin27's upstream LICENSE is retained; the FSL template's source manifest refers to upstream terms and the S3 inventory does not provide a LICENSE object. This project does not assign those assets an Apache license or redistribute them in its package.

AAL SPM12 assets retain upstream GPL terms. Schaefer2018 / CBIG retains MIT terms and source attribution. AAL published abbreviation/name facts are taken from the linked Table S9; the paper's figure or layout is not copied. See [exact atlas sources and version](viewer-atlases.md). No BrainNet Viewer, Surf Ice, BRAPH or HyperNetX-Widget code or surface is copied into Hyper-Brain; those projects are visual references only.

ABIDE, ADHD-200, REST-meta-MDD, ADNI and other user-provided research datasets retain their own access/use agreements. They are not distributed with this project. Optional GPL/AGPL/noncommercial tools in the catalogue are research references, not copied into the core.
