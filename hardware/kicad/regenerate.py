"""
OAS — master regeneration orchestrator.

This is a thin dispatcher. The actual work is in `pipeline/NN_<name>.py`
sub-scripts (one stage per file). Each pipeline file is independently
runnable for debugging (`python pipeline/03_drc.py`); this orchestrator
runs them in numeric order, aggregates exit codes, and prints a final
SUMMARY table.

Stage layout (numbered for visible ordering — note the 08–09 gap reserved
for future verification checks):

  01 generate          rebuild every KiCad source file from generate.py
  02 determinism       hash + re-run + diff (bit-identity guardrail)
  03 drc               kicad-cli pcb drc strict (errors + warnings)
  04 erc               kicad-cli sch erc strict (errors + warnings)
  05 check_dc          DC voltage propagation analytical model
  06 check_boot        ESP32-C6 strap + signal pin audit
  07 check_ampacity    IPC-2221 trace width verifier
  10 render_2d         PCB top / cutouts / bottom SVG
  11 render_sch        Schematic root + 4 sub-sheets SVG
  12 render_png        cairosvg batch SVG → PNG
  13 render_3d         3D top + iso renders via kicad-cli

Usage:  python regenerate.py
"""
from __future__ import annotations

import os
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
    return 0 if all(s == "PASS" for _, _, s, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
