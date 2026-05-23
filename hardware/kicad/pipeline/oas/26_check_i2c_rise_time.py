"""OAS - I2C bus signal-integrity (rise time + capacitance) check.

Verifies the shared I2C bus (SEN66 + NT3H1101 + J9 Qwiic expansion)
stays inside the UM10204 ("I2C-bus specification and user manual",
NXP Rev 7) limits:

  * t_r <= 1000 ns at Standard-mode 100 kHz (UM10204 Table 10).
  * C_bus_total <= 400 pF (UM10204 sec. 6.1 hard ceiling).

The OAS bus is unusually long for a I2C net (~140 mm of PCB track plus
the 50 cm AWG26 JST GH cable feeding the SEN66 at the end), so the
rise-time margin needs to be computed, not assumed. CLAUDE.md "Shared
I2C bus" already commits to 4.7 kOhm pull-ups and a t_r ~1 us target;
this stage closes the loop by re-deriving t_r from the *actual* routed
geometry (track length per line counted out of oas_routes.py) and the
device-end capacitance budget.

Bus-capacitance budget
----------------------
Per-line lumped model: C_bus = C_track + C_via + C_cable + C_devices.

  * Track capacitance: 1.5 pF/cm worst case. The OAS GND pour is
    fragmented by the central 10 mm cable hole and the LED-ring
    annulus, so the reference plane is intermittent under the I2C
    tracks - bumped from the textbook ~1 pF/cm to a conservative
    1.5 pF/cm. (Research note in .tmp/post-v0.50-test-research.md
    sec. "I2C signal integrity".)
  * Via capacitance: 1 pF per via. Counted directly from oas_routes.py.
    If a line carries zero vias the budget gets a 2 pF safety pad to
    absorb pad/stub parasitics that the lumped model otherwise misses.
  * JST GH cable: 50 cm AWG26 paired -> ~50 pF/m -> ~25 pF per line.
    The SEN66 sits at the *end* of the cable; its input pin sees the
    full cable capacitance.
  * Device input capacitance (lumped at the far end of each line; the
    ~1 pF/pin connector cushion is folded into these numbers):
       - SEN66:     10 pF  (UM10204 ceiling -- Sensirion does NOT
                            publish C_i in the SEN6x datasheet, so
                            this is conservative; logged WARN).
       - NT3H1101:   6 pF  (NXP NT3H1101 datasheet sec. Electrical
                            characteristics).
       - Qwiic:     10 pF  (budgeted for one expansion device on J9).

Pull-up resistance: hard-coded 4700 Ohm; verified by stage 09
(`pipeline/oas/09_check_semantic.py` enforces R5/R6 = 4.7 kOhm from the
mcu.kicad_sch property string, so this stage trusts that result and
does not re-parse the schematic).

Rise-time formula
-----------------
UM10204 sec. 6.1 measures t_r between 0.3*Vcc and 0.7*Vcc on an RC step.
For a single-pole RC response charging from 0 toward Vcc through
R_pull into C_bus,

    v(t) = Vcc * (1 - exp(-t / (R * C)))

Solving for the 0.3-0.7 transit gives

    t_r = R * C * ln(0.7 / 0.3) ~= 0.8473 * R * C

We round the prefactor to 0.84 for headline reporting.

Standard-mode 100 kHz is the spec OAS must meet. Fast-mode 400 kHz is
reported for context (the bus does not run there in the firmware, but
the margin is useful info -- if Fast-mode passes too, future firmware
has the option).

Failure modes
-------------
  * t_r > 1000 ns at Standard-mode -> bus too slow, edges miss the
    setup window. HARD FAIL.
  * C_bus_total > 400 pF -> UM10204 hard ceiling, regardless of
    pull-up choice. HARD FAIL.
  * /IO/I2C_SDA or /IO/I2C_SCL net missing entirely from oas_routes.py
    -> route accidentally deleted. HARD FAIL.

The stage is INTENTIONALLY read-only against the board. If either of
the first two limits fires, the fix is a board change (shorter tracks,
stronger pull-up, shorter SEN66 cable) -- DO NOT relax the budget here
to make it pass.
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
KICAD_DIR = HERE.parent.parent  # pipeline/oas/ -> pipeline/ -> hardware/kicad
ROUTES_PATH = KICAD_DIR / "oas_routes.py"

# pipeline/_common is loaded via the sys.path trick (NN_*.py filenames
# cannot be imported, so subprocess + sys.path.insert is the convention).
sys.path.insert(0, str(HERE.parent))
from _common import Stage  # noqa: E402

# I2C bus parameters (verified by stage 09; see CLAUDE.md "Shared I2C bus").
R_PULLUP_OHM = 4700.0       # R5 = R6 = 4.7 kOhm on +3V3, enforced by stage 09.

# Capacitance budgets (pF). See module docstring for sourcing.
C_TRACK_PF_PER_MM = 0.15    # 1.5 pF/cm worst case with fragmented GND ref.
C_VIA_PF = 1.0              # 1 pF per via on the net.
C_VIA_SAFETY_PF = 2.0       # Safety pad if zero vias on the net.
C_CABLE_PF = 25.0           # 50 cm AWG26 JST GH @ ~50 pF/m per line.

C_SEN66_PF = 10.0           # UM10204 ceiling; Sensirion does NOT publish C_i.
C_NFC_PF = 6.0              # NXP NT3H1101 datasheet.
C_QWIIC_PF = 10.0           # Budget for one user-plugged expansion device.

# UM10204 limits.
T_R_MAX_STANDARD_NS = 1000.0   # UM10204 Table 10: Standard-mode 100 kHz.
T_R_MAX_FAST_NS = 300.0        # UM10204 Table 10: Fast-mode 400 kHz (info).
C_BUS_MAX_PF = 400.0           # UM10204 sec. 6.1 hard ceiling.

# RC step 0.3*Vcc -> 0.7*Vcc transit factor: ln(0.7/0.3) ~= 0.8473.
RC_TRANSIT_FACTOR = math.log(0.7 / 0.3)

# Qwiic-marginal warning threshold: if the bus already exceeds this
# *without* the Qwiic budget, a user-plugged expansion device could
# easily push past the 400 pF ceiling.
C_QWIIC_HEADROOM_PF = 250.0

# Net names as they appear in oas_routes.py (extracted by tools/extract_routes.py).
SDA_NET = "/IO/I2C_SDA"
SCL_NET = "/IO/I2C_SCL"


def load_routes() -> tuple[list[dict], list[dict]]:
    """Import oas_routes.py and return (ROUTES_SEGMENTS, ROUTES_VIAS).

    The file lives next to oas.kicad_pcb; importlib.util keeps it out
    of sys.modules pollution. Hard-fails if the file is missing - the
    pipeline before this stage (01_emit_sources, then the routing
    snapshot replay) is expected to have produced it.
    """
    if not ROUTES_PATH.exists():
        Stage.fail(f"{ROUTES_PATH} not found - boardgen has not been run.")
    spec = importlib.util.spec_from_file_location("oas_routes", ROUTES_PATH)
    if spec is None or spec.loader is None:
        Stage.fail(f"failed to build importlib spec for {ROUTES_PATH}")
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)                 # type: ignore[union-attr]
    return module.ROUTES_SEGMENTS, module.ROUTES_VIAS


def net_track_length_mm(segments: list[dict], net_name: str) -> float:
    """Sum of |end - start| over every routed segment belonging to net_name."""
    total = 0.0
    for s in segments:
        if s.get("net_name") != net_name:
            continue
        sx, sy = s["start"]
        ex, ey = s["end"]
        total += math.hypot(ex - sx, ey - sy)
    return total


def net_segment_count(segments: list[dict], net_name: str) -> int:
    return sum(1 for s in segments if s.get("net_name") == net_name)


def net_via_count(vias: list[dict], net_name: str) -> int:
    return sum(1 for v in vias if v.get("net_name") == net_name)


def compute_t_r_ns(r_ohm: float, c_pf: float) -> float:
    """t_r (10-90% per single-pole RC, between 0.3*Vcc and 0.7*Vcc).

    R in ohms, C in picofarads -> t_r in nanoseconds. The conversion
    is: tau (s) = R (Ohm) * C (F) = R * C * 1e-12; t_r (ns) = tau (s) * 1e9
    * factor = R * C * 1e-3 * factor.
    """
    return r_ohm * c_pf * 1e-3 * RC_TRANSIT_FACTOR


def report_line(s: Stage, label: str, length_mm: float, seg_count: int,
                via_count: int, c_device_pf: float, device_label: str) -> float:
    """Emit the per-line breakdown table + return C_bus_total for that line."""
    c_track = length_mm * C_TRACK_PF_PER_MM
    c_via = via_count * C_VIA_PF if via_count > 0 else C_VIA_SAFETY_PF
    c_bus = c_track + c_via + C_CABLE_PF + c_device_pf
    s.info(
        f"  {label}: {seg_count} segs, {length_mm:.1f} mm, "
        f"{via_count} via -> "
        f"C_track={c_track:.1f} pF, "
        f"C_via={c_via:.1f} pF, "
        f"C_cable={C_CABLE_PF:.1f} pF, "
        f"C_dev({device_label})={c_device_pf:.1f} pF "
        f"=> C_bus={c_bus:.1f} pF"
    )
    return c_bus


def main() -> int:
    with Stage("check_i2c_rise_time") as s:
        s.info("OAS I2C bus signal-integrity check (UM10204 t_r/C_bus)")
        s.info(f"  Pull-up: R_pull = {R_PULLUP_OHM:.0f} Ohm "
               "(R5/R6 = 4.7 kOhm, verified by stage 09)")
        s.info(f"  Track cap budget: {C_TRACK_PF_PER_MM*10:.1f} pF/cm "
               "(fragmented GND ref bump from 1 pF/cm)")
        s.info(f"  Cable: 50 cm AWG26 JST GH @ {C_CABLE_PF:.0f} pF/line")
        s.warn("  SEN66 C_i: Sensirion does NOT publish I2C input cap; "
               f"using UM10204 ceiling {C_SEN66_PF:.0f} pF as conservative bound")

        segments, vias = load_routes()
        s.info(f"  oas_routes.py: {len(segments)} segments, {len(vias)} vias total")

        # Check 1: nets present at all. Catches accidental net deletion.
        sda_segs = net_segment_count(segments, SDA_NET)
        scl_segs = net_segment_count(segments, SCL_NET)
        if sda_segs == 0:
            s.fail(f"{SDA_NET} has 0 segments in oas_routes.py -- net deleted?")
        if scl_segs == 0:
            s.fail(f"{SCL_NET} has 0 segments in oas_routes.py -- net deleted?")

        # Track length + via count per net.
        sda_len = net_track_length_mm(segments, SDA_NET)
        scl_len = net_track_length_mm(segments, SCL_NET)
        sda_vias = net_via_count(vias, SDA_NET)
        scl_vias = net_via_count(vias, SCL_NET)

        # On the shared bus the total device-end capacitance per line is the
        # sum across every slave that hangs off the line (SEN66 + NT3H1101 +
        # Qwiic budget) - each device's input pin contributes in parallel.
        c_device_total = C_SEN66_PF + C_NFC_PF + C_QWIIC_PF

        s.info("Per-line capacitance breakdown:")
        c_bus_sda = report_line(s, "SDA", sda_len, sda_segs, sda_vias,
                                c_device_total, "SEN66+NFC+Qwiic")
        c_bus_scl = report_line(s, "SCL", scl_len, scl_segs, scl_vias,
                                c_device_total, "SEN66+NFC+Qwiic")

        # Rise-time analysis.
        t_r_sda_std = compute_t_r_ns(R_PULLUP_OHM, c_bus_sda)
        t_r_scl_std = compute_t_r_ns(R_PULLUP_OHM, c_bus_scl)
        t_r_sda_fm = t_r_sda_std  # t_r depends only on R*C; mode just sets the limit.
        t_r_scl_fm = t_r_scl_std

        s.info("Rise-time analysis (t_r ~= 0.8473 * R_pull * C_bus):")
        s.info(f"  SDA: t_r = {t_r_sda_std:.0f} ns  "
               f"(Std-mode limit {T_R_MAX_STANDARD_NS:.0f} ns, "
               f"margin {T_R_MAX_STANDARD_NS - t_r_sda_std:+.0f} ns)")
        s.info(f"  SCL: t_r = {t_r_scl_std:.0f} ns  "
               f"(Std-mode limit {T_R_MAX_STANDARD_NS:.0f} ns, "
               f"margin {T_R_MAX_STANDARD_NS - t_r_scl_std:+.0f} ns)")
        s.info(f"  Fast-mode 400 kHz (info-only) limit {T_R_MAX_FAST_NS:.0f} ns: "
               f"SDA {'PASS' if t_r_sda_fm <= T_R_MAX_FAST_NS else 'FAIL'} "
               f"({t_r_sda_fm:.0f} ns), "
               f"SCL {'PASS' if t_r_scl_fm <= T_R_MAX_FAST_NS else 'FAIL'} "
               f"({t_r_scl_fm:.0f} ns)")

        # Check 2: UM10204 hard 400 pF ceiling.
        if c_bus_sda > C_BUS_MAX_PF:
            s.fail(
                f"SDA C_bus = {c_bus_sda:.1f} pF exceeds UM10204 ceiling "
                f"{C_BUS_MAX_PF:.0f} pF -- bus over-capacitance. "
                "Board-level fix required (shorter cable, shorter tracks, "
                "or strapping bus topology); DO NOT relax budget here."
            )
        if c_bus_scl > C_BUS_MAX_PF:
            s.fail(
                f"SCL C_bus = {c_bus_scl:.1f} pF exceeds UM10204 ceiling "
                f"{C_BUS_MAX_PF:.0f} pF -- bus over-capacitance. "
                "Board-level fix required (shorter cable, shorter tracks, "
                "or strapping bus topology); DO NOT relax budget here."
            )

        # Check 3: UM10204 Standard-mode 1 us rise-time ceiling.
        if t_r_sda_std > T_R_MAX_STANDARD_NS:
            s.fail(
                f"SDA t_r = {t_r_sda_std:.0f} ns exceeds UM10204 Standard-mode "
                f"limit {T_R_MAX_STANDARD_NS:.0f} ns. Board-level fix: "
                "stronger pull-up, shorter cable, or shorter tracks; "
                "DO NOT relax budget here."
            )
        if t_r_scl_std > T_R_MAX_STANDARD_NS:
            s.fail(
                f"SCL t_r = {t_r_scl_std:.0f} ns exceeds UM10204 Standard-mode "
                f"limit {T_R_MAX_STANDARD_NS:.0f} ns. Board-level fix: "
                "stronger pull-up, shorter cable, or shorter tracks; "
                "DO NOT relax budget here."
            )


        # Qwiic-headroom advisory: if the bus is already heavy without the
        # Qwiic budget, a user-plugged expansion device could push past 400 pF.
        c_bus_sda_no_qwiic = c_bus_sda - C_QWIIC_PF
        c_bus_scl_no_qwiic = c_bus_scl - C_QWIIC_PF
        c_no_qwiic_worst = max(c_bus_sda_no_qwiic, c_bus_scl_no_qwiic)
        if c_no_qwiic_worst > C_QWIIC_HEADROOM_PF:
            s.warn(
                f"J9 Qwiic expansion C-budget marginal: bus without Qwiic "
                f"already at {c_no_qwiic_worst:.1f} pF "
                f"(threshold {C_QWIIC_HEADROOM_PF:.0f} pF). A user-plugged "
                "expansion device may push past the 400 pF ceiling."
            )

        s.ok(f"SDA t_r = {t_r_sda_std:.0f} ns, SCL t_r = {t_r_scl_std:.0f} ns "
             f"(both <= {T_R_MAX_STANDARD_NS:.0f} ns Standard-mode)")
        s.ok(f"SDA C_bus = {c_bus_sda:.1f} pF, SCL C_bus = {c_bus_scl:.1f} pF "
             f"(both <= {C_BUS_MAX_PF:.0f} pF UM10204 ceiling)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
