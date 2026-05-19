"""Stage 16: byte-compile every Python file under boardgen/ + pipeline/.

`python -m compileall -q` parses every .py file under the targets,
which catches syntax errors in modules that `build.py` doesn't import
directly on the happy path (e.g. `tools/` helpers, alternative entry
points, future stage files that have a typo but haven't been wired into
the pipeline yet).

Cheap (<1 s typically), zero dependencies, surface any Python-level
brokenness before the more expensive checks run further down.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT  # noqa: E402

STAGE_NAME = "lint_compileall"

TARGETS = ["boardgen", "pipeline", "tools"]


def main() -> int:
    with Stage(STAGE_NAME) as st:
        for sub in TARGETS:
            path = KICAD_ROOT / sub
            if not path.exists():
                st.info(f"skipping {sub}/ (not present)")
                continue
            st.info(f"compileall {sub}/")
            r = subprocess.run(
                [sys.executable, "-m", "compileall", "-q", str(path)],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            if r.returncode != 0:
                print(r.stdout)
                print(r.stderr, file=sys.stderr)
                st.fail(f"compileall failed for {sub}/")
        st.ok("all targets parse cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
