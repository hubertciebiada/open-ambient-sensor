"""boardgen stage 13: apply copper routing + final silk post-process.

Emits tracks + vias + GND pour zones for the chunks in ROUTING_CHUNKS.
Runs AFTER stage 12 because _routing_pad_db() needs every pad to carry
its net assignment.

As the LAST boardgen stage that mutates `oas.kicad_pcb`, it also runs
the silkscreen line-width lift — every sub-0.15 mm silk stroke is raised
to the JLCPCB DFM "Silkscreen line width" floor. Placed here so it
catches footprint-internal silk (stock KiCad libraries emit 0.12 mm
frames) as well as board-level silk in one pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from boardgen._routing import (
    ROUTING_CHUNKS,
    SILK_MIN_STROKE_MM,
    apply_routing_to_pcb,
    _lift_silk_line_widths,
)


def run(ctx) -> None:
    print()
    print("Applying copper routing...")
    n_tracks = apply_routing_to_pcb(chunks=ROUTING_CHUNKS)
    print(f"  {n_tracks} track records emitted (chunks: {', '.join(ROUTING_CHUNKS) or '(none)'}).")

    n_lifted = _lift_silk_line_widths()
    print(f"  {n_lifted} sub-{SILK_MIN_STROKE_MM} mm silk strokes lifted (JLCPCB DFM floor).")


if __name__ == "__main__":
    from boardgen._common import Context
    run(Context())
