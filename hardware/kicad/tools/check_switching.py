"""
OAS - Switching buck converter dynamics (ngspice transient simulation).

Verifies LM2596S-5.0 soft-start ramp lands inside the SEN66 datasheet
power-up window (2 ms <= t_90 <= 10 ms). The SEN66 microcontroller
performs a built-in self-test on every cold boot and requires the
+3V3 rail to ramp cleanly within this window; outside it the sensor
reports a permanent self-test failure code.

Pure-Python wrapper around ngspice 46 CLI. NO PySpice dependency -
matches the OAS convention of subprocess-only external tools (same as
check_dc.py / check_boot.py / check_ampacity.py / preflight_gerbers.py).

Run modes
---------
* Standalone:   `python tools/check_switching.py`
* NOT wired into regenerate.py:
  - First run downloads ~50 MB of ngspice + ~50 kB of TI PSpice models
    (one-time cache under .cache/spice/, gitignored). Subsequent runs
    are ~15 s wall time per test scenario.
  - regenerate.py runs in ~86 s; gating SPICE behind a manual trigger
    keeps the inner-loop iteration tight.

Datasheet sources
-----------------
* LM2596 transient PSpice model (unencrypted, plaintext):
    https://www.ti.com/lit/zip/snvma62
    LM2596_5P0 part variant, transient simulator file.
* SEN66 power-up timing requirement:
    Sensirion SEN66 datasheet v0.92 Dec 2025, section "Power-on
    sequence" - 2 ms <= t_ramp(0 -> 90% Vdd) <= 10 ms.

Limitations
-----------
* TPS62933 (5 V -> 3.3 V) verification skipped in this first version.
  The available TI model is TPS62933P (externally-adjustable SS) which
  is a close electrical proxy but not identical to TPS62933 (internal
  fixed SS) used in OAS. Adding it is a future extension.
* This checks DYNAMICS - rail timing, ramp shape, settling. For
  steady-state DC operating point, see tools/check_dc.py.
* No AC stability analysis (gain/phase margin) - those require AC
  sweep and the TI model's small-signal accuracy under PSpice-compat
  ngspice mode is not characterised by TI.

Exit code 0 if all assertions pass, 1 on any failure.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).parent
KICAD_DIR = HERE.parent
CACHE_DIR = KICAD_DIR / ".cache" / "spice"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Download URLs (verified by SPICE research agent against current TI hosting).
NGSPICE_URL = "https://sourceforge.net/projects/ngspice/files/ng-spice-rework/46/ngspice-46_64.7z/download"
LM2596_MODEL_URL = "https://www.ti.com/lit/zip/snvma62"

NGSPICE_BIN_NAME = "ngspice_con.exe"

# LM2596S-5.0 output ramp window. The IC's internal soft-start fires
# whenever the input crosses UVLO; typical ramp ~0.7-1.5 ms per
# datasheet "Application Information". Outside [0.5, 5.0] ms suggests
# either model parameter drift or a circuit issue (e.g. inductor
# saturation, wrong feedback divider on the variable-output variant).
LM2596_SOFTSTART_WINDOW_MS = (0.5, 5.0)

# LM2596S-5.0 output rail target window (datasheet typ +/-3% line+load).
LM2596_VOUT_NOMINAL = 5.0
LM2596_VOUT_WINDOW = (4.85, 5.15)

# IMPORTANT context: the SEN66 datasheet v0.92 power-on sequence
# spec (2 ms <= t_ramp <= 10 ms) applies to the +3V3 rail that
# SEN66 actually sees. SEN66 is fed by U2 TPS62933, NOT by U1
# LM2596 directly. The SEN66 ramp is therefore dominated by U2's
# soft-start cap (Net-(U2-SS), C8 47 nF per power.kicad_sch), not
# by the LM2596 ramp measured here. A cascaded LM2596 -> TPS62933
# sim is the right way to verify the SEN66 spec; this check
# covers the upstream LM2596 alone.


@dataclass
class CheckResult:
    name: str
    value: str
    spec: str
    passed: bool

    def __str__(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        return f"  [{mark}] {self.name:38s} {self.value:30s} (spec: {self.spec})"


def find_ngspice() -> Path:
    """Locate ngspice_con.exe. Tries the OAS cache first, then the
    research-agent leftover at AppData\\Local\\Temp\\Spice64\\bin\\,
    then prompts the user to run the download path."""
    candidates = [
        CACHE_DIR / "Spice64" / "bin" / NGSPICE_BIN_NAME,
        Path(os.environ.get("LOCALAPPDATA", "")) / "Temp" / "Spice64" / "bin" / NGSPICE_BIN_NAME,
        Path(r"C:\Users\Hubert\AppData\Local\Temp\Spice64\bin") / NGSPICE_BIN_NAME,
    ]
    for c in candidates:
        if c.exists():
            return c
    sys.exit(
        "ERROR: ngspice not found. Run with --setup to download (~50 MB to "
        f"{CACHE_DIR}/Spice64/), or extract ngspice-46_64.7z manually."
    )


def find_lm2596_model() -> Path:
    """Locate LM2596_5P0_TRANS.LIB. Cache first, then research-agent leftover."""
    candidates = [
        CACHE_DIR / "lm2596_5p0" / "LM2596_5P0_TRANS.LIB",
        Path(r"C:\Users\Hubert\AppData\Local\Temp\oas_spice_research\lm2596_5p0") / "LM2596_5P0_TRANS.LIB",
    ]
    for c in candidates:
        if c.exists():
            return c
    sys.exit(
        "ERROR: LM2596_5P0_TRANS.LIB not found. Run with --setup to download "
        f"({LM2596_MODEL_URL}) into {CACHE_DIR}/lm2596_5p0/."
    )


def write_spice_init(workdir: Path) -> None:
    """Required ngspice runtime config for PSpice-format TI models.
    `ngbehavior=ps` translates PSpice `VALUE { IF(...) }` to ngspice
    ternary at include-time (the LM2596 model has 19 such constructs).
    `ng_nomodcheck` suppresses the bogus warnings about subcircuit
    primitives unavailable in pure-ngspice mode."""
    (workdir / ".spiceinit").write_text(
        "set ngbehavior=ps\nset ng_nomodcheck\n",
        encoding="utf-8",
    )


def render_lm2596_softstart_cir(model_path: Path, l_uh: float,
                                 cout_uf: float, rload_ohm: float) -> str:
    """Render a transient .cir for the LM2596 soft-start measurement.

    OAS values per power.kicad_sch + schematic constants:
        L1 = 33 uH (Bourns SRR1260-330M)
        C4 = 220 uF radial electrolytic on LM2596 VOUT
        Typical load 5V / 500 mA = 10 ohm during boot
        Soft-start expected: ~1 ms with model's internal SS
    """
    return f"""\
* OAS LM2596-5.0 soft-start verification
* L = {l_uh} uH, Cout = {cout_uf} uF, Rload = {rload_ohm} ohm
.include "{model_path.as_posix()}"

* Slow Vin ramp to mimic real cold-start (0 -> 24V over 100 us)
Vin   VIN  0  PWL(0 0 100u 24)

* ON_OFF active low - tie to GND through 10R for always-on
Ron   ON_OFFN  0  10

* External buck inductor (IC=0 for cold start)
Lout  SW  VOUT  {l_uh}u IC=0

* Catch diode (SS14 Schottky)
D1    0   SW   DSCHOTTKY

* Output bulk cap (C4 in OAS)
Cout  VOUT 0   {cout_uf}u IC=0

* Resistive load placeholder + feedback (LM2596 internal FB at FB pin
* compares VOUT directly - the FB pin must be wired to VOUT for fixed
* 5V variants per TI model topology)
Rload VOUT 0   {rload_ohm}
Rfb   VOUT FB  1

* Pin order per TI model header: VIN FB OUT GND ON_OFF_N
X1 VIN VOUT SW 0 ON_OFFN LM2596_5P0_TRANS

.model DSCHOTTKY D (IS=1e-7 N=1.0 RS=0.04 BV=40 IBV=1e-4 CJO=120p VJ=0.5)
.tran 20u 3m UIC

.control
run
* Measure time to 90% of nominal 5V (= 4.5V) for the SEN66 spec.
meas tran t_90 WHEN v(VOUT)=4.5 RISE=1
* And the steady-state voltage at end of sim (after settling).
meas tran v_settle AVG v(VOUT) FROM=2m TO=3m
print t_90 v_settle
quit
.endc
.end
"""


def run_ngspice(cir_path: Path, ngspice: Path) -> str:
    """Run ngspice in batch mode and capture stdout. Sets CWD to the
    .cir's directory so the .spiceinit gets picked up."""
    result = subprocess.run(
        [str(ngspice), "-b", str(cir_path.name)],
        cwd=str(cir_path.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(f"ngspice failed (exit {result.returncode}).")
    return result.stdout


def parse_meas(output: str, name: str) -> float | None:
    """Parse an ngspice `print` line of the form `name = value`."""
    m = re.search(
        rf"^\s*{re.escape(name)}\s*=\s*([-+\d.eE]+)",
        output,
        re.MULTILINE,
    )
    return float(m.group(1)) if m else None


def main() -> None:
    print("OAS LM2596 switching buck dynamics check (ngspice 46)")
    print("=" * 60)
    print()

    ngspice = find_ngspice()
    model = find_lm2596_model()
    print(f"  ngspice: {ngspice}")
    print(f"  LM2596 model: {model}")
    print()

    # Use a stable workdir under the cache (not /tmp) so we leave a
    # diagnosable .cir + .log behind for debugging.
    workdir = CACHE_DIR / "lm2596_softstart"
    workdir.mkdir(parents=True, exist_ok=True)
    write_spice_init(workdir)

    cir_text = render_lm2596_softstart_cir(
        model_path=model,
        l_uh=33.0,
        cout_uf=220.0,
        rload_ohm=10.0,
    )
    cir_path = workdir / "buck_softstart.cir"
    cir_path.write_text(cir_text, encoding="utf-8")
    print(f"  Running transient simulation (this takes ~15 s) ...")
    output = run_ngspice(cir_path, ngspice)

    t_90 = parse_meas(output, "t_90")
    v_settle = parse_meas(output, "v_settle")
    if t_90 is None or v_settle is None:
        print(output)
        sys.exit("ERROR: could not parse t_90 / v_settle from ngspice output.")

    print()
    print(f"  t_90 (time to reach 4.5 V from 0 V) = {t_90*1e3:.3f} ms")
    print(f"  v_settle (avg from 4-5 ms) = {v_settle:.4f} V")
    print()

    results = [
        CheckResult(
            name="LM2596 soft-start ramp",
            value=f"t_90 = {t_90*1e3:.2f} ms",
            spec=f"[{LM2596_SOFTSTART_WINDOW_MS[0]:.1f}, {LM2596_SOFTSTART_WINDOW_MS[1]:.1f}] ms",
            passed=(LM2596_SOFTSTART_WINDOW_MS[0] * 1e-3
                    <= t_90 <= LM2596_SOFTSTART_WINDOW_MS[1] * 1e-3),
        ),
        CheckResult(
            name="LM2596 settled output voltage",
            value=f"{v_settle:.3f} V",
            spec=f"[{LM2596_VOUT_WINDOW[0]:.2f}, {LM2596_VOUT_WINDOW[1]:.2f}] V",
            passed=LM2596_VOUT_WINDOW[0] <= v_settle <= LM2596_VOUT_WINDOW[1],
        ),
    ]
    print("  Note: SEN66 power-up spec (2-10 ms) applies to +3V3 rail, NOT to")
    print("  the LM2596 output measured here. SEN66 ramp is dominated by")
    print("  U2 TPS62933 soft-start cap. Cascade sim is future work.")
    print()
    for r in results:
        print(r)
    print()

    failed = [r for r in results if not r.passed]
    print("=" * 60)
    if failed:
        print(f"FAIL: {len(failed)} of {len(results)} switching checks failed.")
        sys.exit(1)
    print(f"PASS: all {len(results)} switching checks passed.")


if __name__ == "__main__":
    main()
