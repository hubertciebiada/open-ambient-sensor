"""
OAS - IEC 61000-4-5 surge stress (ngspice transient).

Two independent surge simulations sharing the same upstream chain (TVS
D1 SMBJ24A -> L_trace -> Q1 AO3401A with R4/R1/D3 gate clamp), the
same surge source (200 V peak / 2 Ohm-source combination wave), and
the same L_trace sweep (12.5 / 25 / 37.5 nH), but with DIFFERENT
downstream models to answer two different physics questions:

  Sim 1 ("Q1 Vds worst-case"):
    Q1 drain sits on a deliberately weak 1 uF lumped cap + 100 Ohm
    load - all downstream energy absorption (F1, C1 bulk, C5+C6 input
    bypass on LM2596) is intentionally STRIPPED OUT so the simulation
    exposes the worst possible drain-vs-source voltage delta Q1 might
    see across the transient. ACCEPTANCE: |Vds| <= 30 V everywhere
    (AO3401A absolute max, no EAS rating published).

  Sim 2 ("LM2596 Vin realistic"):
    Full realistic downstream chain modelled in detail - C1 100 uF
    electrolytic with ESR (~50 mOhm Panasonic EEU-FR series typ.),
    F1 cold-resistance 0.1 Ohm series, ~15 nH PCB inductance from Q1
    drain to LM2596 Vin pin, then C5+C6 = ~32 uF input bypass at the
    LM2596 Vin node with ESR/ESL parasitics, plus a 10 mA LM2596
    quiescent current sink. ACCEPTANCE: |V(vin_lm2596)| <= 40 V
    everywhere (LM2596 SNVS124N §6.1 absolute max Vin).

The contrast is the diagnostic. Sim 1 answered "is Q1 itself at risk"
(answer: no, it stays ON as a near-zero-Vds pass element). Sim 2
answers the natural follow-up: "is the high drain voltage Sim 1
reported (~67 V) a real threat to the buck, or an artifact of the
deliberately conservative load model?" - by re-running with the bulk
energy absorption that physically IS on the OAS board.

EXPECTED OUTCOME (per research doc):
  Sim 1: PASS - Q1 Vds stays small because Q1 is fully ON.
  Sim 2: depends on the bulk-cap absorption. Open question on entry,
         which is the whole point of this follow-up.

DO NOT weaken either threshold to make a sim pass. Both thresholds
are part-datasheet absolute maxima; if either fails, the answer is a
BOM change (TVS choice, Q1 substitution, bigger bulk cap, additional
inductor in series), not a relaxed check.

Run modes
---------
* Pipeline stage:  invoked from build.py as stage 27.
* Standalone:      `python pipeline/oas/27_check_surge.py`.

Self-provisioning, NO soft-skip: on first run the stage auto-downloads
ngspice 46 (via _spice.ensure_ngspice) plus the SMBJ24A + AO3401A
SPICE models into `.tmp/spice/surge/`. Subsequent runs reuse the cache.
HARD FAIL on any download / extraction failure.

Model sources
-------------
* SMBJ24A (Vishay General Semiconductor, Allen Su 2016):
    https://www.vishay.com/docs/98017/_p_smbj24a.txt
  Plaintext .SUBCKT, ngspice-compatible with `set ngbehavior=ps`.
  Note: the LCSC part in the BOM is Brightking SMBJ24A (C87268). Both
  meet the JEDEC SMBJ envelope (Vc_max=38.9 V @ Ipp=80 A) so the
  Vishay model is a conservative stand-in.
* AO3401A (Alpha & Omega, community LTspice port by rdmeneze):
    https://raw.githubusercontent.com/rdmeneze/LTSpiceModels/master/AO3401A.mod
  Community PMOS Level-3 subcircuit. Cgs=30 pF explicit; Cgd is
  implicit in the body-diode parasitic. Fidelity at ns-scale: +/-30%
  per community testing - the 20 us surge timescale this stage cares
  about is well within the model's reliable envelope.

Surge waveform (IEC 61000-4-5 1.2/50 us voltage / 8/20 us current
combination wave, 2 Ohm source impedance):

    V(t) = V0 * (exp(-t/tau1) - exp(-t/tau2))
    tau1 = 3.911 us, tau2 = 92.8 ns
    V0 chosen so peak(V) = 200 V (open-circuit)  =>  V0 ~= 213 V

Sampled as a PWL with ~200 points across 0..100 us (covers the 1.2 us
front, the 50 us 50% decay tail, and ~50 us of post-surge settling).

Limitations
-----------
* L_trace = engineering estimate (25 nH default) for J1 -> D1 -> Q1
  loop, NOT a FastHenry extraction. Sweep +/-50% bounds the parasitic
  uncertainty.
* Sim 2's F1 cold-resistance = 0.1 Ohm is a midpoint of the Littelfuse
  1812L075/33DR datasheet R_min cold range (0.05..0.2 Ohm). The PTC
  thermal time constant is ms-scale, well above the surge envelope, so
  treating R_F1 as constant-cold across 100 us is physically correct.
* No coupling to the +5V / +3V3 rails - this stage isolates the
  input cluster. Downstream of LM2596 Vin is a separate question.
* PWL discretization: 200 sample points across 100 us = 500 ns step
  on the slow tail, refined to 25 ns step on the 1.2 us front.

Exit code 0 if ALL assertions across BOTH sims pass; 1 on any failure,
ngspice runtime error, or missing-dependency hard-fail.
"""
from __future__ import annotations

import math
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

# Surge cache subdir (sibling to .tmp/spice/lm2596_5p0/).
SURGE_CACHE = CACHE_DIR / "surge"

# Model URLs (verified 200 OK + non-empty: 708 B and 1241 B respectively).
SMBJ24A_URL = "https://www.vishay.com/docs/98017/_p_smbj24a.txt"
AO3401A_URL = "https://raw.githubusercontent.com/rdmeneze/LTSpiceModels/master/AO3401A.mod"

# AO3401A datasheet absolute-max Vds. No EAS energy rating is published,
# so this static limit governs the transient envelope too.
VDS_MAX_V = 30.0

# PCB parasitic inductance of the J1 -> D1 -> Q1 loop. Engineering
# estimate; sweep +/-50% to bound the uncertainty.
L_TRACE_NH_NOMINAL = 25.0
L_TRACE_SWEEP_NH = (12.5, 25.0, 37.5)

# IEC 61000-4-5 §6.2 - source impedance of the combination wave generator.
R_SOURCE_OHM = 2.0

# Nominal 24 V SELV input (steady-state DC).
V_DC_NOMINAL = 24.0

# IEC 61000-4-5 1.2/50 us voltage waveform analytic form:
#   V(t) = V0 * (exp(-t/tau1) - exp(-t/tau2))
# tau values per IEC 61000-4-5 Annex A (1.2/50 us double-exponential).
SURGE_PEAK_V = 200.0       # open-circuit peak (200 V test level, IEC class)
SURGE_TAU1_S = 3.911e-6    # decay time constant of the tail
SURGE_TAU2_S = 92.8e-9     # rise time constant of the front

# Representative resistive load on the protected rail (~100 Ohm models
# the bulk capacitance + downstream buck-input impedance during a 20 us
# transient: C5 + C6 = ~32 uF on the +Vin node; |Z|@50 kHz ~ 100 mOhm,
# but the practical AC impedance seen by Q1's drain during the ns-front
# is the loop impedance through to GND via the buck cap stack, which
# at fast dV/dt is dominated by ESR. Use 100 Ohm as a generic resistive
# proxy that lets the drain follow the source without artificially
# clamping it).
R_LOAD_OHM = 100.0

# --- Sim 2: realistic downstream chain (Q1 drain -> F1 -> LM2596 Vin) ---
# LM2596 SNVS124N §6.1 Absolute Maximum Ratings: Vin = 45 V abs max,
# recommended op <= 40 V. Use the recommended-op envelope as the hard
# limit (the absolute max is a destruction threshold; sitting at 45 V
# for a 20 us transient is "probably fine" by datasheet annex notes,
# but the 40 V recommended bound is the design intent we hold to).
V_LM2596_MAX_V = 40.0

# C1 bulk electrolytic on the V_24V_PROT rail (drain side of Q1).
# Panasonic EEU-FR1V101 series 100 uF/35 V radial typical ESR ~50 mOhm,
# ESL ~3 nH. The IC=24 V keeps it at steady-state at t=0.
C1_BULK_UF = 100.0
C1_ESR_MOHM = 50.0
C1_ESL_NH = 3.0

# F1 PTC cold-resistance (Littelfuse 1812L075/33DR datasheet typ R_min:
# 0.05..0.2 Ohm). The PTC thermal time constant is ms-scale, so for a
# ~100 us surge envelope F1 stays cold and acts as a pure resistor;
# 0.1 Ohm picks the geometric midpoint of the data sheet R_min range.
F1_COLD_OHM = 0.1

# PCB trace inductance from Q1 drain through C1 + F1 to LM2596 Vin.
# Short cluster trace (the J1 input bundle is tightly packed under ZT1
# per the v0.50 routing rework); ~15 nH is consistent with a 10..15 mm
# trace length and the same 5..7 mm/nH rule used for L_TRACE.
L_DRAIN_TO_LM_NH = 15.0

# LM2596 Vin input bypass: C5 (22 uF MLCC X7R 50 V) || C6 (10 uF MLCC
# X7R 50 V). Both have ESR ~2..5 mOhm and ESL ~0.5..1 nH for 1206/0805
# MLCC. Modelled as a SINGLE lumped 32 uF cap with the parallel-
# equivalent ESR/ESL since both caps sit ~mm apart at the LM2596 Vin
# pin (the Vin pad itself is the via aggregation point).
C56_BYPASS_UF = 32.0
C56_ESR_MOHM = 2.5            # parallel of two ~5 mOhm
C56_ESL_NH = 0.5

# LM2596 quiescent current: datasheet Iq typ 6 mA at switching, plus
# pre-soft-start standby ~50 uA. During a 20..100 us surge envelope
# the buck either keeps switching (Iq ~ 6 mA) or trips into UVLO/OVP
# (Iq drops). Pick 10 mA as a representative round number that lets
# the bulk cap actually have a steady-state load at t=0 - small enough
# that it does not appreciably bleed C1 during the surge tail.
I_LM2596_QUIESCENT_MA = 10.0


# ---------------------------------------------------------------------
# Model fetchers
# ---------------------------------------------------------------------
def ensure_smbj24a_model() -> Path:
    """Idempotent download of the Vishay SMBJ24A plaintext .SUBCKT.
    Returns the local path. Hard-fails on download error."""
    target = SURGE_CACHE / "_p_smbj24a.txt"
    if target.exists() and target.stat().st_size > 0:
        return target
    print("  SMBJ24A SPICE model not in cache - downloading from Vishay")
    _download(SMBJ24A_URL, target)
    if target.stat().st_size == 0:
        sys.exit(f"[FAIL] {target} downloaded as empty file.")
    return target


def ensure_ao3401a_model() -> Path:
    """Idempotent download of the AO3401A community LTSpice .mod.
    Returns the local path. Hard-fails on download error."""
    target = SURGE_CACHE / "AO3401A.mod"
    if target.exists() and target.stat().st_size > 0:
        return target
    print("  AO3401A SPICE model not in cache - downloading from rdmeneze GitHub")
    _download(AO3401A_URL, target)
    if target.stat().st_size == 0:
        sys.exit(f"[FAIL] {target} downloaded as empty file.")
    return target


def extract_smbj24a_subckt(model_path: Path) -> str:
    """Return just the .SUBCKT smbj24a ... .ENDS block. The Vishay
    file already contains exactly one such block (708 B total); the
    extraction protects against future header changes that might add
    extra Vishay metadata, ngspice .control sections, etc."""
    text = model_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(
        r"(?ims)^\.SUBCKT\s+smbj24a\b.*?^\.ENDS\b.*?$",
        text,
    )
    if not m:
        sys.exit(
            f"[FAIL] could not extract .SUBCKT smbj24a from {model_path}. "
            "Vishay file layout may have changed."
        )
    return m.group(0)


def extract_ao3401a_subckt(model_path: Path) -> str:
    """Return the .SUBCKT AO3401A block + its .MODEL declarations. The
    rdmeneze .mod is structured as `.SUBCKT ... .ENDS` with the .MODEL
    cards INSIDE the subckt, so extraction is a single .SUBCKT..ENDS
    region match (regex anchored at start-of-line, multiline + DOTALL)."""
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


# ---------------------------------------------------------------------
# Surge PWL synthesis
# ---------------------------------------------------------------------
def synth_surge_pwl(*, n_front: int = 60, n_tail: int = 140,
                    t_total_s: float = 100e-6) -> list[tuple[float, float]]:
    """Sample the 1.2/50 us voltage double-exponential as a PWL.

    Returns a list of (t, v) tuples to be emitted as `PWL(t1 v1 t2 v2 ...)`.

    Uses a two-region time grid:
      * `n_front` log-spaced points across 0..2.5 us (captures the
        ~1.2 us rise + peak).
      * `n_tail`  linear points across 2.5 us..t_total_s (captures
        the 50 us 50%-decay tail + post-surge settling toward 0).

    The peak of (exp(-t/tau1) - exp(-t/tau2)) occurs at:
        t_peak = (tau1*tau2 / (tau1-tau2)) * ln(tau1/tau2)
    For tau1=3.911e-6, tau2=92.8e-9: t_peak ~= 358 ns; the headline
    "1.2 us front" is the time TO HALF-PEAK on the rise, not to peak.
    We rescale V0 so that peak(V) = SURGE_PEAK_V exactly.
    """
    tau1 = SURGE_TAU1_S
    tau2 = SURGE_TAU2_S
    # Time of peak (analytic).
    t_peak = (tau1 * tau2 / (tau1 - tau2)) * math.log(tau1 / tau2)
    # Unit-V0 peak amplitude.
    peak_unit = math.exp(-t_peak / tau1) - math.exp(-t_peak / tau2)
    V0 = SURGE_PEAK_V / peak_unit  # ~= 213 V

    # Front grid: log-spaced t in (0, 2.5 us] to resolve the ns-scale
    # rise + the ~358 ns peak. We start at t=10 ns to avoid log(0).
    front_pts: list[float] = []
    for i in range(n_front):
        # frac in (0, 1]; log space from 10 ns to 2.5 us.
        frac = (i + 1) / n_front
        t = 10e-9 * (2.5e-6 / 10e-9) ** frac
        front_pts.append(t)

    # Tail grid: linear t in (2.5 us, t_total_s].
    tail_pts: list[float] = []
    t0 = 2.5e-6
    for i in range(1, n_tail + 1):
        t = t0 + (t_total_s - t0) * i / n_tail
        tail_pts.append(t)

    # Build (t, v) including t=0 anchor.
    pts: list[tuple[float, float]] = [(0.0, 0.0)]
    for t in front_pts + tail_pts:
        v = V0 * (math.exp(-t / tau1) - math.exp(-t / tau2))
        pts.append((t, v))
    return pts


def format_pwl_args(pts: list[tuple[float, float]]) -> str:
    """Format the PWL pairs into ngspice syntax with engineering suffixes."""
    parts = []
    for t, v in pts:
        # ngspice PWL accepts plain SI engineering numbers; emit ns for
        # sub-us, us above that. Voltage as plain float.
        if t < 1e-6:
            t_str = f"{t * 1e9:.3f}n"
        else:
            t_str = f"{t * 1e6:.3f}u"
        parts.append(f"{t_str} {v:.4f}")
    # Wrap lines at ~6 pairs each for readability of the cached .cir.
    out = []
    for i in range(0, len(parts), 6):
        out.append("+ " + " ".join(parts[i:i + 6]))
    return "\n".join(out)


# ---------------------------------------------------------------------
# Sim 1 ("Q1 Vds worst-case") .cir renderer
# ---------------------------------------------------------------------
def render_q1_worstcase_cir(*, smbj_subckt: str, ao3401_subckt: str,
                            l_trace_nh: float, pwl_offset_text: str) -> str:
    """Build the Sim 1 ngspice deck for one L_trace value.

    The PWL voltage source carries the +24 V DC offset baked in
    (so PWL(0)=24 V, PWL(t_peak)=24+200=224 V, PWL(100us)~=24 V),
    which avoids any topology gymnastics with a separate Vdc source.

    Net naming
    ----------
      0           : ground.
      surge_in    : output of (24 V + surge) PWL source.
      vin         : after Rsrc + Ltrace; D1 cathode; Q1 source.
      drain       : Q1 drain; protected rail with R_LOAD + Cdrain.
      gate        : Q1 gate; R4 to zenode; R1 to GND.
      zenode      : D3 anode; Zener cathode tied to vin.

    Q1 AO3401A pin order from the rdmeneze model:
        .SUBCKT AO3401A  4   1   2
                       (D) (G) (S)
    (verified by inspecting the model: M1 is `3 1 2 2 PMOS` -> internal
    drain=3, gate=1, source=2; R1 4 3 = external drain (4) -> internal
    drain (3) through Rds_on). So external (D G S) = (4 1 2).

    SMBJ24A pin order from the Vishay model:
        .SUBCKT smbj24a  9  2
                       (A) (K)
    (verified by inspecting the model header comment block: "Reverse
    direction: node 9 <- node 2", i.e. A=9, K=2). For a uni-directional
    TVS clamping Vin -> GND on a positive surge: cathode=Vin, anode=GND.

    D3 BZT52C10S Zener clamp - modelled as a generic 10 V Zener diode
    via `.MODEL DZ10 D BV=10.0` (the gate-clamp behaviour at the ~10 us
    timescale this stage cares about is dominated by BV + junction
    capacitance, both of which a generic D-model captures adequately
    for the static-Vds threshold question).

    Downstream model is deliberately WEAK (1 uF + 100 Ohm). This is
    NOT the realistic OAS downstream chain - it is intentionally
    stripped of bulk-cap absorption to maximise the Vds delta Q1
    might see. The realistic chain is modelled separately by
    render_lm2596_realistic_cir() below.
    """
    return f"""\
* OAS surge stress test, Sim 1 (Q1 Vds worst-case): TVS + Q1 P-MOS
* Configuration: L_trace = {l_trace_nh:.2f} nH, PWL biased to +{V_DC_NOMINAL:.0f} V DC
*
* === SMBJ24A TVS model (Vishay) ===
{smbj_subckt}

* === AO3401A P-MOSFET model (rdmeneze community) ===
{ao3401_subckt}

* === BZT52C10S Zener (generic 10 V model) ===
.MODEL DZ10 D (BV=10.0 IBV=5m N=1.0 IS=1e-12 CJO=80p TT=20n RS=2.0)

* === Surge source: analytic 1.2/50 us PWL on top of {V_DC_NOMINAL:.0f} V DC ===
Vsurge surge_in 0 PWL(
{pwl_offset_text}
+ )

* === Series source impedance (IEC 61000-4-5 §6.2) ===
Rsrc surge_in n_rs {R_SOURCE_OHM:.3f}

* === PCB parasitic L from J1 -> D1 -> Q1 loop ===
Ltrace n_rs vin {l_trace_nh:.4f}n IC=0

* === D1 SMBJ24A TVS: cathode = vin, anode = 0 (clamps positive surge) ===
XD1 0 vin smbj24a

* === Q1 AO3401A P-MOS: external pin order (D G S) = (4 1 2) ===
XQ1 drain gate vin AO3401A

* === Gate clamp network ===
R4 gate zenode 1k
R1 gate 0 100k
D3 zenode vin DZ10

* === Protected rail load (representative resistive 100 Ohm) ===
Rload drain 0 {R_LOAD_OHM:.3f}

* === Downstream bulk approximation (conservative 1 uF) ===
Cdrain drain 0 1u IC={V_DC_NOMINAL:.3f}

* Transient sim: 5 ns max step across 100 us total. DO NOT use UIC -
* we want ngspice to compute the DC operating point first so the Zener
* clamp settles Vgs at ~-10 V (R1 pulls gate to GND, but Cgs and the
* D3+R4 clamp loop establish the proper bias). Gear method + tighter
* tolerances help with the ns-scale TVS clamp event.
.options method=gear reltol=1e-3 abstol=1e-9 vntol=1e-6
.tran 5n 100u

.control
run
* ngspice `.meas tran ... MAX <expr>` only accepts node references
* (v(a), v(a,b)) directly, NOT expressions like abs(...). Use vector
* arithmetic in the control block: synthesize abs(Vds) as a derived
* vector, then `meas` it as a plain v(...)-style reference.
let vds = v(drain,vin)
let vds_abs = abs(vds)
* Peak |Vds| across the full transient (max of derived |Vds| vector).
meas tran vds_peak MAX vds_abs
* Positive- and negative-going peaks of Vds (sanity / direction).
meas tran vds_pos_peak MAX vds
meas tran vds_neg_peak MIN vds
meas tran vdrain_peak MAX v(drain)
meas tran vsrc_peak MAX v(vin)
* First crossing of |Vds| = VDS_MAX (30 V threshold). CROSS=1.
* If |Vds| never reaches the threshold, ngspice reports "no match"
* and parse_meas() returns None - that is the PASS condition for
* this measurement (strict 0 ns above threshold).
meas tran t_above_30 WHEN vds_abs={VDS_MAX_V:.3f} CROSS=1
print vds_peak vds_pos_peak vds_neg_peak vdrain_peak vsrc_peak t_above_30
quit
.endc
.end
"""


# ---------------------------------------------------------------------
# Sim 2 ("LM2596 Vin realistic") .cir renderer
# ---------------------------------------------------------------------
def render_lm2596_realistic_cir(*, smbj_subckt: str, ao3401_subckt: str,
                                l_trace_nh: float, pwl_offset_text: str) -> str:
    """Build the Sim 2 ngspice deck: same upstream chain as Sim 1, but
    the full realistic downstream model from Q1 drain through to the
    LM2596 Vin pin.

    Net naming (NEW nodes vs Sim 1 indicated):
      0            : ground.
      surge_in     : output of (24 V + surge) PWL source.
      vin          : after Rsrc + Ltrace; D1 cathode; Q1 source.
      drain        : Q1 drain (== V_24V_PROT rail).
      gate         : Q1 gate; R4 to zenode; R1 to GND.
      zenode       : D3 anode; Zener cathode tied to vin.
      c1_top       : NEW. Top of C1 bulk cap (= drain via ESR+ESL).
      n_after_f1   : NEW. After F1 PTC; before L_drain_to_lm.
      vin_lm2596   : NEW. LM2596 Vin pin (after L_drain_to_lm); top
                     of C5+C6 bypass; load current sink.
      c56_top      : NEW. Top of lumped C5+C6 cap (= vin_lm2596 via
                     bypass ESR+ESL).

    Component map vs OAS schematic + BOM:
      C1   100 uF Panasonic EEU-FR series (drain bulk) - ESR/ESL modeled.
      F1   Littelfuse 1812L075/33DR cold (0.1 Ohm series resistor).
      L_drain_to_lm  ~15 nH PCB trace Q1 drain -> LM2596 Vin.
      C5+C6  22 uF + 10 uF X7R MLCC parallel at LM2596 Vin (lumped 32 uF).
      I_LM2596 ~10 mA constant-current quiescent load.

    Implementation note on ESR/ESL chains in ngspice
    -------------------------------------------------
    A capacitor with parasitic ESR + ESL is modeled as three series
    elements:  node_top -[L_ESL]- n_a -[R_ESR]- n_b -[C_pure]- GND
    where the IC on C_pure is the steady-state V_DC_NOMINAL = 24 V.
    On Sim 2 we add IC=0 to all the ESL inductors (they carry zero
    DC current at steady state through the cap) and IC=24 V to the
    pure-C nodes via the .ic directive.
    """
    return f"""\
* OAS surge stress test, Sim 2 (LM2596 Vin realistic):
*   TVS -> L_trace -> Q1 -> C1(100uF+ESR+ESL) -> F1(cold 0.1R)
*        -> L_drain_to_lm({L_DRAIN_TO_LM_NH:.1f}nH) -> C5+C6(32uF+ESR+ESL) -> LM2596_Vin
* Configuration: L_trace = {l_trace_nh:.2f} nH, PWL biased to +{V_DC_NOMINAL:.0f} V DC
*
* === SMBJ24A TVS model (Vishay) ===
{smbj_subckt}

* === AO3401A P-MOSFET model (rdmeneze community) ===
{ao3401_subckt}

* === BZT52C10S Zener (generic 10 V model) ===
.MODEL DZ10 D (BV=10.0 IBV=5m N=1.0 IS=1e-12 CJO=80p TT=20n RS=2.0)

* === Surge source: analytic 1.2/50 us PWL on top of {V_DC_NOMINAL:.0f} V DC ===
Vsurge surge_in 0 PWL(
{pwl_offset_text}
+ )

* === Series source impedance (IEC 61000-4-5 §6.2) ===
Rsrc surge_in n_rs {R_SOURCE_OHM:.3f}

* === PCB parasitic L from J1 -> D1 -> Q1 loop ===
Ltrace n_rs vin {l_trace_nh:.4f}n IC=0

* === D1 SMBJ24A TVS: cathode = vin, anode = 0 (clamps positive surge) ===
XD1 0 vin smbj24a

* === Q1 AO3401A P-MOS: external pin order (D G S) = (4 1 2) ===
XQ1 drain gate vin AO3401A

* === Gate clamp network ===
R4 gate zenode 1k
R1 gate 0 100k
D3 zenode vin DZ10

* === C1 bulk electrolytic (100 uF, ESR 50 mOhm, ESL 3 nH) on drain ===
* drain --[L_C1_ESL]-- c1_esl --[R_C1_ESR]-- c1_pure --[C1]-- 0
L_C1_ESL drain c1_esl {C1_ESL_NH:.4f}n IC=0
R_C1_ESR c1_esl c1_pure {C1_ESR_MOHM:.3f}m
C1       c1_pure 0 {C1_BULK_UF:.3f}u IC={V_DC_NOMINAL:.3f}

* === F1 PTC fuse (cold-resistance midpoint of 1812L075/33DR datasheet) ===
* drain --[F1]-- n_after_f1
R_F1 drain n_after_f1 {F1_COLD_OHM:.3f}

* === PCB trace inductance from Q1 drain cluster to LM2596 Vin pin ===
L_drain_to_lm n_after_f1 vin_lm2596 {L_DRAIN_TO_LM_NH:.4f}n IC=0

* === C5+C6 LM2596 Vin bypass (lumped 32 uF, ESR 2.5 mOhm, ESL 0.5 nH) ===
* vin_lm2596 --[L_C56_ESL]-- c56_esl --[R_C56_ESR]-- c56_pure --[C56]-- 0
L_C56_ESL vin_lm2596 c56_esl {C56_ESL_NH:.4f}n IC=0
R_C56_ESR c56_esl c56_pure {C56_ESR_MOHM:.3f}m
C56       c56_pure 0 {C56_BYPASS_UF:.3f}u IC={V_DC_NOMINAL:.3f}

* === LM2596 quiescent load: 10 mA constant current sink to GND ===
* (ngspice DC ammeter convention: I flows from + node into the source,
* so to SINK current from vin_lm2596 to GND we use I from vin_lm2596 to 0)
I_LM2596 vin_lm2596 0 {I_LM2596_QUIESCENT_MA:.3f}m

* Transient sim: 5 ns max step across 100 us total. DC operating point
* solved first (no UIC) so the cap stack settles to V_DC_NOMINAL.
* Gear method + tighter tolerances help with the ns-scale TVS clamp event.
.options method=gear reltol=1e-3 abstol=1e-9 vntol=1e-6
.tran 5n 100u

.control
run
* ngspice .meas MAX/WHEN only accepts node references; pre-compute the
* abs() vectors with `let` and then meas the derived vectors.
let vlm = v(vin_lm2596)
let vlm_abs = abs(vlm)
let vdrain = v(drain)
let vdrain_abs = abs(vdrain)
* Headline: peak |V(vin_lm2596)| across the full transient.
meas tran vlm_peak MAX vlm_abs
* Comparison: peak |V(drain)| - this is what Sim 1 reported as
* "vdrain_peak" in its weaker downstream model.
meas tran vdrain_peak MAX vdrain_abs
* Source-side peak (sanity check that the TVS still clamps).
meas tran vsrc_peak MAX v(vin)
* First crossing of |V(vin_lm2596)| = V_LM2596_MAX (40 V threshold).
* CROSS=1; if never crossed, parse_meas() returns None - that is the
* PASS condition.
meas tran t_vlm_above_40 WHEN vlm_abs={V_LM2596_MAX_V:.3f} CROSS=1
print vlm_peak vdrain_peak vsrc_peak t_vlm_above_40
quit
.endc
.end
"""


def biased_pwl(pts: list[tuple[float, float]], bias_v: float) -> str:
    """Re-format `pts` adding a DC bias to every voltage sample."""
    biased = [(t, v + bias_v) for t, v in pts]
    return format_pwl_args(biased)


# ---------------------------------------------------------------------
# Per-L_trace simulation runners
# ---------------------------------------------------------------------
@dataclass
class Q1SimResult:
    """Parsed measurements from Sim 1 (Q1 Vds worst-case)."""
    l_nh: float
    vds_peak: float
    vdrain_peak: float
    vsrc_peak: float
    t_above_30: float | None


@dataclass
class LMSimResult:
    """Parsed measurements from Sim 2 (LM2596 Vin realistic)."""
    l_nh: float
    vlm_peak: float
    vdrain_peak: float
    vsrc_peak: float
    t_vlm_above_40: float | None


def run_q1_worstcase(*, workdir: Path, ngspice: Path, smbj_subckt: str,
                     ao3401_subckt: str, l_nh: float,
                     pwl_text: str) -> Q1SimResult:
    """Render + run one Sim 1 (Q1 worst-case) L_trace point."""
    cir_text = render_q1_worstcase_cir(
        smbj_subckt=smbj_subckt,
        ao3401_subckt=ao3401_subckt,
        l_trace_nh=l_nh,
        pwl_offset_text=pwl_text,
    )
    cir_path = workdir / f"sim1_q1_L{l_nh:.2f}nH.cir"
    cir_path.write_text(cir_text, encoding="utf-8")
    print(f"  Sim 1, L_trace = {l_nh:5.2f} nH: running transient (~10 s) ...")
    output = run_ngspice(cir_path, ngspice, timeout=120)

    vds = parse_meas(output, "vds_peak")
    vdr = parse_meas(output, "vdrain_peak")
    vsr = parse_meas(output, "vsrc_peak")
    t30 = parse_meas(output, "t_above_30")

    if vds is None or vdr is None or vsr is None:
        # Dump output for diagnosis; this is a script bug (netlist or
        # measure directive), not a board defect.
        print(output)
        sys.exit(
            f"[FAIL] Sim 1: could not parse vds_peak / vdrain_peak / "
            f"vsrc_peak from ngspice output for L={l_nh:.2f} nH. "
            "Check meas syntax."
        )
    return Q1SimResult(
        l_nh=l_nh, vds_peak=vds, vdrain_peak=vdr, vsrc_peak=vsr,
        t_above_30=t30,
    )


def run_lm2596_realistic(*, workdir: Path, ngspice: Path, smbj_subckt: str,
                         ao3401_subckt: str, l_nh: float,
                         pwl_text: str) -> LMSimResult:
    """Render + run one Sim 2 (LM2596 Vin realistic) L_trace point."""
    cir_text = render_lm2596_realistic_cir(
        smbj_subckt=smbj_subckt,
        ao3401_subckt=ao3401_subckt,
        l_trace_nh=l_nh,
        pwl_offset_text=pwl_text,
    )
    cir_path = workdir / f"sim2_lm2596_L{l_nh:.2f}nH.cir"
    cir_path.write_text(cir_text, encoding="utf-8")
    print(f"  Sim 2, L_trace = {l_nh:5.2f} nH: running transient (~10 s) ...")
    output = run_ngspice(cir_path, ngspice, timeout=120)

    vlm = parse_meas(output, "vlm_peak")
    vdr = parse_meas(output, "vdrain_peak")
    vsr = parse_meas(output, "vsrc_peak")
    t40 = parse_meas(output, "t_vlm_above_40")

    if vlm is None or vdr is None or vsr is None:
        print(output)
        sys.exit(
            f"[FAIL] Sim 2: could not parse vlm_peak / vdrain_peak / "
            f"vsrc_peak from ngspice output for L={l_nh:.2f} nH. "
            "Check meas syntax."
        )
    return LMSimResult(
        l_nh=l_nh, vlm_peak=vlm, vdrain_peak=vdr, vsrc_peak=vsr,
        t_vlm_above_40=t40,
    )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main() -> int:
    with Stage("check_surge") as s:
        s.info("OAS surge stress under IEC 61000-4-5 (ngspice)")
        s.info(f"Surge envelope: 1.2/50 us, peak {SURGE_PEAK_V:.0f} V "
               f"open-circuit, Rsrc = {R_SOURCE_OHM:.1f} Ohm")
        s.info(f"L_trace sweep: {L_TRACE_SWEEP_NH} nH "
               f"(nominal {L_TRACE_NH_NOMINAL:.1f} nH +/-50%)")
        s.info(f"Sim 1 limit: |Vds(Q1)| <= {VDS_MAX_V:.1f} V "
               "(AO3401A absolute max, no published EAS rating)")
        s.info(f"Sim 2 limit: |V(vin_lm2596)| <= {V_LM2596_MAX_V:.1f} V "
               "(LM2596 SNVS124N §6.1 absolute max Vin)")

        # Provision binaries + models.
        ngspice = ensure_ngspice()
        smbj_path = ensure_smbj24a_model()
        ao_path = ensure_ao3401a_model()
        s.info(f"ngspice: {ngspice}")
        s.info(f"SMBJ24A model: {smbj_path}")
        s.info(f"AO3401A model: {ao_path}")

        smbj_subckt = extract_smbj24a_subckt(smbj_path)
        ao_subckt = extract_ao3401a_subckt(ao_path)
        s.info(f"SMBJ24A .SUBCKT extracted ({len(smbj_subckt)} chars)")
        s.info(f"AO3401A .SUBCKT extracted ({len(ao_subckt)} chars)")

        # Synthesize PWL once; reuse across all six L sims.
        pts = synth_surge_pwl()
        s.info(f"Surge PWL synthesized: {len(pts)} points across 100 us")
        # Sanity: peak of the PWL should be ~SURGE_PEAK_V before DC bias.
        peak_observed = max(v for _, v in pts)
        s.info(f"Surge PWL peak (unbiased): {peak_observed:.2f} V "
               f"(target {SURGE_PEAK_V:.0f} V)")
        if abs(peak_observed - SURGE_PEAK_V) > 1.0:
            s.fail(f"surge PWL peak {peak_observed:.2f} V deviates from "
                   f"target {SURGE_PEAK_V:.0f} V - check synth_surge_pwl")

        pwl_biased_text = biased_pwl(pts, V_DC_NOMINAL)

        # Workdir under the surge cache so the .cir + .log survive runs
        # for forensic debugging.
        workdir = SURGE_CACHE / "sim"
        workdir.mkdir(parents=True, exist_ok=True)
        write_spice_init(workdir)

        # ============================================================
        # Sim 1: Q1 Vds worst-case (deliberately weak downstream model)
        # ============================================================
        print()
        s.info("=== Sim 1: Q1 Vds worst-case (weak downstream: 1 uF + 100 Ohm) ===")
        sim1_results: list[Q1SimResult] = []
        for l_nh in L_TRACE_SWEEP_NH:
            sim1_results.append(run_q1_worstcase(
                workdir=workdir, ngspice=ngspice,
                smbj_subckt=smbj_subckt, ao3401_subckt=ao_subckt,
                l_nh=l_nh, pwl_text=pwl_biased_text,
            ))
        sim1_worst = max(sim1_results, key=lambda r: r.vds_peak)
        print()
        s.info("Sim 1 per-L_trace measurements:")
        for sim in sim1_results:
            t30_str = ("never" if sim.t_above_30 is None
                       else f"{sim.t_above_30 * 1e9:.1f} ns")
            print(f"    L = {sim.l_nh:5.2f} nH:  "
                  f"vds_peak = {sim.vds_peak:6.2f} V  "
                  f"vdrain_peak = {sim.vdrain_peak:6.2f} V  "
                  f"vsrc_peak = {sim.vsrc_peak:6.2f} V  "
                  f"t>30V first cross: {t30_str}")
        s.info(f"Sim 1 worst case: L = {sim1_worst.l_nh:.2f} nH, "
               f"vds_peak = {sim1_worst.vds_peak:.2f} V")

        # ============================================================
        # Sim 2: LM2596 Vin realistic (full bulk + F1 + bypass)
        # ============================================================
        print()
        s.info("=== Sim 2: LM2596 Vin realistic (C1 100uF + F1 0.1R + L_drain_to_lm + C5+C6 32uF) ===")
        sim2_results: list[LMSimResult] = []
        for l_nh in L_TRACE_SWEEP_NH:
            sim2_results.append(run_lm2596_realistic(
                workdir=workdir, ngspice=ngspice,
                smbj_subckt=smbj_subckt, ao3401_subckt=ao_subckt,
                l_nh=l_nh, pwl_text=pwl_biased_text,
            ))
        sim2_worst = max(sim2_results, key=lambda r: r.vlm_peak)
        print()
        s.info("Sim 2 per-L_trace measurements:")
        for lmsim in sim2_results:
            t40_str = ("never" if lmsim.t_vlm_above_40 is None
                       else f"{lmsim.t_vlm_above_40 * 1e9:.1f} ns")
            print(f"    L = {lmsim.l_nh:5.2f} nH:  "
                  f"vlm_peak = {lmsim.vlm_peak:6.2f} V  "
                  f"vdrain_peak = {lmsim.vdrain_peak:6.2f} V  "
                  f"vsrc_peak = {lmsim.vsrc_peak:6.2f} V  "
                  f"t>40V first cross: {t40_str}")
        s.info(f"Sim 2 worst case: L = {sim2_worst.l_nh:.2f} nH, "
               f"vlm_peak = {sim2_worst.vlm_peak:.2f} V")

        # ============================================================
        # Build all CheckResult assertions (Sim 1 + Sim 2 combined)
        # ============================================================
        results = [
            CheckResult(
                name="[Sim 1] Q1 Vds peak (worst L_trace)",
                value=f"{sim1_worst.vds_peak:.2f} V",
                spec=f"<= {VDS_MAX_V:.1f} V (AO3401A abs max)",
                passed=sim1_worst.vds_peak <= VDS_MAX_V,
            ),
            CheckResult(
                name="[Sim 1] Q1 Vds threshold-cross duration",
                value=("never" if sim1_worst.t_above_30 is None
                       else f"first cross at {sim1_worst.t_above_30 * 1e9:.1f} ns"),
                spec="never cross (strict 0 ns above threshold)",
                passed=sim1_worst.t_above_30 is None,
            ),
            CheckResult(
                name="[Sim 2] LM2596 Vin peak (worst L_trace)",
                value=f"{sim2_worst.vlm_peak:.2f} V",
                spec=f"<= {V_LM2596_MAX_V:.1f} V (LM2596 abs max Vin)",
                passed=sim2_worst.vlm_peak <= V_LM2596_MAX_V,
            ),
            CheckResult(
                name="[Sim 2] LM2596 Vin threshold-cross duration",
                value=("never" if sim2_worst.t_vlm_above_40 is None
                       else f"first cross at {sim2_worst.t_vlm_above_40 * 1e9:.1f} ns"),
                spec="never cross (info report; hard check is the peak)",
                passed=sim2_worst.t_vlm_above_40 is None,
            ),
        ]

        # Comparison line: was the 67 V drain peak from Sim 1 real?
        delta = sim1_worst.vdrain_peak - sim2_worst.vlm_peak
        print()
        s.info(f"Sim 1 vs Sim 2 comparison: "
               f"drain peak {sim1_worst.vdrain_peak:.2f} V (weak model) "
               f"-> LM2596 Vin peak {sim2_worst.vlm_peak:.2f} V (realistic), "
               f"delta {delta:+.2f} V absorbed by C1+F1+C5+C6 chain")

        print()
        for r in results:
            print(r)
        print()

        # Per-sim verdicts
        sim1_failed = [r for r in results[:2] if not r.passed]
        sim2_failed = [r for r in results[2:] if not r.passed]
        any_failed = sim1_failed or sim2_failed

        if sim1_failed:
            overshoot = sim1_worst.vds_peak - VDS_MAX_V
            print(f"  Sim 1 overshoot: vds_peak {sim1_worst.vds_peak:.2f} V - "
                  f"limit {VDS_MAX_V:.1f} V = {overshoot:+.2f} V "
                  f"({overshoot / VDS_MAX_V * 100:+.1f}%)")
            print("  Q1 AO3401A is over-stressed under surge. The")
            print("  recommended remediation is Q1 -> AON7415 substitution")
            print("  (Vds_max = -60 V) - see CLAUDE.md TODO.")
            print()
        if sim2_failed:
            overshoot = sim2_worst.vlm_peak - V_LM2596_MAX_V
            print(f"  Sim 2 overshoot: vlm_peak {sim2_worst.vlm_peak:.2f} V - "
                  f"limit {V_LM2596_MAX_V:.1f} V = {overshoot:+.2f} V "
                  f"({overshoot / V_LM2596_MAX_V * 100:+.1f}%)")
            print("  LM2596 Vin abs max exceeded even with the realistic")
            print("  C1+F1+C5+C6 absorption chain. Remediation options:")
            print("    - lower-Vc TVS (SMBJ20A or SMAJ22CA bidirectional)")
            print("    - additional series L_filter on V_24V_PROT rail")
            print("    - larger C1 bulk cap (220 uF or 470 uF)")
            print("    - downstream MOV / GDT in addition to TVS")
            print("  DO NOT relax this check; the failure is the diagnostic.")
            print()

        if any_failed:
            s.fail(f"{len(sim1_failed) + len(sim2_failed)} of {len(results)} "
                   "surge checks failed")

        # All passed
        s.ok(f"all {len(results)} surge checks passed across both sims")
        s.info(f"Sim 1: Q1 stays ON (Vds <= {sim1_worst.vds_peak:.1f} V) "
               "as a near-zero-Vds pass element under positive surge")
        s.info(f"Sim 2: realistic C1+F1+C5+C6 absorption holds LM2596 "
               f"Vin to {sim2_worst.vlm_peak:.1f} V <= "
               f"{V_LM2596_MAX_V:.1f} V abs max")
        s.info("NOT covered here: REVERSE-polarity Q1 Vds scenario "
               "(planned stage 28_check_reverse_polarity).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
