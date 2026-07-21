"""
OAS - DC voltage propagation check (pure Python).

Verifies the OAS power chain delivers correct regulated voltages when 24 V
is applied to J1. Catches resistor-value regressions like the v0.36
R3 10k -> 30.9k fix (pre-fix produced 4.34 V on +3V3 instead of 3.39 V,
which would have destroyed the ESP32 and SEN66 at first power-on) and
the v0.37 D3 18 V -> 10 V fix (pre-fix would have over-stressed the
AO3401A's +/-12 V Vgs rating).

Approach
--------
Reads the actual R-values + D3 Zener spec from `power.kicad_sch` (the
generated artifact - source-of-truth at simulation time), then runs
SIMPLIFIED ANALYTICAL MODELS of each active component to compute the
DC operating point at every named net. No SPICE engine needed -
just linear-network math with hardcoded IC datasheet behaviors.

Models used
-----------
  * D1 SMBJ24A (TVS):  Vbr ~ 26.7 V, Vcl ~ 38.9 V at 15 A peak.
                       Cathode tied to V_24V, anode to GND.
                       At nominal Vin=24V: reverse-biased, no DC effect.
  * Q1 AO3401A (P-FET): Vds_max=-30V, Vgs_max=+/-12V, Rds_on=45 mΩ @ Vgs=-10V.
                       Modeled as 45 mΩ series resistance when forward
                       conducting (Source at Vin, Drain at output side,
                       Gate pulled below Source via R4+R1 chain through D3).
  * D3 BZT52C10S (Zener): Vz=10 V at 5 mA test. Clamps Q1 Vgs at -Vz.
  * R1 100 k ohm:         Q1 gate pulldown to GND.
  * R4 1 k ohm:           Series gate-drive resistor (D3 clamp current limit).
  * F1 polyfuse:       Cold resistance ~0.1 Ohm (Littelfuse 2920L075/60MR).
  * U1 LM2596-5.0:     Ideal regulator. Vout = 5.0 V when 7 <= Vin <= 40 V.
                       Efficiency ~85% (modeled but doesn't affect Vout).
  * U2 TPS62933:       Ideal regulator. Vout = Vref × (1 + R2/R3),
                       Vref = 0.8 V. Valid when 3.8 <= Vin <= 30 V.
  * Loads:             Combined currents derived from CLAUDE.md per-component
                       budgets - ESP32 ~80 mA + SEN66 ~130 mA
                       + LD2410 ~80 mA + LED ring avg ~80 mA + misc.

Scenarios tested
----------------
  1. Nominal (Vin = +24 V): every regulated rail in spec window.
  2. Reverse polarity (Vin = -24 V): Q1 blocks, all downstream = 0 V.
  3. TVS clamp event (transient Vin spikes to +50 V): D1 clamps to 38.9 V,
     Q1 Vds stays within -30 V rating with margin.
  4. Brown-out (Vin = +6 V, below LM2596 minimum): rails collapse cleanly.

Exit code 0 if all checks pass, 1 on any assertion failure. Designed to
be run as a `build.py` post-check OR standalone (`python pipeline/oas/05_check_dc.py`).

Limitations
-----------
This is NOT a switching-converter simulator - soft-start ramp, output
ripple, transient response, and stability are NOT modeled. For those,
use TI WEBENCH or the KiCad built-in ngspice simulator with actual
PSpice models from TI. This tool is specifically designed to catch
DESIGN-VALUE regressions (resistor renumberings, Zener voltage drift,
component swap mistakes) that DRC and ERC cannot detect.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).parent
KICAD_DIR = HERE.parent.parent  # pipeline/oas/ -> pipeline/ -> hardware/kicad
POWER_SCH = KICAD_DIR / "power.kicad_sch"
MCU_SCH = KICAD_DIR / "mcu.kicad_sch"

# ---------------------------------------------------------------------------
# Component datasheet constants (sourced from datasheets, not LLM memory).
# Update only when the actual part is swapped in `lcsc-mapping.csv`.
# ---------------------------------------------------------------------------
TPS62933_VREF = 0.8         # TI TPS62933 datasheet Electrical Characteristics
TPS62933_VIN_MIN = 3.8      # TI TPS62933 minimum input voltage
TPS62933_VIN_MAX = 30.0
LM2596_VOUT_FIXED_5V = 5.0  # TI LM2596S-5.0 fixed-output variant
LM2596_VIN_MIN = 7.0        # TI LM2596 datasheet minimum operating Vin
LM2596_VIN_MAX = 40.0
SMBJ24A_VBR = 26.7          # Brightking SMBJ24A breakdown voltage
SMBJ24A_VCL = 38.9          # Clamp voltage at 15.4 A peak (600 W)
AO3401A_VDS_MAX_ABS = 30.0  # AOS AO3401A absolute max Vds (-30 V)
AO3401A_VGS_MAX_ABS = 12.0  # AOS AO3401A absolute max Vgs (+/-12 V)
AO3401A_RDS_ON = 0.045      # AOS AO3401A datasheet Rds(on) @ Vgs=-10V (Ω)
F1_COLD_R = 0.1             # Littelfuse 2920L075 cold trace resistance (Ω)

# OAS rail expected windows (datasheet-driven specs).
RAIL_5V_WINDOW = (4.85, 5.15)     # LM2596 +/-3% line+load
RAIL_3V3_WINDOW = (3.15, 3.60)    # SEN66 absolute spec window per datasheet section3
V24_PROT_WINDOW = (23.5, 24.05)   # After Q1 (45 mΩ * ~0.5A = 22.5 mV drop) + F1

# Per-component current budgets derived from datasheets (typical operating,
# not peak). Sources: SEN66 datasheet §4 (~130 mA), Espressif ESP32-C6 §4
# active+RF (~80 mA), HLK-LD2410C manual V1.00 Table 2 (79 mA avg),
# SK6812-SIDE x7 at 50% brightness (~80 mA avg).
LOAD_5V_TYPICAL_A = 0.16    # LED ring avg 80 mA + LD2410C 79 mA
LOAD_3V3_TYPICAL_A = 0.22   # ESP32 80 mA + SEN66 130 mA + 10 mA misc/margin
TOTAL_INPUT_TYPICAL_A = 0.5  # rough total after buck efficiency losses


@dataclass
class CheckResult:
    """One named PASS/FAIL row, plus the actual value the test computed."""
    name: str
    value: str
    spec: str
    passed: bool

    def __str__(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        return f"  [{mark}] {self.name:35s} {self.value:30s} (spec: {self.spec})"


def parse_resistor_value(value_string: str) -> float | None:
    """Parse a KiCad value string like '100k', '30.9k 1%', '4.7k', '1k' into ohms.
    Returns None if the string can't be parsed."""
    # Pattern: <number><optional k/M/m suffix>[ optional tolerance]
    m = re.match(r"^\s*([\d.]+)\s*([kMm])?", value_string.strip())
    if not m:
        return None
    base = float(m.group(1))
    suffix = m.group(2) or ""
    multipliers = {"": 1.0, "k": 1e3, "M": 1e6, "m": 1e-3}
    return base * multipliers.get(suffix, 1.0)


def parse_zener_voltage(value_string: str) -> float | None:
    """Parse 'NV Zener ...' into the Zener voltage. Returns None if not matched.

    Handles formats like '10V Zener 200mW', '18V Zener 500mW', 'BZT52C10S'."""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*V\s+Zener", value_string)
    if m:
        return float(m.group(1))
    # BZT52CnnS family: nn = Zener voltage (no decimal).
    m = re.match(r"^\s*BZT52C(\d+)S?", value_string)
    if m:
        return float(m.group(1))
    return None


def read_schematic_property(sch_text: str, reference: str, prop: str) -> str | None:
    """Find the value of a named property on the first symbol whose Reference
    matches `reference`. Uses the same depth-counting parse as
    `boardgen/_postprocess.py:_apply_schematic_footprints` to handle nested blocks correctly."""
    i = 0
    n = len(sch_text)
    while True:
        idx = sch_text.find("(symbol", i)
        if idx == -1:
            return None
        depth = 0
        j = idx
        while j < n:
            ch = sch_text[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = sch_text[idx:j]
        m_ref = re.search(r'\(property "Reference" "([^"]+)"', block)
        if m_ref and m_ref.group(1) == reference:
            m_prop = re.search(
                r'\(property "' + re.escape(prop) + r'" "([^"]*)"',
                block,
            )
            return m_prop.group(1) if m_prop else None
        i = j


def read_design_values() -> dict[str, float]:
    """Parse `power.kicad_sch` + `mcu.kicad_sch` to extract every value
    that influences the DC operating point. Returns a dict of named
    quantities (ohms for resistors, volts for the Zener).

    Aborts with a clear error message if any expected reference is
    missing from the schematic - this catches the case where a
    component is accidentally removed before the simulation can warn
    that the design no longer matches the model.
    """
    power_text = POWER_SCH.read_text(encoding="utf-8")
    mcu_text = MCU_SCH.read_text(encoding="utf-8")

    def _r(text: str, ref: str) -> float:
        v = read_schematic_property(text, ref, "Value")
        if v is None:
            sys.exit(f"ERROR: {ref} missing from schematic - cannot simulate.")
        r = parse_resistor_value(v)
        if r is None:
            sys.exit(f"ERROR: {ref} value {v!r} not parseable as a resistance.")
        return r

    def _zener(text: str, ref: str) -> float:
        v = read_schematic_property(text, ref, "Value")
        if v is None:
            sys.exit(f"ERROR: {ref} missing from schematic - cannot simulate.")
        z = parse_zener_voltage(v)
        if z is None:
            sys.exit(f"ERROR: {ref} value {v!r} not parseable as a Zener voltage.")
        return z

    return {
        "R1": _r(power_text, "R1"),    # Q1 gate pulldown
        "R2": _r(power_text, "R2"),    # TPS62933 FB top
        "R3": _r(power_text, "R3"),    # TPS62933 FB bottom
        "R4": _r(power_text, "R4"),    # Q1 gate series resistor
        "R5": _r(mcu_text, "R5"),      # I2C pull-up
        "R6": _r(mcu_text, "R6"),      # I2C pull-up
        "R7": _r(mcu_text, "R7"),      # GPIO 8 bootstrap pull-up
        "D3_Vz": _zener(power_text, "D3"),
    }


# ---------------------------------------------------------------------------
# DC operating-point computation
# ---------------------------------------------------------------------------
def simulate_dc(vin: float, design: dict[str, float]) -> dict[str, float]:
    """Compute steady-state voltages at every named net of the OAS power chain
    for the given input voltage. Returns a dict of net -> volts. Negative
    voltages (e.g. for reverse-polarity input) propagate through the model
    correctly: Q1 blocks when Vgs is positive (P-FET off), so all downstream
    rails collapse to 0 V."""
    v = {}
    v["V_24V_RAW"] = vin

    # D1 SMBJ24A clamp: if Vin exceeds Vcl (38.9 V), clamp at Vcl.
    if vin > SMBJ24A_VCL:
        v["V_24V_RAW"] = SMBJ24A_VCL
    elif vin < -1.0:
        # SMBJ24A is unidirectional. With anode->GND and cathode->V_24V,
        # reverse polarity (Vin < 0) forward-biases the diode through
        # its anode-to-cathode path (Vf ~ 0.7 V) - D1 clamps the raw
        # rail at roughly -0.7 V regardless of how negative Vin is.
        v["V_24V_RAW"] = -0.7

    # Q1 AO3401A P-FET behavior. Source connects to V_24V_RAW, Gate
    # pulled toward GND via R1 (100 k ohm) and clamped via D3 Zener
    # through R4 (1 k ohm).
    v_source = v["V_24V_RAW"]
    # Compute the un-clamped Vgs the gate would settle at without D3.
    # With Q1 OFF, no gate current -> R1 pulls gate fully to 0 V ->
    # Vgs = V_gate - V_source = 0 - V_source = -V_source.
    vgs_open = 0.0 - v_source
    # D3 (Zener Vz=10) limits Vgs to no more negative than -Vz when forward
    # current flows (S -> D3 -> R4/R1 junction -> GND).
    if vgs_open < -design["D3_Vz"]:
        vgs = -design["D3_Vz"]
    else:
        vgs = vgs_open

    # Threshold check: AO3401A turns ON only when Vgs is more negative
    # than about -1 V (datasheet Vth_max). When Vsource < 0 (reverse
    # polarity), Vgs is POSITIVE so Q1 stays OFF and isolates downstream.
    q1_on = vgs <= -1.0 and v_source > 0.0

    if q1_on:
        # Q1 conducts with Rds_on series resistance. Drop across Q1 at
        # typical current is negligible (~22 mV at 0.5 A) for DC sanity.
        v_drop_q1 = TOTAL_INPUT_TYPICAL_A * AO3401A_RDS_ON
        v_after_q1 = v_source - v_drop_q1
        # F1 polyfuse adds another ~50 mV at typical current.
        v_drop_f1 = TOTAL_INPUT_TYPICAL_A * F1_COLD_R
        v["V_24V_PROT"] = v_after_q1 - v_drop_f1
    else:
        v["V_24V_PROT"] = 0.0

    # LM2596-5.0 buck (24 V -> 5 V). Ideal regulator within the
    # specified Vin window; otherwise output collapses.
    vin_lm2596 = v["V_24V_PROT"]
    if LM2596_VIN_MIN <= vin_lm2596 <= LM2596_VIN_MAX:
        v["+5V"] = LM2596_VOUT_FIXED_5V
    else:
        v["+5V"] = 0.0

    # TPS62933 buck (5 V -> 3.3 V) with R2/R3 feedback divider.
    vin_tps = v["+5V"]
    if TPS62933_VIN_MIN <= vin_tps <= TPS62933_VIN_MAX:
        v["+3V3"] = TPS62933_VREF * (1.0 + design["R2"] / design["R3"])
    else:
        v["+3V3"] = 0.0

    # Computed stress quantities (for safety-margin checks).
    v["Q1_Vgs"] = vgs
    v["Q1_Vds"] = v_source - v["V_24V_PROT"] if q1_on else v_source - 0.0
    # v0.40 post-order MATH FIX: D3 Zener dissipation. With Q1's gate at
    # DC high-impedance (Igss <= 100 nA), the gate-bias loop is
    # V_source -> D3 -> R1 (100 kohm gate pulldown) -> GND. R4 (1 kohm
    # gate series) carries NO steady-state current because R4 sits
    # between the R1/D3 junction and Q1.gate, and gate current is zero.
    # The pre-v0.40 expression used `design["R4"]` (1k) here which gave
    # 140 mW — 100x overstated. Correct expression uses design["R1"]
    # (100k) for I_z = (V_source - Vz) / R1 = 0.14 mA, so P_D3 = 1.4 mW
    # steady state. (R4 is documented in lcsc-mapping.csv row 11 + power
    # schematic; verified against power.kicad_sch R1 placement.)
    v["D3_P_diss"] = (
        ((v_source - design["D3_Vz"]) / design["R1"]) * design["D3_Vz"]
        if vgs <= -design["D3_Vz"] else 0.0
    )

    return v


def check_in_window(name: str, actual: float, lo: float, hi: float,
                     unit: str = "V") -> CheckResult:
    return CheckResult(
        name=name,
        value=f"{actual:.3f} {unit}",
        spec=f"[{lo:.2f}, {hi:.2f}] {unit}",
        passed=lo <= actual <= hi,
    )


def check_below(name: str, actual: float, limit: float, unit: str = "V") -> CheckResult:
    return CheckResult(
        name=name,
        value=f"{actual:.3f} {unit}",
        spec=f"<= {limit:.2f} {unit}",
        passed=actual <= limit,
    )


def main() -> None:
    print("OAS DC voltage propagation check")
    print("=" * 60)
    print()
    print("Reading design values from schematic...")
    design = read_design_values()
    print(f"  R1 = {design['R1']/1e3:.1f} k ohm (Q1 gate pulldown)")
    print(f"  R2 = {design['R2']/1e3:.1f} k ohm (TPS62933 FB top)")
    print(f"  R3 = {design['R3']/1e3:.1f} k ohm (TPS62933 FB bottom)")
    print(f"  R4 = {design['R4']/1e3:.1f} k ohm (Q1 gate series)")
    print(f"  R5 = {design['R5']/1e3:.1f} k ohm (I2C SDA pull-up)")
    print(f"  R6 = {design['R6']/1e3:.1f} k ohm (I2C SCL pull-up)")
    print(f"  R7 = {design['R7']/1e3:.1f} k ohm (GPIO 8 bootstrap pull-up)")
    print(f"  D3 = {design['D3_Vz']:.1f} V Zener (Q1 Vgs clamp)")
    print()

    all_results: list[CheckResult] = []

    # ---------- Scenario 1: Nominal +24 V ----------
    print("Scenario 1: Nominal Vin = +24.0 V")
    v = simulate_dc(+24.0, design)
    for name, val in v.items():
        if not name.startswith(("Q1_", "D3_")):
            print(f"  V({name}) = {val:.3f} V")
    print()
    s1 = [
        check_in_window("V(V_24V_PROT) - post-Q1+F1",
                         v["V_24V_PROT"], *V24_PROT_WINDOW),
        check_in_window("V(+5V) - LM2596 output",
                         v["+5V"], *RAIL_5V_WINDOW),
        check_in_window("V(+3V3) - TPS62933 output",
                         v["+3V3"], *RAIL_3V3_WINDOW),
        check_below("|Q1.Vgs| - AO3401A clamp",
                     abs(v["Q1_Vgs"]), AO3401A_VGS_MAX_ABS, "V"),
        check_below("D3.P_diss - BZT52C10S",
                     v["D3_P_diss"] * 1000, 200.0, "mW"),
    ]
    all_results.extend(s1)
    for r in s1:
        print(r)
    print()

    # ---------- Scenario 2: Reverse polarity -24 V ----------
    print("Scenario 2: Reverse polarity Vin = -24.0 V (D1 forward bias clamps to -0.7V)")
    v = simulate_dc(-24.0, design)
    for name, val in v.items():
        if not name.startswith(("Q1_", "D3_")):
            print(f"  V({name}) = {val:.3f} V")
    print()
    s2 = [
        check_in_window("V(+5V) - should be 0 V (Q1 off)",
                         v["+5V"], -0.01, 0.01),
        check_in_window("V(+3V3) - should be 0 V",
                         v["+3V3"], -0.01, 0.01),
    ]
    all_results.extend(s2)
    for r in s2:
        print(r)
    print()

    # ---------- Scenario 3: TVS clamp event +50 V transient ----------
    print("Scenario 3: TVS clamp event Vin = +50.0 V transient")
    v = simulate_dc(+50.0, design)
    for name, val in v.items():
        if not name.startswith(("Q1_", "D3_")):
            print(f"  V({name}) = {val:.3f} V")
    print()
    s3 = [
        check_below("V(V_24V_RAW) - D1 clamps to SMBJ24A Vcl",
                     v["V_24V_RAW"], SMBJ24A_VCL + 0.01),
        check_below("|Q1.Vds| - AO3401A absolute max",
                     abs(v["Q1_Vds"]), AO3401A_VDS_MAX_ABS,
                     "V (tight margin)"),
        check_below("|Q1.Vgs| - AO3401A absolute max",
                     abs(v["Q1_Vgs"]), AO3401A_VGS_MAX_ABS, "V"),
    ]
    all_results.extend(s3)
    for r in s3:
        print(r)
    print()

    # ---------- Scenario 4: Brown-out Vin = +6 V ----------
    print("Scenario 4: Brown-out Vin = +6.0 V (below LM2596 Vin_min = 7 V)")
    v = simulate_dc(+6.0, design)
    for name, val in v.items():
        if not name.startswith(("Q1_", "D3_")):
            print(f"  V({name}) = {val:.3f} V")
    print()
    s4 = [
        check_in_window("V(+5V) - should collapse cleanly",
                         v["+5V"], -0.01, 0.01),
        check_in_window("V(+3V3) - should collapse cleanly",
                         v["+3V3"], -0.01, 0.01),
    ]
    all_results.extend(s4)
    for r in s4:
        print(r)
    print()

    # ---------- Summary ----------
    total = len(all_results)
    failed = [r for r in all_results if not r.passed]
    print("=" * 60)
    if failed:
        print(f"FAIL: {len(failed)} of {total} checks failed.")
        for r in failed:
            print(f"  {r}")
        sys.exit(1)
    print(f"PASS: all {total} DC voltage checks passed.")


if __name__ == "__main__":
    main()
