"""Render the real bundled sample without changing its ROI order or FC values."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from brainfc import Config, extract_connectome
from brainfc.demo import create_demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory() as temporary:
        spec = create_demo(Path(temporary) / 'input', kind='rest01')
        manifest = json.loads((Path(temporary) / 'input/example.json').read_text(encoding='utf-8'))
        cfg = Config(**spec.pop('config'))
        result = extract_connectome(**spec, config=cfg)
    result.provenance.update(synthetic=False, example=manifest)
    for item in result.provenance['inputs'].values():
        item['path'] = 'data/' + Path(item['path']).name
    result.qc['warnings'].extend(manifest['limitations'])
    result.view(args.output / 'report.html', open_browser=False)

    # Contract: single-participant demonstration, all 100 ROIs and 145 retained
    # frames; one quantitative panel. No statistical/group inference, clustering,
    # interpolation, value thresholding, smoothing or ROI permutation.
    matrix = result.connectivity
    assert matrix.shape == (100, 100) and np.isfinite(matrix).all()
    assert len(result.sample_indices) == 145
    np.testing.assert_allclose(matrix, np.corrcoef(result.timeseries.T), atol=1e-12)
    plt.rcParams.update({
        'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'DejaVu Sans'],
        'font.size': 8, 'pdf.fonttype': 42, 'svg.fonttype': 'none',
        'axes.linewidth': .6, 'axes.spines.top': False, 'axes.spines.right': False,
        'figure.facecolor': 'white', 'savefig.facecolor': 'white',
    })
    groups = []
    for row in result.rois:
        hemisphere = 'L' if '_LH_' in row['name'] else 'R'
        short = {'SomMot': 'SM', 'DorsAttn': 'DAN', 'SalVentAttn': 'VAN',
                 'Limbic': 'Limb', 'Cont': 'Cont', 'Default': 'DMN'}.get(row['network'], row['network'])
        groups.append(f'{hemisphere}-{short}')
    starts = [0] + [i for i in range(1, 100) if groups[i] != groups[i-1]]
    ends = starts[1:] + [100]
    centers = [(a+b-1)/2 for a, b in zip(starts, ends)]
    labels = [groups[a] for a in starts]
    fig, ax = plt.subplots(figsize=(7.2, 7.0))
    fig.subplots_adjust(left=.12, bottom=.17, right=.85, top=.86)
    im = ax.imshow(matrix, cmap='RdBu_r', vmin=-1, vmax=1, interpolation='nearest')
    assert np.array_equal(np.asarray(im.get_array()), matrix)
    for border in starts[1:]:
        is_hemisphere = groups[border][0] != groups[border-1][0]
        ax.axhline(border-.5, color='#3c5263' if is_hemisphere else '#ffffff',
                   linewidth=.8 if is_hemisphere else .35)
        ax.axvline(border-.5, color='#3c5263' if is_hemisphere else '#ffffff',
                   linewidth=.8 if is_hemisphere else .35)
    ax.set_xticks(centers, labels, rotation=90, rotation_mode='anchor', ha='right', va='center', fontsize=7)
    ax.set_yticks(centers, labels, fontsize=7)
    ax.tick_params(length=0, pad=5)
    cax = fig.add_axes([.89, .255, .025, .52])
    bar = fig.colorbar(im, cax=cax, ticks=[-1, -.5, 0, .5, 1])
    bar.set_label('Pearson r', fontsize=8, labelpad=8)
    bar.outline.set_visible(False)
    fig.text(.12, .955, 'Resting-state functional connectivity', fontsize=14,
             weight='bold', color='#17394b', va='top')
    fig.text(.12, .91, 'Real example  |  1 participant  |  100 ROIs  |  145 frames',
             fontsize=8.5, color='#53697b', va='top')
    fig.text(.12, .065, 'Schaefer-100 original order · full signed matrix', fontsize=8, color='#53697b')
    fig.text(.12, .035, 'L / R: hemisphere · lines: network boundaries · diagonal r = 1',
             fontsize=7, color='#53697b')
    fig.canvas.draw()
    fig.savefig(args.output / 'matrix.png', dpi=600)
    fig.savefig(args.output / 'matrix.pdf', dpi=600)
    fig.savefig(args.output / 'matrix.svg', dpi=600)
    plt.close(fig)
    ids = [r['roi_id'] for r in result.rois]
    pd.DataFrame(matrix, index=ids, columns=ids).to_csv(args.output / 'matrix-values.csv', index_label='roi_id')
    record = {'sample': 'rest01', 'synthetic': False, 'n_participants': 1, 'n_rois': 100,
              'retained_frames': 145, 'roi_order': 'Original Schaefer-100 order, unchanged',
              'matrix': 'Full signed Pearson correlation; diagonal one; no display threshold',
              'color_limits': [-1, 1], 'interpolation': 'nearest',
              'matrix_float64_sha256': hashlib.sha256(matrix.astype('<f8').tobytes()).hexdigest(),
              'alignment': 'Not applicable: single quantitative panel; colorbar is a scale',
              'scope': 'Software demonstration; not a diagnosis or population average'}
    (args.output / 'matrix-provenance.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
