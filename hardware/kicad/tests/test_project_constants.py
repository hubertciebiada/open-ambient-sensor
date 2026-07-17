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
# _footprints_custom is KiCad-free at import (it imports only _common +
# _project + textwrap), so the suite stays runnable without a KiCad install.
from boardgen import _footprints_custom
from boardgen._routing import ROUTING_CHUNKS

# Signal routing is deferred to GitHub issue #8 (see boardgen/_routing.py):
# while "autoroute" is absent from ROUTING_CHUNKS the oas_routes.py snapshot
# is a frozen reference that no longer matches the emitted (pours-only) board,
# so the snapshot-sanity suites below skip. Geometry tests run regardless.
_routing_deferred = pytest.mark.skipif(
    "autoroute" not in ROUTING_CHUNKS,
    reason="signal routing deferred to issue #8",
)

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

@_routing_deferred
def test_routes_snapshot_counts() -> None:
    # v0.53 snapshot: SW1 removal (GitHub issue #5) dropped the /IO/BTN
    # net's 7 segments + 2 vias from the v0.50 613 seg / 42 via baseline,
    # then the follow-up dead-copper sweep removed the 6 orphaned GND
    # stitch segments that used to terminate at SW1 pad 2 (600 + 40).
    # The NFC removal (GitHub issue #7) then dropped 14 more segments
    # (2 on the deleted /MCU/NFC_FD net + 12 dead GND stitches anchored
    # at the removed J7.8/J8.8/C12.2 pads) and ADDED 3 bridge vias that
    # replace the former J7.7/J8.5/J8.6 THT feed-throughs on the +3V3 /
    # I2C_SCL / I2C_SDA runs to J3 (SEN66). The J3 SDA/SCL pin swap
    # (GitHub issue #6, Lesson 21) then unwound the west-end braid at
    # the I2C bridge vias: -4 braid segments, +3 direct via-to-trunk
    # connectors (585 = 586 - 4 + 3).
    assert len(oas_routes.ROUTES_SEGMENTS) == 585
    assert len(oas_routes.ROUTES_VIAS) == 43


@_routing_deferred
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


@_routing_deferred
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


@_routing_deferred
def test_routes_uuid_tags_unique() -> None:
    # Deterministic UUID v5 emission (Lesson 9) requires unique tags —
    # a duplicated tag would abort the boardgen replay at emit time.
    tags = [s["uuid_tag"] for s in oas_routes.ROUTES_SEGMENTS]
    tags += [v["uuid_tag"] for v in oas_routes.ROUTES_VIAS]
    assert len(tags) == len(set(tags))


# ---------------------------------------------------------------------------
# SEN66 recess cutout (v0.53, GitHub issue #2)
# ---------------------------------------------------------------------------

def test_sen66_anchor_west_shift() -> None:
    # v0.53: anchor moved 2 mm west (23.5 -> 21.5) so the +0.75 mm east cutout
    # margin clears the R60 arc at the body NE corner.
    assert _project.SEN66_ANCHOR_X == 21.5
    assert _project.SEN66_ANCHOR_Y == 22.0
    assert _project.SEN66_ROTATION == 90


def test_sen66_body_dims_in_sync() -> None:
    # _project duplicates the SEN66 body dims (import-DAG constraint) to derive
    # the cutout; they MUST match the real footprint constants.
    assert _project._SEN66_BODY_LONG == _footprints_custom.SEN66_BODY_X
    assert _project._SEN66_BODY_SHORT == _footprints_custom.SEN66_BODY_Y


def test_sen66_ziptie_pcb_positions() -> None:
    # v0.53: pinch points pushed 2 mm outward so their holes clear the cutout.
    expected = {
        "ZT1": (16.5, 0.0),
        "ZT2": (52.1, 0.0),
        "ZT3": (16.5, -8.0),
        "ZT4": (52.1, -8.0),
    }
    for ref, lx, ly in _project.SEN66_ZIPTIE_LOCAL:
        gx, gy = _project._sen66_local_to_pcb(lx, ly)
        ex, ey = expected[ref]
        assert gx == pytest.approx(ex, abs=1e-6)
        assert gy == pytest.approx(ey, abs=1e-6)


def test_j3_placement() -> None:
    # v0.53-b (issue #2 change order): J3 sits in the ZT1/ZT3 column
    # (X = ZT3's PCB X = 16.5), slightly south, mouth still faces WEST.
    assert _project.J3_X == 16.5
    assert _project.J3_Y == 33.5
    assert _project.J3_ROTATION == 90
    # J3 shares the X column with the ZT1/ZT3 zip-tie holes.
    zt3 = next(t for t in _project.SEN66_ZIPTIE_LOCAL if t[0] == "ZT3")
    zt3_pcb_x = _project._sen66_local_to_pcb(zt3[1], zt3[2])[0]
    assert _project.J3_X == pytest.approx(zt3_pcb_x, abs=1e-6)


def _cutout_bounds() -> tuple[float, float, float, float]:
    return (
        _project.SEN66_CUTOUT_X_MIN, _project.SEN66_CUTOUT_X_MAX,
        _project.SEN66_CUTOUT_Y_MIN, _project.SEN66_CUTOUT_Y_MAX,
    )


def test_sen66_cutout_corner_radius_min() -> None:
    # (iv) rounded corners must be >= 1.0 mm so a Ø2 mm internal router bit
    # can mill them.
    assert _project.SEN66_CUTOUT_CORNER_R >= 1.0


def test_sen66_cutout_ne_corner_inside_outline() -> None:
    # (i) the worst-case (sharp) NE cutout corner must stay >= 1.3 mm inside
    # the R60 D-shape outline. Corner rounding pulls the true corner further
    # in, so testing the sharp corner is conservative.
    x0, x1, y0, y1 = _cutout_bounds()
    r = math.hypot(x1, y0)   # NE corner = max X, min Y (north is -Y)
    assert _project.R_OUTLINE - r >= 1.3, (
        f"NE cutout corner rim = {_project.R_OUTLINE - r:.3f} mm (< 1.3 mm)"
    )
    for cx, cy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        _assert_inside_outline(cx, cy, "SEN66 cutout corner")


def _dist_point_to_aabb(px: float, py: float,
                        x0: float, x1: float, y0: float, y1: float) -> float:
    dx = max(x0 - px, 0.0, px - x1)
    dy = max(y0 - py, 0.0, py - y1)
    return math.hypot(dx, dy)


def test_sen66_ziptie_web_to_cutout() -> None:
    # (ii) each Ø3 zip-tie hole must leave >= 2.0 mm of FR4 web between its
    # hole edge and the cutout edge (AABB distance is conservative vs the
    # inward-rounded corners).
    x0, x1, y0, y1 = _cutout_bounds()
    hole_r = _footprints_custom.ZIPTIE_HOLE_DIAMETER / 2.0
    for ref, lx, ly in _project.SEN66_ZIPTIE_LOCAL:
        gx, gy = _project._sen66_local_to_pcb(lx, ly)
        web = _dist_point_to_aabb(gx, gy, x0, x1, y0, y1) - hole_r
        assert web >= 2.0, f"{ref} web to cutout = {web:.3f} mm (< 2.0 mm)"


def test_protection_cluster_east_clearance_to_cutout() -> None:
    # (iii) the protection cluster's right column (X=+17 as of v0.53) — widest
    # courtyard is D1's SMB, half-extent 2.25 mm along PCB X at rotation 90
    # (stock Diode_SMD:D_SMB courtyard 3.65 x 2.25 mm; rot90 swaps axes). Its
    # east courtyard edge must clear the cutout west edge by >= 1.0 mm.
    # RIGHT_COL_X + D_SMB_CRTYD_HALF are documented literals mirroring
    # gen_power_pcb_footprints() and the KiCad stock D_SMB footprint (kept out
    # of the import path so the suite stays KiCad-free).
    RIGHT_COL_X = 17.0
    D_SMB_CRTYD_HALF_X_AT_ROT90 = 2.25
    east_edge = RIGHT_COL_X + D_SMB_CRTYD_HALF_X_AT_ROT90
    gap = _project.SEN66_CUTOUT_X_MIN - east_edge
    assert gap >= 1.0, (
        f"cluster east courtyard to cutout = {gap:.3f} mm (< 1.0 mm)"
    )


def test_cutout_margin_restored_to_full() -> None:
    # v0.53 (issue #3): the Task-1 west-margin trim (0.8) was reverted once the
    # ESP32 silk left X≈20. Full 1.0 mm press-fit margin -> cutout west 20.5.
    assert _project.SEN66_CUTOUT_MARGIN_W == 1.0
    assert _project.SEN66_CUTOUT_X_MIN == pytest.approx(20.5, abs=1e-6)


# ---------------------------------------------------------------------------
# ESP32-C6 DevKitM-1 -7.5 mm west move + antenna tab (issue #3)
# ---------------------------------------------------------------------------

def test_esp32_moved_west_for_issue3() -> None:
    # -7.5 mm west of the old -27.76 so the DevKit seats next to the THT caps.
    assert _project.ESP32_ANCHOR_X == pytest.approx(-35.26, abs=1e-6)
    # J5/J6 pin rows derive from the anchor: row-1 X = anchor + pin_start.
    row_x_start = _project.ESP32_ANCHOR_X + _project.ESP32_PIN_START_OFFSET
    assert row_x_start == pytest.approx(-29.89, abs=1e-6)


def test_esp32_antenna_tab_constants() -> None:
    # Both from the Espressif dimensions PDF (Lesson 6): width 13.20 over the
    # antenna rectangle, protrusion 5.37 from the board antenna edge to the
    # tab tip (reviewer-confirmed).
    assert _project.ESP32_ANTENNA_TAB_W == pytest.approx(13.20, abs=1e-6)
    assert _project.ESP32_ANTENNA_TAB_PROTRUSION == pytest.approx(5.37, abs=1e-6)


def test_esp32_body_nw_corner_overhang_is_expected() -> None:
    # KNOWN, user-ACCEPTED overhang (issue #3, pending enclosure check): the
    # DevKit body NW corner sits PAST the R60 outline. Assert the exact value
    # so any silent drift (a further move, a body-dim change) is caught.
    # NW corner PCB = (anchor_x, anchor_y - body_w) under the rot-90 daughter-
    # board transform LIB(lx,ly) -> PCB(anchor_x+ly, anchor_y-lx).
    nx = _project.ESP32_ANCHOR_X
    ny = _project.ESP32_ANCHOR_Y - _project.ESP32_BODY_W
    r = math.hypot(nx, ny)
    assert r > _project.R_OUTLINE, "body NW corner should overhang R60"
    assert r - _project.R_OUTLINE == pytest.approx(1.264, abs=0.01)


def test_esp32_antenna_tab_corner_just_inside_outline() -> None:
    # With the PDF-exact 5.37 mm protrusion the antenna tab far corner sits
    # JUST INSIDE the R60 outline (~0.11 mm) — so the tab itself does NOT
    # overhang; only the body NW corner does. Assert the exact clearance so a
    # protrusion change (or a further move) that pushes the tab off-board is
    # caught. Tab far corner PCB = (anchor_x - protrusion,
    #                               anchor_y - (body_w + tab_w)/2).
    tx = _project.ESP32_ANCHOR_X - _project.ESP32_ANTENNA_TAB_PROTRUSION
    ty = _project.ESP32_ANCHOR_Y - (
        _project.ESP32_BODY_W + _project.ESP32_ANTENNA_TAB_W
    ) / 2.0
    r = math.hypot(tx, ty)
    assert r < _project.R_OUTLINE, "antenna tab corner should stay inside R60"
    assert _project.R_OUTLINE - r == pytest.approx(0.11, abs=0.02)


def test_devkit_east_edge_clears_c3_can() -> None:
    # The whole point of the move: the DevKit body east edge must clear the
    # C3 Ø8 mm radial can's west rim by a comfortable margin so the module
    # seats fully. C3 can centre (25.75, -39) + Ø8 mirror gen_power_pcb_
    # footprints(); documented literals keep the suite KiCad-free.
    C3_CAN_CENTRE_X = 25.75
    C3_CAN_DIAMETER = 8.0
    devkit_east = _project.ESP32_ANCHOR_X + _project.ESP32_BODY_L
    c3_west_rim = C3_CAN_CENTRE_X - C3_CAN_DIAMETER / 2.0
    gap = c3_west_rim - devkit_east
    assert gap >= 5.0, f"DevKit east to C3 can = {gap:.3f} mm (< 5.0 mm)"


def test_j9_clears_cutout_after_margin_restore() -> None:
    # v0.53 (issue #3): J9 nudged to +16.0 so its east mounting-ear copper /
    # courtyard clear the restored cutout west edge (+20.5). J9 MP-ear east
    # copper edge = J9_X + 3.40, courtyard east = J9_X + 3.90 (from the stock
    # JST_SH footprint; documented literals). Both must clear the cutout west
    # edge by >= 0.30 mm.
    assert _project.J9_PCB_X == pytest.approx(16.0, abs=1e-6)
    mp_copper_east = _project.J9_PCB_X + 3.40
    mp_courtyard_east = _project.J9_PCB_X + 3.90
    assert _project.SEN66_CUTOUT_X_MIN - mp_copper_east >= 0.30
    assert _project.SEN66_CUTOUT_X_MIN - mp_courtyard_east >= 0.30
