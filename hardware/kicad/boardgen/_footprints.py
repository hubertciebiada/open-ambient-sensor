"""boardgen/_footprints.py — backward-compat shim.

The 5,092-line monolith was split at v0.40-post-audit-16 into three
layered modules:

  _footprints_custom.py     — project-local `oas:*` mechanical refs
  _footprints_stock.py      — KiCad-stock parse-and-emit wrappers + infra
  _footprints_placement.py  — 3 public orchestrators + gen_cutouts

External consumers (`01_custom_footprints.py`, `_pcb.py`, `_lib_symbols.py`)
import names directly from `boardgen._footprints` — this shim re-exports
the union so the public surface is unchanged. The wildcard `from X import *`
skips `_`-prefixed names; `_read_kicad_lib_symbol` is re-exported
explicitly because `_lib_symbols.py` imports it by name.
"""
from __future__ import annotations

from boardgen._footprints_custom import *      # noqa: F401, F403
from boardgen._footprints_stock import *       # noqa: F401, F403
from boardgen._footprints_placement import *   # noqa: F401, F403
from boardgen._footprints_stock import _read_kicad_lib_symbol  # noqa: F401
