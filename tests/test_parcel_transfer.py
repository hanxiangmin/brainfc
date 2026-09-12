from copy import deepcopy
import json

import nibabel as nib
import numpy as np
import pytest

from brainfc.imaging import brain_geometry, parcel_geometry
from brainfc.models import InputError
from brainfc.network.web.source_geometry import restore_source_parcels
from brainfc.network.web.storage import Store
from brainfc.pipeline import fingerprint


def atlas():
    data = np.zeros((14, 10, 10), dtype='int16')
    data[1:5, 2:7, 2:7] = 2
    data[8:12, 2:7, 2:7] = 9
    img = nib.Nifti1Image(data, np.diag([-2., 3., 4., 1.]))
    rois = [dict(roi_id='right-custom', label_value=2), dict(roi_id='left-custom', label_value=9)]
    return img, rois


def test_display_parcels_use_label_mapping_and_world_geometry():
    img, rois = atlas()
    before = np.asarray(img.dataobj).copy()
    geometry = brain_geometry(img, space='test-space', rois=rois)
    assert set(geometry['parcels']) == {'right-custom', 'left-custom'}
    for roi in rois:
        mesh = geometry['parcels'][roi['roi_id']]
        xyz = np.array(mesh['positions']).reshape(-1, 3)
        faces = np.array(mesh['indices']).reshape(-1, 3)
        expected = nib.affines.apply_affine(img.affine, np.argwhere(before == roi['label_value']).mean(0))
        np.testing.assert_allclose(xyz.mean(0), expected, atol=.1)
        assert faces.max() < len(xyz) and np.isfinite(xyz).all()
    np.testing.assert_array_equal(before, img.dataobj)
    with pytest.raises(InputError, match='label values'):
        parcel_geometry(img, [dict(roi_id='missing', label_value=3)])
    with pytest.raises(InputError, match='distinct'):
        parcel_geometry(img, [rois[0], rois[0]])
    assert brain_geometry(img)['parcels'] == {}


def setup_link(tmp_path):
    img, rois = atlas()
    path = tmp_path / 'atlas.nii.gz'
    nib.save(img, path)
    source = dict(rois=rois, provenance=dict(inputs=dict(atlas=fingerprint(path)),
                  config=dict(atlas_space='test-space', data_space='test-space')))
    job, upload, result_id = 'a'*32, 'b'*32, 'c'*32
    folder = tmp_path / 'jobs' / job
    (folder / 'result').mkdir(parents=True)
    (folder / 'request.json').write_text(json.dumps(dict(atlas=str(path))))
    (folder / 'result/result.json').write_text(json.dumps(source))
    store = Store(tmp_path / 'networks')
    store.put('uploads', dict(id=upload, brainfc_job=job))
    store.put('results', dict(id=result_id, file_id=upload))
    result = dict(roi_ids=[r['roi_id'] for r in rois], connectivity=[[1, -.2], [-.2, 1]],
                  metadata=dict(brainfc_geometry=dict(space='test-space', parcels={}, brain={}),
                                roi_metadata=rois, brainfc=dict(inputs=dict(atlas=dict(path='untrusted.nii')))))
    return store, result_id, result, folder, path


def test_old_linked_results_restore_without_following_imported_paths_or_changing_matrix(tmp_path):
    store, rid, result, folder, path = setup_link(tmp_path)
    before = (folder / 'result/result.json').read_bytes()
    restored = restore_source_parcels(store, tmp_path, rid, deepcopy(result))
    assert set(restored['metadata']['brainfc_geometry']['parcels']) == set(result['roi_ids'])
    assert restored['connectivity'] == result['connectivity']
    assert (folder / 'result/result.json').read_bytes() == before
    cached = folder / 'network-parcels.json'
    stamp = cached.stat().st_mtime_ns
    assert restore_source_parcels(store, tmp_path, rid, deepcopy(result)) == restored
    assert cached.stat().st_mtime_ns == stamp
    path.write_bytes(b'changed atlas')
    refused = restore_source_parcels(store, tmp_path, rid, deepcopy(result))
    assert not refused['metadata']['brainfc_geometry']['parcels']
    assert '内容改变' in refused['metadata']['parcel_surface_unavailable']


def test_recovery_refuses_changed_order_and_unlinked_results(tmp_path):
    store, rid, result, folder, path = setup_link(tmp_path)
    result['roi_ids'].reverse()
    assert not restore_source_parcels(store, tmp_path, rid, deepcopy(result))['metadata']['brainfc_geometry']['parcels']
    store.put('uploads', dict(id='b'*32))
    restored = restore_source_parcels(store, tmp_path, rid, result)
    assert not restored['metadata']['brainfc_geometry']['parcels']
    assert not (folder / 'network-parcels.json').exists()
