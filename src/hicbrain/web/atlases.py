"""Compatibility alias; implementation: brainfc.network.web.atlases."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("brainfc.network.web.atlases")
