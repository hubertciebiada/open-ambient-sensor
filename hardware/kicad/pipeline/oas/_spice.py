"""
OAS - Shared ngspice harness for SPICE-driven verification stages.

This module exposes the GENERIC ngspice infrastructure that multiple
OAS pipeline stages need to share:

    - `ensure_ngspice()`     : locate / auto-download ngspice 46 binary.
    - `_download()`          : urllib HTTP downloader (with size check).
    - `write_spice_init()`   : emit `.spiceinit` configured for PSpice
                               TI-model translation (`ngbehavior=ps`).
    - `run_ngspice()`        : batch-mode subprocess wrapper (CWD-aware).
    - `parse_meas()`         : parse a single `name = value` line from
                               ngspice `print` output.
    - `CheckResult`          : dataclass for one named PASS/FAIL spec
                               assertion (consumed by stage main()s for
                               their final summary table).

Consumers (current + planned):
    - `08_check_switching.py`  : LM2596 soft-start transient.
    - `27_check_surge.py`      : TVS clamping / IEC 61000-4-5 surge
                                 envelope (future).
    - `28_check_reverse_polarity.py` : AO3401A turn-off vs BZT52C10
                                       clamp during reverse-Vin event
                                       (future).
    - Future cascade-buck extension of stage 08 (LM2596 -> TPS62933
      cascade to verify the SEN66 +3V3 ramp spec end-to-end).

Stages import BOTH `_common.Stage` and `_spice.*` (this module is
INDEPENDENT of `_common.py` on purpose; consumers compose the two).

Deliberately NOT here
---------------------
* Per-circuit `render_*_cir(...)` text-template helpers. Each consumer
  stage owns the SPICE netlist for the circuit under test - the model
  pin order, the load network, the measurement directives, the
  acceptance windows - because those are physics, not infrastructure.
* Per-model download helpers (LM2596 / TPS62933 / etc.). Each model
  has a different vendor host + archive layout; those live next to
  the stage that uses them.

Run modes
---------
* Imported as a module from sibling stages (the primary use case).
* Standalone: `python pipeline/oas/_spice.py` runs a smoke test
  (ensures ngspice is downloaded + runs a trivial .op netlist).

Cache
-----
All downloads land under `<repo>/.tmp/spice/`, sibling to
`.tmp/jlcparts/` etc. (gitignored). Subfolders per artefact:
  - `.tmp/spice/Spice64/bin/ngspice_con.exe`  (binary, ~50 MB unpacked)
  - `.tmp/spice/<model_id>/...`               (per-stage model caches)

Failure policy (per CLAUDE.md "hard FAIL on download / py7zr failure")
---------------------------------------------------------------------
No soft-skip anywhere. Missing py7zr -> raise with `pip install py7zr`.
HTTP download failure -> raise. Size mismatch -> raise. ngspice exit
code != 0 -> raise. Consumers wrap calls in `try` only when they want
to add stage-specific context to the message before re-raising.

Implements Lesson 18 (CLAUDE.md) — leading underscore in the filename
excludes this module from the `build.py` `pipeline/<subdir>/NN_*.py`
glob, so the shared ngspice infrastructure is imported (never executed)
by stages 08 / 27 / 28.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# Paths ---------------------------------------------------------------------
HERE = Path(__file__).parent              # hardware/kicad/pipeline/oas
KICAD_DIR = HERE.parent.parent            # hardware/kicad
REPO_ROOT = KICAD_DIR.parent.parent       # repo root
CACHE_DIR = REPO_ROOT / ".tmp" / "spice"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Download URL (verified by SPICE research agent against current hosting).
NGSPICE_URL = (
    "https://sourceforge.net/projects/ngspice/files/ng-spice-rework/46/"
    "ngspice-46_64.7z/download"
)

NGSPICE_BIN_NAME = "ngspice_con.exe"


# Result type ---------------------------------------------------------------
@dataclass
class CheckResult:
    """One named PASS/FAIL assertion produced by a SPICE-driven stage.

    Stages collect a list of these, print them with the inherited
    `__str__`, and `sys.exit(1)` if any has `passed == False`.

    Fields
    ------
    name   : human label, e.g. "LM2596 soft-start ramp".
    value  : the measured value as a formatted string, including units,
             e.g. "t_90 = 1.24 ms" or "4.987 V".
    spec   : the acceptance window as a formatted string, e.g.
             "[0.5, 5.0] ms" or "[4.85, 5.15] V".
    passed : True iff the measurement satisfies the spec.
    """

    name: str
    value: str
    spec: str
    passed: bool

    def __str__(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        return f"  [{mark}] {self.name:38s} {self.value:30s} (spec: {self.spec})"


# Download helpers ----------------------------------------------------------
def _download(url: str, target: Path) -> None:
    """urllib download with redirects + minimal progress print + size check.

    Writes the response body to `target`. On size mismatch versus the
    server's Content-Length header (when present), raises SystemExit
    with a clear message; consumers must NOT swallow the failure.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {url}")
    with urllib.request.urlopen(url, timeout=120) as resp:
        size = int(resp.headers.get("Content-Length") or 0)
        target.write_bytes(resp.read())
    actual = target.stat().st_size
    if size and actual != size:
        sys.exit(f"  download size mismatch: expected {size} B, got {actual} B")
    print(f"  wrote {target.name} ({actual / 1024:.1f} kB)")


# ngspice locator + auto-download ------------------------------------------
def find_ngspice() -> Path | None:
    """Locate `ngspice_con.exe`. Tries the project-local cache first,
    then the system's LOCALAPPDATA/Temp/Spice64 path that some installers
    use. Returns None if no candidate exists."""
    candidates = [
        CACHE_DIR / "Spice64" / "bin" / NGSPICE_BIN_NAME,
        Path(os.environ.get("LOCALAPPDATA", "")) / "Temp" / "Spice64" / "bin" / NGSPICE_BIN_NAME,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def ensure_ngspice() -> Path:
    """Idempotent: locate or auto-download ngspice 46 into
    `<repo>/.tmp/spice/Spice64/`. Returns the `ngspice_con.exe` path.

    First-run behaviour: downloads `ngspice-46_64.7z` from SourceForge
    (~50 MB) and extracts via `py7zr`. Subsequent runs short-circuit
    on the cached binary.

    Hard-fails (SystemExit) on:
      * `py7zr` not importable -> emits `pip install py7zr` hint.
      * HTTP download failure / size mismatch.
      * Binary missing from the archive after extract (archive layout
        change upstream).
    """
    cached = find_ngspice()
    if cached:
        return cached

    print("  ngspice not in cache - auto-downloading from SourceForge")
    try:
        import py7zr
    except ImportError:
        sys.exit(
            "[FAIL] py7zr not installed - needed to extract ngspice-46_64.7z.\n"
            "       Install with: pip install py7zr\n"
            f"       Or manually extract ngspice-46_64.7z to {CACHE_DIR}/Spice64/."
        )

    archive = CACHE_DIR / "ngspice-46_64.7z"
    _download(NGSPICE_URL, archive)

    print(f"  extracting {archive.name} (~50 MB)")
    with py7zr.SevenZipFile(archive, mode="r") as z:
        z.extractall(path=CACHE_DIR)
    archive.unlink()

    found = find_ngspice()
    if not found:
        sys.exit(
            f"[FAIL] {NGSPICE_BIN_NAME} not present after extracting "
            f"ngspice-46_64.7z to {CACHE_DIR}. Archive layout may have changed."
        )
    print(f"  ngspice ready at {found}")
    return found


# Runtime config + execution -----------------------------------------------
def write_spice_init(workdir: Path) -> None:
    """Required ngspice runtime config for PSpice-format TI models.

    `ngbehavior=ps` translates PSpice `VALUE { IF(...) }` to ngspice
    ternary at include-time (the LM2596 model has 19 such constructs;
    the TPS62933P and SMBJ24A models have similar PSpice idioms).

    `ng_nomodcheck` suppresses the bogus warnings about subcircuit
    primitives unavailable in pure-ngspice mode.

    Writes `<workdir>/.spiceinit`. ngspice picks it up automatically
    when launched with CWD = workdir (see `run_ngspice`).
    """
    (workdir / ".spiceinit").write_text(
        "set ngbehavior=ps\nset ng_nomodcheck\n",
        encoding="utf-8",
    )


def run_ngspice(cir_path: Path, ngspice: Path, *, timeout: int = 180) -> str:
    """Run ngspice in batch mode and capture stdout.

    Sets CWD to the .cir's parent directory so the sibling `.spiceinit`
    (written by `write_spice_init`) is picked up. Decodes as UTF-8
    with replacement so any model-vendor wide-char comments survive.

    On non-zero exit: prints stdout/stderr and SystemExit with the
    ngspice return code in the message. Consumers must not catch this
    quietly - a SPICE runtime error is a hard FAIL.
    """
    result = subprocess.run(
        [str(ngspice), "-b", str(cir_path.name)],
        cwd=str(cir_path.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(f"ngspice failed (exit {result.returncode}).")
    return result.stdout


# Measurement parsing -------------------------------------------------------
def parse_meas(output: str, name: str) -> float | None:
    """Parse an ngspice `print` line of the form `name = value`.

    Returns the float value or None if the named measurement is absent
    (e.g. the `.meas` directive failed to find a crossing). Consumers
    that require the value should check for None and raise/abort with
    the full ngspice stdout for diagnosis.

    Matches scientific notation (`1.234e-3`) and signed values.
    """
    m = re.search(
        rf"^\s*{re.escape(name)}\s*=\s*([-+\d.eE]+)",
        output,
        re.MULTILINE,
    )
    return float(m.group(1)) if m else None


# Smoke test (standalone run) ----------------------------------------------
def _smoke_test() -> int:
    """Verify the module works end-to-end: download (if needed), then run
    a trivial netlist through ngspice. Returns process exit code."""
    print("=== _spice.py smoke test ===")
    print()
    ngspice = ensure_ngspice()
    print(f"  ngspice located at: {ngspice}")
    print()

    workdir = CACHE_DIR / "_smoketest"
    workdir.mkdir(parents=True, exist_ok=True)
    write_spice_init(workdir)

    # Trivial: a 1 V source across a 1-ohm resistor, op-point + meas.
    # Use a tran sweep so .meas can run (op-only meas is awkward).
    cir = workdir / "smoke.cir"
    cir.write_text(
        "* _spice.py smoke test\n"
        "v1 1 0 PWL(0 0 1m 1)\n"
        "r1 1 0 1\n"
        ".tran 1u 2m UIC\n"
        ".control\n"
        "run\n"
        "meas tran v_end FIND v(1) AT=1.5m\n"
        "print v_end\n"
        "quit\n"
        ".endc\n"
        ".end\n",
        encoding="utf-8",
    )

    output = run_ngspice(cir, ngspice)
    v_end = parse_meas(output, "v_end")
    if v_end is None:
        print(output)
        print("[FAIL] smoke test: could not parse v_end from ngspice output.")
        return 1
    print(f"  v_end = {v_end:.4f} V (expected ~1.0 V)")
    if not (0.95 <= v_end <= 1.05):
        print(f"[FAIL] smoke test: v_end outside [0.95, 1.05] V window.")
        return 1

    # Exercise CheckResult round-trip too (typing + repr).
    r = CheckResult(
        name="smoke test PWL endpoint",
        value=f"{v_end:.3f} V",
        spec="[0.95, 1.05] V",
        passed=True,
    )
    print(r)
    print()
    print("[OK]   _spice.py smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(_smoke_test())
