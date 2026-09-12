from __future__ import annotations
import argparse
import json
from pathlib import Path
import threading
import webbrowser
from .models import Config, InputError
from ._version import __version__


def _parser():
    parser = argparse.ArgumentParser(
        prog="brainfc", description="fMRI → ROI time series → functional connectivity"
    )
    parser.add_argument("--version", action="version", version=f"brainfc {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Start the local graphical interface")
    serve.add_argument("--port", type=int, default=8766)
    serve.add_argument("--workspace", type=Path)
    serve.add_argument("--no-browser", action="store_true")
    inspect = sub.add_parser("inspect", help="Inspect an image or discover BIDS derivatives")
    inspect.add_argument("source")
    fetch = sub.add_parser("atlas", help="Explicitly download a supported standard atlas")
    fetch.add_argument("name", choices=["schaefer100", "schaefer200", "schaefer400", "aal116"])
    fetch.add_argument("--data-dir", type=Path)
    demo = sub.add_parser("demo", help="Create synthetic NIfTI and extract a complete example report")
    demo.add_argument("--output", type=Path, required=True)
    extract = sub.add_parser("extract", help="Extract one run")
    extract.add_argument("source")
    for key in ("atlas", "rois", "confounds", "mask", "reference"):
        extract.add_argument("--" + key)
    extract.add_argument("--config", type=Path, help="Config JSON")
    extract.add_argument("--output", type=Path, required=True)
    extract.add_argument("--preprocessed", action="store_true", default=None)
    extract.add_argument("--data-space")
    extract.add_argument("--atlas-space")
    extract.add_argument("--tr", type=float)
    extract.add_argument("--no-report", action="store_true")
    extract.add_argument("--no-figures", action="store_true")
    batch = sub.add_parser("batch", help="Extract each fMRIPrep run separately; failed runs are recorded")
    batch.add_argument("bids_dir", type=Path)
    batch.add_argument("--atlas", required=True)
    batch.add_argument("--rois")
    batch.add_argument("--config", type=Path, required=True)
    batch.add_argument("--output", type=Path, required=True)
    dicom = sub.add_parser("dicom", help="Plan or run dcm2niix conversion")
    dicom.add_argument("source")
    dicom.add_argument("--output", required=True)
    dicom.add_argument("--run", action="store_true")
    preproc = sub.add_parser("preprocess", help="Plan or run external fMRIPrep (requires Docker)")
    preproc.add_argument("bids_dir")
    preproc.add_argument("--output", required=True)
    preproc.add_argument("--license", required=True)
    preproc.add_argument("--participant")
    preproc.add_argument("--space", default="MNI152NLin6Asym")
    preproc.add_argument("--run", action="store_true")
    return parser


def main(argv=None):
    """Run the CLI with a list of arguments, or sys.argv when argv is None.

    Returns 0 on success. argparse raises SystemExit(0) for help/version and
    SystemExit(2) for usage, InputError and common path errors. Unexpected
    library/external-process errors propagate; a failed batch exits with 2
    after preserving successful run outputs and batch.json.
    """
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            if not 1 <= args.port <= 65535:
                raise InputError("Port must be between 1 and 65535.")
            try:
                import uvicorn
                from .web.app import create_app
            except ImportError as exc:
                raise InputError(
                    "The installation is incomplete. Reinstall the BrainFC wheel or source "
                    "with dependencies in this Python environment."
                ) from exc
            url = f"http://127.0.0.1:{args.port}"
            if not args.no_browser:
                timer = threading.Timer(1.5, lambda: webbrowser.open(url))
                timer.daemon = True
                timer.start()
            print(f"BrainFC: {url}", flush=True)
            uvicorn.run(create_app(args.workspace), host="127.0.0.1", port=args.port)
        elif args.command == "inspect":
            from .io import inspect_input

            print(json.dumps(inspect_input(args.source), ensure_ascii=False, indent=2))
        elif args.command == "atlas":
            from .atlases import fetch_atlas

            print(json.dumps(fetch_atlas(args.name, data_dir=args.data_dir), ensure_ascii=False, indent=2))
        elif args.command == "demo":
            from .demo import create_demo
            from .pipeline import extract_connectome

            args.output.mkdir(parents=True, exist_ok=False)
            spec = create_demo(args.output / "input")
            config = Config(**spec.pop("config"))
            result = extract_connectome(**spec, config=config, progress=print)
            result.provenance["synthetic"] = True
            print(result.save(args.output / "result"))
        elif args.command == "extract":
            from .pipeline import extract_connectome

            config = json.loads(args.config.read_text(encoding="utf-8-sig")) if args.config else {}
            for key in ("preprocessed", "data_space", "atlas_space"):
                if getattr(args, key) is not None:
                    config[key] = getattr(args, key)
            if args.tr is not None:
                config["t_r"] = args.tr
            result = extract_connectome(
                args.source,
                config=Config(**config),
                progress=print,
                **{k: getattr(args, k) for k in ("atlas", "rois", "confounds", "mask", "reference")},
            )
            print(result.save(args.output, figures=not args.no_figures, report=not args.no_report))
        elif args.command == "batch":
            from .io import discover_bids
            from .pipeline import extract_connectome

            runs = discover_bids(args.bids_dir)
            if not runs:
                raise InputError("No fMRIPrep preprocessed volume runs found.")
            args.output.mkdir(parents=True, exist_ok=False)
            config = Config(**json.loads(args.config.read_text(encoding="utf-8-sig")))
            records = []
            for i, run in enumerate(runs):
                record = {
                    "index": i,
                    "source": run["bold"],
                    "subject": run["subject"],
                    "session": run["session"],
                    "run": run["run"],
                }
                try:
                    result = extract_connectome(
                        run["bold"],
                        atlas=args.atlas,
                        rois=args.rois,
                        confounds=run["confounds"],
                        mask=run["mask"],
                        config=config,
                        progress=print,
                    )
                    destination = args.output / f"run-{i:04d}"
                    result.save(destination)
                    record.update(status="complete", output=str(destination.resolve()))
                except Exception as exc:
                    record.update(status="failed", error=str(exc))
                records.append(record)
                (args.output / "batch.json").write_text(
                    json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            if any(r["status"] == "failed" for r in records):
                raise InputError("Some runs failed. Inspect batch.json; successful results are preserved.")
        elif args.command == "dicom":
            from .preprocessing import dicom_plan, convert_dicom

            plan = dicom_plan(args.source, args.output)
            print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
            if args.run:
                convert_dicom(args.source, args.output)
        else:
            from .preprocessing import fmriprep_plan

            plan = fmriprep_plan(
                args.bids_dir, args.output, args.license, participant=args.participant, space=args.space
            )
            print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
            if args.run:
                plan.run()
        return 0
    except (InputError, FileExistsError, FileNotFoundError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
