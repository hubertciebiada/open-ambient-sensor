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
    oas-bom.csv           Bill of materials (LCSC column placeholder)
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
    """SMT pick-and-place position files. JLCPCB column convention:
        Designator, Val, Package, Mid X, Mid Y, Rotation, Layer
      KiCad's default CSV header is:
        Ref, Val, Package, PosX, PosY, Rot, Side
      JLCPCB's web uploader auto-detects the column meaning, so renaming
      isn't strictly required. We emit one file per side (top + bottom),
      using the same drill-file origin as the gerbers and excluding DNP
      footprints (J2 recovery header, J10 native-USB recovery header)."""
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
        # Count rows (header + N footprints)
        rows = (OUT / fname).read_text(encoding="utf-8").count("\n") - 1
        print(f"  wrote {fname} ({rows} footprints)")


def export_bom(kcli: str) -> None:
    """BOM CSV for SMT assembly. Column layout matches JLCPCB's "Standard
    BOM Template" (which they auto-detect on upload):
        Comment, Designator, Footprint, LCSC, Qty

    LCSC field is left empty — populated manually before fab order. The
    schematic doesn't carry LCSC numbers yet; once first-prototype assembly
    runs, the user will fill in the matched LCSC parts (or rely on JLCPCB's
    smart-matching against value + footprint).

    Grouping: parts with identical Value + Footprint get one row with a
    comma-separated Designator list (the JLCPCB convention)."""
    run([
        kcli, "sch", "export", "bom",
        "--output", str(OUT / "oas-bom.csv"),
        "--fields", "Value,Reference,Footprint,LCSC,${QUANTITY}",
        "--labels", "Comment,Designator,Footprint,LCSC,Qty",
        "--group-by", "Value,Footprint",
        "--sort-field", "Value",
        "--exclude-dnp",
        str(SCH),
    ], hide_output=True)
    rows = (OUT / "oas-bom.csv").read_text(encoding="utf-8").count("\n") - 1
    print(f"  wrote oas-bom.csv ({rows} unique part groups)")


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
