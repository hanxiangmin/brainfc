"""Command-line entry points for local analysis and the bundled browser UI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import threading
import webbrowser
from .._version import __version__


def main(argv=None):
    """Run legacy hicbrain commands through the integrated BrainFC implementation.

    argv is an argument list or None for sys.argv. Retains inspect/analyze flags
    and port 8765 for serve, which now starts the unified BrainFC app. argparse
    uses SystemExit for help/invalid arguments; analysis failures propagate.
    New scripts should use brainfc network and brainfc serve.
    """
    parser = argparse.ArgumentParser(prog="hicbrain", description="Local brain graph and hypergraph analysis")
    parser.add_argument("--version", action="version", version=f"BrainFC {__version__} (hicbrain compatibility)")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Open the local browser interface")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--workspace", type=Path, default=None)
    serve.add_argument("--no-browser", action="store_true")
    inspect = commands.add_parser("inspect", help="Inspect available numeric variables")
    inspect.add_argument("file", type=Path)
    analyze = commands.add_parser("analyze", help="Analyze a matrix or ROI time series")
    analyze.add_argument("file", type=Path)
    analyze.add_argument("--kind", choices=["auto", "timeseries", "connectivity"], default="auto")
    analyze.add_argument("--matrix-kind", choices=["auto", "correlation", "fisher_z", "covariance"], default="auto")
    analyze.add_argument("--variable")
    analyze.add_argument("--roi-columns", help="Zero-based half-open slice, e.g. 0:116")
    analyze.add_argument("--preset", default="generic")
    analyze.add_argument("--config", type=Path, help="AnalysisConfig JSON")
    analyze.add_argument("--metadata", type=Path, help="ROI IDs/labels/coordinates and metadata JSON")
    analyze.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "serve":
        try:
            import uvicorn
            from brainfc.web.app import create_app
        except ImportError:
            parser.error('Dependencies missing. Install with: pip install brainfc')
        if not 1 <= args.port <= 65535:
            parser.error("port must be between 1 and 65535")
        app = create_app(args.workspace)
        url = f"http://127.0.0.1:{args.port}"
        print(f"BrainFC local interface (hicbrain compatibility): {url}", flush=True)
        if not args.no_browser:
            timer = threading.Timer(1.5, lambda: webbrowser.open(url))
            timer.daemon = True
            timer.start()
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
    elif args.command == "inspect":
        from .io import inspect_file
        print(json.dumps(inspect_file(args.file), ensure_ascii=False, indent=2))
    else:
        from . import AnalysisConfig, analyze, load_data
        from .export import export_result
        config = AnalysisConfig.from_dict(json.loads(args.config.read_text(encoding="utf-8"))) if args.config else None
        meta = json.loads(args.metadata.read_text(encoding="utf-8")) if args.metadata else {}
        dataset = load_data(args.file, kind=args.kind, matrix_kind=args.matrix_kind, variable=args.variable,
            roi_columns=args.roi_columns, preset=args.preset, **meta)
        result = analyze(dataset, config)
        export_result(result, args.output)
        print(str(args.output.resolve()))


if __name__ == "__main__":
    main()
