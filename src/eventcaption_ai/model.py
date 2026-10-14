"""Compatibility path; implementation lives in eventcaption_ai.learning.model."""
import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module("eventcaption_ai.learning.model")
if __name__ == "__main__":
    raise SystemExit(_implementation.main())
sys_module_name = __name__
_sys.modules[sys_module_name] = _implementation
