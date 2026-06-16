# W4 CLI wrapper — runs maya_core.demo_evidence as a CLI; safe to delete only if the
# command is migrated to `python -m`. NOT a compatibility shim.
from __future__ import annotations
import runpy
_TARGET = "maya_core.demo_evidence"
import importlib
import sys
if __name__ == "__main__":
    runpy.run_module(_TARGET, run_name="__main__")
else:
    _module = importlib.import_module(_TARGET)
    sys.modules[__name__] = _module
