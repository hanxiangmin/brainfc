"""Extract fMRIPrep runs individually, preserving successes and recording failures.

Run: python examples/batch_derivatives.py DERIVATIVES --atlas ATLAS --config CONFIG --output NEW_DIR
The config JSON must declare compatible preprocessing/spaces for the chosen atlas.
"""

import argparse
import json
from pathlib import Path
from brainfc import Config, InputError, discover_bids, extract_connectome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("derivatives")
    parser.add_argument("--atlas", required=True)
    parser.add_argument("--rois")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    runs = discover_bids(args.derivatives)
    if not runs:
        raise InputError("No preprocessed volume runs found.")
    config = Config(**json.loads(args.config.read_text(encoding="utf-8-sig")))
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for i, run in enumerate(runs):
        record = {"source": run["bold"], "index": i}
        try:
            result = extract_connectome(
                run["bold"],
                atlas=args.atlas,
                rois=args.rois,
                confounds=run["confounds"],
                mask=run["mask"],
                reference=run["mask"],
                config=config,
            )
            record.update(status="complete", output=str(result.save(args.output / f"run-{i:04d}")))
        except Exception as error:
            record.update(status="failed", error_type=type(error).__name__, message=str(error))
        records.append(record)
        (args.output / "batch.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 1 if any(r["status"] == "failed" for r in records) else 0


if __name__ == "__main__":
    raise SystemExit(main())
