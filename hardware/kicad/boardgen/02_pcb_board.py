"""boardgen stage 02: write oas.kicad_pcb."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from boardgen._common import HERE
from boardgen._pcb import gen_pcb


def run(ctx) -> None:
    pcb_text = gen_pcb()
    (HERE / "oas.kicad_pcb").write_text(pcb_text, encoding="utf-8")
    ctx.pcb_text = pcb_text


if __name__ == "__main__":
    from boardgen._common import Context
    run(Context())
