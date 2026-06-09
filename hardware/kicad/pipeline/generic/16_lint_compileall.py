"""Stage 16: byte-compile boardgen/ + pipeline/ + tools/ + tests/, then
run the pytest unit suite under tests/.

`python -m compileall -q` parses every .py file under the targets,
which catches syntax errors in modules that `build.py` doesn't import
directly on the happy path (e.g. `tools/` helpers, alternative entry
points, future stage files that have a typo but haven't been wired into
the pipeline yet).

After compileall passes, the unit-test suite (`tests/`) runs via
pytest with the cacheprovider plugin disabled so no `.pytest_cache/`
directory litters the repo. The suite covers the pure-Python boardgen
helpers: deterministic UUIDs (Lesson 9), `fmt()` formatting, geometry
invariants from `boardgen/_project.py`, POWER_BUDGET schema, and the
`oas_routes.py` snapshot sanity. Hard-fails (with the pytest output)
on any test failure; hard-fails with a setup hint if pytest is not
importable — same convention as stage 15's mypy requirement.

STAGE_NAME stays "lint_compileall" (the build.py orchestrator displays
the filename-derived stage name anyway, so the banner is unaffected).

Cheap (a few seconds), surfaces Python-level brokenness and helper
regressions before the more expensive checks run further down.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT  # noqa: E402

STAGE_NAME = "lint_compileall"

TARGETS = ["boardgen", "pipeline", "tools", "tests"]


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

        if importlib.util.find_spec("pytest") is None:
            print("[FAIL] pytest module not importable — required for stage 16 unit tests")
            print("[FAIL] one-time setup: pip install pytest")
            st.fail("pytest missing")

        st.info("pytest tests/")
        r = subprocess.run(
            [sys.executable, "-m", "pytest", str(KICAD_ROOT / "tests"),
             "-q", "--no-header", "-p", "no:cacheprovider"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr, file=sys.stderr)
            st.fail("unit-test suite failed")
        summary = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        st.ok(f"unit suite green ({summary})" if summary else "unit suite green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
