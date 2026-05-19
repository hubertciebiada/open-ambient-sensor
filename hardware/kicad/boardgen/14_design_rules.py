"""boardgen stage 14: write oas.kicad_dru (JLCPCB custom DRC rules).

`.kicad_dru` lives alongside `.kicad_pcb` and is auto-loaded by KiCad's
DRC engine (kicad-cli pcb drc included). It expresses per-element-type
constraints (track vs via vs pad vs NPTH) that don't fit the basic
schema in `oas.kicad_pro::board.design_settings.rules`.

Source rules adapted from third_party/kicad-jlcpcb-dru. See
`boardgen/_design_rules.py` for the full template + OAS profile choice.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from boardgen._common import HERE
from boardgen._design_rules import gen_kicad_dru


def run(ctx) -> None:
    (HERE / "oas.kicad_dru").write_text(gen_kicad_dru(), encoding="utf-8")


if __name__ == "__main__":
    from boardgen._common import Context
    run(Context())
