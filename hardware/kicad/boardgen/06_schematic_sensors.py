"""boardgen stage 06: write sensors.kicad_sch."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from boardgen._common import HERE, sheet_context
from boardgen._postprocess import (
    _build_pcb_ref_to_footprint, _build_lcsc_metadata_map,
    _apply_schematic_footprints, _apply_schematic_lcsc_metadata,
)
from boardgen._sch_sensors import gen_sensors_sch


def run(ctx) -> None:
    if not ctx.pcb_ref_to_fp:
        ctx.pcb_ref_to_fp = _build_pcb_ref_to_footprint()
    if not ctx.lcsc_metadata_map:
        ctx.lcsc_metadata_map = _build_lcsc_metadata_map()
    with sheet_context("sensors"):
        content = gen_sensors_sch()
    content = _apply_schematic_footprints(content, ctx.pcb_ref_to_fp)
    content = _apply_schematic_lcsc_metadata(content, ctx.lcsc_metadata_map)
    (HERE / "sensors.kicad_sch").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    from boardgen._common import Context
    run(Context())
