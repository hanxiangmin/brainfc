"""Compatibility alias; implementation: brainfc.network.web.limits."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("brainfc.network.web.limits")
