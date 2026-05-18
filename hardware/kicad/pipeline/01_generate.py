"""Stage 01/11: run generate.py to rebuild every KiCad source file.

`generate.py` is the source-of-truth Python that emits 17 deterministic
KiCad files (oas.kicad_pcb, oas.kicad_sch + 4 sub-sheets, oas.kicad_pro,
fp-lib-table, sym-lib-table, libraries/OAS.kicad_sym, libraries/oas.pretty/*).
It also runs internal guardrails (Z-clearance under daughterboards,
pin-allocation asserts).

This stage is a thin subprocess wrapper. Aborts on any non-zero exit.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import Stage, run, KICAD_ROOT  # noqa: E402

STAGE_NAME = "generate"


def main() -> int:
    with Stage(STAGE_NAME) as st:
        st.info("running generate.py")
        run([sys.executable, str(KICAD_ROOT / "generate.py")])
        st.ok("KiCad source files regenerated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
