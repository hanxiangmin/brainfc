"""Temporal interpolation with an explicit acquisition-time convention."""

import numpy as np
from scipy.fft import rfft, irfft, rfftfreq

from ..models import InputError


def slice_time_correct(data, slice_times, t_r, *, axis=2, reference=0.5):
    """Interpolate each slice to one acquisition time using a padded Fourier shift.

    Parameters
    ----------
    data : array-like, shape (X, Y, Z, T)
        Finite voxel signals in ORIGINAL NIfTI index order, at least four frames.
    slice_times : sequence of float
        Acquisition offsets in seconds, in increasing voxel-index order along
        axis. Repeated offsets are supported (multiband). Reverse BIDS negative
        SliceEncodingDirection timing lists before calling this function.
    t_r : float
        Constant positive repetition time in seconds. Variable-TR/sparse timing
        is not supported. Every slice offset must be in [0, t_r).
    axis : int, default 2
        Spatial slice dimension, 0, 1 or 2; never the time dimension.
    reference : float, default 0.5
        Target offset as a fraction of TR, in [0, 1). Does not select a slice.

    Returns
    -------
    numpy.ndarray
        New float32 array of the same shape. Reflect-pad by T samples at each
        endpoint, apply exp(+2*pi*i*f*(reference*TR-offset)/TR), then crop.
        Positive shift evaluates a later time in the observed slice series.

    Notes
    -----
    Endpoint extrapolation is defined by reflection. This implementation is not
    an exact reproduction of SPM's interpolation/boundary rules. No frame is
    discarded. BIDS timing is in seconds, not SPM's millisecond time vector.
    """
    x = np.asarray(data, dtype=np.float32)
    times = np.asarray(slice_times, dtype=float)
    if x.ndim != 4 or x.shape[-1] < 4 or not np.isfinite(x).all():
        raise InputError("Slice timing requires finite 4D data with at least four frames.")
    if isinstance(axis, bool) or axis not in (0, 1, 2):
        raise InputError("Slice axis must be 0, 1 or 2.")
    if not np.isfinite(t_r) or t_r <= 0 or not np.isfinite(reference) or not 0 <= reference < 1:
        raise InputError("TR must be positive; slice reference must be in [0, 1).")
    if times.shape != (x.shape[axis],) or not np.isfinite(times).all() or np.any((times < 0) | (times >= t_r)):
        raise InputError("SliceTiming length must match the slice axis, with times in [0, TR) seconds.")
    out = np.empty_like(x)
    n = x.shape[-1]
    for i, time in enumerate(times):
        index = [slice(None)] * 4
        index[axis] = i
        index = tuple(index)
        shift = reference - time / t_r
        if abs(shift) < 1e-12:
            out[index] = x[index]
            continue
        slab = np.pad(x[index], [(0, 0), (0, 0), (n, n)], mode="reflect")
        phase = np.exp(2j * np.pi * rfftfreq(slab.shape[-1]) * shift)
        out[index] = irfft(rfft(slab, axis=-1) * phase, n=slab.shape[-1], axis=-1)[..., n:2*n]
    return out
