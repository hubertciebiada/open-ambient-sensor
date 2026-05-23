"""Stage 23: power-budget check — per-rail current sum vs derated spec.

Reads `boardgen._project.POWER_BUDGET` (single source of truth — the same
table feeds the planned stage 25 thermal check). Sums typical and peak
current per rail, projects rail power back onto the 24 V input via the
conservative min(η) of the LM2596, and compares each rail's peak load
against the derated spec maximum of the chain protector (LM2596 / TPS62933
/ F1 PTC).

Catches the class of regression where a new load gets added (firmware
adds a Wi-Fi mesh, or hardware adds a second-bus current sink) and the
combined draw silently exceeds what the protectors can deliver — most
visible to the user as F1 PTC trip + rail brown-out under load.

Derating
--------
`POWER_BUDGET_SAFETY_DERATING = 0.80` (module constant in `_project.py`)
applies to every rail uniformly. 80% is industrial-default; tighten to
0.70 (long-life) or relax to 0.85 (DIY hobbyist) in one place.

Radio concurrency
-----------------
ESP32-C6 Wi-Fi and BLE entries share a `radio_group = "esp32_radio"`
tag. Per-rail peak summation de-duplicates: only the LARGEST peak inside
a group counts (radio time-shares within a single SoC).

24 V projection
---------------
   I_24V_peak ≈ (P_5V_peak + P_3V3_peak) / η_min / 24V
with η_min = POWER_BUDGET_BUCK_ETA_MIN = 0.50 (LM2596 light-load floor
per TI SNVS124N efficiency curves). This is conservative — actual η
near full load is ~80%, so the computed I_24V_peak overstates by ~1.6×.
Comfortable margin against F1 hold (750 mA).

Exit code 0 on PASS (every rail's derated budget covers its peak load).
Exit 1 on FAIL with all rail totals + which rail(s) breached. Designed
to run as a `build.py` stage OR standalone.

Implements Lesson 17 (CLAUDE.md) — TypedDict POWER_BUDGET pattern with
NotRequired[...] for optional keys + TYPE_CHECKING import of
PowerBudgetEntry from boardgen._project (no runtime cost, no cycle).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT  # noqa: E402

if TYPE_CHECKING:
    sys.path.insert(0, str(KICAD_ROOT))
    from boardgen._project import PowerBudgetEntry

STAGE_NAME = "check_power_budget"

V_24V = 24.0
V_5V = 5.0
V_3V3 = 3.3
RAIL_VOLTAGE = {"24V": V_24V, "5V": V_5V, "3V3": V_3V3}


@dataclass
class RailTotals:
    rail: str
    typ_ma: float
    peak_ma: float


def _summed_peak_with_radio_groups(entries: list[PowerBudgetEntry]) -> float:
    """Sum peak_ma over entries, but for any entry that carries a
    `radio_group` key, only the LARGEST peak within each group counts
    (radios time-share within one SoC — never two TX simultaneously).

    Entries WITHOUT a `radio_group` key sum normally."""
    plain = 0.0
    by_group: dict[str, float] = {}
    for e in entries:
        peak = e["peak_ma"]
        grp = e.get("radio_group")
        if grp:
            if peak > by_group.get(grp, 0.0):
                by_group[grp] = peak
        else:
            plain += peak
    return plain + sum(by_group.values())


def main() -> int:
    with Stage(STAGE_NAME) as st:
        sys.path.insert(0, str(KICAD_ROOT))
        from boardgen._project import (  # noqa: E402
            POWER_BUDGET,
            POWER_BUDGET_BUCK_ETA_MIN,
            POWER_BUDGET_RAIL_LIMITS_MA,
            POWER_BUDGET_SAFETY_DERATING,
        )

        st.info(f"Loaded {len(POWER_BUDGET)} power-budget entries")
        st.info(
            f"Safety derating: {POWER_BUDGET_SAFETY_DERATING * 100:.0f}% "
            f"of spec maximum; buck min(eta) = {POWER_BUDGET_BUCK_ETA_MIN:.2f}"
        )

        # Group entries by rail (preserves source order within each rail).
        by_rail: dict[str, list[PowerBudgetEntry]] = {}
        for e in POWER_BUDGET:
            rail = e["rail"]
            if rail not in RAIL_VOLTAGE:
                st.fail(
                    f"POWER_BUDGET entry {e['name']!r} has unknown rail "
                    f"{rail!r} (expected one of {list(RAIL_VOLTAGE)})"
                )
            by_rail.setdefault(rail, []).append(e)

        # Per-rail sums.
        rail_totals: dict[str, RailTotals] = {}
        for rail, entries in by_rail.items():
            typ = sum(e["typ_ma"] for e in entries)
            peak = _summed_peak_with_radio_groups(entries)
            rail_totals[rail] = RailTotals(rail=rail, typ_ma=typ, peak_ma=peak)

        # Project 5V + 3V3 rail power back onto the 24V input via min(η)
        # of the LM2596. The 3V3 rail comes from the TPS62933 which is
        # itself fed by 5V; we treat the cascade as a single net efficiency
        # for the conservative bound (η_cascade ≤ η_LM2596 since η_TPS ≤ 1).
        p_5v_typ_w = (rail_totals.get("5V", RailTotals("5V", 0, 0)).typ_ma
                      / 1000.0) * V_5V
        p_5v_peak_w = (rail_totals.get("5V", RailTotals("5V", 0, 0)).peak_ma
                       / 1000.0) * V_5V
        p_3v3_typ_w = (rail_totals.get("3V3", RailTotals("3V3", 0, 0)).typ_ma
                       / 1000.0) * V_3V3
        p_3v3_peak_w = (rail_totals.get("3V3", RailTotals("3V3", 0, 0)).peak_ma
                        / 1000.0) * V_3V3

        i_24v_typ_ma = ((p_5v_typ_w + p_3v3_typ_w)
                        / POWER_BUDGET_BUCK_ETA_MIN / V_24V * 1000.0)
        i_24v_peak_ma = ((p_5v_peak_w + p_3v3_peak_w)
                         / POWER_BUDGET_BUCK_ETA_MIN / V_24V * 1000.0)

        # Any explicit 24V loads in the table (none today, but keep the
        # arithmetic honest for future additions).
        rail_24v = rail_totals.get("24V", RailTotals("24V", 0, 0))
        i_24v_typ_ma += rail_24v.typ_ma
        i_24v_peak_ma += rail_24v.peak_ma
        rail_totals["24V"] = RailTotals(
            rail="24V", typ_ma=i_24v_typ_ma, peak_ma=i_24v_peak_ma
        )

        # Detailed per-rail report (info — never alone a fail).
        st.info("")
        st.info("Per-rail load enumeration:")
        for rail in ("3V3", "5V", "24V"):
            tot = rail_totals.get(rail)
            if tot is None:
                continue
            st.info(
                f"  {rail:>4s}: typ = {tot.typ_ma:7.1f} mA, "
                f"peak = {tot.peak_ma:7.1f} mA"
            )
            if rail == "24V":
                # Show the components of the 24V calc.
                st.info(
                    f"        (computed as (P_5V_peak={p_5v_peak_w:.2f} W "
                    f"+ P_3V3_peak={p_3v3_peak_w:.2f} W) / eta_min="
                    f"{POWER_BUDGET_BUCK_ETA_MIN:.2f} / 24 V = "
                    f"{i_24v_peak_ma:.1f} mA peak)"
                )
            else:
                for e in by_rail.get(rail, []):
                    grp = (
                        f" [group:{e['radio_group']}]"
                        if "radio_group" in e else ""
                    )
                    st.info(
                        f"        - {e['name']}: "
                        f"typ={e['typ_ma']:.1f} mA, "
                        f"peak={e['peak_ma']:.1f} mA{grp}"
                    )

        # Per-rail derated checks.
        st.info("")
        st.info("Per-rail derated checks:")
        failures: list[str] = []
        for rail in ("3V3", "5V", "24V"):
            limit_ma = POWER_BUDGET_RAIL_LIMITS_MA[rail]
            derated_ma = limit_ma * POWER_BUDGET_SAFETY_DERATING
            tot = rail_totals[rail]
            margin = (
                (derated_ma - tot.peak_ma) / derated_ma * 100.0
                if derated_ma > 0 else 0.0
            )
            headroom_x = (
                derated_ma / tot.peak_ma if tot.peak_ma > 0 else float("inf")
            )
            verdict = "PASS" if tot.peak_ma <= derated_ma else "FAIL"
            st.info(
                f"  [{verdict}] {rail:>4s}: peak {tot.peak_ma:7.1f} mA "
                f"<= derated {derated_ma:7.1f} mA "
                f"(= {POWER_BUDGET_SAFETY_DERATING:.0%} of "
                f"{limit_ma:.0f} mA spec); "
                f"margin {margin:+.1f}% / headroom {headroom_x:.2f}x"
            )
            if tot.peak_ma > derated_ma:
                failures.append(
                    f"{rail} peak {tot.peak_ma:.1f} mA exceeds derated "
                    f"limit {derated_ma:.1f} mA (spec {limit_ma:.0f} mA x "
                    f"{POWER_BUDGET_SAFETY_DERATING:.0%})"
                )

        if failures:
            for f in failures:
                print(f"[FAIL] {f}")
            st.fail(f"{len(failures)} rail(s) breached the derated budget")

        st.ok(
            f"All {len(rail_totals)} rails within "
            f"{POWER_BUDGET_SAFETY_DERATING:.0%} derated budget"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
