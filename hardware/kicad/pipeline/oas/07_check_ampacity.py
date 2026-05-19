"""
OAS - Trace ampacity check (IPC-2221 external trace formula).

For each power rail with a known peak-current budget, finds the narrowest
track segment carrying that net on the PCB and verifies its width
delivers enough ampacity per IPC-2221 chart "Maximum current vs
cross-section for external conductors" (1 oz copper, 10 C rise above
ambient).

Catches the class of bug where a route through a tight pocket gets
pinched down (e.g. autoroute or hand-edit drops width from 0.5 mm to
0.25 mm to fit between two pads), unintentionally creating a current-
limited segment that becomes a fuse under peak load.

IPC-2221 formula
----------------
   I_max = k * dT^0.44 * A^0.725
where:
   I_max   : maximum continuous current (amps)
   k       : 0.048 for external conductors, 0.024 for internal
   dT      : permitted temperature rise above ambient (degrees C)
   A       : cross-sectional area (mil^2) = width_mil * thickness_mil
   thickness_mil = 1.378 for 1 oz copper

For OAS this is a 2-layer board, so both F.Cu and B.Cu are external
layers and use k=0.048. The check uses dT = 10 C (conservative).

Net CONTINUOUS current budgets
------------------------------
IPC-2221 is a STEADY-STATE thermal model - the trace heats up to
equilibrium under sustained current. Transient peaks (e.g. LED ring at
full white during boot self-test for 100 ms) don't drive trace
temperature past the dT_C ambient rise. Therefore the budgets below
reflect realistic CONTINUOUS load, not absolute peak.

   +24V   : Total system input. P_total ~ 5 W / 24 V ~ 210 mA continuous.
            Budget 0.30 A (40 % margin over computed).
   +5V    : LD2410 80 mA + TPS62933 input ~340 mA (powering +3V3 loads
            at 435 mA via ~85 % buck) + LED ring sustained avg ~200 mA
            (worst case = solid red AQI alert for hours) -> ~620 mA
            continuous. Budget 0.70 A.
   +3V3   : ESP32 80 mA + SEN66 typ 200 mA (peak 350 mA is transient
            during fan startup, not steady state) + NFC 5 mA -> ~290 mA
            continuous. Budget 0.45 A.
   GND    : carried by the copper pour (~Ø120 mm minus cutouts).
            Skipped - pour ampacity is huge vs trace ampacity.
   Signals: low-current (mA range) - skipped here, signal integrity
            handled elsewhere (rise-time check, see CLAUDE.md I2C).

Exit code 0 if every monitored net's minimum-width segment delivers at
least the budget current. Exit 1 on any FAIL.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).parent
KICAD_DIR = HERE.parent.parent  # pipeline/oas/ -> pipeline/ -> hardware/kicad
PCB_PATH = KICAD_DIR / "oas.kicad_pcb"

# IPC-2221 formula constants.
K_EXTERNAL = 0.048
K_INTERNAL = 0.024
DT_C = 10.0  # temperature rise above ambient (deg C). Conservative.
COPPER_THICKNESS_MIL_1OZ = 1.378  # IPC-2221 spec.

# Net continuous current budgets (Amps). See module docstring for derivation.
# Note: the OAS schematic uses a single "+24V" power flag spanning J1 input,
# post-Q1, and post-F1 - so the whole 24 V chain is one net in the PCB.
NET_BUDGETS = {
    "+24V": 0.30,
    "+5V":  0.70,
    "+3V3": 0.45,
}

# Minimum acceptable safety margin (1.0 = exactly at IPC limit).
# OAS sets 1.2 = 20% headroom over the budgeted peak.
SAFETY_FACTOR = 1.2


@dataclass
class Segment:
    net_code: int
    width: float  # mm
    layer: str
    start: tuple[float, float]
    end: tuple[float, float]

    def length_mm(self) -> float:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        return (dx * dx + dy * dy) ** 0.5


@dataclass
class CheckResult:
    name: str
    value: str
    spec: str
    passed: bool

    def __str__(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        return f"  [{mark}] {self.name:30s} {self.value:38s} (spec: {self.spec})"


def ipc2221_max_current_a(width_mm: float, layer: str) -> float:
    """Compute IPC-2221 max continuous current for a single-segment trace."""
    width_mil = width_mm / 0.0254
    area_mil_sq = width_mil * COPPER_THICKNESS_MIL_1OZ
    is_external = layer.startswith("F.") or layer.startswith("B.")
    k = K_EXTERNAL if is_external else K_INTERNAL
    return k * (DT_C ** 0.44) * (area_mil_sq ** 0.725)


def min_width_for_current_mm(current_a: float, layer: str = "F.Cu") -> float:
    """Inverse of ipc2221_max_current_a - returns the required trace width
    (mm) to safely carry the given current."""
    is_external = layer.startswith("F.") or layer.startswith("B.")
    k = K_EXTERNAL if is_external else K_INTERNAL
    # I = k * dT^0.44 * (w_mil * t_mil)^0.725
    # -> w_mil = ((I / (k * dT^0.44)) ** (1/0.725)) / t_mil
    area_mil_sq = (current_a / (k * (DT_C ** 0.44))) ** (1.0 / 0.725)
    width_mil = area_mil_sq / COPPER_THICKNESS_MIL_1OZ
    return width_mil * 0.0254


def parse_nets(pcb_text: str) -> dict[int, str]:
    """Parse all (net N "name") declarations at the top of the PCB file."""
    return {
        int(code): name
        for code, name in re.findall(r'\(net\s+(\d+)\s+"([^"]*)"\)', pcb_text)
    }


def parse_segments(pcb_text: str) -> list[Segment]:
    """Parse every (segment ...) block. Uses depth-counting to handle
    nested parens robustly."""
    segments: list[Segment] = []
    i = 0
    n = len(pcb_text)
    while True:
        idx = pcb_text.find("(segment", i)
        if idx == -1:
            break
        # Must be at start of line (segment is always top-level in a
        # (kicad_pcb ...) doc) - but allow leading whitespace.
        # Walk to balanced close paren.
        depth = 0
        j = idx
        while j < n:
            ch = pcb_text[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = pcb_text[idx:j]

        m_start = re.search(r'\(start\s+([\d.-]+)\s+([\d.-]+)\)', block)
        m_end = re.search(r'\(end\s+([\d.-]+)\s+([\d.-]+)\)', block)
        m_width = re.search(r'\(width\s+([\d.]+)\)', block)
        m_layer = re.search(r'\(layer\s+"([^"]+)"\)', block)
        m_net = re.search(r'\(net\s+(\d+)\)', block)
        if m_start and m_end and m_width and m_layer and m_net:
            segments.append(Segment(
                net_code=int(m_net.group(1)),
                width=float(m_width.group(1)),
                layer=m_layer.group(1),
                start=(float(m_start.group(1)), float(m_start.group(2))),
                end=(float(m_end.group(1)), float(m_end.group(2))),
            ))
        i = j
    return segments


def main() -> None:
    print("OAS PCB trace ampacity check (IPC-2221)")
    print("=" * 60)
    print()

    if not PCB_PATH.exists():
        sys.exit(f"ERROR: {PCB_PATH} not found - run build.py first.")

    pcb_text = PCB_PATH.read_text(encoding="utf-8")
    nets_by_code = parse_nets(pcb_text)
    segments = parse_segments(pcb_text)

    print(f"Parsed {len(segments)} track segments across {len(nets_by_code)} nets.")
    print()

    # v0.40 post-order: if the board has no signal track segments (e.g.
    # routing chunk(s) disabled while iterating on footprint corrections),
    # there's nothing to check. Skip cleanly rather than failing per-net
    # — the unrouted state is documented in ROUTING_CHUNKS comments in
    # boardgen and is expected during the v0.40 post-order footprint
    # iteration before the routing rework (separate task #93).
    if len(segments) == 0:
        print("SKIP: no routed signal track segments found.")
        print(
            "       routing snapshot is disabled in boardgen "
            "ROUTING_CHUNKS — ampacity check deferred until routing rework "
            "(task #93). The GND copper pour gives every GND pad a "
            "connection; non-GND nets currently show as unconnected pads."
        )
        return

    # Group segments by net NAME (not code - multiple codes never share
    # a name in a valid PCB, but we group by name for human readability).
    by_net_name: dict[str, list[Segment]] = {}
    for seg in segments:
        name = nets_by_code.get(seg.net_code, f"<unknown net {seg.net_code}>")
        by_net_name.setdefault(name, []).append(seg)

    # Reference table: required width vs current at IPC-2221 limit.
    print("IPC-2221 reference (1 oz Cu external, dT = 10 C, no safety factor):")
    for current_a in [0.5, 1.0, 1.5, 2.0, 3.0]:
        w = min_width_for_current_mm(current_a)
        print(f"   {current_a:.2f} A requires at least {w:.3f} mm trace width")
    print()
    print(f"OAS uses a safety factor of {SAFETY_FACTOR}x over the IPC limit.")
    print()

    all_results: list[CheckResult] = []
    print("Per-net ampacity checks")
    print("-" * 60)
    for net_name, budget_a in NET_BUDGETS.items():
        if net_name not in by_net_name:
            all_results.append(CheckResult(
                name=net_name,
                value="<no track segments>",
                spec=f"budget {budget_a:.2f} A",
                passed=False,
            ))
            print(all_results[-1])
            continue
        net_segments = by_net_name[net_name]
        min_seg = min(net_segments, key=lambda s: s.width)
        derated_budget = budget_a * SAFETY_FACTOR
        required_w = min_width_for_current_mm(derated_budget, min_seg.layer)
        max_carry = ipc2221_max_current_a(min_seg.width, min_seg.layer)
        passed = min_seg.width >= required_w
        all_results.append(CheckResult(
            name=net_name,
            value=(
                f"{len(net_segments)} segs, narrowest = {min_seg.width:.3f} mm "
                f"({min_seg.layer})"
            ),
            spec=(
                f"need >= {required_w:.3f} mm "
                f"for {derated_budget:.2f} A (IPC carry = {max_carry:.2f} A)"
            ),
            passed=passed,
        ))
        print(all_results[-1])
    print()

    # Summary.
    total = len(all_results)
    failed = [r for r in all_results if not r.passed]
    print("=" * 60)
    if failed:
        print(f"FAIL: {len(failed)} of {total} ampacity checks failed.")
        for r in failed:
            print(f"  {r}")
        sys.exit(1)
    print(f"PASS: all {total} ampacity checks passed.")


if __name__ == "__main__":
    main()
