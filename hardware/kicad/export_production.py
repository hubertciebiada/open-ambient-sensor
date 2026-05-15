"""
OAS — production deliverables export.

Generates everything needed to send the board to JLCPCB (or any reasonable
EU/US fab) for bare-board production + SMT assembly:

  gerbers/
    oas-F_Cu.gtl          Top copper            (Protel ext)
    oas-B_Cu.gbl          Bottom copper
    oas-F_Mask.gts        Top solder mask
    oas-B_Mask.gbs        Bottom solder mask
    oas-F_Silkscreen.gto  Top silkscreen
    oas-B_Silkscreen.gbo  Bottom silkscreen
    oas-F_Paste.gtp       Top solder paste      (SMT stencil)
    oas-B_Paste.gbp       Bottom solder paste
    oas-Edge_Cuts.gm1     Board outline
    oas-PTH.drl           Plated through-holes  (Excellon, mm, decimal)
    oas-NPTH.drl          Non-plated holes      (mounting + zip-tie)
    oas-drill_map.pdf     Drill map for human review
    oas-top-pos.csv       SMT placement file (top side)
    oas-bottom-pos.csv    SMT placement file (bottom side — empty for OAS)
    oas-bom.csv           Bill of materials, post-processed against
                          ../bom/lcsc-mapping.csv — LCSC column filled in
                          for every SMD part, JLCPCB_Library column added
                          (Basic / Extended / THT hand-solder) for the
                          user's visibility before quote submission.
    oas-jlcpcb.zip        Bundle for JLCPCB web uploader

This script is OUT of the regenerate.py inner loop on purpose. Production
export should run only when the board is actually being sent to fab —
running it on every geometry iteration wastes CPU.

Usage:  python export_production.py

Prerequisites: same as regenerate.py — KiCad 10.0 installed, kicad-cli on
the standard Windows path, sources up-to-date (run regenerate.py first if
you've edited generate.py since the last export).
"""
from __future__ import annotations

import csv
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
PCB = HERE / "oas.kicad_pcb"
SCH = HERE / "oas.kicad_sch"
OUT = HERE.parent / "gerbers"   # hardware/gerbers/
LCSC_MAPPING = HERE.parent / "bom" / "lcsc-mapping.csv"  # source-of-truth

# Through-hole-only references that must NOT carry an LCSC number — the
# user hand-solders these because they are mechanical assemblies (terminal
# block, pin sockets) or oversized radial capacitors that JLCPCB cannot
# place on the SMT line. THT items still appear in the BOM as a
# completeness check but with JLCPCB_Library = "THT (hand-solder)" and
# LCSC blank.
#
# Designators sourced from oas-bom.csv at v0.34: J1 (Phoenix terminal),
# J4 (LD2410 1.27 mm THT pin header), J5/J6 (ESP32 socket rows), J7/J8
# (MIKROE-2462 socket rows), C1/C3 (D8 radial bulk), C4 (D6.3 radial bulk).
THT_REFERENCES = {"J1", "J4", "J5", "J6", "J7", "J8", "C1", "C3", "C4"}

KICAD_CLI_CANDIDATES = [
    r"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe",
    r"C:/Program Files/KiCad/9.0/bin/kicad-cli.exe",
    "kicad-cli",
]

# Production layers for fab (JLCPCB standard 2-layer board):
#   - copper, mask, silkscreen on both sides
#   - paste on both sides (SMT stencil)
#   - Edge.Cuts for board outline
# NOT included: F.Fab / B.Fab / F.CrtYd / B.CrtYd / Dwgs.User — these are
# internal documentation layers, not part of the fab deliverable.
FAB_LAYERS = (
    "F.Cu,B.Cu,"
    "F.Mask,B.Mask,"
    "F.Silkscreen,B.Silkscreen,"
    "F.Paste,B.Paste,"
    "Edge.Cuts"
)


def find_kicad_cli() -> str:
    for c in KICAD_CLI_CANDIDATES:
        if Path(c).exists() or shutil.which(c):
            return c
    sys.exit("ERROR: kicad-cli not found. Install KiCad 10 or add it to PATH.")


def step(title: str) -> None:
    print(f"\n=== {title} ===")


def run(cmd: list[str], *, hide_output: bool = False) -> None:
    if hide_output:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr, file=sys.stderr)
            sys.exit(f"command failed: {' '.join(cmd)}")
    else:
        subprocess.run(cmd, check=True)


def clean_output_dir() -> None:
    """Wipe gerbers/ before regenerating. Stale files from a previous run
    (e.g. an old PCB revision's gerbers) would otherwise sneak into the
    JLCPCB zip alongside the new ones. Preserves dotfiles (.gitkeep,
    .gitignore) so the directory itself stays tracked in git."""
    if OUT.exists():
        for child in OUT.iterdir():
            if child.name.startswith("."):
                continue
            if child.is_file():
                child.unlink()
            else:
                shutil.rmtree(child)
    else:
        OUT.mkdir(parents=True)


def export_gerbers(kcli: str) -> None:
    """Plot fab gerbers. Settings tuned for JLCPCB standard 2-layer process:
      - Protel extensions (.gtl/.gbl/...) — JLCPCB accepts both Protel and
        KiCad-default (.gbr) but Protel is the historical fab convention.
      - X2 format enabled (KiCad default) — modern fabs prefer it.
      - --check-zones forces a zone refill before plotting so the GND pour
        appears as solid copper in the deliverable (matches the rendered
        SVG previews from regenerate.py).
      - --subtract-soldermask: keeps silkscreen text from landing on top of
        pads' exposed copper (where the mask opening exists). Standard
        practice for cleaner production silk.
      - --use-drill-file-origin: aligns gerber coordinates with the drill
        file origin. Since we don't set an aux origin, this is the same as
        the absolute origin (KiCad page corner), so all 4 outputs (gerbers,
        drill, pos, BOM) share one coordinate frame."""
    run([
        kcli, "pcb", "export", "gerbers",
        "--output", str(OUT) + "/",
        "--layers", FAB_LAYERS,
        "--subtract-soldermask",
        "--check-zones",
        "--use-drill-file-origin",
        str(PCB),
    ], hide_output=True)
    print(f"  wrote {len(list(OUT.glob('*.g*')))} gerber files")


def export_drill(kcli: str) -> None:
    """Drill files in Excellon format, mm units, decimal zeros.
      - --excellon-separate-th: separates PTH (component holes) from NPTH
        (mounting holes + zip-tie holes). JLCPCB accepts merged drill files
        too, but separating is more explicit and matches their own preferred
        upload convention.
      - --generate-map: produces a PDF drill map for human review (which
        hole is which size, with reference designators). Not part of the
        JLCPCB zip, but useful for sanity-checking before upload."""
    run([
        kcli, "pcb", "export", "drill",
        "--output", str(OUT) + "/",
        "--format", "excellon",
        "--excellon-units", "mm",
        "--excellon-zeros-format", "decimal",
        "--excellon-separate-th",
        "--generate-map",
        "--map-format", "pdf",
        "--drill-origin", "absolute",
        str(PCB),
    ], hide_output=True)
    print(f"  wrote {len(list(OUT.glob('*.drl')))} drill files + map")


def export_position(kcli: str) -> None:
    """SMT pick-and-place position files in JLCPCB upload-ready format.

    JLCPCB CPL upload REQUIRES these exact column names (per the 2026-05-15
    first-order learning the hard way — "Failed processing the CPL file"
    error):
        Designator, Mid X, Mid Y, Layer, Rotation
    KiCad's default CSV header is `Ref, Val, Package, PosX, PosY, Rot, Side`
    and JLCPCB does NOT auto-detect that — the comment claiming so in
    pre-v0.40 post-order versions of this file was wrong. We post-process the CSV
    after kicad-cli emits it: rename columns, capitalize 'Top'/'Bottom',
    keep 4-decimal precision (more is rejected, less is fine), drop the
    Val/Package columns (JLCPCB ignores them).

    Excludes DNP footprints (J2 recovery header, J10 native-USB recovery)
    and uses the drill-file origin so the CPL coordinate frame matches
    the gerbers."""
    for side, fname in (("front", "oas-top-pos.csv"),
                        ("back",  "oas-bottom-pos.csv")):
        run([
            kcli, "pcb", "export", "pos",
            "--output", str(OUT / fname),
            "--side", side,
            "--format", "csv",
            "--units", "mm",
            "--use-drill-file-origin",
            "--smd-only",
            "--exclude-dnp",
            str(PCB),
        ], hide_output=True)
        _postprocess_cpl_for_jlcpcb(OUT / fname)
        rows = (OUT / fname).read_text(encoding="utf-8").count("\n") - 1
        print(f"  wrote {fname} ({rows} footprints, JLCPCB-format)")


def _postprocess_cpl_for_jlcpcb(path: Path) -> None:
    """Rewrite a kicad-cli CPL output in place to JLCPCB upload format.

    Input header (kicad-cli):   Ref,Val,Package,PosX,PosY,Rot,Side
    Output header (JLCPCB):     Designator,Mid X,Mid Y,Layer,Rotation
    """
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return
    # First row is header; rest are data. KiCad header is in fixed order.
    out = [["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]]
    for row in rows[1:]:
        if not row:
            continue
        ref, _val, _pkg, x, y, rot, side = row
        x_fmt = f"{float(x):.4f}"
        y_fmt = f"{float(y):.4f}"
        rot_f = float(rot)
        rot_fmt = str(int(rot_f)) if rot_f == int(rot_f) else f"{rot_f:g}"
        layer = "Top" if side.lower().startswith("top") else "Bottom"
        out.append([ref, x_fmt, y_fmt, layer, rot_fmt])
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(out)


def export_bom(kcli: str) -> None:
    """BOM CSV for SMT assembly. Column layout matches JLCPCB's "Standard
    BOM Template" (which they auto-detect on upload):
        Comment, Designator, Footprint, LCSC, JLCPCB_Library, Qty

    Two-pass workflow:
      1. kicad-cli emits a 5-column CSV (Value, Reference, Footprint, LCSC,
         Qty) — LCSC blank because the schematic doesn't carry LCSC
         numbers. Grouping: parts with identical Value + Footprint get one
         row with a comma-separated Designator list.
      2. _postprocess_bom_with_lcsc_mapping() reads the mapping file at
         hardware/bom/lcsc-mapping.csv (the source-of-truth, human-curated
         after researching JLCPCB Parts Library), and rewrites the BOM:
           * SMD parts get LCSC filled in via (Value, Footprint) lookup
             and JLCPCB_Library set to the mapping's library tier.
           * THT-only references (J1 terminal block, J4-J8 pin headers and
             sockets, C1/C3/C4 radial bulk caps) get LCSC blank and
             JLCPCB_Library = "THT (hand-solder)". The user hand-solders
             these after the SMT line.
           * Unknown (Value, Footprint) combos that aren't in the mapping
             produce an explicit error so the user catches missing
             coverage before submitting the order.
    """
    # v0.38: include Manufacturer + MPN as native BOM columns. These come
    # from schematic symbol properties injected by generate.py's
    # `_apply_schematic_lcsc_metadata` post-process (closes audit-16
    # "projekt sobie, BOM sobie" — full sourcing metadata now lives on
    # the schematic, kicad-cli emits it directly into the BOM CSV).
    run([
        kcli, "sch", "export", "bom",
        "--output", str(OUT / "oas-bom.csv"),
        "--fields", "Value,Reference,Footprint,Manufacturer,MPN,LCSC,${QUANTITY}",
        "--labels", "Comment,Designator,Footprint,Manufacturer,MPN,LCSC,Qty",
        "--group-by", "Value,Footprint",
        "--sort-field", "Value",
        "--exclude-dnp",
        str(SCH),
    ], hide_output=True)
    rows = (OUT / "oas-bom.csv").read_text(encoding="utf-8").count("\n") - 1
    print(f"  wrote oas-bom.csv (raw, {rows} unique part groups)")

    _postprocess_bom_with_lcsc_mapping()


def _load_lcsc_mapping() -> dict[tuple[str, str], tuple[str, str]]:
    """Read hardware/bom/lcsc-mapping.csv and return a lookup:
        (Value, Footprint) -> (LCSC, JLCPCB_Library)

    The mapping CSV is the source-of-truth for which LCSC SKU to use for
    each (Value, Footprint) pair on the OAS PCB. Maintained by hand after
    researching JLCPCB Parts Library availability — see hardware/bom/
    lcsc-mapping.csv for the full notes per part (substitution rationale,
    stock risks, BOM library tier). The columns relevant here are Value,
    Footprint, LCSC, and JLCPCB_Library; the rest is human documentation.
    """
    if not LCSC_MAPPING.exists():
        sys.exit(
            f"ERROR: LCSC mapping file missing at {LCSC_MAPPING}. "
            "Cannot post-process BOM."
        )
    mapping: dict[tuple[str, str], tuple[str, str]] = {}
    with LCSC_MAPPING.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["Value"].strip(), row["Footprint"].strip())
            lcsc = row["LCSC"].strip()
            lib = row["JLCPCB_Library"].strip()
            mapping[key] = (lcsc, lib)
    return mapping


def _expand_designator_ranges(s: str) -> str:
    """Expand range notation `C10-C17` -> `C10,C11,...,C17`.

    JLCPCB BOM upload does NOT understand range notation — it cross-checks
    BOM designators against CPL designators (which are always individual),
    and a row like `100nF | C10-C17 | C_0603 | C14663 | 9` produces a
    `"C10-C17 designators don't exist in the CPL file"` error.

    Tokens that don't match the `PREFIX<a>-<b>` pattern pass through
    verbatim (single designators, weird names, etc.).
    """
    import re
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


def _postprocess_bom_with_lcsc_mapping() -> None:
    """Rewrite oas-bom.csv in place — fill LCSC, add JLCPCB_Library column.

    Detects THT-only rows by checking whether ALL designators in the
    Designator field belong to THT_REFERENCES. SMD rows must match the
    LCSC mapping; an unmatched SMD (Value, Footprint) is a HARD ERROR
    so the user notices missing mapping coverage before submitting the
    JLCPCB quote."""
    mapping = _load_lcsc_mapping()
    bom_path = OUT / "oas-bom.csv"
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

        is_tht = bool(designators) and all(_strip_designator_index(d) in THT_REFERENCES
                                            for d in designators)

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

        # v0.40 post-order JLCPCB-upload-ready format: expand range notation in
        # Designator (`C10-C17` -> `C10,C11,...,C17`) — JLCPCB does NOT
        # accept ranges and the BOM↔CPL cross-check fails otherwise.
        # Also strip library prefix from Footprint (`Capacitor_SMD:C_0805`
        # -> `C_0805`) — JLCPCB only wants the bare footprint name.
        designator_expanded = _expand_designator_ranges(
            row.get("Designator", "")
        )
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
        print("\nERROR: BOM contains rows not in hardware/bom/lcsc-mapping.csv:")
        for e in errors:
            print(e)
        sys.exit(
            "Update lcsc-mapping.csv to cover every SMD (Value, Footprint) "
            "in the BOM, then re-run export_production.py."
        )

    fieldnames = ["Comment", "Designator", "Footprint",
                  "Manufacturer", "MPN", "LCSC Part #", "JLCPCB_Library", "Qty"]
    with bom_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    total = smd_basic + smd_extended + smd_other
    print(
        f"  post-processed oas-bom.csv: "
        f"{smd_basic} Basic + {smd_extended} Extended + {smd_other} other SMD "
        f"+ {tht_rows} THT rows (total {total + tht_rows})"
    )
    if smd_extended:
        # JLCPCB charges a one-time $3 setup fee per unique Extended part
        # (per assembly job, NOT per board). For a 5-prototype run the
        # setup fee dominates the per-board cost.
        print(
            f"  JLCPCB Extended setup estimate: {smd_extended} × $3 = "
            f"${smd_extended * 3} one-time fee for this build."
        )


def _strip_designator_index(designator: str) -> str:
    """Map e.g. 'C20' -> 'C', 'J5' -> 'J', 'D11' -> 'D'. Used so we can
    test designator-prefix membership in THT_REFERENCES which uses
    full refs like 'J1' / 'J5' / 'C1' / 'C3' / 'C4'. Since this function's
    callers compare against full references (not prefixes), we return the
    full designator unchanged; the indirection exists purely so future
    extension can apply prefix-stripping if needed."""
    return designator


def bundle_jlcpcb_zip() -> None:
    """Pack the fab deliverables into a single zip for JLCPCB upload.
    Includes: all gerbers (*.g*), both drill files (*.drl). Excludes:
    drill map PDF (human-only), pos/BOM (separate upload to JLCPCB SMT
    quoting page)."""
    zip_path = OUT / "oas-jlcpcb.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for pattern in ("*.gtl", "*.gbl", "*.gts", "*.gbs", "*.gto", "*.gbo",
                        "*.gtp", "*.gbp", "*.gm1", "*.drl"):
            for f in sorted(OUT.glob(pattern)):
                zf.write(f, arcname=f.name)
    bundled = len(zipfile.ZipFile(zip_path).namelist())
    size_kb = zip_path.stat().st_size / 1024
    print(f"  wrote oas-jlcpcb.zip ({bundled} files, {size_kb:.1f} kB)")


def main() -> None:
    t0 = time.time()
    kcli = find_kicad_cli()

    # Bail out if source files don't exist yet — production export only
    # makes sense after generate.py has run.
    if not PCB.exists() or not SCH.exists():
        sys.exit(
            "ERROR: KiCad source files missing. Run regenerate.py first to "
            "generate oas.kicad_pcb / oas.kicad_sch."
        )

    step("1/5  Clean output directory")
    clean_output_dir()
    print(f"  cleaned {OUT}/")

    step("2/5  Export gerbers")
    export_gerbers(kcli)

    step("3/5  Export drill files + map")
    export_drill(kcli)

    step("4/5  Export pick-and-place position files")
    export_position(kcli)

    step("5/5  Export BOM + bundle JLCPCB zip")
    export_bom(kcli)
    bundle_jlcpcb_zip()

    print(f"\nDone in {time.time()-t0:.1f} s. Outputs in {OUT.relative_to(HERE.parent)}/")
    print("\nReady for JLCPCB upload:")
    print(f"  - Bare board:   upload {OUT.relative_to(HERE.parent)}/oas-jlcpcb.zip")
    print(f"  - SMT assembly: also upload oas-top-pos.csv + oas-bom.csv")
    print(f"  - Drill review: open {OUT.relative_to(HERE.parent)}/oas-drill_map.pdf")


if __name__ == "__main__":
    main()
