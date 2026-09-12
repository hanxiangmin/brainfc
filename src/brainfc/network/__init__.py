"""BrainFC graph and native-hypergraph analysis, integrated from Hyper-Brain."""
from .types import AnalysisConfig, AnalysisResult, BrainDataset, ValidationError
from .atlas import AtlasRegistry, AtlasSpec
from .view import ViewConfig

from .._version import __version__ as __version__
from .bridge import from_connectome, load_connectome
from .analysis import analyze
from .io import load_data

__all__ = ["AnalysisConfig", "AnalysisResult", "BrainDataset", "ValidationError",
           "AtlasRegistry", "AtlasSpec", "ViewConfig", "analyze", "load_data",
           "from_connectome", "load_connectome"]
