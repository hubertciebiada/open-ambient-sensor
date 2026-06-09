"""Shared pytest setup for the OAS unit-test suite.

Puts `hardware/kicad/` on sys.path so tests can import the project
modules the same way the pipeline stages do:

    import boardgen._project
    import oas_routes
    from tools import extract_routes

Run from anywhere:  pytest hardware/kicad/tests/
(stage 16 invokes exactly that as part of `build.py`).
"""
from __future__ import annotations

import sys
from pathlib import Path

KICAD_ROOT = Path(__file__).parent.parent
if str(KICAD_ROOT) not in sys.path:
    sys.path.insert(0, str(KICAD_ROOT))
