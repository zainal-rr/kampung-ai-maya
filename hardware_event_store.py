# W4 compatibility shim — re-exports the relocated module (removed/converted in Wave 5).
from maya_core import hardware_event_store as _m
import sys as _sys
_sys.modules[__name__] = _m
