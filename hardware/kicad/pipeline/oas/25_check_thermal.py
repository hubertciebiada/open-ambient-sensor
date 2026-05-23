"""Stage 25: LM2596 junction-temperature check (pure Python analytical).

Verifies the U1 LM2596S-5.0/NOPB buck regulator stays within TI's
recommended Tj operating envelope under worst-case OAS load. Catches
the class of regression where (a) the +5 V load budget grows
silently (e.g. LED ring brightness uncapped, an additional 5 V
peripheral added), (b) the U1 footprint thermal-pad Cu area shrinks
in a layout iteration, or (c) the ambient assumption drifts.

Single source of truth couplings
--------------------------------
  * Load currents:  `boardgen._project.POWER_BUDGET` — same table that
    feeds stage 23 (`23_check_power_budget`). Sum every entry with
    `rail == "5V"` (peak_ma) to get the LM2596 output peak current.
  * Tab Cu area:    `boardgen._footprints_stock.gen_to263_5_lm2596_footprint`
    encodes the pad "3" tab geometry verbatim from EasyEDA LCSC C116713
    (8.705 × 10.587 mm). We extract the same numbers by parsing
    `oas.kicad_pcb` so any geometric drift surfaces here, not in the
    next JLCPCB DFM round.

Thermal model
-------------
   Tj = Tamb + Pdiss × RθJA

   Pdiss(U1) = Vout × Iout × (1/η - 1)         [async-buck low-side]
             = 5.0 V × Iout × (1/0.75 - 1)
             = 5.0 V × Iout × 0.333

   η_LM2596 ≈ 0.75 at Iout ≈ 0.5 A, Vin = 24 V, Vout = 5 V
     (TI SNVS124N §7.2 "Efficiency vs Load Current" curves for the
      LM2596-5.0 variant, 12 V and 25 V Vin traces; 24V/5V/0.5A is
      between published curves — 75% is the conservative read).

RθJA extrapolation
------------------
TI SNVS124N §7.4 "Thermal Information" Table 7-2 publishes RθJA for
the TO-263-5 (KTW) package on the JEDEC JESD51-7 single-sided
1-oz Cu eval board:

   RθJA = 50 °C/W   at 2.5 in² (1613 mm²) of free-air-side Cu
   RθJA = 73 °C/W   at 0.5 in² ( 323 mm²)

Neither anchor reaches the OAS pad-only ~92 mm² (0.143 in²). We
extrapolate piecewise-linearly on the (area, RθJA) plane and clamp
to a conservative 90 °C/W at and below 92 mm² — this matches the
TI app-note SLVA462 ("Semiconductor and IC Package Thermal Metrics")
guidance that RθJA degrades sharply at sub-0.25 in² heatsinking and
that extrapolations below the published anchors should err high.

Closed-enclosure derating
-------------------------
JESD51-7 assumes 25 °C still air on an open eval board. The AK-N-94
perforated ABS enclosure restricts convection — typical derating is
+20-30% on RθJA OR +5-10 °C on Tamb. This stage chooses the latter:
Tamb = 45 °C worst-case (= 30 °C summer indoor ambient + 15 °C
enclosure internal rise) and uses the raw extrapolated RθJA from
the JESD51-7 curve. The two approaches give equivalent margin on
this rail; documenting the choice in one place keeps the math
auditable.

Pass / Warn / Fail
------------------
   Tj > 125 °C   -> FAIL  (TI recommended Tj_max, 25 °C below absolute)
   Tj > 110 °C   -> WARN  (15 °C buffer)
   Cu < 200 mm²  -> WARN  (info: confirms the tab is small)
   otherwise     -> PASS

Exit code 0 on PASS or WARN, 1 on FAIL.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
from _common import Stage  # noqa: E402

KICAD_DIR = HERE.parent.parent  # pipeline/oas/ -> pipeline/ -> hardware/kicad
PCB_PATH = KICAD_DIR / "oas.kicad_pcb"

STAGE_NAME = "check_thermal"

# Datasheet-anchored constants. Update only when the part is swapped.
# ---------------------------------------------------------------------------

# Worst-case enclosed-ambient air temperature inside the AK-N-94.
# Derivation:
#   30 °C summer indoor ambient (Polish climate, no A/C deployment)
# + 15 °C enclosure internal rise (closed perforated ABS, low convection)
# = 45 °C steady-state air around U1.
# This is the "enclosure derating" knob — bumping Tamb here is
# equivalent to multiplying RθJA by ~1.2 (the alternative knob).
TAMB_WORST_C = 45.0

# TI LM2596 efficiency at the OAS operating point.
# SNVS124N §7.2 efficiency curves — for Vin=12 V/25 V the 0.5-A
# Vout=5 V trace sits at ~78%/72%. Interpolating to 24 V Vin and
# rounding down for margin → 0.75.
ETA_LM2596 = 0.75

# Output voltage of the fixed LM2596S-5.0 variant (TI SNVS124N §4
# "Electrical Characteristics" Vout nominal).
VOUT_LM2596 = 5.0

# RθJA piecewise-linear table — list of (Cu_area_mm2, RθJA_C_per_W).
# Anchors:
#   (1613 mm² / 2.5 in²,  50 °C/W)  TI SNVS124N Table 7-2, footnote 6.
#   ( 323 mm² / 0.5 in²,  73 °C/W)  TI SNVS124N Table 7-2.
#   (  92 mm² / 0.14 in², 90 °C/W)  OAS-conservative extrapolation
#                                   below the smallest TI anchor (see
#                                   SLVA462 guidance on sub-0.25 in²
#                                   heatsinking derating).
RTHJA_CURVE = [
    (92.0,   90.0),
    (323.0,  73.0),
    (1613.0, 50.0),
]

# Pass / warn / fail thresholds (junction temperature, °C).
TJ_FAIL_C = 125.0   # TI recommended operating max (25 °C below 150 °C absolute)
TJ_WARN_C = 110.0   # 15 °C buffer under FAIL
CU_WARN_MM2 = 200.0  # below this, flag the tab as small (info only)


def rthja_from_area(cu_mm2: float) -> tuple[float, str]:
    """Look up RθJA for the given Cu area on `RTHJA_CURVE`.

    Returns (rthja_C_per_W, citation_str). Piecewise-linear between
    anchors; clamped to the first anchor below the smallest area
    (conservative — extrapolating linearly past the small-area end
    would understate RθJA, masking real risk)."""
    anchors = sorted(RTHJA_CURVE)
    if cu_mm2 <= anchors[0][0]:
        a, r = anchors[0]
        return r, f"clamped to anchor at {a:.0f} mm^2 ({r:.0f} C/W)"
    if cu_mm2 >= anchors[-1][0]:
        a, r = anchors[-1]
        return r, f"clamped to anchor at {a:.0f} mm^2 ({r:.0f} C/W)"
    for (a0, r0), (a1, r1) in zip(anchors, anchors[1:]):
        if a0 <= cu_mm2 <= a1:
            t = (cu_mm2 - a0) / (a1 - a0)
            r = r0 + t * (r1 - r0)
            return r, (
                f"linear between ({a0:.0f} mm^2, {r0:.0f} C/W) and "
                f"({a1:.0f} mm^2, {r1:.0f} C/W)"
            )
    # Should be unreachable given the clamps above.
    return anchors[0][1], "fallback clamp"


def _block_end(text: str, start: int) -> int:
    """Index just past the ')' matching the '(' at `start`."""
    n = len(text)
    depth = 0
    in_str = False
    j = start
    while j < n:
        c = text[j]
        if in_str:
            if c == "\\":
                j += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    raise ValueError("unbalanced S-expression")


def parse_u1_tab_area_mm2(pcb_text: str) -> tuple[float, str]:
    """Find U1 (oas:TO-263-5_LM2596) and return the tab pad's Cu area.

    The tab pad is identified as pad "3" with the LARGEST size — the
    footprint emits two pads numbered "3": the small 3.5 × 1.02 mm
    lead at -8.23 mm and the 8.705 × 10.587 mm thermal tab at +2.022 mm.
    Returns (area_mm2, "<w> × <h> mm at (<x>, <y>)").
    """
    # Locate the U1 footprint block.
    fp_re = re.compile(r'\(footprint\s+"oas:TO-263-5_LM2596"')
    ref_re = re.compile(r'\(property\s+"Reference"\s+"U1"')
    for m in fp_re.finditer(pcb_text):
        fp_start = m.start()
        fp_end = _block_end(pcb_text, fp_start)
        block = pcb_text[fp_start:fp_end]
        if not ref_re.search(block):
            continue
        # Scan all (pad "3" ... blocks; pick the one with the largest area.
        best_area = 0.0
        best_desc = ""
        i = 0
        while True:
            k = block.find('(pad "3"', i)
            if k < 0:
                break
            pe = _block_end(block, k)
            pad_block = block[k:pe]
            ms = re.search(r"\(size\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\)", pad_block)
            mat = re.search(
                r"\(at\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)(?:\s+-?\d+\.?\d*)?\)",
                pad_block,
            )
            if ms and mat:
                w, h = float(ms.group(1)), float(ms.group(2))
                x, y = float(mat.group(1)), float(mat.group(2))
                area = w * h
                if area > best_area:
                    best_area = area
                    best_desc = (
                        f"{w:.3f} x {h:.3f} mm at ({x:.3f}, {y:.3f}) "
                        "[footprint-local]"
                    )
            i = pe
        if best_area > 0.0:
            return best_area, best_desc
    raise RuntimeError(
        "U1 (oas:TO-263-5_LM2596) tab pad not found in oas.kicad_pcb"
    )


def main() -> int:
    with Stage(STAGE_NAME) as st:
        if not PCB_PATH.exists():
            st.fail(f"{PCB_PATH} not found — run build.py first.")

        # ---- 1. Tab Cu area (from oas.kicad_pcb) ----
        pcb_text = PCB_PATH.read_text(encoding="utf-8")
        cu_mm2, cu_desc = parse_u1_tab_area_mm2(pcb_text)
        st.info(
            f"U1 tab Cu (pad 3, thermal): {cu_mm2:.2f} mm^2 "
            f"({cu_mm2 * 0.00155:.4f} in^2)"
        )
        st.info(f"  geometry: {cu_desc}")
        st.info(
            "  source: oas.kicad_pcb (verbatim EasyEDA C116713 land via "
            "boardgen._footprints_stock.gen_to263_5_lm2596_footprint)"
        )
        st.info(
            "  note: no pour extension to the tab on F.Cu - V_24V_PROT "
            "pour blocks GND pour fan-out around U1. Computed area = "
            "pad-only (conservative)."
        )

        # ---- 2. Load Iout(5V peak) from POWER_BUDGET ----
        sys.path.insert(0, str(KICAD_DIR))
        from boardgen._project import POWER_BUDGET  # noqa: E402

        rail_5v = [e for e in POWER_BUDGET if e.get("rail") == "5V"]
        if not rail_5v:
            st.fail("POWER_BUDGET has no entries on the 5V rail — cannot compute Iout.")
        iout_ma = sum(e["peak_ma"] for e in rail_5v)
        iout_a = iout_ma / 1000.0
        st.info(f"Iout(LM2596, peak) = {iout_ma:.1f} mA from POWER_BUDGET 5V rail:")
        for e in rail_5v:
            st.info(f"  + {e['peak_ma']:6.1f} mA   {e['name']}")

        # ---- 3. RthJA chosen ----
        rthja, rthja_cite = rthja_from_area(cu_mm2)
        st.info(
            f"RthJA = {rthja:.1f} C/W  ({rthja_cite}; "
            f"TI SNVS124N Table 7-2 anchors at 0.5 in^2 / 2.5 in^2)"
        )

        # ---- 4. Pdiss ----
        # Async buck low-side approximation: P_loss = P_out * (1/eta - 1)
        # = Vout * Iout * (1/eta - 1).
        pdiss_w = VOUT_LM2596 * iout_a * (1.0 / ETA_LM2596 - 1.0)
        st.info(
            f"eta_LM2596 = {ETA_LM2596:.2f} (TI SNVS124N sec.7.2 efficiency "
            f"curves, 24V/5V/~{iout_ma:.0f} mA conservative read)"
        )
        st.info(
            f"Pdiss(U1) = Vout * Iout * (1/eta - 1) = "
            f"{VOUT_LM2596:.1f} V * {iout_a:.3f} A * "
            f"{1.0/ETA_LM2596 - 1.0:.3f} = {pdiss_w*1000:.1f} mW"
        )

        # ---- 5. Tj ----
        tj_c = TAMB_WORST_C + pdiss_w * rthja
        st.info(
            f"Tamb (worst-case, AK-N-94 closed perforated ABS) = "
            f"{TAMB_WORST_C:.1f} C  (30 C summer indoor + 15 C "
            f"enclosure internal rise)"
        )
        st.info(
            f"Tj = Tamb + Pdiss * RthJA = "
            f"{TAMB_WORST_C:.1f} + {pdiss_w*1000:.1f} mW * {rthja:.1f} C/W = "
            f"{tj_c:.1f} C"
        )

        # ---- 6. Pass / warn / fail ----
        margin_c = TJ_FAIL_C - tj_c
        warned = False
        if cu_mm2 < CU_WARN_MM2:
            st.warn(
                f"Tab Cu area {cu_mm2:.0f} mm^2 < {CU_WARN_MM2:.0f} mm^2 "
                "- small thermal-pad heatsinking is acknowledged (info only; "
                "the RthJA extrapolation reflects this)."
            )
            warned = True
        if tj_c > TJ_FAIL_C:
            st.fail(
                f"Tj = {tj_c:.1f} C exceeds {TJ_FAIL_C:.0f} C TI "
                f"recommended Tj_max. "
                f"Margin = {margin_c:.1f} C (NEGATIVE). "
                f"Reduce Iout(5V) (cap LED brightness / lighten ring load), "
                f"or enlarge U1 tab Cu (pour extension / bottom-side fill via "
                f"thermal vias), or both. DO NOT relax this threshold."
            )
            # st.fail() calls sys.exit(1); unreached.
        if tj_c > TJ_WARN_C:
            st.warn(
                f"Tj = {tj_c:.1f} C exceeds {TJ_WARN_C:.0f} C warn buffer. "
                f"Margin to FAIL ({TJ_FAIL_C:.0f} C) = {margin_c:.1f} C."
            )
            warned = True

        if warned:
            st.ok(
                f"thermal check PASS (with warnings). Tj = {tj_c:.1f} C, "
                f"margin to TI Tj_max = {margin_c:.1f} C."
            )
        else:
            st.ok(
                f"thermal check PASS. Tj = {tj_c:.1f} C "
                f"(< {TJ_WARN_C:.0f} C warn, < {TJ_FAIL_C:.0f} C fail). "
                f"Margin to TI Tj_max = {margin_c:.1f} C."
            )
        return 0


if __name__ == "__main__":
    sys.exit(main())
