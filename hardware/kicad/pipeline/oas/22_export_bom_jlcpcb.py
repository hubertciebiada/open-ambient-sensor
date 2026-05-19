"""Stage 22: BOM CSV in JLCPCB Standard Template format.

JLCPCB auto-detects this exact column layout on upload:

    Comment, Designator, Footprint, Manufacturer, MPN, LCSC Part #,
    JLCPCB_Library, Qty

Two-pass workflow:

  1. kicad-cli emits a 7-column CSV (Value/Reference/Footprint/Manufacturer/
     MPN/LCSC/Qty) — LCSC blank because the schematic doesn't carry LCSC
     numbers. Grouping: parts with identical (Value, Footprint) get one
     row with a comma-separated Designator list.
  2. Post-process: read the LCSC mapping CSV (project-specific, human-
     curated after researching JLCPCB Parts Library), and rewrite the BOM:
       * SMD parts get LCSC filled via (Value, Footprint) lookup and
         JLCPCB_Library set to the mapping's library tier.
       * THT-only references (per _project.THT_REFERENCES) get blank
         LCSC and JLCPCB_Library = "THT (hand-solder)".
       * Unknown (Value, Footprint) combos are a HARD ERROR so missing
         coverage gets caught before submitting the JLCPCB quote.

Range expansion: KiCad emits `C10-C17` notation for groups of consecutive
designators. JLCPCB CPL cross-check does NOT understand ranges — it
compares BOM designators against CPL designators (always individual) and
reports `"C10-C17 designators don't exist in the CPL file"`. We expand
to `C10,C11,...,C17` here.

Footprint stripping: KiCad emits `Capacitor_SMD:C_0805` (library:name).
JLCPCB wants the bare `C_0805` — strip the library prefix.

This stage is project-specific (OAS) because the LCSC mapping CSV schema
and THT_REFERENCES set are bound to this project's BOM conventions.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, run, find_kicad_cli, KICAD_ROOT  # noqa: E402
from _project import (  # noqa: E402
    SCH_PATH,
    GERBER_OUTPUT_DIR,
    BOM_OUTPUT_FILE,
    THT_REFERENCES,
)

# Import the canonical Python dict (hardware/kicad/lcsc_mapping.py).
sys.path.insert(0, str(KICAD_ROOT))
from lcsc_mapping import LCSC_MAPPING  # noqa: E402

STAGE_NAME = "export_bom_jlcpcb"


def load_lcsc_mapping() -> dict[tuple[str, str], tuple[str, str]]:
    """Return (Value, Footprint) -> (LCSC, JLCPCB_Library) from the
    canonical Python dict in hardware/kicad/lcsc_mapping.py."""
    return {
        key: (entry["lcsc"], entry["library"])
        for key, entry in LCSC_MAPPING.items()
    }


def expand_designator_ranges(s: str) -> str:
    """Expand `C10-C17` -> `C10,C11,...,C17`. Tokens that don't match
    `PREFIX<a>-<b>` pattern pass through verbatim."""
    out = []
    for tok in s.split(","):
        tok = tok.strip()
        m = re.match(r"^([A-Za-z]+)([0-9]+)-([A-Za-z]*)([0-9]+)$", tok)
        if m:
            prefix, a, prefix2, b = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
            # Mismatched prefixes (e.g. "C10-D17") are not a real range — pass through.
            if prefix2 and prefix2 != prefix:
                out.append(tok)
                continue
            for i in range(a, b + 1):
                out.append(f"{prefix}{i}")
        else:
            out.append(tok)
    return ",".join(out)


def strip_designator_index(designator: str) -> str:
    """Returns the full designator unchanged. The indirection exists so
    a future caller could apply prefix-only matching (e.g. 'C20' -> 'C')
    if THT_REFERENCES ever uses prefix tokens."""
    return designator


def postprocess_bom_with_lcsc_mapping(bom_path: Path, st: Stage) -> None:
    """Rewrite bom_path in place — fill LCSC, add JLCPCB_Library column."""
    mapping = load_lcsc_mapping()
    raw_rows = list(csv.DictReader(bom_path.open(encoding="utf-8", newline="")))

    out_rows: list[dict[str, str]] = []
    errors: list[str] = []
    smd_basic = 0
    smd_extended = 0
    smd_other = 0
    tht_rows = 0

    for row in raw_rows:
        value = row.get("Comment", "").strip()
        footprint = row.get("Footprint", "").strip()
        designators = [d.strip() for d in row.get("Designator", "").split(",") if d.strip()]

        is_tht = bool(designators) and all(
            strip_designator_index(d) in THT_REFERENCES for d in designators
        )

        if is_tht:
            lcsc = ""
            lib = "THT (hand-solder)"
            tht_rows += 1
        else:
            key = (value, footprint)
            if key not in mapping:
                errors.append(
                    f"  unmapped SMD row: Value={value!r} Footprint={footprint!r} "
                    f"Designators={designators}"
                )
                continue
            lcsc, lib = mapping[key]
            if lib == "Basic":
                smd_basic += 1
            elif lib == "Extended":
                smd_extended += 1
            else:
                smd_other += 1

        designator_expanded = expand_designator_ranges(row.get("Designator", ""))
        footprint_bare = footprint.split(":", 1)[-1]

        out_rows.append({
            "Comment": value,
            "Designator": designator_expanded,
            "Footprint": footprint_bare,
            "Manufacturer": row.get("Manufacturer", ""),
            "MPN": row.get("MPN", ""),
            "LCSC Part #": lcsc,
            "JLCPCB_Library": lib,
            "Qty": row.get("Qty", ""),
        })

    if errors:
        for e in errors:
            print(e)
        st.fail(
            f"BOM contains {len(errors)} row(s) not in lcsc_mapping.py; "
            "update mapping to cover every SMD (Value, Footprint)"
        )

    fieldnames = ["Comment", "Designator", "Footprint",
                  "Manufacturer", "MPN", "LCSC Part #", "JLCPCB_Library", "Qty"]
    with bom_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    total_smd = smd_basic + smd_extended + smd_other
    st.ok(
        f"post-processed {bom_path.name}: {smd_basic} Basic + {smd_extended} Extended"
        f" + {smd_other} other SMD + {tht_rows} THT rows (total {total_smd + tht_rows})"
    )
    if smd_extended:
        # JLCPCB charges a one-time $3 setup fee per unique Extended part.
        st.info(
            f"JLCPCB Extended setup estimate: {smd_extended} x $3 = "
            f"${smd_extended * 3} one-time fee for this build"
        )


def main() -> int:
    with Stage(STAGE_NAME) as st:
        kcli = find_kicad_cli()
        GERBER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        bom_path = GERBER_OUTPUT_DIR / BOM_OUTPUT_FILE

        st.info(f"kicad-cli sch export bom -> {bom_path.name}")
        run([
            kcli, "sch", "export", "bom",
            "--output", str(bom_path),
            "--fields", "Value,Reference,Footprint,Manufacturer,MPN,LCSC,${QUANTITY}",
            "--labels", "Comment,Designator,Footprint,Manufacturer,MPN,LCSC,Qty",
            "--group-by", "Value,Footprint",
            "--sort-field", "Value",
            "--exclude-dnp",
            str(SCH_PATH),
        ], hide_output=True)
        raw_rows = bom_path.read_text(encoding="utf-8").count("\n") - 1
        st.info(f"raw kicad-cli BOM: {raw_rows} unique (Value, Footprint) groups")

        postprocess_bom_with_lcsc_mapping(bom_path, st)
    return 0


if __name__ == "__main__":
    sys.exit(main())
