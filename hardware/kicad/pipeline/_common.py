"""Generic helpers for a KiCad build pipeline.

This module contains ONLY project-agnostic helpers: subprocess wrapper,
kicad-cli locator, SHA-256 hash, the Stage context manager. NO OAS-
specific paths or lists — those live in `_project.py`. Together with
`pipeline/generic/`, this file is portable to any KiCad project that
provides a matching `_project.py`.

Stages under `pipeline/<subdir>/NN_<name>.py` import from this module via:

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from _common import Stage, run, find_kicad_cli, ...

The numeric-prefix filenames cannot be `import`-ed directly, so each
stage runs as its own subprocess (the orchestrator in `build.py`
invokes them via `subprocess.run`) and `_common` is loaded via the
sys.path trick.

Format contract (consumed by `build.py`):
  - Every stage prints `=== STAGE NN: name ===` on entry.
  - Every stage emits `[INFO] ...`, `[OK] ...`, `[WARN] ...`, `[FAIL] ...`
    log lines (uniform 4-char tag column with a 3-space pad after `OK`).
  - On clean exit a stage prints `[OK]   stage passed in X.Xs` and returns 0.
  - On failure a stage prints `[FAIL] <reason>` and returns 1.

The orchestrator parses nothing from stdout; it relies purely on the
subprocess return code. The structured log format is for humans reading
the terminal and for LLMs grepping logs after the fact.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Paths ---------------------------------------------------------------------
HERE = Path(__file__).parent              # hardware/kicad/pipeline
KICAD_ROOT = HERE.parent                  # hardware/kicad
RENDERS = KICAD_ROOT.parent / "renders"   # hardware/renders/ (sibling of kicad/)

# kicad-cli locator ---------------------------------------------------------
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


# Subprocess wrapper --------------------------------------------------------
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Stage reporter ------------------------------------------------------------
class Stage:
    """Context manager for a single pipeline stage.

    Prints the entry banner on `__enter__`, captures elapsed wall-clock
    time, prints `[OK] stage passed in X.Xs` on clean exit. On exception
    inside the `with` block, prints `[FAIL] <exc>` then re-raises so the
    sub-process exits non-zero.

    Position-in-pipeline (`NN/TT`) is picked up from the env vars
    `PIPELINE_IDX` and `PIPELINE_TOTAL` that the orchestrator
    (`build.py`) injects per subprocess call. When the stage script
    is run standalone for debug, those vars are unset and the banner
    omits the position counter.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.idx = os.environ.get("PIPELINE_IDX")
        # When the orchestrator already printed the banner, skip ours
        # to avoid the duplicate `=== STAGE NN: name ===` line.
        self._banner_already = os.environ.get("PIPELINE_BANNER_EMITTED") == "1"
        self._t0: float = 0.0

    def __enter__(self) -> "Stage":
        if not self._banner_already:
            if self.idx:
                print(f"\n=== STAGE {self.idx}: {self.name} ===")
            else:
                print(f"\n=== STAGE: {self.name} ===")
        self._t0 = time.time()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        elapsed = time.time() - self._t0
        if exc_type is None:
            print(f"[OK]   stage passed in {elapsed:.1f}s")
            return
        # Let SystemExit (from .fail()) propagate verbatim — it already
        # printed [FAIL]. Other exceptions get a generic FAIL line.
        if not isinstance(exc, SystemExit):
            print(f"[FAIL] {exc_type.__name__}: {exc}")
        # Never suppress; returning None (or any falsy) lets the
        # exception propagate as normal.

    @staticmethod
    def info(msg: str) -> None:
        print(f"[INFO] {msg}")

    @staticmethod
    def ok(msg: str) -> None:
        print(f"[OK]   {msg}")

    @staticmethod
    def warn(msg: str) -> None:
        print(f"[WARN] {msg}")

    @staticmethod
    def fail(msg: str) -> None:
        print(f"[FAIL] {msg}")
        sys.exit(1)
