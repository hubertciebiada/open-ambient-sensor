"""Invariant tests on boardgen/_project.py constants + the routing snapshot.

These guard the project-level facts that every downstream artefact
(PCB outline, JLCPCB order, power-protection chain) silently depends on:

  - The 3x M3 mounting holes sit exactly on the Ø110 mm pitch circle at
    the AK-N-94 DXF-derived positions.
  - The AQI LED ring placement helper puts every populated slot on the
    code's pitch-circle radius at 45 deg angular pitch, with the J1 slot
    (index 2 / D13) vacated.

    NOTE on documentation drift: CLAUDE.md mentions both "Ø22 mm" and
    "Ø26 mm" for the ring. The CODE (single source of truth) uses
    LED_RING_RADIUS = 13.0 -> Ø26 mm base pitch circle, with per-index
    radius overrides (LED_RING_RADIUS_OVERRIDE) for clearance reasons.
    These tests assert against the code constants.

  - All mounting holes, LED slots and daughterboard reference anchors
    fall inside the Ø120 mm D-shape outline (r <= 60 mm and, in KiCad's
    +Y-down PCB-local frame, y <= +Y_CHORD where the flat chord lies).
  - POWER_BUDGET schema + per-rail sums vs the derated protector limits
    (CLAUDE.md Lesson 17; radio-group max() mirrors stage 23).
  - The committed oas_routes.py snapshot is structurally sane.

    The counts asserted below track the committed snapshot header in
    oas_routes.py ("Source snapshot: N segments, M vias.").
"""
from __future__ import annotations

import math
from typing import cast

import pytest

import oas_routes
from boardgen import _project

# ---------------------------------------------------------------------------
# Mounting holes — Ø110 mm pitch circle (CLAUDE.md hard constraint #4)
# ---------------------------------------------------------------------------

def test_three_mounting_holes_on_pitch_circle() -> None:
    assert len(_project.HOLE_POSITIONS) == 3
    for x, y in _project.HOLE_POSITIONS:
        assert math.hypot(x, y) == pytest.approx(_project.R_PITCH, abs=1e-6)
    assert _project.R_PITCH == 55.0


def test_mounting_hole_documented_positions() -> None:
    expected = [(47.631, 27.500), (-47.631, 27.500), (0.0, -55.000)]
    for (ex, ey), (x, y) in zip(expected, _project.HOLE_POSITIONS):
        assert abs(x - ex) < 1e-3
        assert abs(y - ey) < 1e-3


# ---------------------------------------------------------------------------
# D-shape outline containment
# ---------------------------------------------------------------------------

def test_chord_y_derivation() -> None:
    # Y_CHORD must stay derived from the outline radius + flat chord.
    expected = math.sqrt(
        _project.R_OUTLINE**2 - (_project.CHORD / 2.0) ** 2
    )
    assert _project.Y_CHORD == pytest.approx(expected, abs=1e-9)
    assert _project.CHORD == 82.6545
    assert _project.R_OUTLINE == 60.0


def _assert_inside_outline(x: float, y: float, what: str) -> None:
    """PCB-local frame: origin = board centre, +Y = screen-down = toward
    the flat chord. Inside the D-shape: within the Ø120 circle AND not
    past the chord line at y = +Y_CHORD."""
    r = math.hypot(x, y)
    assert r <= _project.R_OUTLINE + 1e-9, (
        f"{what} at ({x:.3f}, {y:.3f}) lies outside the Ø120 circle "
        f"(r = {r:.3f} mm)"
    )
    assert y <= _project.Y_CHORD + 1e-9, (
        f"{what} at ({x:.3f}, {y:.3f}) lies past the flat chord "
        f"(y_chord = {_project.Y_CHORD:.4f} mm)"
    )


def test_mounting_holes_inside_outline() -> None:
    for i, (x, y) in enumerate(_project.HOLE_POSITIONS):
        _assert_inside_outline(x, y, f"mounting hole H{i + 1}")


def test_led_slots_inside_outline() -> None:
    for i in range(_project.LED_RING_COUNT):
        if i in _project.LED_RING_SKIP_INDICES:
            continue
        x, y, _rot = _project._led_ring_position(i)
        _assert_inside_outline(x, y, f"LED slot index {i}")


def test_daughterboard_anchors_inside_outline() -> None:
    anchors = {
        "SEN66": (_project.SEN66_ANCHOR_X, _project.SEN66_ANCHOR_Y),
        "LD2410": (_project.LD2410_ANCHOR_X, _project.LD2410_ANCHOR_Y),
        "ESP32 DevKitM-1": (_project.ESP32_ANCHOR_X, _project.ESP32_ANCHOR_Y),
    }
    for name, (x, y) in anchors.items():
        _assert_inside_outline(x, y, f"{name} anchor")


# ---------------------------------------------------------------------------
# AQI LED ring — radius, 45 deg pitch, vacated J1 slot
# ---------------------------------------------------------------------------

def test_led_ring_pitch_is_45_degrees() -> None:
    assert _project.LED_RING_COUNT == 8
    assert _project.LED_RING_THETA_STEP_DEG == 45.0


def test_led_ring_skips_the_j1_slot() -> None:
    # Index 2 -> theta = 90 deg (PCB +Y / south), vacated for the J1
    # 24 V terminal block; designator D13 + cap C22 do not exist.
    assert _project.LED_RING_SKIP_INDICES == (2,)


def test_led_slots_on_code_pitch_radius_and_angle() -> None:
    # Base pitch circle: LED_RING_RADIUS = 13.0 (Ø26 mm), with documented
    # per-index overrides. Assert each placed slot lands at exactly the
    # radius/angle the constants dictate.
    for i in range(_project.LED_RING_COUNT):
        if i in _project.LED_RING_SKIP_INDICES:
            continue
        x, y, _rot = _project._led_ring_position(i)
        expected_r = _project.LED_RING_RADIUS_OVERRIDE.get(
            i, _project.LED_RING_RADIUS
        )
        assert math.hypot(x, y) == pytest.approx(expected_r, abs=1e-9)
        theta = math.degrees(math.atan2(y, x)) % 360.0
        expected_theta = (
            _project.LED_RING_THETA_START_DEG
            + i * _project.LED_RING_THETA_STEP_DEG
        ) % 360.0
        assert theta == pytest.approx(expected_theta, abs=1e-9)


# ---------------------------------------------------------------------------
# POWER_BUDGET — schema + derated rail sums (Lesson 17 / stage 23 mirror)
# ---------------------------------------------------------------------------

_KNOWN_RAILS = {"3V3", "5V", "24V"}


def test_power_budget_schema() -> None:
    assert _project.POWER_BUDGET, "POWER_BUDGET must not be empty"
    for e in _project.POWER_BUDGET:
        assert e["name"], "every entry needs a non-empty name"
        assert e["rail"] in _KNOWN_RAILS, (
            f"{e['name']}: unknown rail {e['rail']!r}"
        )
        assert 0.0 <= e["typ_ma"] <= e["peak_ma"], (
            f"{e['name']}: expected 0 <= typ_ma ({e['typ_ma']}) "
            f"<= peak_ma ({e['peak_ma']})"
        )


def _rail_peak_ma(rail: str) -> float:
    """Per-rail peak sum with radio-group de-duplication: within a
    radio_group only the largest peak counts (ESP32-C6 Wi-Fi/BLE Coex
    time-share — same rule as pipeline/oas/23_check_power_budget.py)."""
    plain = 0.0
    by_group: dict[str, float] = {}
    for e in _project.POWER_BUDGET:
        if e["rail"] != rail:
            continue
        grp = e.get("radio_group")
        if grp:
            by_group[grp] = max(by_group.get(grp, 0.0), e["peak_ma"])
        else:
            plain += e["peak_ma"]
    return plain + sum(by_group.values())


def test_direct_rails_within_derated_limits() -> None:
    derating = _project.POWER_BUDGET_SAFETY_DERATING
    assert 0.0 < derating <= 1.0
    for rail in ("3V3", "5V"):
        peak = _rail_peak_ma(rail)
        derated = _project.POWER_BUDGET_RAIL_LIMITS_MA[rail] * derating
        assert peak <= derated, (
            f"{rail} peak {peak:.1f} mA exceeds derated limit "
            f"{derated:.1f} mA"
        )


def test_projected_24v_input_within_derated_f1_hold() -> None:
    # Conservative upper bound mirroring stage 23: project 5V + 3V3 peak
    # power back through the buck cascade at min(eta), add any direct
    # 24V loads, compare against the derated F1 hold current.
    p_w = (_rail_peak_ma("5V") / 1000.0) * 5.0 + (
        _rail_peak_ma("3V3") / 1000.0
    ) * 3.3
    i_24v_ma = (
        p_w / _project.POWER_BUDGET_BUCK_ETA_MIN / 24.0 * 1000.0
        + _rail_peak_ma("24V")
    )
    derated = (
        _project.POWER_BUDGET_RAIL_LIMITS_MA["24V"]
        * _project.POWER_BUDGET_SAFETY_DERATING
    )
    assert i_24v_ma <= derated, (
        f"projected 24V input peak {i_24v_ma:.1f} mA exceeds derated "
        f"F1 hold budget {derated:.1f} mA"
    )


# ---------------------------------------------------------------------------
# oas_routes.py snapshot sanity
# ---------------------------------------------------------------------------

def test_routes_snapshot_counts() -> None:
    # v0.53 snapshot: SW1 removal (GitHub issue #5) dropped the /IO/BTN
    # net's 7 segments + 2 vias from the v0.50 613 seg / 42 via baseline,
    # then the follow-up dead-copper sweep removed the 6 orphaned GND
    # stitch segments that used to terminate at SW1 pad 2 (600 + 40).
    # The NFC removal (GitHub issue #7) then dropped 14 more segments
    # (2 on the deleted /MCU/NFC_FD net + 12 dead GND stitches anchored
    # at the removed J7.8/J8.8/C12.2 pads) and ADDED 3 bridge vias that
    # replace the former J7.7/J8.5/J8.6 THT feed-throughs on the +3V3 /
    # I2C_SCL / I2C_SDA runs to J3 (SEN66).
    assert len(oas_routes.ROUTES_SEGMENTS) == 586
    assert len(oas_routes.ROUTES_VIAS) == 43


def test_routes_segments_well_formed() -> None:
    # The snapshot dicts hold mixed value types (str / tuple / float),
    # so mypy types lookups as `object` — coerce explicitly.
    for seg in oas_routes.ROUTES_SEGMENTS:
        assert seg["net_name"], f"{seg['uuid_tag']}: empty net_name"
        assert seg["layer"] in ("F.Cu", "B.Cu"), (
            f"{seg['uuid_tag']}: unexpected layer {seg['layer']!r}"
        )
        width = cast(float, seg["width"])
        assert width > 0, f"{seg['uuid_tag']}: non-positive width"


def test_routes_vias_well_formed() -> None:
    for via in oas_routes.ROUTES_VIAS:
        assert via["net_name"], f"{via['uuid_tag']}: empty net_name"
        drill = cast(float, via["drill"])
        size = cast(float, via["size"])
        assert drill > 0, f"{via['uuid_tag']}: non-positive drill"
        assert drill < size, (
            f"{via['uuid_tag']}: drill {drill} must be smaller "
            f"than via size {size}"
        )


def test_routes_uuid_tags_unique() -> None:
    # Deterministic UUID v5 emission (Lesson 9) requires unique tags —
    # a duplicated tag would abort the boardgen replay at emit time.
    tags = [s["uuid_tag"] for s in oas_routes.ROUTES_SEGMENTS]
    tags += [v["uuid_tag"] for v in oas_routes.ROUTES_VIAS]
    assert len(tags) == len(set(tags))
