import json

import nibabel as nib
import numpy as np
import pandas as pd
import pytest

from brainfc import Config, extract_connectome
from brainfc.demo import create_demo


def test_real_example_is_recomputable_and_brain_only(tmp_path):
    spec = create_demo(tmp_path / 'input', kind='rest01')
    source = pd.read_csv(spec['source'], sep='\t')
    assert source.shape == (150, 100)
    reference = nib.load(spec['reference'])
    assert set(np.unique(np.asarray(reference.dataobj))) == {0, 1}
    for field in ('descrip', 'aux_file', 'intent_name', 'db_name', 'data_type'):
        assert not reference.header[field].tobytes().strip(b'\0')
    assert not reference.header.extensions
    manifest = json.loads((tmp_path / 'input' / 'example.json').read_text())
    assert manifest['synthetic'] is False
    assert manifest['privacy']['raw_dicom_included'] is False
    config = Config(**spec.pop('config'))
    result = extract_connectome(**spec, config=config)
    assert result.connectivity.shape == (100, 100)
    assert len(result.sample_indices) == 145
    np.testing.assert_allclose(result.connectivity, np.corrcoef(result.timeseries.T), atol=1e-12)
    assert np.isfinite(result.connectivity).all()
    assert result.geometry['brain']['positions']
    with pytest.raises(FileExistsError):
        create_demo(tmp_path / 'input', kind='rest01')


def test_bad_demo_kind_does_not_create_output(tmp_path):
    with pytest.raises(ValueError, match='kind'):
        create_demo(tmp_path / 'no-create', kind='unknown')
    assert not (tmp_path / 'no-create').exists()
