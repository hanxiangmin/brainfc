"""Review a single UIH DICOM series and write a new corrected JSON sidecar.

Requires pydicom (``pip install pydicom``). No DICOM or source JSON is modified.
This utility corrects two verified conversion signatures; it does not de-identify
pixel data, validate fieldmap units, or perform fMRI preprocessing.
"""

from pathlib import Path
import argparse
import json
import math

import pydicom


def reconcile(source, sidecar, output):
    """Return an audit dict and write a new sidecar for one legacy UIH MR series.

    source: directory containing .dcm files from exactly one SeriesInstanceUID.
    sidecar: matching dcm2niix JSON, including SeriesNumber and Manufacturer.
    output: new JSON filename; its parent must already exist.

    All source headers are checked. Correct EchoTime only if every standard TE
    agrees and conflicting EffectiveEchoTime matches the independently calculated
    effective echo spacing. Remove a non-EPI TotalReadoutTime only if it equals
    the known UIH AcquisitionDuration / 1000 fallback. Ambiguity raises ValueError;
    existing output raises FileExistsError. No identity field values are returned.
    """
    source, sidecar, output = map(Path, (source, sidecar, output))
    if output.exists():
        raise FileExistsError(output)
    paths = sorted(p for p in source.rglob('*') if p.suffix.lower() == '.dcm')
    if not paths:
        raise ValueError('No .dcm files found.')
    headers = [pydicom.dcmread(p, stop_before_pixels=True) for p in paths]
    series_ids = {str(d.get('SeriesInstanceUID', '')) for d in headers}
    if len(series_ids) != 1 or '' in series_ids:
        raise ValueError('Provide exactly one DICOM series.')
    if any(str(d.get('Manufacturer', '')).strip().upper() != 'UIH' for d in headers):
        raise ValueError('This narrowly scoped correction applies only to UIH.')
    if any(str(d.get('SOPClassUID', '')) != '1.2.840.10008.5.1.4.1.1.4' for d in headers):
        raise ValueError('Enhanced or non-MR DICOM requires a separate review.')
    metadata = json.loads(sidecar.read_text(encoding='utf-8'))
    if metadata.get('Manufacturer', '').upper() != 'UIH':
        raise ValueError('Sidecar manufacturer does not match.')
    if any(int(d.SeriesNumber) != int(metadata.get('SeriesNumber', -1)) for d in headers):
        raise ValueError('Sidecar series number does not match.')

    def uniform(key):
        values = [d.get(key) for d in headers]
        if all(v is None for v in values):
            return None
        if any(v is None for v in values):
            raise ValueError(f'Incomplete {key} metadata.')
        numbers = [float(v.value if hasattr(v, 'value') else v) for v in values]
        if not all(math.isfinite(v) and math.isclose(v, numbers[0], rel_tol=1e-6, abs_tol=1e-9)
                   for v in numbers):
            raise ValueError(f'Nonuniform or nonfinite {key}; no automatic correction.')
        return numbers[0]

    changes = []
    te, effective_te = uniform('EchoTime'), uniform('EffectiveEchoTime')
    bandwidth = uniform((0x0019, 0x1028))
    if te is not None and not math.isclose(metadata.get('EchoTime', -1), te / 1000, rel_tol=1e-5):
        pe = metadata.get('ReconMatrixPE', 0)
        ees = 1 / (bandwidth * pe) if bandwidth and pe > 0 else None
        known = (effective_te is not None and ees is not None and te > effective_te > 0
                 and math.isclose(effective_te / 1000, ees, rel_tol=1e-5)
                 and math.isclose(metadata.get('EchoTime', -1), effective_te / 1000, rel_tol=1e-5)
                 and math.isclose(metadata.get('EffectiveEchoSpacing', -1), ees, rel_tol=1e-5))
        if not known:
            raise ValueError('Unrecognized EchoTime conflict; needs independent review.')
        changes.append({'field': 'EchoTime', 'old': metadata['EchoTime'], 'new': te / 1000,
                        'evidence': 'Uniform DICOM (0018,0081); (0018,9082) equals echo spacing'})
        metadata['EchoTime'] = te / 1000
    duration = uniform('AcquisitionDuration')
    if bandwidth is None and duration is not None and 'TotalReadoutTime' in metadata:
        if math.isclose(metadata['TotalReadoutTime'], duration / 1000, rel_tol=1e-5):
            changes.append({'field': 'TotalReadoutTime', 'old': metadata.pop('TotalReadoutTime'),
                            'new': None, 'evidence': 'UIH scan-duration fallback; no EPI bandwidth evidence'})
    with output.open('x', encoding='utf-8') as stream:
        json.dump(metadata, stream, indent=2)
        stream.write('\n')
    return {'source_header_count': len(headers), 'changes': changes,
            'identity_data_removed': False, 'fieldmap_units_verified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('sidecar', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(reconcile(args.source, args.sidecar, args.output), indent=2))
