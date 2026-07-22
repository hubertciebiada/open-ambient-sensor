"""
Via geometry invariants — the class DRC and the fab's DFM both miss.

WHY THIS EXISTS (CLAUDE.md Lesson 26). GND stitch vias are placed
programmatically: the island stitcher drops one wherever a point sits
inside GND copper on both layers, and it knows nothing about pads. That
is fine for connectivity and catastrophic for manufacturing — a via can
land on a same-net SMD land, where:

  * KiCad DRC is silent BY DESIGN. Same-net copper overlap is not a
    clearance violation, so no rule fires.
  * JLCPCB's DFM scanner ALSO missed it. On the 2026-07-22 board a via
    sat with its drill 0.07 mm INSIDE D18.4's pad copper and both
    "Via to pad" and "Via placed within a pad" scored 0/0/0.

Nobody checks this for us, so the build does.

SCOPE. Deliberately limited to what the fab does NOT reliably catch:
via-to-pad-copper and via-to-via. Silkscreen-to-hole is left out — it
needs stroke-rendered text (i.e. the silk gerber, which only exists from
stage 20 onward, after this suite runs at stage 16) and JLCDFM has caught
that class reliably on every pass. Foreign-net copper clearance is left
to DRC, which does it properly; duplicating it here would only add a
second, worse implementation.

ACCURACY IS THE WHOLE POINT (Lesson 26, second half). Every pad shape is
modelled EXACTLY — circle, oval, rect and roundrect all have closed-form
point distances. Modelling a pad as its bounding box is what turns a
clean board into a page of phantom findings: a circular THT pad becomes
its circumscribed square, whose corners overhang real copper by 0.207*d,
and every 45-degree fanout track clips that phantom corner. An audit that
cries wolf gets ignored, so it must not approximate in the direction of
false alarms.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import NamedTuple

import pytest

from boardgen._routing import ROUTING_CHUNKS

PCB = Path(__file__).parent.parent / "oas.kicad_pcb"
PAGE_CENTRE_X, PAGE_CENTRE_Y = 148.5, 105.0

# Thresholds ---------------------------------------------------------------
# The MANUFACTURING hazard, not the placement target. A via's copper ring
# is 0.35 mm; requiring 0.05 mm of clear space between that ring and any
# pad's copper edge is what keeps the drill out of a solder land and the
# annular ring intact. Lesson 25's 0.60 mm is where a via gets PLACED —
# asserting it here would fail two vias that are physically fine (a +3V3
# via at 0.563 mm from C17.1, the C20.2 rescue at exactly 0.600 mm), and
# churning good geometry to satisfy a round number is not an improvement.
VIA_RING_CLEARANCE = 0.05
# Two 0.30 mm drills need a real FR4 web between them; below this they
# risk breaking into one slot. Same-net stitches are the usual offenders
# because, again, DRC does not look.
MIN_VIA_TO_VIA = 0.90

# A parse that silently finds nothing would make every assertion below
# vacuously true — the failure mode Lesson 12 hit in extract_routes.py.
# These floors are deliberately loose: they catch a broken regex, not a
# design change.
MIN_EXPECTED_PADS = 150
MIN_EXPECTED_VIAS = 20

_routing_on = pytest.mark.skipif(
    "autoroute" not in ROUTING_CHUNKS,
    reason="no snapshot vias on the board while signal routing is off",
)


class Pad(NamedTuple):
    ref: str
    num: str
    x: float
    y: float
    w: float
    h: float
    rot: float
    shape: str
    rratio: float

    def distance_to(self, px: float, py: float) -> float:
        """Exact distance from (px, py) to this pad's copper outline.

        0.0 when the point is inside the copper. Every shape used on this
        board has a closed form; see the module docstring for why an
        approximation is not acceptable here.
        """
        # into the pad's own frame
        t = math.radians(-self.rot)
        dx, dy = px - self.x, py - self.y
        lx = dx * math.cos(t) - dy * math.sin(t)
        ly = dx * math.sin(t) + dy * math.cos(t)

        if self.shape == "circle":
            return max(0.0, math.hypot(lx, ly) - self.w / 2.0)

        if self.shape == "oval":
            # capsule: a segment of length |w-h| swept by a radius
            r = min(self.w, self.h) / 2.0
            if self.w >= self.h:
                cx = _clamp(lx, self.w / 2.0 - r)
                return max(0.0, math.hypot(lx - cx, ly) - r)
            cy = _clamp(ly, self.h / 2.0 - r)
            return max(0.0, math.hypot(lx, ly - cy) - r)

        if self.shape in ("rect", "roundrect"):
            # roundrect = rect inset by the corner radius, then grown by it
            r = (self.rratio * min(self.w, self.h)
                 if self.shape == "roundrect" else 0.0)
            ox = max(abs(lx) - (self.w / 2.0 - r), 0.0)
            oy = max(abs(ly) - (self.h / 2.0 - r), 0.0)
            return max(0.0, math.hypot(ox, oy) - r)

        raise AssertionError(  # pragma: no cover - guarded by its own test
            f"{self.ref}.{self.num}: unmodelled pad shape {self.shape!r}. "
            "Add a closed form for it — falling back to a bounding box "
            "would manufacture false findings (Lesson 26)."
        )


class Via(NamedTuple):
    x: float
    y: float
    size: float


def _clamp(v: float, limit: float) -> float:
    return min(max(v, -limit), limit)


def _parse_board() -> tuple[list[Pad], list[Via]]:
    """Pads (with footprint rotation applied) and vias, in PCB-local mm."""
    text = PCB.read_text(encoding="utf-8")

    pads: list[Pad] = []
    # Footprints are NOT all at column 0 — the LED-ring ones are emitted
    # indented, and a `\n(footprint` split silently swallows them (their
    # pads then get attributed to the preceding component).
    for block in re.split(r"\n(?=[ \t]*\(footprint )", text)[1:]:
        m_ref = re.search(r'\(property "Reference" "([A-Za-z]+\d*)"', block)
        if not m_ref:
            continue
        # The footprint's own placement is the (at ...) BEFORE the first
        # (property ...); later ones belong to properties or pads.
        head = block.split("(property", 1)[0]
        m_at = re.search(r"\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", head)
        if not m_at:
            continue
        fx, fy = float(m_at.group(1)), float(m_at.group(2))
        frot = float(m_at.group(3) or 0.0)

        for pm in re.finditer(
            r'\n[\t ]*\(pad "([^"]*)" \S+ (\S+)\s*\n'
            r"[\t ]*\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)\s*\n"
            r"[\t ]*\(size ([-\d.]+) ([-\d.]+)\)"
            r"((?:(?!\n[\t ]*\(pad ).)*)",
            block,
            re.S,
        ):
            num, shape = pm.group(1), pm.group(2)
            px, py = float(pm.group(3)), float(pm.group(4))
            # A pad's own `at` angle is already board-frame in KiCad; when
            # absent the pad inherits the footprint's rotation.
            prot = float(pm.group(5)) if pm.group(5) is not None else frot
            w, h = float(pm.group(6)), float(pm.group(7))
            m_rr = re.search(r"\(roundrect_rratio ([-\d.]+)\)", pm.group(8))
            rratio = float(m_rr.group(1)) if m_rr else 0.0
            # KiCad's Y axis points down, so a footprint rotation theta maps
            # a pad offset to (x + px*cos + py*sin, y - px*sin + py*cos).
            a = math.radians(frot)
            ax = fx + px * math.cos(a) + py * math.sin(a)
            ay = fy - px * math.sin(a) + py * math.cos(a)
            pads.append(Pad(m_ref.group(1), num,
                            ax - PAGE_CENTRE_X, ay - PAGE_CENTRE_Y,
                            w, h, prot, shape, rratio))

    vias = [
        Via(float(x) - PAGE_CENTRE_X, float(y) - PAGE_CENTRE_Y, float(s))
        for x, y, s in re.findall(
            r"\(via\s*\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([-\d.]+)\)", text)
    ]
    return pads, vias


BOARD_PADS, BOARD_VIAS = _parse_board()


def test_parse_found_a_real_board() -> None:
    """Guard against a silently-empty parse (Lesson 12's failure mode).

    Without this, a regex that stops matching turns every geometry
    assertion below into a vacuous pass — the board would look verified
    while nothing was checked.
    """
    assert len(BOARD_PADS) >= MIN_EXPECTED_PADS, (
        f"only {len(BOARD_PADS)} pads parsed from {PCB.name} — the pad "
        "regex has drifted from the emitted format, not the board"
    )
    assert {p.shape for p in BOARD_PADS} <= {"circle", "oval", "rect",
                                             "roundrect"}, (
        "a pad shape appeared that Pad.distance_to() has no closed form "
        "for; add one rather than approximating (Lesson 26)"
    )


@_routing_on
def test_snapshot_vias_present() -> None:
    assert len(BOARD_VIAS) >= MIN_EXPECTED_VIAS, (
        f"only {len(BOARD_VIAS)} vias parsed — expected the routing "
        "snapshot's stitch vias to be on the board"
    )


@_routing_on
def test_no_via_ring_touches_pad_copper() -> None:
    """No via's copper ring may reach a pad's copper edge, ANY net.

    The same-net case is the whole point: DRC ignores it, and JLCPCB's
    scanner has been observed to miss it outright (a drill 0.07 mm inside
    D18.4's copper scored 0/0/0 on both of its via-in-pad checks).
    """
    worst: list[str] = []
    for via in BOARD_VIAS:
        ring = via.size / 2.0
        for pad in BOARD_PADS:
            gap = pad.distance_to(via.x, via.y) - ring
            if gap < VIA_RING_CLEARANCE:
                worst.append(
                    f"via ({via.x:+.4f},{via.y:+.4f}) vs {pad.ref}.{pad.num}: "
                    f"ring-to-copper {gap:+.4f} mm "
                    f"(need >= {VIA_RING_CLEARANCE})"
                    + ("  <-- DRILL INSIDE PAD COPPER"
                       if gap < -ring else "")
                )
    assert not worst, "via(s) on or near pad copper:\n  " + "\n  ".join(worst)


@_routing_on
def test_vias_do_not_share_a_drill() -> None:
    """Two vias closer than MIN_VIA_TO_VIA would break into one slot."""
    bad: list[str] = []
    for i, a in enumerate(BOARD_VIAS):
        for b in BOARD_VIAS[i + 1:]:
            d = math.hypot(a.x - b.x, a.y - b.y)
            if d < MIN_VIA_TO_VIA:
                bad.append(f"({a.x:+.4f},{a.y:+.4f}) and "
                           f"({b.x:+.4f},{b.y:+.4f}): {d:.4f} mm apart")
    assert not bad, "via pair(s) too close:\n  " + "\n  ".join(bad)
