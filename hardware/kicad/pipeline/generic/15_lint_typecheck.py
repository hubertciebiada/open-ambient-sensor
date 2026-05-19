"""Stage 15: mypy strict type-check on boardgen/ + pipeline/.

Catches type drift that the rest of the pipeline can't:
- `boardgen/_common.py::Context` dataclass field renames vs stage usage,
- footprint generator signature drift (positional vs keyword args),
- GPIO map dict literal vs enum key churn,
- return-type contracts between helper modules.

Soft-skips with [WARN] (exit 0) if `mypy` is not on PATH — pattern
mirrored from `08_check_switching.py` so the pipeline runs out-of-box
without forcing a fresh `pip install mypy`. Once the user has mypy
installed, the check kicks in automatically.

Targets `boardgen/` + `pipeline/` only. `tools/` is debug-scratch and
not exercised on the harness path, so its strict-typing burden would
just slow contributors without preventing real bugs.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT  # noqa: E402

STAGE_NAME = "lint_typecheck"

TARGETS = ["boardgen", "pipeline"]


def main() -> int:
    with Stage(STAGE_NAME) as st:
        if shutil.which("mypy") is None:
            st.warn("mypy not on PATH — skipping (run `pip install mypy` to enable)")
            return 0

        cmd = [
            "mypy",
            "--strict",
            "--ignore-missing-imports",
            "--no-incremental",
            "--show-error-codes",
            "--pretty",
            *[str(KICAD_ROOT / t) for t in TARGETS],
        ]
        st.info(f"running: mypy --strict {' '.join(TARGETS)}/")
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            cwd=str(KICAD_ROOT),
        )
        if r.returncode != 0:
            print(r.stdout)
            if r.stderr:
                print(r.stderr, file=sys.stderr)
            st.fail("mypy --strict reported type errors")
        st.ok("mypy --strict clean across boardgen/ + pipeline/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
