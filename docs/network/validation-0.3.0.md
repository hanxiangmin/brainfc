# Hyper-Brain 0.3.0

## Display changes

- Three styles: Node-link (`ballstick`), Envelope (`envelope`), Parcel surfaces (`parcels`). Midnight and Paper remain independent themes.
- Legacy `skeleton` view files migrate to `ballstick`, retaining selection, camera and other display parameters. Analysis results are not changed.
- Membership links terminate at a screen-facing, outlined hexagonal H badge. This auxiliary anchor has no ROI identity. Its selected diameter is 30 CSS pixels; global diameter is 18 CSS pixels. Marker sizes do not encode hyperedge weight.
- Anchor hit testing retains separate candidates for coincident hyperedges. Nonselected context uses the existing transparent focus policy.

## Verification

- Python: **137 tests passed**, including six view/theme round trips, legacy migration, atlas mapping, numerical methods, parsing and local HTTP behavior. Warnings came from upstream deprecations.
- Frontend: **8 tests passed**; TypeScript check, production build and bundled third-party license hash verification passed.
- Real browser selection: selected H06 through the H badge, rotated the brain and selected it again; six members remained selected. Coincident H04 and H04-repeat appeared as independent candidates. The analysis JSON remained identical.
- Installed wheel: imported from isolated site-packages; core analysis and five cached atlases worked with network connections disabled. Upload-worker output matched the Python API; wheel and source metadata passed `twine check`.
- Bilingual showcase: English and Chinese routes; all six style/theme combinations; 26 gallery entries, category filtering, modal opening and Escape dismissal; 390-pixel mobile viewport without horizontal overflow. No page errors in these checks.
- Captures: AAL 90/116 and Schaefer 200/400 with full selected structural layers; 3/4/6/8/12-member custom hyperedges; graph-only and overlay views; node and edge selection; linked matrix, native member table and NIfTI/reference slices.

- Static publication: both rendered routes and all gallery interactions passed under the GitHub Pages `/Hyper-Brain` prefix, including mobile layout and original-image downloads.

## Screenshot provenance

All 26 images in `website/public/gallery` are actual local application captures. They use **synthetic data**, not patient records or disease findings. The local application UI is currently Chinese; the introduction website and README are bilingual.

`examples/prepare_gallery.py` generates 240 observations with `numpy.random.default_rng(20260910 + n_rois)`: seven independent Gaussian latent series plus Gaussian ROI noise, then Pearson correlation. AAL 116 uses seven explicitly specified illustrative hyperedges (including two IDs with identical membership). AAL 90 and Schaefer 200/400 use FC-profile kNN with k=3. Ordinary graphs use density 0.04. All fixtures pass through public upload, analysis and atlas-binding endpoints.

`frontend/scripts/capture-gallery.cjs` saves the images and `manifest.json`. The manifest records the atlas version and space, matrix checksum, configuration, exact selected members, layer counts and image checksum. ROI coordinates come from the selected atlas. Display geometry does not establish a biological network or an anatomical fiber trajectory.

Rendering was checked in local Chromium with software WebGL. The captured frame durations are observations on this machine, not a cross-device performance benchmark. A dense 400-region view deliberately retains the full structure; label crowding remains visible rather than being hidden by automatic deletion.

## Documentation design

The English and Chinese READMEs use a concise introduction, installation near the top, a real workbench image, a side-by-side style grid, an expandable gallery and a compact capability table. The September 10, 2026 Trending pages for [i-have-adhd](https://github.com/ayghri/i-have-adhd) and [teamai-cli](https://github.com/Tencent/teamai-cli) informed information hierarchy only. No ranking, usage, endorsement or clinical-performance claims were transferred to this project.
