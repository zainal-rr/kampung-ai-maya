# W4 compatibility shim — re-exports the relocated module (removed/converted in Wave 5).
from maya_documents import office_pptx_text as _m
import sys as _sys
_sys.modules[__name__] = _m
