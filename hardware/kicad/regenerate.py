"""
OAS — master regeneration script.

Single entry point for rebuilding the entire KiCad project from sources:

  1. Run `generate.py` — regenerates oas.kicad_pcb / oas.kicad_sch /
     oas.kicad_pro / footprint library / lib tables from the Python
     geometry constants. Deterministic UUIDs → bit-identical output
     when no inputs changed.
  2. Validate — kicad-cli pcb drc + kicad-cli sch erc, fail loudly
     if there are any errors or warnings.
  2b. DC voltage propagation check (tools/check_dc.py) — verifies
     every regulated rail (V_24V_PROT, +5V, +3V3) lands in its datasheet
     spec window when 24 V is applied at J1, plus safety margins on
     Q1 Vgs / Vds and D3 power dissipation. Catches design-value
     regressions (resistor renumberings, Zener voltage drift) that
     DRC / ERC cannot detect.
  2c. Boot-strap + signal-pin audit (tools/check_boot.py) — exports the
     schematic netlist, maps J5/J6 socket pins to ESP32-C6 GPIOs, and
     verifies the 5 strap pins (GPIO 4 / 5 / 8 / 9 / 15) plus 9 signal
     pins (I2C, UART, USB, LED, interrupts) are on the expected nets.
     Catches boot-mode bricks, missing GPIO 8 pull-up to +3V3, and
     accidental pinout swaps in future schematic edits.
  2d. Trace ampacity check (tools/check_ampacity.py) — parses every
     track segment in oas.kicad_pcb, finds the narrowest segment on
     +24V / +5V / +3V3, and verifies each carries its budgeted
     continuous current per IPC-2221 (1 oz Cu, 10 C rise) with a 1.2x
     safety factor. Catches pinched routes through tight pockets that
     would fuse under sustained load.
  3. Render — produce committable PNG / SVG previews into renders/:
        2d-top.{svg,png}        Top-side production view
        2d-cutouts.{svg,png}    Edge.Cuts + Dwgs.User keepout markers
        2d-bottom.{svg,png}     Bottom-side production view (mirrored)
        3d-top.png              3D raytraced render
        3d-iso.png              3D isometric render with shadow plane
        sch-root.{svg,png}      Root schematic (4 sub-sheet blocks)
        sch-power.{svg,png}     Power sub-sheet
        sch-mcu.{svg,png}       MCU sub-sheet
        sch-sensors.{svg,png}   Sensors sub-sheet
        sch-io.{svg,png}        IO sub-sheet

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


def _kicad_source_files() -> list[Path]:
    """Return all generated KiCad source-files whose content must be
    bit-identical across consecutive regenerations (v0.23 review Nt2 —
    determinism self-check). Excludes the renders/ directory and the
    auto-managed .kicad_prl runtime state file."""
    files: list[Path] = [
        HERE / "oas.kicad_pcb",
        HERE / "oas.kicad_sch",
        HERE / "oas.kicad_pro",
        HERE / "power.kicad_sch",
        HERE / "mcu.kicad_sch",
        HERE / "sensors.kicad_sch",
        HERE / "io.kicad_sch",
        HERE / "fp-lib-table",
        HERE / "sym-lib-table",
    ]
    lib_dir = HERE / "libraries"
    if lib_dir.exists():
        files.extend(sorted(lib_dir.rglob("*.kicad_mod")))
        files.extend(sorted(lib_dir.rglob("*.kicad_sym")))
    return [p for p in files if p.exists()]


def _hash_file(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    t0 = time.time()
    kcli = find_kicad_cli()
    RENDERS.mkdir(exist_ok=True)

    # 1) Regenerate KiCad source files from Python
    step("1/4  Regenerating KiCad source files (generate.py)")
    run([sys.executable, str(HERE / "generate.py")])

    # 1b) Determinism self-check (v0.23 review Nt2): snapshot every
    #     generated source file's hash, run generate.py a second time, then
    #     verify nothing changed. All UUIDs in generate.py are deterministic
    #     v5; two consecutive runs MUST produce bit-identical sources. If
    #     they don't, that's a real bug to fix (e.g. an accidental
    #     dependency on Python's hash randomization or dict-iteration
    #     order) — flag loudly rather than silently committing flapping
    #     diffs.
    step("1b/4  Determinism self-check (re-run generate.py)")
    pre_hashes: dict[Path, str] = {p: _hash_file(p) for p in _kicad_source_files()}
    run([sys.executable, str(HERE / "generate.py")])
    post_hashes: dict[Path, str] = {p: _hash_file(p) for p in _kicad_source_files()}
    drifted: list[Path] = []
    for p, post_h in post_hashes.items():
        pre_h = pre_hashes.get(p)
        if pre_h is None:
            # File didn't exist before the second run — that's only
            # possible if generate.py creates files conditionally, which
            # it doesn't. Flag as drift defensively.
            drifted.append(p)
        elif pre_h != post_h:
            drifted.append(p)
    if drifted:
        for p in drifted:
            print(f"  DRIFT: {p.relative_to(HERE)}")
        sys.exit("ERROR: regenerate.py is not deterministic — see drifted files above.")
    print(f"  OK — generate.py output is bit-identical across consecutive runs ({len(post_hashes)} files checked).")

    # 2) DRC + ERC
    step("2/4  Running DRC + ERC")
    drc_report = RENDERS / "_drc.rpt"
    erc_report = RENDERS / "_erc.rpt"
    # v0.28: `--refill-zones` makes the DRC check fill zones before
    # checking connectivity. Without this, GND pads inside the F.Cu /
    # B.Cu GND pour would still appear as "unconnected_items" because
    # the connectivity check looks only at routed-track copper + filled
    # zone polygons. We deliberately DO NOT pass `--save-board`: KiCad's
    # save would (a) re-write the PCB file in its compact native format
    # losing the (net N "name") integer codes that generate.py emits,
    # and (b) inject fresh random UUIDs on every save, breaking the
    # determinism guarantee. The 2D PCB previews further down render
    # `kicad-cli pcb export svg` on a freshly-filled snapshot internally
    # (see `--include-extra-board-info` behavior), so the rendered
    # output reflects the filled pour without us needing to save it.
    # v0.28e: split DRC strict-enforcement into "real rule violations" vs
    # "unconnected pads". kicad-cli's --exit-code-violations counts BOTH
    # categories the same, but they mean different things:
    #   - Real violations (clearance, edge, thermal, shorts, etc.) = design
    #     correctness bugs; MUST abort regenerate.
    #   - Unconnected pads = layout work-in-progress (not all nets routed
    #     yet); SHOULD warn loudly but NOT abort, because routing may be
    #     iterative (v0.28b autoroute left 23 unconnected, v0.28d closed
    #     some, more iterations expected).
    # Approach: run DRC WITHOUT --exit-code-violations, parse the report,
    # abort only on the "Found N DRC violations" count.
    run([
        kcli, "pcb", "drc",
        "--output", str(drc_report),
        "--severity-error", "--severity-warning",
        "--refill-zones",
        str(PCB),
    ])
    # Parse the report to extract violation + unconnected counts.
    drc_text = drc_report.read_text(encoding="utf-8", errors="replace")
    import re
    m_viol = re.search(r"Found (\d+) DRC violations", drc_text)
    m_unc  = re.search(r"Found (\d+) unconnected pads", drc_text)
    n_viol = int(m_viol.group(1)) if m_viol else 0
    n_unc  = int(m_unc.group(1))  if m_unc  else 0
    print(f"  DRC: {n_viol} violations, {n_unc} unconnected pads")
    if n_viol > 0:
        sys.exit(f"ERROR: {n_viol} DRC violation(s) — see {drc_report}")
    if n_unc > 0:
        print(f"  WARNING: {n_unc} unconnected pads (routing in progress; not gating)")
    # v0.24 fix (review iteration 2 Mj2): make ERC strict on warnings.
    # `--severity-warning` includes warning-level violations in the report;
    # `--exit-code-violations` makes kicad-cli return non-zero when any
    # violation (error OR warning) exists. Without both flags, the v0.23
    # Mn3 regression (15 `footprint_link_issues` warnings) silently passed
    # CI because the subprocess returned 0. Mirrors the DRC step's
    # `--severity-error --severity-warning` strictness — every ERC issue
    # now aborts the regenerate run, matching CLAUDE.md "PCB design
    # workflow" §3 ("aborts on any error or warning").
    run([
        kcli, "sch", "erc",
        "--output", str(erc_report),
        "--severity-error", "--severity-warning",
        "--exit-code-violations",
        str(SCH),
    ])

    # 2b) DC voltage propagation check (v0.38).
    # Runs `tools/check_dc.py` which parses R2/R3/D3 values from the
    # freshly-generated schematic and asserts every regulated rail lands
    # in its datasheet spec window (V_24V_PROT, +5V, +3V3) plus safety
    # margins on Q1 Vgs / Vds and D3 power dissipation. Catches the same
    # regression class as the v0.36 R3 10k -> 30.9k fix (which would
    # have destroyed ESP32 + SEN66 at first power-on) and the v0.37
    # D3 18V -> 10V fix (AO3401A Vgs overstress).
    #
    # Pure-Python analytical model with simplified ideal regulators and
    # AO3401A as a series resistance — DRC + ERC catch wiring bugs,
    # this catches design-value bugs.
    step("2b/5  DC voltage propagation check (tools/check_dc.py)")
    run([sys.executable, str(HERE / "tools" / "check_dc.py")])

    # 2c) Boot-strap + signal-pin audit.
    # Verifies the ESP32-C6 boots in run mode (not download mode), that
    # GPIO 8 has the external pull-up R7 (DevKitM-1's onboard pull-up
    # runs off VCC_5V which is unpowered in OAS), and that every signal
    # pin is on the net the firmware expects. Catches pinout swaps that
    # would otherwise show up as "device works on the bench but the
    # presence interrupt lands on the wrong handler" type bugs.
    step("2c/5  Boot-strap + signal-pin audit (tools/check_boot.py)")
    run([sys.executable, str(HERE / "tools" / "check_boot.py")])

    # 2d) Trace ampacity check (IPC-2221).
    # Parses every routed segment on +24V / +5V / +3V3, finds the
    # narrowest width on each rail, and verifies it can carry the
    # net's continuous-current budget with a 1.2x safety factor at 10 C
    # ambient rise. Catches pinched routes through tight pockets that
    # would burn out under sustained load.
    step("2d/5  Trace ampacity check (tools/check_ampacity.py)")
    run([sys.executable, str(HERE / "tools" / "check_ampacity.py")])

    # 3a) 2D PCB SVG renders (Edge.Cuts always included)
    step("3/5  Rendering 2D PCB previews (SVG)")
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
            # v0.28: --check-zones makes the SVG export refill zones
            # before plotting so the GND pour appears as filled copper
            # in the rendered image. Without this, the SVG would show
            # only the zone polygon outlines (since generate.py doesn't
            # emit pre-computed `filled_polygon` data — that's KiCad's
            # job, and we don't want to commit its non-deterministic
            # UUID-randomized output).
            "--check-zones",
            str(PCB),
        ]
        if name == "2d-bottom":
            cmd.insert(-1, "--mirror")
        run(cmd, hide_output=True)
        print(f"  wrote {out.name}")

    # 3b) Schematic SVG renders
    # kicad-cli sch export svg writes one SVG per schematic file into the
    # output directory, naming it after the input file's stem (e.g. power.svg).
    # We render each hierarchical sub-sheet directly (passing its file) so we
    # get one clean SVG per sub-sheet, then rename to sch-<name>.svg so the
    # output set is consistent and gitignore-friendly.
    step("4/5  Rendering schematic previews (SVG)")
    sch_targets = [
        ("sch-root",    HERE / "oas.kicad_sch"),
        ("sch-power",   HERE / "power.kicad_sch"),
        ("sch-mcu",     HERE / "mcu.kicad_sch"),
        ("sch-sensors", HERE / "sensors.kicad_sch"),
        ("sch-io",      HERE / "io.kicad_sch"),
    ]
    for out_name, src in sch_targets:
        # Render into a temp subdir then move the produced file into renders/
        # under the desired sch-<name>.svg filename. The temp dir is prefixed
        # with `_` so it stays gitignored along with the DRC/ERC reports.
        tmp_dir = RENDERS / f"_{out_name}-tmp"
        tmp_dir.mkdir(exist_ok=True)
        run([
            kcli, "sch", "export", "svg",
            "--output", str(tmp_dir),
            "--exclude-drawing-sheet",
            "--no-background-color",
            str(src),
        ], hide_output=True)
        produced = tmp_dir / f"{src.stem}.svg"
        final = RENDERS / f"{out_name}.svg"
        # Use replace() which atomically overwrites the destination on
        # Windows (Path.rename() can fail if final.exists() and a viewer
        # has it locked; replace() retries / overwrites in one call).
        produced.replace(final)
        # Clean up the temp dir (kicad-cli created only one file)
        try:
            tmp_dir.rmdir()
        except OSError:
            pass
        print(f"  wrote {final.name}")

    # 4) Convert SVGs to PNG + 3D render
    step("5/5  PNG conversion + 3D render")
    try:
        import cairosvg
    except ImportError:
        print("  cairosvg not available — pip install cairosvg to enable PNG conversion")
    else:
        for svg in sorted(RENDERS.glob("*.svg")):
            png = svg.with_suffix(".png")
            cairosvg.svg2png(url=str(svg), write_to=str(png), output_width=1600)
            print(f"  {svg.name} -> {png.name}")

    # 3D renders (expensive — ~15 s each)
    render_targets = [
        # (output, extra args)
        ("3d-top.png",  []),
        # Isometric view per KiCad docs: --rotate '-45,0,45' (with --floor
        # to add a shadow plane so component height is easier to read)
        ("3d-iso.png",  ["--rotate", "-45,0,45", "--perspective", "--floor"]),
    ]
    for out_name, extra in render_targets:
        print(f"  rendering {out_name} (~15 s)...")
        run([
            kcli, "pcb", "render",
            "--output", str(RENDERS / out_name),
            "--side", "top",
            "--width", "1600", "--height", "1600",
            "--background", "opaque",
            "--quality", "high",
            *extra,
            str(PCB),
        ], hide_output=True)
        print(f"  wrote {out_name}")

    print(f"\nDone in {time.time()-t0:.1f} s. Outputs in {RENDERS}/")


if __name__ == "__main__":
    main()
