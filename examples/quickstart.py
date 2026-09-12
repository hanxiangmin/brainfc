"""Offline synthetic volume -> connectivity -> every result export.

Run: python examples/quickstart.py --output ./demo-001
The destination must not exist; no participant data or atlas downloads.
"""

import argparse
from pathlib import Path

from brainfc import Config, extract_connectome
from brainfc.demo import create_demo


def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    specification = create_demo(output / "input")
    config = Config(**specification.pop("config"))
    result = extract_connectome(**specification, config=config, progress=print)
    result.provenance["synthetic"] = True
    result.save(output / "result")
    print(f"Matrix: {result.connectivity.shape}; retained: {len(result.sample_indices)}")
    print(output / "result/report.html")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    run(parser.parse_args().output)
