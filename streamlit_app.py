"""
Streamlit Cloud entry point.
Deploy with main file: streamlit_app.py (at repo root).
"""

import runpy
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if os.path.join(_ROOT, "frontend") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "frontend"))

runpy.run_path(os.path.join(_ROOT, "frontend", "app.py"), run_name="__main__")
