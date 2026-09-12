"""Run extraction and native network analysis with no external data/downloads."""
import argparse
from pathlib import Path

from brainfc import Config, extract_connectome
from brainfc.demo import create_demo
from brainfc.network import AnalysisConfig
from brainfc.network.export import export_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    spec = create_demo(args.output / "input")
    config = Config(**spec.pop("config"))
    connectome = extract_connectome(**spec, config=config)
    connectome.save(args.output / "connectome", figures=False)
    result = connectome.analyze_network(AnalysisConfig(
        graph_method="density", density=0.15, hypergraph_method="multiscale", hypergraph_ks=[2, 4],
    ))
    export_result(result, args.output / "network.zip")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
