"""Synthetic, identifier-free DICOM fixtures test geometry, ordering and failure gates."""

import json

import nibabel as nib
import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage, generate_uid
import pytest

from brainfc import InputError, scan_dicom, convert_dicom_python


def mosaic_series(source, n_frames=20):
    source.mkdir()
    study, series = generate_uid(), generate_uid()
    for frame in range(n_frames):
        meta = FileMetaDataset()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        meta.MediaStorageSOPClassUID = MRImageStorage
        meta.MediaStorageSOPInstanceUID = generate_uid()
        d = FileDataset(None, {}, file_meta=meta, preamble=b"\0"*128)
        d.SOPClassUID = MRImageStorage
        d.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
        d.StudyInstanceUID, d.SeriesInstanceUID = study, series
        d.Modality, d.Manufacturer = "MR", "UIH"
        d.SeriesDescription = "fixture BOLD"
        d.PatientName, d.PatientID = "DO_NOT_COPY", "PRIVATE_FIXTURE"
        d.ImageType = ["ORIGINAL", "PRIMARY", "M", "VFRAME"]
        d.Rows, d.Columns = 12, 8
        d.PixelSpacing = [2, 3]
        d.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        d.RepetitionTime, d.EchoTime = 2000, 30
        d.EffectiveEchoTime = .1  # Must not replace the standard 30 ms echo time.
        d.NumberOfTemporalPositions = n_frames
        d.TemporalPositionIdentifier = frame + 1
        d.InstanceNumber = frame + 1
        d.BitsAllocated = d.BitsStored = 16
        d.HighBit, d.PixelRepresentation = 15, 0
        d.SamplesPerPixel, d.PhotometricInterpretation = 1, "MONOCHROME2"
        d.add_new((0x65, 0x10), "LO", "Image Private Header")
        d.add_new((0x65, 0x1050), "IS", 4)
        seq = []
        tiles = np.empty((12, 8), dtype="uint16")
        for k, offset in enumerate([0, .5, 0, .5]):
            item = Dataset()
            item.ImagePositionPatient = [-12, -18, k*4-8]
            item.AcquisitionTime = f"1200{frame*2 + offset:06.3f}"
            seq.append(item)
            row, col = divmod(k, 2)
            tiles[row*6:(row+1)*6, col*4:(col+1)*4] = 100*frame + 10*k + np.arange(24).reshape(6, 4)
        d.add_new((0x65, 0x1051), "SQ", Sequence(seq))
        d.PixelData = tiles.tobytes()
        # Reverse filename ordering to ensure temporal identity controls ordering.
        d.save_as(source / f"file-{n_frames-frame:03d}.dcm", enforce_file_format=True)
    return series


def test_uih_mosaic_pixels_world_coordinates_timing_and_private_metadata(tmp_path):
    source = tmp_path / "input"
    mosaic_series(source)
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    inventory = scan_dicom(source)
    assert len(inventory) == 1 and inventory[0]["candidate"] == "bold"
    assert "DO_NOT_COPY" not in json.dumps(inventory)
    result = convert_dicom_python(source, tmp_path / "converted")
    image = nib.load(result["image"])
    assert image.shape == (4, 6, 4, 20)
    a = image.get_fdata()
    assert a[2, 3, 1, 7] == 700+10+14
    np.testing.assert_allclose(image.affine @ [2, 3, 1, 1], [6, 12, -4, 1])
    meta = json.loads((tmp_path / "converted/image.json").read_text())
    assert meta["SliceTiming"] == [0, .5, 0, .5]
    assert meta["RepetitionTime"] == 2 and meta["EchoTime"] == .03
    assert image.header.get_dim_info()[2] == 2
    assert "DO_NOT_COPY" not in json.dumps(meta) and "PRIVATE_FIXTURE" not in str(image.header)
    assert before == {p.name: p.read_bytes() for p in source.iterdir()}


def test_missing_mosaic_volume_is_rejected_without_output(tmp_path):
    source = tmp_path / "input"
    mosaic_series(source, 21)
    (source / "file-010.dcm").unlink()
    with pytest.raises(InputError, match="temporal positions"):
        convert_dicom_python(source, tmp_path / "converted")
    assert not (tmp_path / "converted").exists()


def test_duplicate_instances_and_changed_slice_geometry_rejected(tmp_path):
    source = tmp_path / "input"
    mosaic_series(source)
    path = next(source.iterdir())
    duplicate = source / "duplicate.dcm"
    duplicate.write_bytes(path.read_bytes())
    with pytest.raises(InputError, match="Duplicate"):
        convert_dicom_python(source, tmp_path / "converted")
    duplicate.unlink()
    d = pydicom.dcmread(path)
    d[(0x65, 0x1051)].value[1].ImagePositionPatient = [80, 90, 100]
    d.save_as(path, enforce_file_format=True)
    with pytest.raises(InputError, match="geometry|regular grid"):
        convert_dicom_python(source, tmp_path / "converted")


def test_conversion_refuses_output_inside_originals(tmp_path):
    source = tmp_path / "input"
    mosaic_series(source)
    with pytest.raises(InputError, match="outside"):
        convert_dicom_python(source, source / "converted")
