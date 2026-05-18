"""Stage 01: invoke the project's generate script.

`_project.GENERATE_SCRIPT` is expected to be the source-of-truth Python
that emits every deterministic KiCad source file (PCB, SCH + sub-sheets,
project file, lib tables, project libraries). Any internal guardrails
the project wants to enforce at generation time (Z-clearance checks,
pin-allocation asserts, etc.) live inside that script.

This stage is a thin subprocess wrapper. Aborts on any non-zero exit.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, run  # noqa: E402
from _project import GENERATE_SCRIPT  # noqa: E402

STAGE_NAME = "generate"


def main() -> int:
    with Stage(STAGE_NAME) as st:
        st.info(f"running {GENERATE_SCRIPT.name}")
        run([sys.executable, str(GENERATE_SCRIPT)])
        st.ok("KiCad source files regenerated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
