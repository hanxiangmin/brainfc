"""Prevent an unreviewed patient file or changed sample entering a release."""
from pathlib import Path
import runpy

import pytest


def test_release_rejects_added_and_modified_sample_files():
    root = Path(__file__).resolve().parents[1]
    check = runpy.run_path(str(root / 'scripts/check_release.py'))['check_example']
    sample = root / 'src/brainfc/data/rest01'
    payloads = {p.name: p.read_bytes() for p in sample.iterdir() if p.is_file()}
    check(payloads)
    with pytest.raises(AssertionError, match='file set'):
        check(payloads | {'unreviewed-patient.json': b'{"PatientID":"not-for-release"}'})
    with pytest.raises(AssertionError, match='Unreviewed example content'):
        check(payloads | {'timeseries.json': b'{"PatientID":"not-for-release"}'})
