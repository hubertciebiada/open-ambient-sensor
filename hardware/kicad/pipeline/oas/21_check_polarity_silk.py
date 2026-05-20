"""Stage 21: polarity silkscreen guard for orientation-critical parts.

The user-facing concern this stage closes: a polarity-sensitive component
(diode, MOSFET, IC, electrolytic, addressable LED) must carry a polarity /
pin-1 mark on the SILKSCREEN that is DERIVED from the footprint — not a
hand-drawn approximation. Every such part on OAS uses either a verbatim
KiCad stock footprint (whose pad-1 dot / cathode bar / body outline is
copied unchanged and rotates with the placement) or the project-local
`oas:SK6812-SIDE` footprint (whose pin-1 dot is computed from the pad
geometry constants). Both are correct by construction.

This stage is the REGRESSION GUARD for that property: it fails the build
if any designator in `boardgen._project.POLARIZED_DESIGNATORS` loses its
F.SilkS polarity primitive — e.g. if a footprint generator were ever
refactored into a stub that drops the stock silk.

Rules enforced, per polarized designator:
  1. The footprint exists in `oas.kicad_pcb`.
  2. It has a pad named "1" (the polarity reference pad — cathode /
     gate / anode / DIN depending on part class).
  3. It carries at least one F.SilkS graphic primitive (fp_line /
     fp_circle / fp_arc / fp_poly / fp_rect) — the body outline,
     pad-1 dot or cathode bar that marks orientation.

Pure-Python, deterministic, balanced-paren scan over oas.kicad_pcb. Fast.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT  # noqa: E402

STAGE_NAME = "check_polarity_silk"

REFDES_RE = re.compile(r'\(property "Reference" "([^"]+)"')
PAD1_RE = re.compile(r'\(pad\s+"1"\s')

# Footprint graphic primitives that can carry a silkscreen mark.
GRAPHIC_NEEDLES = ("(fp_line", "(fp_circle", "(fp_arc", "(fp_poly", "(fp_rect")


def _balanced_block(text: str, start: int) -> tuple[str, int]:
    """Return (sub-block, end-index) for the balanced `(...)` starting at
    `start` (which must point at an opening paren)."""
    depth = 0
    j = start
    n = len(text)
    while j < n:
        c = text[j]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start:j + 1], j + 1
        j += 1
    return text[start:], n


def _collect_footprint_blocks(text: str) -> dict[str, str]:
    """Map refdes -> footprint S-expression block for every footprint in
    a .kicad_pcb file."""
    blocks: dict[str, str] = {}
    needle = '(footprint "'
    i = 0
    while True:
        idx = text.find(needle, i)
        if idx == -1:
            break
        block, end = _balanced_block(text, idx)
        m = REFDES_RE.search(block)
        if m:
            blocks[m.group(1)] = block
        i = end
    return blocks


def _has_silk_graphic(block: str) -> bool:
    """True if the footprint block contains at least one graphic primitive
    (fp_line / fp_circle / fp_arc / fp_poly / fp_rect) on layer F.SilkS."""
    for needle in GRAPHIC_NEEDLES:
        i = 0
        while True:
            idx = block.find(needle, i)
            if idx == -1:
                break
            sub, end = _balanced_block(block, idx)
            if '(layer "F.SilkS")' in sub:
                return True
            i = end
    return False


def main() -> int:
    with Stage(STAGE_NAME) as st:
        sys.path.insert(0, str(KICAD_ROOT))
        from boardgen._project import POLARIZED_DESIGNATORS  # noqa: E402

        pcb_path = KICAD_ROOT / "oas.kicad_pcb"
        text = pcb_path.read_text(encoding="utf-8", errors="replace")
        blocks = _collect_footprint_blocks(text)
        st.info(
            f"PCB: {len(blocks)} footprints; "
            f"{len(POLARIZED_DESIGNATORS)} polarity-sensitive designators to audit"
        )

        errors: list[str] = []
        for ref in sorted(POLARIZED_DESIGNATORS):
            block = blocks.get(ref)
            if block is None:
                errors.append(f"{ref}: polarized part has no footprint in oas.kicad_pcb")
                continue
            if not PAD1_RE.search(block):
                errors.append(f"{ref}: footprint has no pad \"1\" (polarity reference pad)")
            if not _has_silk_graphic(block):
                errors.append(
                    f"{ref}: footprint carries NO F.SilkS graphic — polarity / "
                    f"pin-1 mark missing"
                )

        if errors:
            for e in errors:
                st.info(f"  {e}")
            st.fail(
                f"{len(errors)} polarity-silk defect(s) — every orientation-critical "
                f"part must keep a derived F.SilkS polarity mark"
            )

        st.ok(
            f"all {len(POLARIZED_DESIGNATORS)} polarized parts carry a pad-1 + "
            f"F.SilkS polarity mark"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
