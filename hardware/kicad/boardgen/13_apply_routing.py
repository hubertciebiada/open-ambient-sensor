"""boardgen stage 13: apply copper routing.

Emits tracks + vias + GND pour zones for the chunks in ROUTING_CHUNKS.
Runs AFTER stage 12 because _routing_pad_db() needs every pad to carry
its net assignment.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from boardgen._routing import ROUTING_CHUNKS, apply_routing_to_pcb


def run(ctx) -> None:
    print()
    print("Applying copper routing...")
    n_tracks = apply_routing_to_pcb(chunks=ROUTING_CHUNKS)
    print(f"  {n_tracks} track records emitted (chunks: {', '.join(ROUTING_CHUNKS) or '(none)'}).")


if __name__ == "__main__":
    from boardgen._common import Context
    run(Context())
