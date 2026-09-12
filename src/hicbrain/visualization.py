"""Compatibility alias; implementation: brainfc.network.visualization."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("brainfc.network.visualization")
