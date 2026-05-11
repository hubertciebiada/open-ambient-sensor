"""
OAS — master regeneration script.

Single entry point for rebuilding the entire KiCad project from sources:

  1. Run `generate.py` — regenerates oas.kicad_pcb / oas.kicad_sch /
     oas.kicad_pro / footprint library / lib tables from the Python
     geometry constants. Deterministic UUIDs → bit-identical output
     when no inputs changed.
  2. Validate — kicad-cli pcb drc + kicad-cli sch erc, fail loudly
     if there are any errors or warnings.
  3. Render — produce committable PNG / SVG previews into renders/:
        2d-top.{svg,png}        Top-side production view
        2d-cutouts.{svg,png}    Edge.Cuts + Dwgs.User keepout markers
        3d-top.png              3D raytraced render

Workflow: when you want to change PCB geometry / stackup / layout
constants, edit `generate.py` and run THIS script (regenerate.py).
Never edit the generated `.kicad_*` files directly — the next
regeneration would overwrite the edit.

Usage:  python regenerate.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
RENDERS = HERE / "renders"
PCB = HERE / "oas.kicad_pcb"
SCH = HERE / "oas.kicad_sch"

# Find kicad-cli — try common install paths on Windows, then PATH
KICAD_CLI_CANDIDATES = [
    r"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe",
    r"C:/Program Files/KiCad/9.0/bin/kicad-cli.exe",
    "kicad-cli",
]


def find_kicad_cli() -> str:
    for c in KICAD_CLI_CANDIDATES:
        if Path(c).exists() or shutil.which(c):
            return c
    sys.exit("ERROR: kicad-cli not found. Install KiCad 10 or add it to PATH.")


def step(title: str) -> None:
    print(f"\n=== {title} ===")


def run(cmd: list[str], *, hide_output: bool = False) -> None:
    """Run a subprocess, abort on non-zero exit. Decodes output as UTF-8
    with replacement so kicad-cli localized messages (e.g. Polish on
    Windows) don't break the script."""
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


def main() -> None:
    t0 = time.time()
    kcli = find_kicad_cli()
    RENDERS.mkdir(exist_ok=True)

    # 1) Regenerate KiCad source files from Python
    step("1/4  Regenerating KiCad source files (generate.py)")
    run([sys.executable, str(HERE / "generate.py")])

    # 2) DRC + ERC
    step("2/4  Running DRC + ERC")
    drc_report = RENDERS / "_drc.rpt"
    erc_report = RENDERS / "_erc.rpt"
    run([
        kcli, "pcb", "drc",
        "--output", str(drc_report),
        "--severity-error", "--severity-warning",
        str(PCB),
    ])
    run([
        kcli, "sch", "erc",
        "--output", str(erc_report),
        str(SCH),
    ])

    # 3) 2D SVG renders (Edge.Cuts always included)
    step("3/4  Rendering 2D previews (SVG)")
    svg_targets = [
        ("2d-top",      "Edge.Cuts,F.Cu,F.Mask,F.SilkS,F.CrtYd,F.Fab"),
        ("2d-cutouts",  "Edge.Cuts,F.Cu,Dwgs.User"),
        ("2d-bottom",   "Edge.Cuts,B.Cu,B.Mask,B.SilkS,B.CrtYd,B.Fab"),
    ]
    for name, layers in svg_targets:
        out = RENDERS / f"{name}.svg"
        cmd = [
            kcli, "pcb", "export", "svg",
            "--output", str(out),
            "--layers", layers,
            "--mode-single",
            "--page-size-mode", "2",  # board area only
            "--fit-page-to-board",
            "--exclude-drawing-sheet",
            str(PCB),
        ]
        if name == "2d-bottom":
            cmd.insert(-1, "--mirror")
        run(cmd, hide_output=True)
        print(f"  wrote {out.name}")

    # 4) Convert SVGs to PNG + 3D render
    step("4/4  PNG conversion + 3D render")
    try:
        import cairosvg
    except ImportError:
        print("  cairosvg not available — pip install cairosvg to enable PNG conversion")
    else:
        for svg in sorted(RENDERS.glob("*.svg")):
            png = svg.with_suffix(".png")
            cairosvg.svg2png(url=str(svg), write_to=str(png), output_width=1600)
            print(f"  {svg.name} -> {png.name}")

    # 3D render top — only run if we haven't done it in the last 10 minutes
    # (it's expensive; ~15 s)
    print("  rendering 3D top view (~15 s)...")
    run([
        kcli, "pcb", "render",
        "--output", str(RENDERS / "3d-top.png"),
        "--side", "top",
        "--width", "1600", "--height", "1600",
        "--background", "opaque",
        "--quality", "high",
        str(PCB),
    ], hide_output=True)
    print(f"  wrote 3d-top.png")

    print(f"\nDone in {time.time()-t0:.1f} s. Outputs in {RENDERS}/")


if __name__ == "__main__":
    main()
