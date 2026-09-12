"""Offline time-series example with exact known numerical expectations.

Run: python examples/roi_timeseries.py --output ./roi-demo-001
"""

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from brainfc import Config, extract_connectome


def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(2026)
    signals = rng.normal(size=(80, 3))
    signals[:, 1] = signals[:, 0] * 0.8 + signals[:, 1] * 0.2
    signals[:, 2] = -signals[:, 0] * 0.7 + signals[:, 2] * 0.3
    pd.DataFrame(signals, columns=["A", "B", "C"]).to_csv(output / "signals.tsv", sep="\t", index=False)
    pd.DataFrame(
        {
            "roi_id": ["A", "B", "C"],
            "name": ["Synthetic left", "Synthetic right", "Synthetic third"],
            "x": [-30, 30, 0],
            "y": [-20, -20, 30],
            "z": [40, 40, 20],
        }
    ).to_csv(output / "rois.tsv", sep="\t", index=False)
    result = extract_connectome(
        output / "signals.tsv",
        rois=output / "rois.tsv",
        config=Config(data_space="synthetic-demo", detrend=False, standardize=False),
    )
    np.testing.assert_allclose(result.connectivity, np.corrcoef(signals, rowvar=False), atol=1e-12)
    result.provenance["synthetic"] = True
    result.save(output / "result")
    result.plot_views(output / "selected.svg", selection={"kind": "node", "id": "A"})
    print(output / "result/report.html")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    run(parser.parse_args().output)
