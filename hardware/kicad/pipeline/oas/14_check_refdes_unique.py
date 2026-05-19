"""Stage 14: reference designator uniqueness across schematic and PCB.

Catches the class of bug where two components accidentally share a refdes
(e.g. two R1 entries after a copy-paste edit), or where a schematic refdes
has no matching PCB footprint (= netlist not pushed → SMT assembly will be
wrong against the PCB). KiCad ERC catches duplicates within a single sheet,
but cross-sheet + schematic-vs-PCB mismatch falls through the cracks.

Rules enforced:
  1. Each refdes appears AT MOST ONCE in the union of all `.kicad_sch` files.
  2. Each refdes appears AT MOST ONCE in `oas.kicad_pcb`.
  3. Each schematic refdes (excluding power flags / hierarchical labels)
     has a matching PCB footprint.

Power flags (#PWR*, #FLG*, etc.) are pseudo-symbols emitted only in
schematics — they have no physical PCB footprint and are excluded from
rule #3.

Pure-Python, deterministic, regex over .kicad_sch / .kicad_pcb. Fast.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT  # noqa: E402

STAGE_NAME = "check_refdes_unique"

# Matches `(property "Reference" "R1"` etc. — captures the refdes.
REFDES_RE = re.compile(r'\(property "Reference" "([^"]+)"')

# A "real" refdes is a letter prefix + digit suffix (R1, C12, U2, J7).
# Anything else is either:
#   - a lib_symbol template entry (`(property "Reference" "C")` — bare
#     letter, defines the default prefix for that part class), or
#   - a power-flag pseudo-symbol (`#PWR0123`).
# We want only actual placed-component refdes, so strict regex.
REAL_REFDES_RE = re.compile(r"^[A-Z]+\d+$")

# Schematic-only pseudo-symbols (power flags, ground/Vcc indicators).
# Also excluded from rule #3 (no PCB footprint expected).
SCH_ONLY_PREFIXES = ("#PWR", "#FLG", "#SYM", "#GND", "#VCC")


def collect_refdes(path: Path) -> list[str]:
    """Return real placed-component refdes (e.g. R1, C12) from a .kicad_sch or
    .kicad_pcb file. Filters out lib_symbol template entries (bare letter,
    no digit) and power-flag pseudo-symbols (#PWR / #FLG / etc.)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    refs = []
    for r in REFDES_RE.findall(text):
        if r.startswith(SCH_ONLY_PREFIXES):
            continue
        if not REAL_REFDES_RE.match(r):
            # bare-letter template entry from a lib_symbol block, skip
            continue
        refs.append(r)
    return refs


def collect_pcb_refdes_excluding_board_only(path: Path) -> tuple[list[str], list[str]]:
    """Walk PCB footprint blocks. Return (all_refdes, board_only_refdes).

    `board_only` attr = mechanical reference (mounting hole, zip-tie hole,
    daughterboard placeholder). These intentionally have no schematic symbol
    and must be excluded from rule #3 cross-check.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    all_refs: list[str] = []
    board_only_refs: list[str] = []
    needle = '(footprint "'
    i = 0
    n = len(text)
    while True:
        idx = text.find(needle, i)
        if idx == -1:
            break
        depth = 0
        j = idx
        while j < n:
            c = text[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = text[idx:j]
        m_ref = REFDES_RE.search(block)
        if m_ref and REAL_REFDES_RE.match(m_ref.group(1)):
            refdes = m_ref.group(1)
            all_refs.append(refdes)
            if re.search(r"\(attr\s+[^)]*\bboard_only\b", block):
                board_only_refs.append(refdes)
        i = j
    return all_refs, board_only_refs


def find_duplicates(refdes: list[str]) -> list[tuple[str, int]]:
    """Return [(refdes, count)] for any refdes appearing more than once."""
    counter = Counter(refdes)
    return [(r, n) for r, n in sorted(counter.items()) if n > 1]


def main() -> int:
    with Stage(STAGE_NAME) as st:
        # ─── Rule 1: schematic refdes uniqueness (union of all sheets) ───
        sch_paths = sorted(KICAD_ROOT.glob("*.kicad_sch"))
        sch_refdes_per_file: dict[Path, list[str]] = {}
        all_sch_refdes: list[str] = []
        for p in sch_paths:
            refs = collect_refdes(p)
            sch_refdes_per_file[p] = refs
            all_sch_refdes.extend(refs)
        st.info(
            f"schematic: {len(sch_paths)} sheets, "
            f"{len(all_sch_refdes)} refdes (power-flags excluded)"
        )

        sch_dupes = find_duplicates(all_sch_refdes)
        if sch_dupes:
            for r, n in sch_dupes:
                # Locate which sheets contain it
                where = [
                    p.name for p, refs in sch_refdes_per_file.items() if r in refs
                ]
                st.info(f"  DUPLICATE {r}: appears {n}x in {', '.join(where)}")
            st.fail(f"{len(sch_dupes)} duplicate refdes(es) across schematic sheets")
        st.ok(f"all {len(set(all_sch_refdes))} schematic refdes are unique")

        # ─── Rule 2: PCB refdes uniqueness ───
        pcb_path = KICAD_ROOT / "oas.kicad_pcb"
        pcb_refdes, board_only = collect_pcb_refdes_excluding_board_only(pcb_path)
        st.info(
            f"PCB: {len(pcb_refdes)} footprints, {len(board_only)} marked board_only"
        )

        pcb_dupes = find_duplicates(pcb_refdes)
        if pcb_dupes:
            for r, n in pcb_dupes:
                st.info(f"  DUPLICATE {r}: appears {n}x in oas.kicad_pcb")
            st.fail(f"{len(pcb_dupes)} duplicate refdes(es) in oas.kicad_pcb")
        st.ok(f"all {len(set(pcb_refdes))} PCB refdes are unique")

        # ─── Rule 3: every schematic refdes has a PCB counterpart ───
        # board_only footprints (mounting holes, zip-tie holes, daughterboard
        # placeholders) intentionally have no schematic symbol — exclude them
        # from this bidirectional check.
        sch_set = set(all_sch_refdes)
        pcb_set = set(pcb_refdes) - set(board_only)

        sch_without_pcb = sorted(sch_set - pcb_set)
        if sch_without_pcb:
            for r in sch_without_pcb:
                st.info(f"  ORPHAN: {r} in schematic but NOT in PCB")
            st.fail(
                f"{len(sch_without_pcb)} schematic refdes(es) without PCB footprint "
                "— netlist not pushed?"
            )

        pcb_without_sch = sorted(pcb_set - sch_set)
        if pcb_without_sch:
            for r in pcb_without_sch:
                st.info(f"  EXTRA: {r} in PCB but NOT in schematic")
            st.fail(
                f"{len(pcb_without_sch)} PCB refdes(es) without schematic symbol "
                "— stale footprint?"
            )

        st.ok(
            f"schematic <-> PCB refdes sets match "
            f"({len(sch_set)} components; {len(board_only)} board_only excluded)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
