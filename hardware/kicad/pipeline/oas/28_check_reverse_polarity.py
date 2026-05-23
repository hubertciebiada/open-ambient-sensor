"""
OAS - Reverse-polarity Vgs(Q1) clamp verification (ngspice transient).

Simulates the OAS input-protection cluster under REVERSE polarity at J1
(applied -24 V across the terminals, i.e. J1.1 = -24 V relative to J1.2
which is the local GND reference), and verifies that the BZT52C10S Zener
clamp (D3) + R4 (1 k series) + R1 (100 k pulldown) hold Q1's |Vgs|
strictly below the AO3401A Vgs_max = +/-12 V absolute-maximum rating
(Lesson 6 - read from datasheet, not from memory).

In normal +24 V operation, D3 acts as a Zener (reverse breakdown at
Vz ~= 10 V) and clamps Vgs at ~-10 V so the channel turns fully on with
low Rds_on. Under REVERSE polarity (VIN = -24 V at Q1.S), the polarity
of every node flips: Q1.S = -24 V, gate gets pulled toward GND through
R1 - that would set Vgs = +24 V (24 V over the +/-12 V absolute maximum,
guaranteed to destroy AO3401A and defeat the reverse-polarity protection
on first power-up). D3 is now FORWARD-biased (cathode at -24 V, anode at
junction sitting near 0 V); it conducts at ~0.7 V drop, pulling the gate
side of R4 to v(S) + Vf ~= -23.3 V, so Vgs ~= +0.7 V. The forward-diode
clamp is far safer than the Zener clamp at +24 V swing.

EXPECTED OUTCOME: both scenarios PASS comfortably. Sustained reverse
polarity should land |Vgs| ~= 0.7-1.0 V (D3 forward-drop + small
contribution from the gate-to-source capacitance partial dV charge).
The -60 V / 1 us transient (arc-during-mating) should peak at a few
volts at most because the R4 + Cgs LPF (tau ~= 7 ns) is fast enough vs
the 1 us pulse, but the Zener gate clamp loop itself is far faster than
the pulse width and the Cgs/Cgd ratio is small (~7p/15p), so the gate
peak is limited.

Acceptance criteria (tight, per spec):
    |vgs_steady| <= 11.0 V   (Scenario A, measured at t = 2 ms)
    |vgs_peak|   <= 11.0 V   (Scenario B, MAX abs over 0-2 us window)

11.0 V leaves only 1.0 V buffer under AO3401A's hard +/-12 V Vgs_max.
DO NOT relax this threshold if a check fails - the failure means R4
is too high, the Zener is too slow, or the gate dV/dt overshoot races
the Zener engagement, all of which need a board-level fix, not a
test-bench fix.

Run modes
---------
* Pipeline stage:  invoked from build.py as stage 28.
* Standalone:      `python pipeline/oas/28_check_reverse_polarity.py`.

Self-provisioning, NO soft-skip: on first run the stage auto-downloads
ngspice 46 (via _spice.ensure_ngspice) plus the AO3401A community VDMOS
model + the Diodes Inc. Zener pack into `.tmp/spice/reverse_polarity/`.
Subsequent runs reuse the cache. HARD FAIL on any download / extract
failure.

Model sources
-------------
* AO3401A (Alpha & Omega, community LTspice port by rdmeneze):
    https://raw.githubusercontent.com/rdmeneze/LTSpiceModels/master/AO3401A.mod
  Same community .SUBCKT used by stage 27. PMOS Level-3 with explicit
  Cgs ~= 30 pF and implicit Cgd via the body-diode parasitic. Fidelity
  at ns-scale: +/-30 % per community testing - the 100 ns rise edge of
  Scenario A and the 1 us pulse of Scenario B are both at or above the
  model's "good" timescale.
* BZT52C10S (Diodes Inc. SOD-323 200 mW Zener):
    https://www.diodes.com/productcollection/spicemodels/8345/Zener+Diodes.spice.txt?eid=88
  Giant concatenation of ~150 Zener subckts (~270 kB total). Stage
  extracts `.SUBCKT DI_BZT52C10S 1 2 ... .ENDS` via regex (subckt name
  `DI_BZT52C10S`, terminals 1=A, 2=K per the file header comment).
  Internal: DF (forward) + DR (reverse breakdown, VZ ~= 7.76 V + Vf ~=
  2 V -> total clamp ~= 10 V which lands inside the Vishay
  Vz(min/typ/max) = 9.4 / 10.0 / 10.6 V envelope at IZT=5 mA).

  Fallback: if the Diodes URL is unreachable OR the extract regex fails
  OR ngspice rejects the subckt, a generic 10 V Zener .MODEL is used in
  place of the subckt. This is documented in the .cir text comment so a
  forensic reader can tell at a glance which model produced the result.

Two scenarios in one stage:
---------------------------
* Scenario A "sustained reverse polarity":
  VIN PWL = 0 -> -24 V with 100 ns rise edge, hold 5 ms.
  Models a slow bench-supply swap of polarity. Measure
  `vgs_steady = v(q1_g, q1_s)` at t = 2 ms (well after the 100 ns edge
  has propagated through R4*Cgs ~= 7 ns RC and any transient settling).

* Scenario B "transient arc-during-mating":
  VIN PWL = 0 V flat 100 ns, then a -60 V / 1 us rectangular pulse,
  then back to 0 V. Models worst-case contact-bounce arc on the screw
  terminal during a misconnect attempt. Measure `vgs_peak = MAX(abs(
  v(q1_g, q1_s)))` over the 0-2 us window.

Each scenario is a separate .cir deck (clean DC operating point, no
cross-contamination between sims).

Exit code 0 if both checks pass; 1 on any assertion failure, ngspice
runtime error, or missing-dependency hard-fail.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
from _common import Stage  # noqa: E402

# _spice.py is a sibling module in pipeline/oas/.
sys.path.insert(0, str(HERE))
from _spice import (  # noqa: E402
    CACHE_DIR,
    CheckResult,
    _download,
    ensure_ngspice,
    parse_meas,
    run_ngspice,
    write_spice_init,
)

# Cache subdir (sibling to .tmp/spice/surge/, .tmp/spice/lm2596_5p0/).
REV_CACHE = CACHE_DIR / "reverse_polarity"

# Model URLs.
AO3401A_URL = "https://raw.githubusercontent.com/rdmeneze/LTSpiceModels/master/AO3401A.mod"
ZENER_PACK_URL = (
    "https://www.diodes.com/productcollection/spicemodels/8345/"
    "Zener+Diodes.spice.txt?eid=88"
)

# Vgs absolute-max envelope per AO3401A datasheet (Alpha & Omega).
# AO3401A datasheet rev D1, June 2014, Table "Absolute Maximum Ratings":
#   Vgs = +/-12 V (NOT +/-20 V as the v0.35-and-earlier comments claimed -
#   Lesson 6, hallucinated value caught by audit-16).
VGS_MAX_V = 12.0

# Acceptance threshold: 1 V buffer under the 12 V hard limit, leaving
# 1 V for AO3401A VDMOS model fidelity (+/-30 % at ns-scale per community
# testing) + Diodes Zener model fidelity vs the real BZT52C10S spread
# (Vz_min/typ/max = 9.4 / 10.0 / 10.6 V at IZT=5 mA per Vishay BZT52
# series datasheet).
VGS_THRESH_V = 11.0

# Nominal +24 V (the polarity is flipped in this stage's PWL sources).
V_DC_NOMINAL = 24.0

# Source impedance on the PWL source (small, but non-zero to avoid
# singular-matrix issues with ideal voltage sources during the fast
# edge transients).
R_SOURCE_OHM = 0.5

# Component values - mirror the schematic. Authoritative source is
# boardgen/_sch_power.py (R1=100k, R4=1k, D3=BZT52C10S).
R_R4_OHM = 1_000.0
R_R1_OHM = 100_000.0

# Drain rail bulk capacitance approximation - C1 (100 uF) + the LM2596
# input loop's combined ceramic bypass. For the gate-clamp question this
# is a load, not a stress factor; conservative 100 uF.
C_DRAIN_F = 100e-6


# ---------------------------------------------------------------------
# Model fetchers
# ---------------------------------------------------------------------
def ensure_ao3401a_model() -> Path:
    """Idempotent download of the AO3401A community LTSpice .mod.
    Returns the local path. Hard-fails on download error."""
    target = REV_CACHE / "AO3401A.mod"
    if target.exists() and target.stat().st_size > 0:
        return target
    print("  AO3401A SPICE model not in cache - downloading from rdmeneze GitHub")
    _download(AO3401A_URL, target)
    if target.stat().st_size == 0:
        sys.exit(f"[FAIL] {target} downloaded as empty file.")
    return target


def ensure_zener_pack() -> Path | None:
    """Idempotent download of the Diodes Inc. Zener pack (giant concat,
    ~274 kB plaintext of ~150 .SUBCKT blocks). Returns the local path on
    success, or None if the download fails (caller will switch to the
    generic-Zener .MODEL fallback)."""
    target = REV_CACHE / "Zener_Diodes.spice.txt"
    if target.exists() and target.stat().st_size > 0:
        return target
    print("  BZT52C10S SPICE pack not in cache - downloading from diodes.com")
    try:
        _download(ZENER_PACK_URL, target)
    except Exception as exc:  # network error, redirect loop, etc.
        print(f"  WARN: Zener pack download failed: {exc!r}")
        return None
    if target.stat().st_size == 0:
        print(f"  WARN: {target} downloaded as empty file")
        return None
    return target


def extract_ao3401a_subckt(model_path: Path) -> str:
    """Return the .SUBCKT AO3401A block + its .MODEL declarations."""
    text = model_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(
        r"(?ims)^\.SUBCKT\s+AO3401A\b.*?^\.ENDS\b.*?$",
        text,
    )
    if not m:
        sys.exit(
            f"[FAIL] could not extract .SUBCKT AO3401A from {model_path}. "
            "Community model file layout may have changed."
        )
    return m.group(0)


def extract_bzt52c10s_subckt(pack_path: Path) -> str | None:
    """Return the .SUBCKT DI_BZT52C10S ... .ENDS block from the Diodes
    Inc. Zener pack.

    The pack has a quirk: some subckts end with `.ENDS` on its own line,
    others have `.ENDS` immediately concatenated to the previous .MODEL
    line (e.g. `... TT=50.1n ).ENDS`). The DI_BZT52C10S block is the
    second kind (line 542 = `.MODEL DR D ( IS=1.65f RS=4.60 N=2.97 ).ENDS`).
    Regex must NOT require `.ENDS` to be at start-of-line.

    Returns the matched block text, or None if the subckt is absent or
    the regex cannot anchor (caller will switch to the generic-Zener
    fallback)."""
    text = pack_path.read_text(encoding="utf-8", errors="replace")
    # Anchor the START at line-begin (`^\.SUBCKT\s+DI_BZT52C10S\b`); the
    # END can be `.ENDS` anywhere on a subsequent line (most blocks) or
    # tacked onto a .MODEL line (DI_BZT52C10S specifically). Use the
    # NON-greedy `.*?\.ENDS\b` and then consume to the next newline (or
    # EOF) so the whole closing line is captured.
    m = re.search(
        r"(?ims)^\.SUBCKT\s+DI_BZT52C10S\b.*?\.ENDS\b[^\n]*",
        text,
    )
    if not m:
        return None
    block = m.group(0)
    # ngspice's parser requires `.ENDS` to begin a fresh line. The
    # DI_BZT52C10S block in the Diodes pack has `.ENDS` glued onto the
    # tail of the preceding `.MODEL DR D ( ... ).ENDS`, which trips a
    # ".subckt ... .ends mismatch" error. Split it onto its own line.
    block = re.sub(r"(\S)\s*(\.ENDS\b)", r"\1\n\2", block)
    return block


# ---------------------------------------------------------------------
# .cir renderers - one per scenario
# ---------------------------------------------------------------------
# Net naming convention (shared between Scenario A and Scenario B):
#   0         : local GND reference (J1.2 in the schematic).
#   vin       : J1.1 net = Q1 SOURCE = D3 CATHODE = D1 (TVS) cathode in
#               the surge stage; here D1 is omitted because its forward-
#               direction current under reverse polarity is negligible
#               (SMBJ24A forward Vf < 1 V at low current; effectively a
#               short from vin to 0 V when vin < -0.7 V, BUT the analysis
#               is for the GATE clamp, not for the TVS limiter. Including
#               D1 only adds a near-short to 0V which CHANGES the topology
#               under test. We model just the gate-clamp loop in
#               isolation; the upstream-rail behaviour is the surge
#               stage's concern).
#   pwlnode   : PWL source positive terminal (Vsrc); Rsrc between it and
#               vin to give the voltage source a small impedance.
#   drain     : Q1 drain = downstream protected rail (loaded with Cdrain
#               + Rload).
#   gate      : Q1 gate = the node we measure Vgs against.
#   gnode     : the R4/R1 junction = anode of D3.

# AO3401A subckt header from rdmeneze .mod:
#   .SUBCKT AO3401A 4 1 2
# where 4=D, 1=G, 2=S (verified by inspection - see stage 27 comment).
# So external (D G S) = (4 1 2).
#
# DI_BZT52C10S subckt header from Diodes pack:
#   .SUBCKT DI_BZT52C10S 1 2
#   *  Terminals    A   K
# So external (A K) = (1 2).

def _build_cir_common_header(*, ao3401_subckt: str,
                             zener_subckt: str | None) -> str:
    """Emit the shared model definitions: AO3401A subckt + either the
    BZT52C10S subckt or the generic-Zener .MODEL fallback."""
    parts = [
        "* === AO3401A P-MOSFET model (rdmeneze community) ===",
        ao3401_subckt,
        "",
    ]
    if zener_subckt is not None:
        parts.extend([
            "* === BZT52C10S Zener model (Diodes Inc. pack) ===",
            zener_subckt,
            "",
        ])
    else:
        parts.extend([
            "* === BZT52C10S Zener (GENERIC FALLBACK - 10 V .MODEL) ===",
            "* Diodes pack URL was unreachable or extract regex failed.",
            "* Generic 10 V Zener with CJO matched to BZT52 datasheet (~80 pF).",
            ".MODEL DZ_BZT52C10S D (BV=10.0 IBV=5m N=1.5 RS=0.5 IS=1e-12",
            "+ CJO=80p TT=20n)",
            "",
        ])
    return "\n".join(parts)


def _build_clamp_topology() -> str:
    """Emit the R4 + R1 + D3 + Q1 + drain-load topology. Identical
    between Scenario A and Scenario B; only the PWL source changes."""
    return f"""\
* === Q1 AO3401A P-MOS: (D G S) = (drain gate vin) ===
XQ1 drain gate vin AO3401A

* === Gate clamp network ===
* R4 (1 k) in series between Q1.G and the R4/R1 junction (gnode).
* R1 (100 k) from gnode to GND.
* D3 BZT52C10S: cathode = vin (Q1.S side), anode = gnode.
*   - Forward (normal +24 V): D3 reverse-biased; breaks down at
*     Vz~=10 V to clamp Vgs at -10 V.
*   - Reverse polarity (this stage): D3 forward-biased; conducts at
*     Vf~=0.7 V to clamp Vgs at +0.7 V.
R4 gate gnode {R_R4_OHM:.3f}
R1 gnode 0 {R_R1_OHM:.3f}
* For the BZT52C10S Diodes subckt, terminals are (A K) -> (gnode vin).
* For the generic-fallback .MODEL DZ_BZT52C10S, the same node order
* matches (D model: anode then cathode for a forward-biased instance).
XD3 gnode vin DI_BZT52C10S
* Conditional alias: if the subckt was not found and we are using the
* generic .MODEL fallback, the XD3 line above is invalid (no subckt
* DI_BZT52C10S exists). The _render_cir code path injects a plain D
* element instead in that branch; see render_*_cir(zener_subckt=...).

* === Protected-rail load + bulk approximation ===
* Q1 OFF (Vgs ~= 0 V under reverse polarity) means the rail is isolated
* from vin. Just a small load + bulk cap so the drain node has a defined
* DC bias and the simulator can solve the operating point.
Rload drain 0 10k
Cdrain drain 0 {C_DRAIN_F:.3e} IC=0
"""


def _build_clamp_topology_generic_zener() -> str:
    """Variant of _build_clamp_topology() that uses a plain D element
    against the generic-Zener fallback .MODEL (no XD3 subckt call)."""
    return f"""\
* === Q1 AO3401A P-MOS: (D G S) = (drain gate vin) ===
XQ1 drain gate vin AO3401A

* === Gate clamp network (generic .MODEL fallback) ===
R4 gate gnode {R_R4_OHM:.3f}
R1 gnode 0 {R_R1_OHM:.3f}
* Plain D element against the .MODEL DZ_BZT52C10S declared above.
* Anode = gnode, Cathode = vin.
D3 gnode vin DZ_BZT52C10S

Rload drain 0 10k
Cdrain drain 0 {C_DRAIN_F:.3e} IC=0
"""


def render_scenario_a_cir(*, ao3401_subckt: str,
                          zener_subckt: str | None) -> str:
    """Scenario A: sustained reverse polarity.

    VIN PWL: 0 V at t=0, fall to -24 V across a 100 ns edge, hold for
    5 ms total. Measure vgs at t = 2 ms (steady-state).
    """
    header = _build_cir_common_header(
        ao3401_subckt=ao3401_subckt, zener_subckt=zener_subckt)
    topology = (
        _build_clamp_topology()
        if zener_subckt is not None
        else _build_clamp_topology_generic_zener()
    )
    return f"""\
* OAS reverse-polarity Vgs check: Scenario A (sustained -24 V)
{header}

* === PWL source: 0 V at t=0, -24 V at t=100 ns, hold to t=5 ms ===
Vpwl pwlnode 0 PWL(0 0 100n {-V_DC_NOMINAL:.3f} 5m {-V_DC_NOMINAL:.3f})
Rsrc pwlnode vin {R_SOURCE_OHM:.3f}

{topology}

* Transient sim: 5 ms total. UIC initial condition (Cdrain) noted; we
* let ngspice compute the DC operating point so D3 forward-bias settles
* cleanly. Gear method + tightened tolerances help with the fast 100 ns
* edge across the Zener loop.
.options method=gear reltol=1e-3 abstol=1e-9 vntol=1e-6
.tran 1u 5m

.control
run
* Steady-state Vgs at t = 2 ms (well after the 100 ns edge has fully
* propagated; R4*Cgs ~= 7 ns RC tau, settling is ~50 ns - 2 ms is
* essentially infinity on that timescale).
let vgs = v(gate)-v(vin)
let vgs_abs = abs(vgs)
meas tran vgs_steady FIND vgs AT=2m
meas tran vgs_steady_abs FIND vgs_abs AT=2m
* Worst-case abs(Vgs) anywhere in the 0.5 - 5 ms window (after the
* initial 100 ns edge settles); catches any oscillation we missed.
meas tran vgs_a_max MAX vgs_abs FROM=0.5m TO=5m
* Also report the Q1 source and gate node voltages for sanity.
meas tran vs_steady FIND v(vin) AT=2m
meas tran vg_steady FIND v(gate) AT=2m
print vgs_steady vgs_steady_abs vgs_a_max vs_steady vg_steady
quit
.endc
.end
"""


def render_scenario_b_cir(*, ao3401_subckt: str,
                          zener_subckt: str | None) -> str:
    """Scenario B: transient arc-during-mating.

    VIN PWL: 0 V flat for 100 ns, fall to -60 V across 20 ns, hold for
    1 us, rise back to 0 V across 20 ns, hold for another 1 us.
    Measure MAX(abs(vgs)) over the 0-2 us window.
    """
    header = _build_cir_common_header(
        ao3401_subckt=ao3401_subckt, zener_subckt=zener_subckt)
    topology = (
        _build_clamp_topology()
        if zener_subckt is not None
        else _build_clamp_topology_generic_zener()
    )
    # PWL: t=0 v=0, t=100 ns v=0, t=120 ns v=-60, t=1.12 us v=-60,
    #      t=1.14 us v=0, t=2 us v=0. Total ~2 us.
    pwl = (
        "PWL("
        "0 0 "
        "100n 0 "
        "120n -60 "
        "1.12u -60 "
        "1.14u 0 "
        "2u 0)"
    )
    return f"""\
* OAS reverse-polarity Vgs check: Scenario B (-60 V / 1 us arc pulse)
{header}

* === PWL source: -60 V / 1 us pulse with 20 ns edges ===
Vpwl pwlnode 0 {pwl}
Rsrc pwlnode vin {R_SOURCE_OHM:.3f}

{topology}

* Transient sim: 2 us total at 1 ns max step (resolves the 20 ns edges
* and the Zener engagement transient).
.options method=gear reltol=1e-3 abstol=1e-9 vntol=1e-6
.tran 1n 2u

.control
run
let vgs = v(gate)-v(vin)
let vgs_abs = abs(vgs)
* MAX abs Vgs across the full 2 us window.
meas tran vgs_peak MAX vgs_abs
* And the time at which the peak occurs (sanity vs the pulse edges at
* 120 ns and 1.14 us).
meas tran vgs_peak_signed MAX vgs
meas tran vgs_peak_neg MIN vgs
meas tran vs_min MIN v(vin)
meas tran vg_min MIN v(gate)
meas tran vg_max MAX v(gate)
print vgs_peak vgs_peak_signed vgs_peak_neg vs_min vg_min vg_max
quit
.endc
.end
"""


# ---------------------------------------------------------------------
# Per-scenario runner
# ---------------------------------------------------------------------
@dataclass
class ScenarioResult:
    label: str
    vgs_value: float           # Scenario A: vgs_steady; B: vgs_peak (already abs).
    vgs_signed: float | None   # For diagnostic - signed peak / steady.
    vs: float | None           # Q1 source voltage (vin) at measure point.
    vg: float | None           # Q1 gate voltage at measure point.
    raw_output: str            # full ngspice stdout for forensic dump on fail.


def run_scenario_a(*, workdir: Path, ngspice: Path,
                   ao3401_subckt: str,
                   zener_subckt: str | None) -> ScenarioResult:
    cir_text = render_scenario_a_cir(
        ao3401_subckt=ao3401_subckt, zener_subckt=zener_subckt)
    cir_path = workdir / "rev_scenario_a.cir"
    cir_path.write_text(cir_text, encoding="utf-8")
    print("  Scenario A: sustained -24 V (100 ns edge, 5 ms hold)")
    output = run_ngspice(cir_path, ngspice, timeout=180)

    vgs_signed = parse_meas(output, "vgs_steady")
    vgs_abs = parse_meas(output, "vgs_steady_abs")
    vgs_max_window = parse_meas(output, "vgs_a_max")
    vs = parse_meas(output, "vs_steady")
    vg = parse_meas(output, "vg_steady")

    if vgs_abs is None or vgs_signed is None or vgs_max_window is None:
        print(output)
        sys.exit(
            "[FAIL] could not parse vgs_steady / vgs_a_max from Scenario A "
            "ngspice output. Check meas syntax / model identifiers."
        )
    # Take the WORST of the steady-state point and the windowed max -
    # protects against the unlikely case of a slow oscillation that's
    # zero-crossing at exactly 2 ms.
    vgs_value = max(abs(vgs_abs), abs(vgs_max_window))
    return ScenarioResult(
        label="A_sustained", vgs_value=vgs_value, vgs_signed=vgs_signed,
        vs=vs, vg=vg, raw_output=output,
    )


def run_scenario_b(*, workdir: Path, ngspice: Path,
                   ao3401_subckt: str,
                   zener_subckt: str | None) -> ScenarioResult:
    cir_text = render_scenario_b_cir(
        ao3401_subckt=ao3401_subckt, zener_subckt=zener_subckt)
    cir_path = workdir / "rev_scenario_b.cir"
    cir_path.write_text(cir_text, encoding="utf-8")
    print("  Scenario B: -60 V / 1 us arc pulse (20 ns edges)")
    output = run_ngspice(cir_path, ngspice, timeout=180)

    vgs_peak = parse_meas(output, "vgs_peak")
    vgs_signed_max = parse_meas(output, "vgs_peak_signed")
    vgs_signed_min = parse_meas(output, "vgs_peak_neg")
    vs_min = parse_meas(output, "vs_min")
    vg_min = parse_meas(output, "vg_min")

    if vgs_peak is None:
        print(output)
        sys.exit(
            "[FAIL] could not parse vgs_peak from Scenario B ngspice output. "
            "Check meas syntax / model identifiers."
        )
    # vgs_peak is already abs() inside ngspice; pick the more extreme of
    # the two signed peaks for the diagnostic.
    signed: float | None = None
    if vgs_signed_max is not None and vgs_signed_min is not None:
        signed = (vgs_signed_max
                  if abs(vgs_signed_max) >= abs(vgs_signed_min)
                  else vgs_signed_min)
    return ScenarioResult(
        label="B_transient", vgs_value=vgs_peak, vgs_signed=signed,
        vs=vs_min, vg=vg_min, raw_output=output,
    )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main() -> int:
    with Stage("check_reverse_polarity") as s:
        s.info("OAS reverse-polarity Vgs(Q1) clamp verification (ngspice)")
        s.info("AO3401A Vgs_max = +/-12 V (datasheet, NOT +/-20 V - Lesson 6)")
        s.info(f"Acceptance: |Vgs| <= {VGS_THRESH_V:.1f} V "
               f"(1 V buffer under {VGS_MAX_V:.1f} V hard max)")
        s.info("Scenarios: A=sustained -24 V (100 ns edge, 5 ms hold); "
               "B=-60 V / 1 us arc pulse (20 ns edges)")

        REV_CACHE.mkdir(parents=True, exist_ok=True)

        # Provision binaries + models.
        ngspice = ensure_ngspice()
        ao_path = ensure_ao3401a_model()
        s.info(f"ngspice: {ngspice}")
        s.info(f"AO3401A model: {ao_path}")
        ao_subckt = extract_ao3401a_subckt(ao_path)
        s.info(f"AO3401A .SUBCKT extracted ({len(ao_subckt)} chars)")

        # Zener: optional - fall back to generic .MODEL if anything goes
        # wrong with the Diodes pack download / extract.
        zener_subckt: str | None = None
        zener_source = "generic-Zener .MODEL fallback"
        pack_path = ensure_zener_pack()
        if pack_path is not None:
            s.info(f"Diodes Zener pack: {pack_path} "
                   f"({pack_path.stat().st_size / 1024:.1f} kB)")
            zener_subckt = extract_bzt52c10s_subckt(pack_path)
            if zener_subckt is None:
                s.warn("BZT52C10S extract from Diodes pack returned None - "
                       "falling back to generic 10 V Zener .MODEL")
            else:
                s.info(f"DI_BZT52C10S .SUBCKT extracted "
                       f"({len(zener_subckt)} chars)")
                zener_source = "Diodes Inc. DI_BZT52C10S .SUBCKT"
        else:
            s.warn("Diodes Zener pack unavailable - falling back to "
                   "generic 10 V Zener .MODEL")
        s.info(f"Zener model in use: {zener_source}")

        # Workdir + .spiceinit (mirrors stage 27 / 08).
        workdir = REV_CACHE / "sim"
        workdir.mkdir(parents=True, exist_ok=True)
        write_spice_init(workdir)

        # Run both scenarios.
        try:
            scen_a = run_scenario_a(
                workdir=workdir, ngspice=ngspice,
                ao3401_subckt=ao_subckt, zener_subckt=zener_subckt,
            )
            scen_b = run_scenario_b(
                workdir=workdir, ngspice=ngspice,
                ao3401_subckt=ao_subckt, zener_subckt=zener_subckt,
            )
        except SystemExit:
            # _spice.run_ngspice() / parse_meas() failure - error already
            # printed; re-raise to abort the stage.
            raise

        # Report.
        print()
        s.info("Scenario A (sustained -24 V):")
        print(f"    vgs_steady (signed):  "
              f"{scen_a.vgs_signed:+.3f} V"
              if scen_a.vgs_signed is not None else
              "    vgs_steady (signed):  N/A")
        print(f"    vgs_steady (abs):     {scen_a.vgs_value:.3f} V")
        if scen_a.vs is not None and scen_a.vg is not None:
            print(f"    v(Q1.S) at 2 ms:      {scen_a.vs:+.3f} V")
            print(f"    v(Q1.G) at 2 ms:      {scen_a.vg:+.3f} V")
        print()
        s.info("Scenario B (-60 V / 1 us arc):")
        if scen_b.vgs_signed is not None:
            print(f"    vgs_peak (signed):    {scen_b.vgs_signed:+.3f} V")
        print(f"    vgs_peak (abs):       {scen_b.vgs_value:.3f} V")
        if scen_b.vs is not None and scen_b.vg is not None:
            print(f"    v(Q1.S) min:          {scen_b.vs:+.3f} V")
            print(f"    v(Q1.G) min:          {scen_b.vg:+.3f} V")
        print()

        # Build CheckResults.
        results = [
            CheckResult(
                name="Vgs steady (Scenario A, sustained -24 V)",
                value=f"{scen_a.vgs_value:.3f} V",
                spec=f"<= {VGS_THRESH_V:.1f} V",
                passed=scen_a.vgs_value <= VGS_THRESH_V,
            ),
            CheckResult(
                name="Vgs peak (Scenario B, -60 V / 1 us)",
                value=f"{scen_b.vgs_value:.3f} V",
                spec=f"<= {VGS_THRESH_V:.1f} V",
                passed=scen_b.vgs_value <= VGS_THRESH_V,
            ),
        ]
        for r in results:
            print(r)
        print()

        failed = [r for r in results if not r.passed]
        if failed:
            print(f"  AO3401A Vgs_max = +/-{VGS_MAX_V:.1f} V (datasheet).")
            print(f"  Threshold {VGS_THRESH_V:.1f} V leaves only "
                  f"{VGS_MAX_V - VGS_THRESH_V:.1f} V buffer.")
            print()
            print("  The reverse-polarity gate clamp (D3 BZT52C10S + R4 + R1)")
            print("  fails to hold Vgs within spec under at least one of the")
            print("  two scenarios. Possible board-level fixes (DO NOT relax")
            print("  this stage's threshold to paper over):")
            print("    - reduce R4 below 1 kOhm so the Zener engages faster")
            print("    - switch D3 to a faster / lower-Vz Zener (e.g.")
            print("      BZT52C7V5 at 7.5 V) for more headroom")
            print("    - substitute Q1 to a part with wider Vgs envelope")
            print("      (e.g. AO3401A -> a +/-20 V Vgs PMOS).")
            s.fail(f"{len(failed)} of {len(results)} reverse-polarity "
                   "Vgs checks failed")

        s.ok(f"all {len(results)} reverse-polarity Vgs checks passed - "
             f"D3+R4+R1 gate clamp holds |Vgs| <= {VGS_THRESH_V:.1f} V "
             "under both -24 V sustained and -60 V / 1 us transient.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
