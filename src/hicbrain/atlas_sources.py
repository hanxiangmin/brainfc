"""Compatibility alias; implementation: brainfc.network.atlas_sources."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("brainfc.network.atlas_sources")
