"""Stage 15: mypy type-check on boardgen/ + pipeline/.

Catches REAL type errors that the rest of the pipeline can't:
- `boardgen/_common.py::Context` dataclass field renames vs stage usage,
- footprint generator signature drift (positional vs keyword args),
- GPIO map dict literal vs enum key churn,
- return-type contracts between helper modules,
- unreachable code branches,
- redundant casts.

Deliberately NOT `--strict`: this codebase predates type-hint coverage
and `--strict` produces ~100 'missing annotation' findings that are
style noise, not bugs. The flags below catch real semantic problems:
type mismatches inside the bodies that DO exist, unused ignores,
unreachable branches. Adding `--strict` becomes feasible after a
codebase-wide annotation pass.

Hard-fails if `mypy` module isn't importable. One-time setup:
`pip install mypy`.

Targets `boardgen/` + `pipeline/` only. `tools/` is debug-scratch and
not exercised on the harness path, so its strict-typing burden would
just slow contributors without preventing real bugs.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT, EXIT_MISSING_DEP  # noqa: E402

STAGE_NAME = "lint_typecheck"

TARGETS = ["boardgen", "pipeline"]


def main() -> int:
    with Stage(STAGE_NAME) as st:
        if importlib.util.find_spec("mypy") is None:
            print("[FAIL] mypy module not importable — required for stage 15 typecheck")
            print("[FAIL] one-time setup: pip install mypy")
            st.fail("mypy missing", code=EXIT_MISSING_DEP)

        cmd = [
            sys.executable, "-m", "mypy",
            # Real-bug flags only — see module docstring for why not --strict.
            "--check-untyped-defs",
            "--warn-unused-ignores",
            "--warn-redundant-casts",
            "--warn-unreachable",
            "--no-implicit-optional",
            "--ignore-missing-imports",
            "--no-incremental",
            "--show-error-codes",
            "--pretty",
            *[str(KICAD_ROOT / t) for t in TARGETS],
        ]
        st.info(f"running: python -m mypy (real-bug flags) {' '.join(TARGETS)}/")
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            cwd=str(KICAD_ROOT),
        )
        if r.returncode != 0:
            print(r.stdout)
            if r.stderr:
                print(r.stderr, file=sys.stderr)
            st.fail("mypy reported type errors")
        st.ok(f"mypy clean across {', '.join(TARGETS)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
