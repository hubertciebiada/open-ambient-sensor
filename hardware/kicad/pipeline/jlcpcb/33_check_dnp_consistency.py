"""Stage 33: DNP attribute consistency across PCB, BOM, and pos.csv.

OAS marks J2 (UART recovery header) and J10 (native-USB recovery header) as
DNP ("Do Not Place") — JLCPCB skips assembly, the user solders the headers
manually if recovery flashing is ever needed. The KiCad attribute carrying
this is `(attr ... dnp exclude_from_bom exclude_from_pos_files)` on the
footprint block.

The three flags must travel TOGETHER and the exports must reflect them:

  PCB.attr.dnp                   ⇔  PCB.attr.exclude_from_bom
                                 ⇔  PCB.attr.exclude_from_pos_files
  PCB.attr.exclude_from_bom      ⇒  refdes NOT in oas-BOM.csv
  PCB.attr.exclude_from_pos_files ⇒ refdes NOT in oas-top-CPL.csv / -bottom-CPL.csv

The class of bug we catch: a developer adds a new DNP part but flips only
one of the three flags, and JLCPCB silently places a part the user didn't
want (or skips one the user expected). The first signal is a wrong board
delivered weeks later — too late.

Runs AFTER vendor export stages (30+31) so it can verify the actual
emitted CSVs in hardware/output/jlcpcb/.

Pure-Python, deterministic, no deps. Parses PCB with a state-machine over
parenthesized blocks (multi-line footprints handled).
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage  # noqa: E402
from _project import (  # noqa: E402
    PCB_PATH,
    JLCPCB_OUTPUT_DIR,
    BOM_OUTPUT_FILE,
    POS_OUTPUT_FILES,
)

STAGE_NAME = "check_dnp_consistency"

REFDES_RE = re.compile(r'\(property "Reference" "([^"]+)"')
ATTR_RE = re.compile(r'\(attr\s+([^)]+)\)')


def parse_pcb_footprints(text: str) -> list[dict]:
    """Walk every `(footprint "Lib:Name" ...)` block and extract refdes + attrs.

    Uses parenthesis depth counting (NOT regex) so multi-line nested blocks
    parse correctly. Each footprint is returned as {refdes, attrs: set[str]}.
    """
    out: list[dict] = []
    needle = '(footprint "'
    i = 0
    n = len(text)
    while True:
        idx = text.find(needle, i)
        if idx == -1:
            break
        # Walk forward through balanced parens
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
        if not m_ref:
            i = j
            continue
        attrs: set[str] = set()
        for m in ATTR_RE.finditer(block):
            for flag in m.group(1).split():
                attrs.add(flag.strip())
        out.append({"refdes": m_ref.group(1), "attrs": attrs})
        i = j
    return out


def load_csv_designators(path: Path, designator_col: int = 0) -> set[str]:
    """Read a CSV, skip header, return the set of values in column 0.

    For pos.csv with header `Designator,Mid X,...` the designator is col 0.
    For oas-BOM.csv with header `Comment,Designator,Footprint,...` the
    designator is col 1 — but multiple designators may be packed into one
    row (e.g. "C10,C11,C12") so we split on comma+whitespace.
    """
    if not path.exists():
        return set()
    out: set[str] = set()
    with path.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if len(row) <= designator_col:
                continue
            cell = row[designator_col].strip()
            for d in re.split(r"[,\s]+", cell):
                d = d.strip()
                if d:
                    out.add(d)
    return out


def main() -> int:
    with Stage(STAGE_NAME) as st:
        # ─── Parse PCB footprints + their attrs ───
        pcb_text = PCB_PATH.read_text(encoding="utf-8", errors="replace")
        footprints = parse_pcb_footprints(pcb_text)
        st.info(f"PCB: parsed {len(footprints)} footprint blocks")

        # board_only = mechanical reference (mounting holes, zip-tie holes,
        # daughterboard placeholders). These legitimately carry
        # exclude_from_bom + exclude_from_pos_files without dnp because they
        # never had a schematic symbol in the first place — they are PCB
        # geometry, not assembled parts. Exclude them from the dnp
        # consistency rules entirely.
        board_only = {fp["refdes"] for fp in footprints if "board_only" in fp["attrs"]}
        assemblable = [fp for fp in footprints if fp["refdes"] not in board_only]

        dnp = {fp["refdes"] for fp in assemblable if "dnp" in fp["attrs"]}
        excl_bom = {fp["refdes"] for fp in assemblable if "exclude_from_bom" in fp["attrs"]}
        excl_pos = {fp["refdes"] for fp in assemblable if "exclude_from_pos_files" in fp["attrs"]}

        st.info(
            f"PCB flags (board_only excluded): "
            f"dnp={len(dnp)}, exclude_from_bom={len(excl_bom)}, "
            f"exclude_from_pos_files={len(excl_pos)}; "
            f"board_only={len(board_only)} mechanical-only excluded"
        )

        # ─── Rule 1: three flags must travel together ───
        dnp_but_not_bom = sorted(dnp - excl_bom)
        if dnp_but_not_bom:
            for r in dnp_but_not_bom:
                st.info(f"  {r}: has dnp but missing exclude_from_bom")
            st.fail(f"{len(dnp_but_not_bom)} part(s) marked dnp but not excluded from BOM")

        dnp_but_not_pos = sorted(dnp - excl_pos)
        if dnp_but_not_pos:
            for r in dnp_but_not_pos:
                st.info(f"  {r}: has dnp but missing exclude_from_pos_files")
            st.fail(f"{len(dnp_but_not_pos)} part(s) marked dnp but not excluded from pos.csv")

        bom_excl_without_dnp = sorted(excl_bom - dnp)
        if bom_excl_without_dnp:
            for r in bom_excl_without_dnp:
                st.info(f"  {r}: has exclude_from_bom but no dnp flag (suspicious)")
            st.fail(
                f"{len(bom_excl_without_dnp)} part(s) excluded from BOM without dnp flag - "
                "intent unclear (real DNP or accidental)"
            )

        pos_excl_without_dnp = sorted(excl_pos - dnp)
        if pos_excl_without_dnp:
            for r in pos_excl_without_dnp:
                st.info(f"  {r}: has exclude_from_pos_files but no dnp flag (suspicious)")
            st.fail(
                f"{len(pos_excl_without_dnp)} part(s) excluded from pos.csv without dnp flag - "
                "intent unclear"
            )

        st.ok(f"PCB DNP flags consistent: {len(dnp)} part(s) carry all three flags together")

        # ─── Rule 2: DNP refdes must NOT appear in emitted BOM ───
        bom_path = JLCPCB_OUTPUT_DIR / BOM_OUTPUT_FILE
        bom_refdes = load_csv_designators(bom_path, designator_col=1)
        leaked_into_bom = sorted(dnp & bom_refdes)
        if leaked_into_bom:
            for r in leaked_into_bom:
                st.info(f"  {r} (DNP) LEAKED into {bom_path.name}")
            st.fail(f"{len(leaked_into_bom)} DNP part(s) appear in emitted BOM")
        st.ok(f"BOM clean: 0 of {len(dnp)} DNP part(s) appear in {bom_path.name}")

        # ─── Rule 3: DNP refdes must NOT appear in emitted pos.csv ───
        for _side, fname in POS_OUTPUT_FILES:
            pos_path = JLCPCB_OUTPUT_DIR / fname
            pos_refdes = load_csv_designators(pos_path, designator_col=0)
            leaked_into_pos = sorted(dnp & pos_refdes)
            if leaked_into_pos:
                for r in leaked_into_pos:
                    st.info(f"  {r} (DNP) LEAKED into {fname}")
                st.fail(f"{len(leaked_into_pos)} DNP part(s) appear in {fname}")
            st.ok(f"{fname} clean: 0 of {len(dnp)} DNP part(s) leaked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
