"""
OAS — master build orchestrator (the only top-level entrypoint).

This is the AI-agent harness for the KiCad project: `python build.py` is
the ONLY way to (re-)emit the KiCad source files. There is no
`generate.py` shortcut at the repo root — the boardgen walker lives
inside `pipeline/generic/01_emit_sources.py` and is reached exclusively
through this orchestrator. That keeps an autonomous agent from "just
rebuilding the sources" while skipping DRC / ERC / determinism / DC /
ampacity / boot-strap / preflight / vendor-export checks.

`build.py` is a thin dispatcher. The actual work is in
`pipeline/<subdir>/NN_<name>.py` sub-scripts (one stage per file). Each
pipeline file is also independently runnable for debugging
(`python pipeline/generic/03_drc.py`); this orchestrator runs them in
numeric order, aggregates exit codes, and prints a final SUMMARY table.

Stage layout (numbered for visible ordering — gaps reserved for future
checks per the per-subdir number budget in CLAUDE.md):

  01 emit_sources       rebuild every KiCad source file via boardgen/
  02 determinism        hash + re-run + diff (bit-identity guardrail)
  03 drc                kicad-cli pcb drc strict (errors + warnings)
  04 erc                kicad-cli sch erc strict (errors + warnings)
  05 check_dc           DC voltage propagation analytical model
  06 check_boot         ESP32-C6 strap + signal pin audit
  07 check_ampacity     IPC-2221 trace width verifier
  08 check_switching    ngspice LM2596 soft-start transient
  10 render_2d          PCB top / cutouts / bottom SVG
  11 render_sch         Schematic root + 4 sub-sheets SVG
  12 render_png         cairosvg batch SVG → PNG
  13 render_3d          3D top + iso renders via kicad-cli
  14 check_refdes       designator uniqueness across schematic
  20 export_gerbers     Protel gerbers + Excellon drill (raw fab data)
  24 preflight_gerbers  pygerber integrity + drill stats
  29 check_bom_consistency  LCSC# bijection
  30 export_pos         JLCPCB CPL header + rotation offsets
  31 export_bom         BOM with LCSC mapping + library tier
  32 bundle             ZIP gerbers + drill -> oas-jlcpcb.zip
  33 check_dnp_consistency  DNP refdes leak audit

Usage:  python build.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
PIPELINE = HERE / "pipeline"


def discover_stages() -> list[Path]:
    """Return NN_<name>.py files from `pipeline/<subdir>/`, sorted by
    basename so numeric prefix order (01..13) is preserved regardless of
    which subdir (`generic/` or `oas/`) each stage lives in. Skips
    `_common.py` / `_project.py` (top-level, no NN_ prefix)."""
    return sorted(PIPELINE.glob("*/[0-9][0-9]_*.py"), key=lambda p: p.name)


def run_stage(prefix: str, name: str, stage: Path) -> int:
    """Invoke a single pipeline script as a subprocess.

    Injects PIPELINE_IDX (the two-digit prefix from the filename) so
    Stage in `_common.py` shows `=== STAGE NN: name ===`. Numbers stay
    aligned with filenames forever — adding/removing siblings does NOT
    renumber unrelated stages.

    For pipeline files that have their OWN output format (check_dc /
    check_boot / check_ampacity — lifted from the pre-refactor tools/
    layout), we emit the banner here BEFORE invoking, since those scripts
    don't import _common.Stage. Newer stages have Stage(...) inside and
    emit the banner themselves; we suppress the duplicate by passing
    PIPELINE_BANNER_EMITTED=1 (Stage honours it and skips its own
    banner)."""
    env = {
        **os.environ,
        "PIPELINE_IDX": prefix,
    }
    print(f"\n=== STAGE {prefix}: {name} ===")
    env["PIPELINE_BANNER_EMITTED"] = "1"
    r = subprocess.run([sys.executable, str(stage)], env=env)
    return r.returncode


def cleanup_temp(renders_dir: Path) -> int:
    """Delete every `_*` entry in renders_dir (files + dirs). Pipeline temp
    artifacts — DRC/ERC reports, schematic-export scratch sub-dirs — live
    there with `_` prefix; on a clean run they are disposable and only
    clutter the explorer view. Returns the number of entries removed.

    Called by main() ONLY after all stages PASS — on FAIL the temp files
    carry the failure context (full DRC report, ERC violations) and stay
    on disk for inspection."""
    count = 0
    if not renders_dir.exists():
        return 0
    for entry in renders_dir.glob("_*"):
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            try:
                entry.unlink()
            except OSError:
                continue
        count += 1
    return count


def print_summary(results: list[tuple[str, str, str, float]], total_elapsed: float) -> None:
    print("\n=== SUMMARY ===")
    for prefix, name, status, dur in results:
        print(f"{prefix} {name:<18} {status}  {dur:.1f}s")
    passed = sum(1 for _, _, s, _ in results if s == "PASS")
    total = len(results)
    if passed == total:
        print(f"Total: {passed}/{total} PASS in {total_elapsed:.1f}s")
    else:
        last_prefix, last_name, _, _ = results[-1]
        print(f"Total: {passed}/{total} PASS, aborted at {last_prefix}_{last_name} in {total_elapsed:.1f}s")


def main() -> int:
    stages = discover_stages()
    if not stages:
        sys.exit(f"ERROR: no pipeline scripts found under {PIPELINE}")

    results: list[tuple[str, str, str, float]] = []
    t_start = time.time()

    for stage in stages:
        prefix, name = stage.stem.split("_", 1)
        t0 = time.time()
        rc = run_stage(prefix, name, stage)
        elapsed = time.time() - t0
        status = "PASS" if rc == 0 else "FAIL"
        results.append((prefix, name, status, elapsed))
        if rc != 0:
            break  # fail-fast

    print_summary(results, time.time() - t_start)

    all_pass = all(s == "PASS" for _, _, s, _ in results)
    if all_pass:
        sys.path.insert(0, str(PIPELINE))
        from _common import RENDERS  # noqa: E402
        removed = cleanup_temp(RENDERS)
        if removed:
            print(f"[OK]   cleanup: removed {removed} temp artefact(s) from {RENDERS}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
