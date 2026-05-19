"""Stage 01: emit every KiCad source file from the boardgen/ package.

Walks `boardgen/[0-9][0-9]_*.py` in numeric order and runs each stage's
`run(ctx)` entry point. Stages share in-memory state via a single
`Context` dataclass (see `boardgen/_common.py`). Every piece of logic that
EMITS a KiCad source file lives inside the boardgen/ package — this
pipeline stage is just the walker.

Boardgen stage layout (visible at `ls boardgen/[0-9][0-9]_*.py`):

  01 custom_footprints     write 7 .kicad_mod files
  02 pcb_board             write oas.kicad_pcb
  03 z_clearance           Z-clearance audit (sys.exit on violation)
  04 schematic_power       write power.kicad_sch
  05 schematic_mcu         write mcu.kicad_sch
  06 schematic_sensors     write sensors.kicad_sch
  07 schematic_io          write io.kicad_sch
  08 schematic_root        write oas.kicad_sch
  09 project_kicad_pro     write oas.kicad_pro
  10 lib_tables            write fp-lib-table + sym-lib-table
  11 oas_symbol_library    write libraries/OAS.kicad_sym
  12 sync_pcb_nets         inject (net code "name") into PCB pads
  13 apply_routing         emit tracks + vias + GND pour zones

Inlined from the former `hardware/kicad/generate.py` (removed 2026-05-19)
so that `build.py` is the only top-level entrypoint — no boardgen walker
runnable from `hardware/kicad/` root, no way for a caller to skip DRC /
ERC / determinism checks by bypassing the orchestrator.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT  # noqa: E402

STAGE_NAME = "emit_sources"
BOARDGEN = KICAD_ROOT / "boardgen"


def _load_stage(path: Path):
    """Import a `boardgen/NN_<name>.py` file by absolute path.

    The numeric `NN_` prefix isn't a valid Python identifier so we
    can't `import boardgen.NN_name` — `importlib.util.spec_from_file_location`
    lets us load the module by path and exec it in its own namespace.
    """
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def emit_all_sources() -> int:
    """Run every `boardgen/NN_*.py` stage with a shared Context.

    Importable for in-process callers (tests, debug); the standalone CLI
    path below wraps this in a Stage banner so the subprocess invocation
    from `build.py` shows uniform `=== STAGE 01: emit_sources ===` output.
    """
    sys.path.insert(0, str(KICAD_ROOT))
    from boardgen._common import Context  # noqa: E402

    ctx = Context()
    stages = sorted(BOARDGEN.glob("[0-9][0-9]_*.py"))
    if not stages:
        sys.exit(f"ERROR: no boardgen stages found under {BOARDGEN}")
    for path in stages:
        prefix, name = path.stem.split("_", 1)
        print(f"  step {prefix}: {name}")
        mod = _load_stage(path)
        mod.run(ctx)
    return len(stages)


def main() -> int:
    with Stage(STAGE_NAME) as st:
        st.info(f"walking {BOARDGEN.relative_to(KICAD_ROOT)}/")
        n = emit_all_sources()
        st.ok(f"emitted KiCad source files from {n} boardgen stages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
