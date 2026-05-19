"""boardgen stage 12: sync PCB nets from the schematic netlist.

After all source files are written, parse the schematic netlist and
inject (net code "name") clauses into every PCB pad whose footprint
reference + pad number matches a schematic node. Script-driven
equivalent of pcbnew's F8 "Update PCB from Schematic".
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from boardgen._postprocess import sync_pcb_nets_from_schematic


def run(ctx) -> None:
    print()
    print("Syncing PCB nets from schematic netlist...")
    assigned = sync_pcb_nets_from_schematic()
    if assigned:
        print(f"  {assigned} pad net assignments applied.")


if __name__ == "__main__":
    from boardgen._common import Context
    run(Context())
