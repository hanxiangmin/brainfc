"""Install a wheel with dependencies in a fresh venv and exercise its public API.

Uses pip's normal configured index. No source-tree import is allowed in the test.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import venv


SMOKE = r"""
import importlib.metadata as metadata
from pathlib import Path
import json, sys, socket, subprocess, time
from urllib.request import urlopen
import numpy as np
import brainfc
from brainfc import Config, extract_connectome
from brainfc.demo import create_demo
from brainfc.web.app import create_app

prefix = Path(sys.prefix).resolve()
module = Path(brainfc.__file__).resolve()
assert module.is_relative_to(prefix), (module, prefix)
assert brainfc.__version__ == metadata.version('brainfc')
spec = create_demo(Path.cwd() / 'input')
cfg = Config(**spec.pop('config'))
result = extract_connectome(**spec, config=cfg)
assert result.connectivity.shape == (12, 12)
assert result.provenance['version'] == brainfc.__version__
assert np.all(np.diag(result.fisher_z) == 0)
import hicbrain
from brainfc.network import AnalysisConfig, BrainDataset
assert hicbrain.BrainDataset is BrainDataset
network = result.analyze_network(AnalysisConfig(k=2))
assert np.array_equal(network.connectivity, result.connectivity)
assert network.roi_ids == [r['roi_id'] for r in result.rois]
assert network.hypergraph['edges']
assert Path(hicbrain.__file__).resolve().is_relative_to(prefix)
target = result.save('result', figures=False)
assert (target / 'report.html').is_file()
manual = module.parent / 'web/static/reference'
assert (manual / 'api-reference.html').is_file()
assert (manual / 'openapi.json').is_file()
schema = create_app('server').openapi()
assert schema['info']['version'] == brainfc.__version__
with socket.socket() as listener:
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
with open('gui.log', 'w', encoding='utf-8') as log:
    process = subprocess.Popen(
        [sys.executable, '-m', 'brainfc', 'serve', '--port', str(port),
         '--workspace', str(Path.cwd() / 'gui'), '--no-browser'],
        stdout=log, stderr=log,
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                with urlopen(f'http://127.0.0.1:{port}/api/health', timeout=2) as response:
                    health = json.load(response)
                break
            except OSError:
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('Installed GUI failed to start: ' + Path('gui.log').read_text())
                time.sleep(0.2)
        assert health['version'] == brainfc.__version__, health
        with urlopen(f'http://127.0.0.1:{port}/networks/api/v1/health', timeout=5) as response:
            assert json.load(response)['version'] == brainfc.__version__
        with urlopen(f'http://127.0.0.1:{port}/networks/', timeout=5) as response:
            assert 'BrainFC' in response.read().decode('utf-8')
        with urlopen(f'http://127.0.0.1:{port}/reference/', timeout=5) as response:
            assert 'BrainFC' in response.read().decode('utf-8')
    finally:
        # This process belongs exclusively to the fresh wheel test.
        process.terminate()
        process.wait(timeout=10)
print(json.dumps({'version': brainfc.__version__, 'installed_module': str(module), 'matrix_shape': list(result.connectivity.shape), 'retained': len(result.sample_indices), 'manual_bundled': True, 'installed_gui_started': True}))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    args = parser.parse_args()
    wheels = sorted(args.wheel_dir.glob("brainfc-*.whl"), key=lambda p: p.stat().st_mtime)
    if not wheels:
        raise SystemExit("No wheel found.")
    wheel = wheels[-1].resolve()
    # TemporaryDirectory owns only this newly created isolated test directory.
    with tempfile.TemporaryDirectory(prefix="fmri-wheel-check-") as temp:
        root = Path(temp).resolve()
        venv.create(root / "venv", with_pip=True)
        python = root / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        environment = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}}
        subprocess.run(
            [str(python), "-m", "pip", "install", str(wheel)], cwd=root, env=environment, check=True
        )
        subprocess.run([str(python), "-m", "pip", "check"], cwd=root, env=environment, check=True)
        script = root / "smoke.py"
        script.write_text(SMOKE, encoding="utf-8")
        subprocess.run([str(python), str(script)], cwd=root, env=environment, check=True)
        subprocess.run(
            [str(python), "-m", "brainfc", "--version"], cwd=root, env=environment, check=True
        )
        command = python.parent / ("brainfc.exe" if os.name == "nt" else "brainfc")
        subprocess.run([str(command), "--version"], cwd=root, env=environment, check=True)
    print(json.dumps({"wheel": wheel.name, "isolated_install": "passed"}))


if __name__ == "__main__":
    main()
