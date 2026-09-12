import importlib.util
import json
from pathlib import Path

import pytest

pydicom = pytest.importorskip("pydicom")
FileDataset, FileMetaDataset = pydicom.dataset.FileDataset, pydicom.dataset.FileMetaDataset
ExplicitVRLittleEndian, MRImageStorage = pydicom.uid.ExplicitVRLittleEndian, pydicom.uid.MRImageStorage

spec = importlib.util.spec_from_file_location(
    "uih_review", Path(__file__).parents[1] / "examples" / "reconcile_uih_sidecar.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def case(tmp_path, *, te=23.0, effective=0.315, epi=True):
    source = tmp_path / "dicom"
    source.mkdir()
    fm = FileMetaDataset()
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(str(source / "test.dcm"), {}, file_meta=fm, preamble=b"\0" * 128)
    ds.SOPClassUID = MRImageStorage
    ds.SOPInstanceUID = "1.2.826.0.1.3680043.10.999.1"
    ds.SeriesInstanceUID = "1.2.826.0.1.3680043.10.999.2"
    ds.SeriesNumber = 1
    ds.Manufacturer = "UIH"
    ds.EchoTime = te
    if effective is not None:
        ds.EffectiveEchoTime = effective
    if epi:
        ds.add_new((0x0019, 0x1028), "FD", 28.86002886002886)
    else:
        ds.AcquisitionDuration = 271785.0
    ds.save_as(source / "test.dcm", enforce_file_format=True)
    metadata = {"Manufacturer": "UIH", "SeriesNumber": 1, "EchoTime": effective / 1000 if effective else te / 1000}
    if epi:
        metadata.update(ReconMatrixPE=110, EffectiveEchoSpacing=0.000315, TotalReadoutTime=0.034335)
    else:
        metadata["TotalReadoutTime"] = 271.785
    sidecar = tmp_path / "original.json"
    sidecar.write_text(json.dumps(metadata))
    return source, sidecar, tmp_path / "reviewed.json"


def test_conflicting_echo_spacing_does_not_overwrite_te(tmp_path):
    source, sidecar, output = case(tmp_path)
    original = sidecar.read_bytes()
    dicom_original = (source / "test.dcm").read_bytes()
    report = module.reconcile(source, sidecar, output)
    corrected = json.loads(output.read_text())
    assert corrected["EchoTime"] == 0.023
    assert corrected["EffectiveEchoSpacing"] == 0.000315
    assert corrected["TotalReadoutTime"] == 0.034335
    assert sidecar.read_bytes() == original
    assert (source / "test.dcm").read_bytes() == dicom_original
    assert not report["identity_data_removed"]
    with pytest.raises(FileExistsError):
        module.reconcile(source, sidecar, output)


def test_does_not_guess_an_unrecognized_te_conflict(tmp_path):
    source, sidecar, output = case(tmp_path, effective=12.0)
    with pytest.raises(ValueError, match="Unrecognized"):
        module.reconcile(source, sidecar, output)
    assert not output.exists()


def test_scan_duration_is_not_epi_readout(tmp_path):
    source, sidecar, output = case(tmp_path, te=3.4, effective=None, epi=False)
    module.reconcile(source, sidecar, output)
    corrected = json.loads(output.read_text())
    assert corrected["EchoTime"] == 0.0034
    assert "TotalReadoutTime" not in corrected


def test_rejects_mixed_echo_times_before_writing(tmp_path):
    source, sidecar, output = case(tmp_path)
    ds = pydicom.dcmread(source / "test.dcm")
    ds.EchoTime = 30.0
    ds.save_as(source / "other.dcm", enforce_file_format=True)
    with pytest.raises(ValueError, match="Nonuniform"):
        module.reconcile(source, sidecar, output)
    assert not output.exists()
