"""An explicit, reproducible fMRI-to-connectome API."""

from .models import Config, Connectome, InputError
from .pipeline import extract_connectome
from .io import inspect_input, discover_bids
from .atlases import fetch_atlas
from .presets import dataset_presets, dataset_preset
from ._version import __version__ as __version__

__all__ = [
    "Config",
    "Connectome",
    "InputError",
    "extract_connectome",
    "inspect_input",
    "discover_bids",
    "fetch_atlas",
    "dataset_presets",
    "dataset_preset",
]
