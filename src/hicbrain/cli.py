"""Compatibility alias; implementation: brainfc.network.cli."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("brainfc.network.cli")
