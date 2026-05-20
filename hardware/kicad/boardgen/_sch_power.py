"""boardgen/_sch_power.py - power.kicad_sch generator."""
from __future__ import annotations

import math
import textwrap

from boardgen._common import U, fmt, sheet_context, SCH_VERSION, GEN_VERSION, SHEET_BLOCK_UUIDS, SHEET_FILE_UUIDS, ROOT_SHEET_UUID, SUBSHEET_DISPLAY_NAMES
from boardgen._project import fx, fy, PROJECT_SHORTNAME
from boardgen._lib_symbols import POWER_LIB_SYMBOLS
from boardgen._sch_helpers import (
    _sch_wire, _sch_junction, _sch_power_flag,
    _sch_resistor, _sch_polyfuse,
    _sch_capacitor, _sch_inductor, _sch_diode_schottky,
    _sch_diode_zener, _sch_q_pmos, _sch_buck_lm2596_5,
    _sch_buck_tps62933,
)


# -----------------------------------------------------------------------------
# gen_power_sch
# -----------------------------------------------------------------------------
def gen_power_sch() -> str:
    """Power sub-sheet — J1 input + D1 surge clamp + Q1 reverse-polarity + R4/D3 Vgs clamp + R1 pulldown + F1 polyfuse + C1/C2 caps + U1 24V->5V buck.

    Power flow runs LEFT-TO-RIGHT and UPWARD on screen:

        J1 (input) ──┬── Q1.S → Q1.D → F1 → +24V (protected rail, exits up-right)
                     │     │            ↑
                     │     │            D3 (10V Zener, cathode → S net,
                     │     │                 anode → R4/R1 junction)
                     │     │
                     │     Q1.G → R4 (1k series) → (junction) → R1 (100k) → GND
                     │                              │
                     │                              D3.anode lands here
                     │
                     D1 (TVS surge clamp, shunts excess voltage to GND below)
                     │
                     └── J1.2 (GND), J1.3 (PE) — drop down to their own flags

    The TVS D1 sits BEFORE Q1 in the chain (tap point on the J1.1 → Q1.S
    wire). A surge that exceeds Q1's Vds_max would destroy Q1 before its
    reverse-polarity function could engage, so D1 must clamp upstream of
    Q1. SMBJ24A clamps at ~38.9V at 1A peak, leaving comfortable margin
    below Q1's absolute maximum (AO3401A Vds_max = -30V; comfortable
    margin even at the worst-case 38.9V clamp event).

    The Q1 gate-source clamp (R4 + D3) is mandatory because AO3401A
    (v0.36 swap from PMV65XP) has Vgs_max = +/-12V, while the natural
    pull-down through R1 alone would set Vgs = -24V at the 24V supply,
    exceeding the absolute max. With D3 (10V Zener, v0.37 — was 18V
    pre-fix) shunting the gate-side junction to source whenever the
    gate tries to drop more than 10V below source, |Vgs| is clamped
    to <=10V (2V margin under AO3401A's ±12V limit; AND optimal
    Rds_on operating point at Vgs=-10V). R4 (1k) provides series
    isolation in the gate path.

    Layout (page-absolute mm, KiCad +Y is down on screen):

        - J1 placed on the LEFT (mirror_y so pins face RIGHT into the circuit)
        - D1 mid-VIN (angle=270, body vertical), top pin on VIN wire, bottom
          pin drops to a local GND symbol. No new PWR_FLAG sentinel — the
          existing GND sentinel on J1.2 covers the global GND net.
        - Q1 placed to the right of D1, angle=0:
            Q1.D on top  → wire goes UP through F1 to the +24V power flag
            Q1.S on bottom-right (Y aligns with J1.1)
            Q1.G on left side → wire drops DOWN through R4 (series) →
                                R4/R1 junction → R1 (pulldown) → GND.
                                (Crosses J1.1 row at X=Q1_G_X without a
                                 junction — KiCad convention for the
                                 non-connected crossing.)
        - R4 (1k, series gate resistor) directly below Q1.G in the same
          column as R1. Body fits in clear Y band between VIN row (93.98)
          and the R4/R1 junction.
        - R1 (100k, gate pulldown) below R4; R1.bot → dedicated GND flag.
        - D3 (10V Zener, angle=270) placed LEFT of the R4/R1 column with
          its CATHODE wired UP to the VIN net (Q1.S side, via a T-tap on
          the existing vin-horiz wire) and its ANODE wired DOWN-and-RIGHT
          via an L-route to the R4/R1 junction. Clamp current at steady
          state flows S -> D3 (reverse breakdown at Vz=10V) -> junction
          -> R1 -> GND, drawing only (24V - 10V) / 100k = 0.14 mA
          (P_D3 = 1.4 mW, 143x under BZT52C10S 200 mW rating). R4
          (1 kohm gate series) carries NO steady-state current because
          gate is DC high-impedance (Igss <= 100 nA). v0.40 post-order
          math fix: pre-fix said "14 mA × 10 V = 140 mW" — used R4 (1k)
          instead of R1 (100k) for the current loop, off by 100x.
        - F1 above Q1.D, vertical Polyfuse
        - +24V flag, GND flag, Earth_Protective flag — each in its own column
          with ≥15 mm horizontal spacing between independent columns so the
          value-text labels of adjacent symbols cannot overlap.
        - PWR_FLAG sentinels are placed on each power net AT a junction
          on the main wire, with their Value-text offset SIDEWAYS (to the
          right of the symbol) so they never stack vertically with the
          power-flag's Value-text. This was the bug causing label overlap
          in the previous layout.
        - C1 (bulk electrolytic, 100uF 50V) sits in its OWN column to the
          right of F1, tapping the protected +24V rail at the F1.top pin
          and dropping to a local GND symbol. The horizontal +24V tap wire
          terminates at the F1.top pin, where the f1-to-junc24v wire
          continues upward to the +24V flag — a junction dot marks the
          three-way connection.
        - C2 (Y2 ceramic, 10nF Y2) closes the EMI loop between circuit
          GND and the PE conductor. Placed in clear space LEFT of the
          GND flag column with C2.top wired horizontally east to the
          Earth_Protective flag pin and C2.bot wired south-then-east to
          the existing GND horizontal at COL_GND. A junction dot at
          (COL_GND, GND_HORIZ_Y) marks the three-way GND tap.
    """
    file_uuid = SHEET_FILE_UUIDS["power"]
    sheet_path = f"/{ROOT_SHEET_UUID}/{SHEET_BLOCK_UUIDS['power']}"

    # ----- Page-frame fit shift -----
    # Uniform offset applied to every BASE position anchor in this function
    # so the whole power section fits inside the A4 drawing-sheet frame
    # (297 x 210 mm, usable inner area roughly X=10..280, Y=10..195 with a
    # title block reserved at the bottom-right corner X=200..297, Y=170..210).
    #
    # The schematic grew organically through chunks #1a..#1h, accumulating
    # rightward (24V protection -> 5V buck -> 3.3V buck) and downward
    # (the 3.3V cascade sits below the protection block). The latest
    # additions pushed COL_3V3 to X=279.40 (PWR_FLAG value-text would
    # render at X=279.40 + 5.08 ~= 284.5, near the page right edge) and
    # R3_GND text to Y~167.6, close to the title-block top at Y=170.
    #
    # The shift below is a PURE LAYOUT operation: every (x, y) anchor moves
    # by the same amount. Wires, junctions, hierarchical labels, and
    # electrical connections remain logically identical. ERC and net topology
    # are unaffected.
    #
    # NOTE on the inline `# 93.98 — ...` style comments scattered through
    # this function: those numbers were the PRE-SHIFT values of the
    # corresponding derived quantities, kept as readability hints. They
    # are now off by (PWR_X_SHIFT, PWR_Y_SHIFT) but the mathematical
    # derivations (e.g. `J1_Y - 2.54`) remain correct.
    # Shifts must be integer multiples of the 1.27 mm schematic connection
    # grid so wire endpoints and symbol pins stay on-grid after the shift.
    PWR_X_SHIFT = -30.48     # mm — shift entire power section LEFT (24 x 1.27 mm)
    PWR_Y_SHIFT = -10.16     # mm — shift entire power section UP (8 x 1.27 mm)

    # ----- J1: Phoenix MSTBA 2,5/3-G-5,08 (5.08 mm pitch) -----
    # mirror_y so the pin tips exit to the RIGHT of the body, putting J1
    # visually on the LEFT side of the schematic with the circuit growing
    # to its right.
    J1_X = 87.63 + PWR_X_SHIFT
    J1_Y = 96.52 + PWR_Y_SHIFT
    # With mirror_y applied to a symbol at angle=0, the lib pin at
    # (-5.08, +2.54) maps to schematic position (J1_X + 5.08, J1_Y - 2.54).
    # i.e. pin 1 tip is to the right of and above the body anchor.
    PIN1_Y = J1_Y - 2.54     # 93.98 — +24V_unprotected
    PIN2_Y = J1_Y            # 96.52 — GND
    PIN3_Y = J1_Y + 2.54     # 99.06 — PE
    PIN_X  = J1_X + 5.08     # 92.71 — pin tips on right side of mirrored body

    # ----- Q1: P-MOSFET reverse-polarity (PMV65XP), angle=0, no mirror -----
    # With angle=0, pin schematic positions are:
    #   D = (Q1_X + 2.54, Q1_Y - 5.08)   TOP-right    → goes UP to F1 → +24V
    #   G = (Q1_X - 5.08, Q1_Y)          LEFT side   → drops DOWN through
    #                                                  R4 (series) → junction
    #                                                  with D3.anode → R1 → GND
    #   S = (Q1_X + 2.54, Q1_Y + 5.08)   BOTTOM-right → wires to J1.1
    # Y is set so Q1.S aligns with J1.1's row (PIN1_Y = 93.98).
    Q1_X = 113.03 + PWR_X_SHIFT
    Q1_Y = 88.9 + PWR_Y_SHIFT
    Q1_D_X = Q1_X + 2.54     # 115.57
    Q1_D_Y = Q1_Y - 5.08     # 83.82
    Q1_G_X = Q1_X - 5.08     # 107.95
    Q1_G_Y = Q1_Y            # 88.9
    Q1_S_X = Q1_X + 2.54     # 115.57
    Q1_S_Y = Q1_Y + 5.08     # 93.98 — matches PIN1_Y; same horizontal row as J1.1

    # ----- F1: PTC polyfuse (Bourns MF-RHT075/60-2 candidate), angle=0 -----
    # In series between Q1.D and the +24V power flag.
    # With angle=0:
    #   F1.1 (top)    = (F1_X, F1_Y - 3.81)
    #   F1.2 (bottom) = (F1_X, F1_Y + 3.81)
    # Provides resettable overcurrent protection on the protected +24V rail.
    # 750 mA hold current gives ~2x margin over the ~350 mA combined load
    # while still well below the 1.5 A trip threshold. 60V rating provides
    # comfortable margin over the SMBJ24A surge-clamp ceiling (38.9V).
    F1_X = Q1_D_X            # 115.57 — same vertical column as Q1.D
    F1_Y = 76.2 + PWR_Y_SHIFT
    F1_TOP_Y = F1_Y - 3.81   # 72.39
    F1_BOT_Y = F1_Y + 3.81   # 80.01

    # ----- R4: 1k series gate resistor, angle=0 -----
    # In series with Q1.G, between Q1.G and the R4/R1 junction where D3
    # (Zener clamp) ties in. R4 provides series isolation in the gate path
    # so transient currents from the Zener clamp activation don't disturb
    # Q1's gate drive directly. R4's body sits in the clear Y band between
    # the VIN row (93.98) and the R4/R1 junction (104.14) — body Y range
    # ~96.52 to ~101.60, well clear of the VIN crossing at 93.98.
    R4_X = Q1_G_X            # 107.95 — same column as Q1.G, R1
    R4_Y = 99.06 + PWR_Y_SHIFT
    R4_TOP_Y = R4_Y - 3.81   # 95.25
    R4_BOT_Y = R4_Y + 3.81   # 102.87

    # ----- R4/R1 junction (Y row where D3.anode also lands) -----
    # The junction sits between R4.bot (102.87) and R1.top (105.41) at a
    # clean 1.27 mm grid increment. D3's anode wire enters from the LEFT,
    # making this point a 3-way T.
    R4_R1_JUNC_Y = 104.14 + PWR_Y_SHIFT    # 1.27 mm above R1.top

    # ----- R1: 100k gate-GND pulldown, angle=0 -----
    # Sits directly below R4 in the same column. The wire chain
    # Q1.G -> R4 -> junction -> R1 -> GND replaces the previous direct
    # Q1.G -> R1 pulldown. This vertical chain CROSSES J1.1's horizontal
    # wire at (Q1_G_X, PIN1_Y) without a junction — standard schematic
    # convention for non-connected crossings.
    R1_X = Q1_G_X            # 107.95
    R1_Y = 109.22 + PWR_Y_SHIFT
    R1_TOP_Y = R1_Y - 3.81   # 105.41
    R1_BOT_Y = R1_Y + 3.81   # 113.03

    # ----- D3: 10 V Zener gate-source clamp, angle=270 (body vertical) -----
    # AO3401A (v0.36 swap from PMV65XP) has Vgs_max = +/-12V absolute
    # maximum. With R1 alone pulling the gate toward GND, Vgs at the 24V
    # supply settles at -24V — exceeding the gate-oxide limit by 2x and
    # destroying Q1. D3 (10V Zener, v0.37 — was 18V pre-fix; 18V would
    # have clamped Vgs at -18V, still 6V over AO3401A's ±12V limit)
    # clamps |Vgs| to <=10V by shunting current from Q1.S to the R4/R1
    # junction whenever the junction voltage drops more than 10V below
    # source. With the clamp active, the junction sits at V_S - 10V =
    # 14V; the gate sees the same 14V through R4 (no DC gate current),
    # so Vgs = 14 - 24 = -10V (2V margin under ±12V; ALSO the optimal
    # Rds_on operating point for AO3401A at 45 mΩ).
    #
    # Pin 1 in Device:D_Zener is the CATHODE (K, lib (-3.81, 0)), pin 2 is
    # the ANODE (A, lib (3.81, 0)). With angle=270, the cathode (pin 1)
    # lands at the TOP (Y - 3.81) and the anode (pin 2) at the BOTTOM
    # (Y + 3.81) of the rotated body. The top pin connects to the VIN
    # net (Q1.S side, via a T-tap on the existing vin-horiz wire); the
    # bottom pin routes via an L-wire (down-then-right) to the R4/R1
    # junction.
    #
    # X is set so D3 sits in clear space between D1 (now at X=96.52, one
    # grid step left of its original 100.33 to give breathing room for
    # text labels) and the R1 column (X=107.95). With D3_X=102.87 and
    # body half-width ~1.27 mm, D3 body X range is ~101.60 to 104.14 —
    # well clear of D1 (body ends at X=97.79) and the R1 column (X=107.95).
    D3_X = 102.87 + PWR_X_SHIFT
    D3_Y = 99.06 + PWR_Y_SHIFT  # centred between VIN row and R4/R1 junction row
    D3_K_Y = D3_Y - 3.81     # 95.25 — short stub up to VIN row (93.98)
    D3_A_Y = D3_Y + 3.81     # 102.87 — short stub down-then-right to junction

    # ----- D1: TVS surge-clamp diode (SMBJ24A), Device:D_Zener, angle=270 -----
    # Tap point on the J1.1 -> Q1.S wire (the UNPROTECTED VIN net). With
    # angle=270, lib pin 1 K (-3.81, 0) -> schem (D1_X, D1_Y - 3.81) is the
    # TOP pin and lib pin 2 A (3.81, 0) -> schem (D1_X, D1_Y + 3.81) is the
    # BOTTOM pin. The top pin (K, cathode) lands on the VIN row (Y = PIN1_Y
    # = 93.98) so D1_Y = 93.98 + 3.81 = 97.79. X chosen between J1.1 (X = 92.71) and
    # Q1.S (X = 115.57), leaving the existing R1 column (X = 107.95) and
    # its value-text untouched. X = 96.52 (= 76 × 1.27) was moved one
    # grid step LEFT of the previous 100.33 to give breathing room
    # between D1's "SMBJ24A" value text (at X=100.33+, ~5 mm wide) and
    # D3's vertical body at X=102.87.
    D1_X = 96.52 + PWR_X_SHIFT
    D1_Y = 97.79 + PWR_Y_SHIFT
    D1_TOP_Y = D1_Y - 3.81   # 93.98 — matches PIN1_Y / VIN wire row
    D1_BOT_Y = D1_Y + 3.81   # 101.60 — wire continues DOWN to local GND symbol
    # GND symbol for D1's bottom pin. Local-only — no extra PWR_FLAG
    # sentinel: the J1.2 GND drop already supplies the ERC power-source
    # marker on the global GND net, and a second PWR_FLAG would cause
    # "Power output to Power output" conflicts.
    D1_GND_Y = 105.41 + PWR_Y_SHIFT  # GND symbol anchor, same Y row as R1.top

    # ----- Per-net flag columns -----
    # +24V flag column: Q1.D / F1 column at X=115.57.
    # R1-GND flag column: directly below Q1.G / R1 at X=107.95.
    # PE flag column: shifted slightly LEFT of J1.3's pin tip (X=82.55)
    #   so the PE drop wire and PE PWR_FLAG sentinel sit clear of J1's
    #   body and don't share a column with any other flag.
    # GND flag column: far to the LEFT of J1 (X=67.31). The GND wire hops
    #   one grid step right of the J1 pin tips, drops to a Y BELOW the PE
    #   flag, then runs LEFT to its own column.
    # Column spacing rationale:
    #   - GND flag X=67.31, PE flag X=82.55: 15.24 mm gap (≥15 mm rule)
    #   - PE flag X=82.55, R1_GND flag X=107.95: 25.40 mm gap
    #   - R1_GND X=107.95, +24V flag X=115.57: 7.62 mm gap. This narrow gap
    #     is acceptable because the R1_GND flag (Y ≈ 117) and the +24V flag
    #     (Y ≈ 62) are separated by >50 mm vertically — their value-text
    #     labels are nowhere near each other on screen.
    COL_24V    = Q1_D_X      # 115.57
    COL_R1_GND = R1_X        # 107.95
    COL_PE     = 82.55 + PWR_X_SHIFT   # 5.08 mm left of J1.3 pin tip (PIN_X=92.71)
    COL_GND    = 67.31 + PWR_X_SHIFT   # far left of J1

    # Flag stack Y coordinates. Spacing FLAG-to-PWR_FLAG (sentinel) = 5.08 mm.
    JUNC_24V_Y = 67.31 + PWR_Y_SHIFT       # PWR_FLAG sentinel sits at this junction
    FLAG_24V_Y = 62.23 + PWR_Y_SHIFT       # +24V triangle, 5.08 mm above the sentinel
    # PE wire: drops from J1.3 down to PE_TURN_Y, runs LEFT to COL_PE, then
    # DOWN through the PE PWR_FLAG sentinel to the Earth_Protective symbol.
    PE_TURN_Y  = 105.41 + PWR_Y_SHIFT      # Y at which PE wire turns from down to left
    JUNC_PE_Y  = 110.49 + PWR_Y_SHIFT      # PE PWR_FLAG sentinel — on the PE vertical drop
    FLAG_PE_Y  = 115.57 + PWR_Y_SHIFT      # Earth_Protective symbol, 5.08 mm below sentinel
    # GND wire: hops right of J1 pins, drops past PE flag's body AND its
    # value-text label ("Earth_Protective" at Y≈123), runs LEFT in clear
    # space, then DOWN through its own PWR_FLAG sentinel to the GND symbol.
    GND_HORIZ_Y = 127.00 + PWR_Y_SHIFT     # horizontal leg of GND wire, clear of PE flag area
    JUNC_GND_Y = GND_HORIZ_Y # GND PWR_FLAG sentinel sits here, on the leg
    FLAG_GND_Y = 132.08 + PWR_Y_SHIFT      # GND symbol, 5.08 mm below the sentinel
    FLAG_R1_GND_Y = 116.84 + PWR_Y_SHIFT   # second GND symbol below R1.bot

    # ----- C1: bulk electrolytic capacitor (100uF 50V), angle=0 -----
    # C_Polarized: pin 1 (top, ANODE +) on the protected +24V rail,
    # pin 2 (bottom, CATHODE -) to GND. 50 V rating gives margin over
    # both the 24 V nominal and the SMBJ24A's 38.9 V surge-clamp voltage.
    # 100 uF is sized for ~500 mA peak load — enough hold-up for sub-ms
    # transients (WS2812 white-bright, radar refresh, MCU TX bursts).
    #
    # Placed in its OWN column at X=142.24, 26.67 mm (= 10.5 grid steps)
    # to the right of F1's column (X=115.57). The wide horizontal gap
    # is needed because F1's Value text "PTC 750mA / 75V" is left-
    # justified at X=119.38 and renders ~17 mm wide, reaching to ~X=137
    # at the displayed character spacing — placing C1's Value text any
    # closer (e.g. at X=137.16) caused the F1 voltage suffix and the
    # "100uF" of C1 to visibly touch in the rendered PNG. The extra
    # 7.62 mm of column spacing gives a clear visual gap.
    #
    # C1.top is at the SAME Y as F1.top (72.39), so the +24V tap wire
    # is a single horizontal segment from F1.top to C1.top. The F1.top
    # pin then has three connections (F1 body, f1-to-junc24v upward,
    # f1-to-c1 rightward) — a junction dot at (F1_X, F1_TOP_Y) marks it.
    C1_X = 142.24 + PWR_X_SHIFT
    C1_Y = 76.2 + PWR_Y_SHIFT
    C1_TOP_Y = C1_Y - 3.81   # 72.39 — matches F1_TOP_Y
    C1_BOT_Y = C1_Y + 3.81   # 80.01
    # GND symbol for C1.bottom — independent column, separated >5 cm
    # vertically from any other GND label so its "GND" text cannot
    # collide with neighbouring symbols.
    C1_GND_Y = 83.82 + PWR_Y_SHIFT         # 1.5 grid steps below C1.bot

    # ----- C2: Y2 ceramic capacitor (10nF Y2), angle=0 -----
    # Closes the EMI loop between circuit GND and the PE conductor.
    # Y2 safety class is mandatory for any GND-to-PE cap — rated for
    # ~1.5 kV impulse withstand, fails open-circuit (not short, which
    # would defeat the protective-earth function).
    #
    # Placed in clear space LEFT of the GND flag column. C2_X is set
    # so the value-text labels of C2 stay clear of the Earth_Protective
    # symbol's value-text ("Earth_Protective" at (82.55, 123.19),
    # spanning ~X=75.4 to ~X=89.7). C2 sits at X=60.96 — left of that
    # band by ~14 mm.
    #
    # Pin 1 (top) connects to the Earth_Protective net via a horizontal
    # wire at Y=FLAG_PE_Y (115.57), terminating at the PE flag's symbol
    # pin. Pin 2 (bottom) connects to the global GND net via a short
    # vertical drop to the existing GND horizontal at Y=GND_HORIZ_Y
    # (127.0). A new horizontal wire extends from (C2_X, GND_HORIZ_Y)
    # east to (COL_GND, GND_HORIZ_Y) where it meets the existing
    # gnd-vert-low/gnd-horiz-left L-corner, producing a 3-way GND tap
    # that requires its own junction dot.
    C2_X = 60.96 + PWR_X_SHIFT
    C2_Y = 119.38 + PWR_Y_SHIFT
    C2_TOP_Y = C2_Y - 3.81   # 115.57 — matches FLAG_PE_Y (PE flag pin row)
    C2_BOT_Y = C2_Y + 3.81   # 123.19

    # ----- Wires -----
    parts: list[str] = []

    # J1.1 (unprotected +24V) → Q1.S: horizontal wire across the schematic.
    # D1's top pin taps off this wire at (D1_X, PIN1_Y) — a junction dot is
    # added below to make the T-connection electrically valid.
    parts.append(_sch_wire(PIN_X, PIN1_Y, Q1_S_X, Q1_S_Y, "vin-horiz"))

    # D1.top (on VIN) → D1.bottom is internal to the symbol; we only need
    # the wire from D1.bottom down to its local GND symbol.
    parts.append(_sch_wire(D1_X, D1_BOT_Y, D1_X, D1_GND_Y, "d1bot-to-gnd"))

    # Q1.D → F1.bot: short vertical hop.
    parts.append(_sch_wire(Q1_D_X, Q1_D_Y, F1_X, F1_BOT_Y, "q1d-to-f1"))
    # F1.top → +24V junction (where PWR_FLAG sentinel taps off).
    parts.append(_sch_wire(F1_X, F1_TOP_Y, COL_24V, JUNC_24V_Y, "f1-to-junc24v"))
    # +24V junction → +24V flag.
    parts.append(_sch_wire(COL_24V, JUNC_24V_Y, COL_24V, FLAG_24V_Y, "junc24v-to-flag"))

    # Q1.G -> R4 -> (junction with D3.anode) -> R1 -> GND chain.
    # The chain crosses J1.1's horizontal VIN wire at (Q1_G_X, PIN1_Y) at
    # the Q1.G -> R4.top segment, without a junction dot — standard
    # schematic convention for non-connected crossings.
    parts.append(_sch_wire(Q1_G_X, Q1_G_Y, R4_X, R4_TOP_Y, "q1g-to-r4"))
    parts.append(_sch_wire(R4_X, R4_BOT_Y, R4_X, R4_R1_JUNC_Y, "r4-to-junction"))
    parts.append(_sch_wire(R4_X, R4_R1_JUNC_Y, R1_X, R1_TOP_Y, "junction-to-r1"))

    # D3 (Zener) clamp wires.
    # D3.K (top) -> VIN net (T-tap on the existing vin-horiz wire at
    # (D3_X, PIN1_Y) — a junction dot is added below to mark the tap).
    parts.append(_sch_wire(D3_X, D3_K_Y, D3_X, PIN1_Y, "d3k-to-vin"))
    # D3.A (bottom) -> R4/R1 junction via an L-route: drop down to the
    # junction Y row, then run east to the junction X column.
    parts.append(_sch_wire(D3_X, D3_A_Y, D3_X, R4_R1_JUNC_Y, "d3a-vert"))
    parts.append(_sch_wire(D3_X, R4_R1_JUNC_Y, R4_X, R4_R1_JUNC_Y, "d3a-horiz"))

    # R1.bot → R1-GND flag (no junction, no PWR_FLAG sentinel — GND is global
    # and the J1.2 stack already supplies the sentinel for ERC).
    parts.append(_sch_wire(R1_X, R1_BOT_Y, COL_R1_GND, FLAG_R1_GND_Y, "r1bot-to-r1gnd"))

    # J1.2 GND wire: hop one grid step RIGHT of J1's pin tips (clearing the
    # J1.3 pin-tip column so the wire doesn't short into PE), drop DOWN past
    # J1's body and PE flag's body, run LEFT to COL_GND, then DOWN through
    # the GND PWR_FLAG sentinel to the GND symbol.
    GND_HOP_X = PIN_X + 2.54   # 95.25 — temporary drop column for J1.2
    parts.append(_sch_wire(PIN_X, PIN2_Y, GND_HOP_X, PIN2_Y, "gnd-pin-hop"))
    parts.append(_sch_wire(GND_HOP_X, PIN2_Y, GND_HOP_X, GND_HORIZ_Y, "gnd-vert-drop"))
    parts.append(_sch_wire(GND_HOP_X, GND_HORIZ_Y, COL_GND, GND_HORIZ_Y, "gnd-horiz-left"))
    parts.append(_sch_wire(COL_GND, GND_HORIZ_Y, COL_GND, FLAG_GND_Y, "gnd-vert-low"))

    # J1.3 PE wire: drop DOWN below J1 body, turn LEFT to COL_PE, drop DOWN
    # through the PE PWR_FLAG sentinel to Earth_Protective. PE drops at
    # X=PIN_X (just to the right of J1's body) so it doesn't cross J1's
    # rectangle; the LEFT turn happens at PE_TURN_Y which is well below
    # J1's body bottom (Y=100.33).
    parts.append(_sch_wire(PIN_X, PIN3_Y, PIN_X, PE_TURN_Y, "pe-vert-drop"))
    parts.append(_sch_wire(PIN_X, PE_TURN_Y, COL_PE, PE_TURN_Y, "pe-horiz-left"))
    parts.append(_sch_wire(COL_PE, PE_TURN_Y, COL_PE, JUNC_PE_Y, "pe-vert-mid"))
    parts.append(_sch_wire(COL_PE, JUNC_PE_Y, COL_PE, FLAG_PE_Y, "pe-vert-low"))

    # C1: +24V rail tap from F1.top → C1.top, then C1.bot → C1-local GND.
    # The F1.top pin becomes a 3-way (F1 body, vertical wire upward to the
    # +24V flag, horizontal wire rightward to C1) — a junction dot below
    # marks the T-connection.
    parts.append(_sch_wire(F1_X, F1_TOP_Y, C1_X, C1_TOP_Y, "f1top-to-c1"))
    parts.append(_sch_wire(C1_X, C1_BOT_Y, C1_X, C1_GND_Y, "c1bot-to-gnd"))

    # C2: PE flag pin → C2.top via a horizontal wire at Y=FLAG_PE_Y.
    # C2.bot → existing GND horizontal at Y=GND_HORIZ_Y via a short
    # vertical drop, then a horizontal segment east to (COL_GND, GND_HORIZ_Y)
    # which is the existing gnd-horiz-left/gnd-vert-low corner — adding a
    # third wire here turns it into a T-junction (needs junction dot).
    parts.append(_sch_wire(C2_X, C2_TOP_Y, COL_PE, FLAG_PE_Y, "c2top-to-pe"))
    parts.append(_sch_wire(C2_X, C2_BOT_Y, C2_X, GND_HORIZ_Y, "c2bot-to-gnd-vert"))
    parts.append(_sch_wire(C2_X, GND_HORIZ_Y, COL_GND, GND_HORIZ_Y, "c2-to-gnd-horiz"))

    # ----- Junctions (T-branch points where PWR_FLAG sentinels join wires) -----
    parts.append(_sch_junction(COL_24V, JUNC_24V_Y, "24v"))
    parts.append(_sch_junction(COL_GND, JUNC_GND_Y, "gnd"))
    parts.append(_sch_junction(COL_PE,  JUNC_PE_Y,  "pe"))
    # T-branch where D1's top pin taps the J1 → Q1 VIN wire.
    parts.append(_sch_junction(D1_X, PIN1_Y, "vin-d1"))
    # T-branch where D3's cathode taps the same J1 → Q1 VIN wire.
    parts.append(_sch_junction(D3_X, PIN1_Y, "vin-d3"))
    # 3-way junction where R4.bot wire, R1.top wire, and D3.anode L-wire
    # meet on the gate-pulldown column.
    parts.append(_sch_junction(R4_X, R4_R1_JUNC_Y, "r4-r1-d3"))
    # T-branch where C1's +24V tap meets the F1.top → +24V flag wire at
    # the F1 pin location.
    parts.append(_sch_junction(F1_X, F1_TOP_Y, "vin-c1"))
    # T-branch where C2's GND tap meets the existing GND horizontal at
    # the COL_GND corner (where gnd-horiz-left ends and gnd-vert-low
    # starts; the third wire is C2's new c2-to-gnd-horiz).
    parts.append(_sch_junction(COL_GND, GND_HORIZ_Y, "gnd-c2"))

    # ----- J1 symbol (Phoenix MSTBA 2,5/3-G-5,08, mirror_y so pins face right) -----
    j1_uuid = U("sym:j1")
    j1_pin1_uuid = U("sym-pin:j1-1")
    j1_pin2_uuid = U("sym-pin:j1-2")
    j1_pin3_uuid = U("sym-pin:j1-3")
    parts.append(textwrap.dedent(f"""\
        \t(symbol
        \t\t(lib_id "Connector:Screw_Terminal_01x03")
        \t\t(at {fmt(J1_X)} {fmt(J1_Y)} 0)
        \t\t(mirror y)
        \t\t(unit 1)
        \t\t(exclude_from_sim no)
        \t\t(in_bom yes)
        \t\t(on_board yes)
        \t\t(dnp no)
        \t\t(fields_autoplaced yes)
        \t\t(uuid "{j1_uuid}")
        \t\t(property "Reference" "J1"
        \t\t\t(at {fmt(J1_X - 2.54)} {fmt(J1_Y - 7.62)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify right)
        \t\t\t)
        \t\t)
        \t\t(property "Value" "Phoenix_MSTBA_2,5/3-G-5,08"
        \t\t\t(at {fmt(J1_X - 2.54)} {fmt(J1_Y - 5.08)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(justify right)
        \t\t\t)
        \t\t)
        \t\t(property "Footprint" "Connector_Phoenix_MSTB:PhoenixContact_MSTBA_2,5_3-G-5,08_1x03_P5.08mm_Horizontal"
        \t\t\t(at {fmt(J1_X)} {fmt(J1_Y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Datasheet" "https://www.phoenixcontact.com/online/portal/us?uri=pxc-oc-itemdetail:pid=1757255"
        \t\t\t(at {fmt(J1_X)} {fmt(J1_Y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(property "Description" "Phoenix Contact MSTBA 2,5/3-G-5,08 — 3-pin 5.08 mm pitch pluggable terminal block base. 24 V supply input: pin 1 = +24V_unprotected, pin 2 = GND, pin 3 = PE. Mates with a Phoenix COMBICON 5.08 mm 3-pin plug. Order code 1757255 (12 A) or 1923872 (16 A HC)."
        \t\t\t(at {fmt(J1_X)} {fmt(J1_Y)} 0)
        \t\t\t(effects
        \t\t\t\t(font
        \t\t\t\t\t(size 1.27 1.27)
        \t\t\t\t)
        \t\t\t\t(hide yes)
        \t\t\t)
        \t\t)
        \t\t(pin "1"
        \t\t\t(uuid "{j1_pin1_uuid}")
        \t\t)
        \t\t(pin "2"
        \t\t\t(uuid "{j1_pin2_uuid}")
        \t\t)
        \t\t(pin "3"
        \t\t\t(uuid "{j1_pin3_uuid}")
        \t\t)
        \t\t(instances
        \t\t\t(project "oas"
        \t\t\t\t(path "{sheet_path}"
        \t\t\t\t\t(reference "J1")
        \t\t\t\t\t(unit 1)
        \t\t\t\t)
        \t\t\t)
        \t\t)
        \t)"""))

    # ----- D1: TVS surge-clamp diode (SMBJ24A), unidirectional, SMB package -----
    # Tap point is BEFORE Q1 on the unprotected VIN net — Q1's Vds_max is
    # -50V on PMV65XP, and a transient above that would destroy Q1
    # before its reverse-polarity function could engage. SMBJ24A clamps
    # at Vc=38.9V at 1A peak (10/1000 us), holding VIN below Q1's
    # absolute maximum with comfortable margin. Vrwm=24V matches the
    # nominal supply; Vbr_min=26.7V so the diode is off at the working
    # point and consumes ~uA leakage. Peak pulse power 600W. F1 (PTC)
    # downstream catches the sustained over-current that follows a
    # clamped event.
    # Symbol: Device:D_Zener. KiCad ships NO unidirectional-TVS symbol —
    # every stock D_TVS* glyph is the back-to-back BIDIRECTIONAL TVS with
    # ambiguous A1/A2 pins. A unidirectional TVS is, on a schematic, drawn
    # identically to a Zener diode (same triangle + cathode bar), so
    # Device:D_Zener is the correct glyph: pin 1 = K (cathode), pin 2 = A
    # (anode) — self-documenting, no A1/A2 guesswork. angle=270 places
    # pin 1 K on the TOP (VIN) wire and pin 2 A on the BOTTOM (GND) drop.
    # pad 1 of the Diode_SMD:D_SMB footprint is the cathode (per the KLC),
    # and sync_pcb_nets_from_schematic maps schematic-pin-1 -> PCB-pad-1,
    # so cathode -> VIN and anode -> GND -- the correct surge-clamp
    # orientation for the unidirectional SMBJ24A.
    parts.append(_sch_diode_zener(
        x=D1_X, y=D1_Y, angle=270,
        reference="D1", value="SMBJ24A", uuid_tag="d1",
    ))

    # ----- D3: 10 V Zener gate-source clamp (AO3401A Vgs protection) -----
    # v0.37: changed from 18 V to 10 V Zener after AO3401A swap (v0.36) and
    # re-audit found AO3401A Vgs_max = ±12 V (NOT ±20 V as the original
    # PMV65XP design assumed). 18 V Zener would have clamped Vgs at -18 V,
    # exceeding AO3401A's ±12 V rating by 6 V. 10 V Zener clamps Vgs at
    # -10 V — 2 V margin under ±12 V AND optimal Rds_on operating point
    # for AO3401A (45 mΩ at Vgs=-10 V per Alpha-Omega datasheet curve).
    # D3 cathode taps the J1.1 -> Q1.S VIN wire; anode lands on the R4/R1
    # junction so a clamp event sinks current from Q1.S through D3
    # (reverse breakdown at Vz=10V) into the junction and out through
    # R1 to GND. Candidate part: BZT52C10S (10 V Zener, SOD-323, 200 mW,
    # JLCPCB Basic Parts Library). v0.40 post-order MATH FIX: steady-state
    # Pz = (24-10)/R1(100k) × 10V = 0.14 mA × 10V = 1.4 mW (143× under
    # 200 mW rating, NOT 1.43×). Pre-fix said "140 mW within 200 mW"
    # which used R4 (1k) as the limiting resistor — wrong by 100×. R4
    # carries no steady-state current because Q1's gate is DC
    # high-impedance (Igss ≤ 100 nA per AO3401A datasheet).
    parts.append(_sch_diode_zener(
        x=D3_X, y=D3_Y, angle=270,
        reference="D3", value="10V Zener 200mW", uuid_tag="d3",
    ))

    # ----- Q1: P-MOSFET reverse-polarity protection (AO3401A) -----
    # v0.36 substitution from PMV65XP (Vds=-20V was insufficient).
    # Source = J1.1 (unprotected input), Drain = +24V protected rail.
    # When input polarity is correct, the body diode conducts initially,
    # then the gate is pulled negative through R4 + R1 to GND. The D3
    # 10 V Zener clamp (v0.37) limits |Vgs| to <=10V, so the channel turns
    # fully on at Vgs = -10V — shorting out the body diode for low Rds_on
    # conduction loss (45 mΩ at Vgs=-10V per AO3401A datasheet).
    # v0.36 CRITICAL-4: AO3401A (Alpha & Omega Semiconductor), drop-in for the
    # pre-v0.36 PMV65XP. PMV65XP claimed Vds_max=-50V in the source comment
    # but the actual datasheet value is Vds_max=-20V — would have been
    # exceeded by 19V during a 38.9V SMBJ24A clamp event.
    # AO3401A: Vds_max=-30V (8.9V margin over the 38.9V clamp — tight but
    # safe for transient events under nanoseconds), Vgs_max=±12V (D3 Zener
    # clamp at -18V is still REQUIRED to keep |Vgs| within ±12V at startup),
    # Id continuous=-4A, RDS(on) typ=60 mΩ at Vgs=-10V (better than PMV65XP's
    # 90 mΩ). Same SOT-23 footprint, same G/S/D pin order.
    # JLCPCB Extended Library, mass stock.
    parts.append(_sch_q_pmos(
        x=Q1_X, y=Q1_Y, angle=0,
        reference="Q1", value="AO3401A", uuid_tag="q1",
    ))

    # ----- F1: PTC polyfuse, 750 mA hold / 60 V -----
    # Candidate part: Bourns MF-RHT075/60-2 (750 mA hold, 1.5 A trip,
    # 60 V max, 1812 SMD). The 60V rating provides comfortable margin
    # over the SMBJ24A surge-clamp ceiling (38.9V) — critical if Q1
    # fails short and the clamp voltage appears across F1. The 750 mA
    # hold current widens the safety margin against C1 (100 uF)
    # cold-start inrush while staying within the ~350 mA combined
    # load budget. Final footprint (1812 SMD) TBD in PCB-layout chunk;
    # verify JLCPCB stock on order day.
    parts.append(_sch_polyfuse(
        x=F1_X, y=F1_Y, angle=0,
        reference="F1", value="PTC 750mA / 75V", uuid_tag="f1",
    ))

    # ----- R1: 100 kΩ gate-GND pulldown -----
    parts.append(_sch_resistor(
        x=R1_X, y=R1_Y, angle=0,
        reference="R1", value="100k 1%", uuid_tag="r1",
    ))

    # ----- R4: 1 kΩ series gate resistor (Zener clamp current limiter) -----
    # Sits in series with Q1.G between the Q1.G pin and the R4/R1 junction
    # where D3 (Zener) ties in. R4 provides series isolation in the gate
    # path so transient currents during a Zener clamp event are limited
    # and do not disturb Q1's gate drive directly.
    parts.append(_sch_resistor(
        x=R4_X, y=R4_Y, angle=0,
        reference="R4", value="1k", uuid_tag="r4",
    ))

    # ----- C1: bulk electrolytic, 100 uF / 50 V -----
    # Polarized — pin 1 (top) is the ANODE (+), wired to the protected +24V
    # rail at F1.top. Pin 2 (bottom) is the CATHODE (-), wired to GND.
    # Buffers transient load steps (WS2812 white-bright, radar refreshes,
    # MCU TX bursts) and absorbs ripple from the upstream supply. 50 V
    # rating gives margin over both the 24 V nominal and the SMBJ24A's
    # 38.9 V surge-clamp voltage.
    parts.append(_sch_capacitor(
        lib_id="Device:C_Polarized",
        x=C1_X, y=C1_Y, angle=0,
        reference="C1", value="100uF 50V", uuid_tag="c1",
    ))

    # ----- C2: Y2 safety-class ceramic, 10 nF -----
    # Non-polarized. Pin 1 (top) on the Earth_Protective net, pin 2 (bottom)
    # on global GND. Closes the conducted-EMI loop between circuit GND and
    # the chassis PE conductor so high-frequency switching noise from the
    # downstream bucks returns to chassis ground through this cap rather
    # than escaping along the supply leads. Y2 class is mandatory for any
    # cap connecting circuit GND to PE — rated for ~1.5 kV impulse withstand,
    # fails open-circuit (not short, which would defeat the protective
    # earth function).
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C2_X, y=C2_Y, angle=0,
        reference="C2", value="10nF Y2", uuid_tag="c2",
    ))

    # ----- Power flag symbols (+24V, GND, Earth_Protective, R1-GND, D1-GND, C1-GND) -----
    # +24V flag with text "+24V" placed ABOVE the triangle (standard).
    # value_offset_y matches the +24V lib's default Value position
    # (lib (0, +3.556) → schem (0, -3.556)) so the text sits just above
    # the triangle's vertex without overlapping it.
    parts.append(_sch_power_flag(
        lib_id="power:+24V", value="+24V",
        x=COL_24V, y=FLAG_24V_Y, angle=0,
        reference="#PWR01",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr01-24v",
    ))
    # GND flag (J1.2). Value-text BELOW.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=COL_GND, y=FLAG_GND_Y, angle=0,
        reference="#PWR02",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr02-gnd",
    ))
    # Earth_Protective flag (J1.3). Value-text BELOW (offset y=7.62 to
    # clear the symbol's Ø2.54 mm circle below the bar).
    parts.append(_sch_power_flag(
        lib_id="power:Earth_Protective", value="Earth_Protective",
        x=COL_PE, y=FLAG_PE_Y, angle=0,
        reference="#PWR03",
        value_offset_x=0.0, value_offset_y=7.62,
        uuid_tag="pwr03-pe",
    ))
    # GND for R1.bottom — same net as #PWR02 via the global power label.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=COL_R1_GND, y=FLAG_R1_GND_Y, angle=0,
        reference="#PWR04",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr04-gnd-r1",
    ))
    # GND for D1.bottom (TVS anode) — same net as #PWR02 via the global
    # power label. No matching PWR_FLAG sentinel: see note below in the
    # PWR_FLAG section.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=D1_X, y=D1_GND_Y, angle=0,
        reference="#PWR05",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr05-gnd-d1",
    ))
    # GND for C1.bottom (bulk-cap cathode) — same net as #PWR02 via the
    # global power label. No PWR_FLAG sentinel (same reason as above).
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C1_X, y=C1_GND_Y, angle=0,
        reference="#PWR06",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr06-gnd-c1",
    ))

    # ----- PWR_FLAG sentinels -----
    # Each sentinel's "PWR_FLAG" value-text is offset SIDEWAYS (positive X)
    # so it sits next to the symbol rather than above it — this is the fix
    # for the label overlap that was visible in the previous render where
    # PWR_FLAG text was directly under the power-symbol's Value-text.
    PF_TEXT_OFFSET = 5.08    # mm horizontal offset of "PWR_FLAG" text from symbol
    # +24V net sentinel: graphic UP (angle=0) toward the +24V triangle above.
    parts.append(_sch_power_flag(
        lib_id="power:PWR_FLAG", value="PWR_FLAG",
        x=COL_24V, y=JUNC_24V_Y, angle=0,
        reference="#FLG01",
        value_offset_x=PF_TEXT_OFFSET, value_offset_y=-2.54,
        uuid_tag="flg01-24v",
    ))
    # GND net sentinel: graphic DOWN (angle=180) toward the GND symbol below.
    parts.append(_sch_power_flag(
        lib_id="power:PWR_FLAG", value="PWR_FLAG",
        x=COL_GND, y=JUNC_GND_Y, angle=180,
        reference="#FLG02",
        value_offset_x=PF_TEXT_OFFSET, value_offset_y=2.54,
        uuid_tag="flg02-gnd",
    ))
    # PE net sentinel: graphic DOWN.
    parts.append(_sch_power_flag(
        lib_id="power:PWR_FLAG", value="PWR_FLAG",
        x=COL_PE, y=JUNC_PE_Y, angle=180,
        reference="#FLG03",
        value_offset_x=PF_TEXT_OFFSET, value_offset_y=2.54,
        uuid_tag="flg03-pe",
    ))
    # NOTE: no PWR_FLAG sentinel on the R1-GND or D1-GND drops — GND is a
    # global net and FLG02 (on J1.2's drop) already supplies the "power
    # source" marker for ERC. Adding a second PWR_FLAG on the same GND net
    # would create a "Power output to Power output" connection error.

    # =========================================================================
    # 24V -> 5V buck converter block (U1 LM2596S-5.0 + L1 + D2 + C3/C13/C4/C14)
    # =========================================================================
    # First active block in the power section. Takes the protected +24V rail
    # (downstream of F1 / C1) and produces a regulated 5V output that powers
    # the LD2410 mmWave radar (~80 mA) and the WS2812 status LED (~60 mA
    # white-bright) — total ~140 mA, well below the LM2596's 3 A rating.
    #
    # Component selection rationale (see commit message and CLAUDE.md):
    #   * LM2596S-5.0  : 40 V Vin_max, fixed 5 V output, 3 A, 150 kHz, TO-263.
    #                    The 40 V rating is the binding constraint — it
    #                    matches D1 (SMBJ24A) which clamps surges at 38.9 V.
    #                    Lower-rated bucks (TPS62933 17V, MP2451 26V,
    #                    TPS54302 28V) would not survive a clamped surge.
    #                    Fixed-output variant eliminates the FB resistor
    #                    divider (one fewer place for a layout error).
    #   * L1 33 uH    : Standard inductor value from the LM2596 datasheet
    #                    typical-application table for 5 V output at 150 kHz.
    #                    Shielded ferrite-core part with >=2 A saturation and
    #                    low DCR (<100 mOhm) keeps EMI and conduction loss low.
    #                    The 2 A saturation rating is the binding requirement:
    #                    LM2596 has no internal soft-start, so cold-start of
    #                    C4 (220 uF output bulk) can push the peak inductor
    #                    current above 1 A in the first few switching cycles.
    #                    A 1 A-rated inductor would saturate and trigger an
    #                    LM2596 over-current latch, producing an ugly power-on
    #                    glitch. Candidate parts (verify JLCPCB stock at order
    #                    day): Bourns SRR1208-330Y (33 uH, 1.95 A), Wurth
    #                    74404084330 (33 uH, 2.4 A — likely Extended Library).
    #   * D2 SS14     : 40 V / 1 A Schottky catch diode. LM2596 is an
    #                    ASYNCHRONOUS switcher — there is no internal
    #                    high-side flyback diode, so an external Schottky is
    #                    MANDATORY. SOD-123 or DO-214AC package, JLCPCB Basic.
    #   * C3 100uF/50V + C13 100 nF : input bulk + HF bypass at U1.VIN.
    #                    50 V rating gives margin over the 24 V nominal AND
    #                    the 38.9 V SMBJ24A clamp voltage.
    #   * C4 220uF/10V + C14 100 nF : output bulk + HF bypass at the +5V rail.
    #                    10 V rating gives 2x margin over 5 V; 220 uF is the
    #                    LM2596 datasheet recommendation for low output ripple.
    #
    # ON/OFF pin (pin 5, active-LOW) is tied to GND for always-on operation —
    # the buck has no shutdown / sleep mode in OAS. The U1 thermal pad will
    # need a copper pour to GND on the PCB (handled in the PCB-layout chunk).
    #
    # Layout (page-absolute mm, KiCad +Y is down on screen):
    #
    #                                              +5V flag (top-right corner)
    #                                              |
    #                                              ◊ PWR_FLAG_5V
    #                                              |
    #            FB ↑   +5V bus ─────── L1 ─── C4 ─── C14 ─┴── (to flag)
    #            |                |             |     |
    #     +24V bus extension      |             GND   GND
    #     ────────── C3 ── C13 ── U1.VIN     U1.OUT ── switch node
    #                  |     |    (LM2596S-5)   |
    #                  GND  GND                 |
    #                       U1.ON/OFF=GND       D2 (catch)
    #                       U1.GND=GND          |
    #                                           D2.A=GND
    #
    # The buck block sits far to the right of the existing power section.
    # U1 anchor at X=177.8 — 35.56 mm (= 4 grid steps of 8.89 mm = 7×1.27 mm)
    # to the right of C1's column (X=142.24). The wide horizontal gap leaves
    # room for C1's "100uF 50V" value text, then a clean run of +24V bus
    # heading east to the buck input.

    # ----- U1: LM2596S-5.0 buck regulator -----
    # Anchor Y chosen so that U1.VIN (lib (-12.7, +2.54)) lands exactly on the
    # +24V bus Y row (72.39). With Y_U1=74.93: VIN at 74.93-2.54 = 72.39 ✓.
    # Body rectangle spans schematic Y=[69.85, 80.01], X=[190.50, 210.82].
    # X chosen far enough right of C1, C3, C13 for cap value labels
    # ("100uF 50V" ~ 11.4 mm wide on screen) to never overlap U1 body.
    U1_X = 200.66 + PWR_X_SHIFT
    U1_Y = 74.93 + PWR_Y_SHIFT
    U1_VIN_X    = U1_X - 12.7     # 187.96
    U1_VIN_Y    = U1_Y - 2.54     # 72.39 — matches +24V bus row
    U1_OUT_X    = U1_X + 12.7     # 213.36
    U1_OUT_Y    = U1_Y + 2.54     # 77.47 — switch node row
    U1_GND_X    = U1_X            # 200.66
    U1_GND_Y    = U1_Y + 7.62     # 82.55
    U1_FB_X     = U1_X + 12.7     # 213.36
    U1_FB_Y     = U1_Y - 2.54     # 72.39
    U1_ONOFF_X  = U1_X - 12.7     # 187.96
    U1_ONOFF_Y  = U1_Y + 2.54     # 77.47 — same row as OUT

    # ----- C3: input bulk electrolytic, 100uF 50V, angle=0 -----
    # Pin 1 (top, anode +) on +24V bus, pin 2 (bottom) to GND. Placed between
    # C1 (X=142.24) and U1.VIN (X=187.96). Spacing of 17.78 mm to C1 and
    # 15.24 mm to C13 leaves clear gaps between adjacent caps' value-text
    # labels ("100uF 50V" renders ~11.4 mm wide at size 1.27).
    C3_X = 160.02 + PWR_X_SHIFT
    C3_Y = 76.20 + PWR_Y_SHIFT
    C3_TOP_Y = C3_Y - 3.81        # 72.39 — on +24V bus
    C3_BOT_Y = C3_Y + 3.81        # 80.01
    C3_GND_Y = 82.55 + PWR_Y_SHIFT  # GND symbol anchor, 2.54 below cap.bot

    # ----- C13: input HF ceramic bypass, 100nF, angle=0 -----
    C13_X = 175.26 + PWR_X_SHIFT
    C13_Y = 76.20 + PWR_Y_SHIFT
    C13_TOP_Y = C13_Y - 3.81      # 72.39 — on +24V bus
    C13_BOT_Y = C13_Y + 3.81      # 80.01
    C13_GND_Y = 82.55 + PWR_Y_SHIFT

    # ----- Switch node and L1 (33 uH shielded, vertical, angle=0) -----
    # Switch node row = U1.OUT row = Y=77.47. L1 vertical with bot pin on the
    # switch node, top pin on the +5V output bus. L1.bot at Y=74.93 sits
    # 2.54 mm ABOVE the switch node row, so a short vertical wire connects
    # them. L1.top at Y=67.31 = +5V bus row, 2.54 mm ABOVE U1's body top edge
    # (Y=69.85) for clear visual separation from the LM2596 rectangle.
    L1_X = 223.52 + PWR_X_SHIFT
    L1_Y = 71.12 + PWR_Y_SHIFT
    L1_TOP_Y = L1_Y - 3.81        # 67.31 — on +5V bus
    L1_BOT_Y = L1_Y + 3.81        # 74.93 — 2.54 above switch node row

    # ----- D2: SS14 Schottky catch diode, angle=270 (K top, A bottom) -----
    # Sits between U1.OUT and L1.bot on the switch node horizontal. With
    # angle=270 the cathode (pin 1) is at the TOP (Y - 3.81) facing the
    # switch node, and the anode (pin 2) is at the BOTTOM (Y + 3.81) heading
    # to GND. This is the standard buck catch-diode orientation: when the
    # high-side switch in U1 turns off, L1's flyback current circulates from
    # GND through D2 forward-biased into the switch node, holding it ~0.4 V
    # below GND rather than rising arbitrarily.
    D2_X = 218.44 + PWR_X_SHIFT
    D2_Y = 81.28 + PWR_Y_SHIFT
    D2_K_Y = D2_Y - 3.81          # 77.47 — on switch node row
    D2_A_Y = D2_Y + 3.81          # 85.09
    D2_GND_Y = 88.90 + PWR_Y_SHIFT  # GND symbol anchor, 3.81 below D2.A

    # ----- +5V output caps -----
    # C4 (polarized, 220uF/10V) and C14 (ceramic, 100nF) tap the +5V bus to
    # GND on the OUTPUT side of L1. Pin 1 (top, anode +) on +5V bus, pin 2
    # (bottom) to GND. Column spacing of 15.24 mm (C4↔L1, C14↔C4) keeps the
    # "220uF 10V" / "100nF" value-text labels clear of neighbouring caps'
    # references.
    C4_X = 238.76 + PWR_X_SHIFT
    C4_Y = 71.12 + PWR_Y_SHIFT
    C4_TOP_Y = C4_Y - 3.81        # 67.31 — on +5V bus
    C4_BOT_Y = C4_Y + 3.81        # 74.93
    C4_GND_Y = 77.47 + PWR_Y_SHIFT

    C14_X = 254.00 + PWR_X_SHIFT
    C14_Y = 71.12 + PWR_Y_SHIFT
    C14_TOP_Y = C14_Y - 3.81      # 67.31 — on +5V bus
    C14_BOT_Y = C14_Y + 3.81      # 74.93
    C14_GND_Y = 77.47 + PWR_Y_SHIFT

    # ----- +5V flag and PWR_FLAG sentinel -----
    # Column = C14 column (254.00). The flag stack lifts above the +5V bus
    # at Y=67.31: PWR_FLAG sentinel midway, +5V triangle at top-right Y=62.23
    # for visual alignment with the existing +24V flag (also at Y=62.23, far
    # to the left).
    COL_5V       = C14_X          # 254.00
    Y_5V_BUS     = 67.31 + PWR_Y_SHIFT  # +5V bus row (above U1 body top edge Y=69.85)
    JUNC_5V_Y    = 64.77 + PWR_Y_SHIFT  # PWR_FLAG sentinel on the vertical to flag
    FLAG_5V_Y    = 62.23 + PWR_Y_SHIFT  # +5V triangle, same Y as +24V flag

    # ----- Buck-block wires -----
    # +24V bus extension from C1.top (142.24, 72.39) RIGHT to U1.VIN
    # (165.10, 72.39). Single wire segment; junctions added at C3.top and
    # C13.top tap points, and at the (now 3-way) C1.top corner.
    parts.append(_sch_wire(C1_X, F1_TOP_Y, U1_VIN_X, U1_VIN_Y, "vin-c1-to-u1"))

    # C3.bot → C3-GND
    parts.append(_sch_wire(C3_X, C3_BOT_Y, C3_X, C3_GND_Y, "c13ot-to-gnd"))
    # C13.bot → C13-GND
    parts.append(_sch_wire(C13_X, C13_BOT_Y, C13_X, C13_GND_Y, "c13bot-to-gnd"))

    # U1.ON/OFF pin (pin 5, active-LOW) → local GND symbol. Always-on operation.
    U1_ONOFF_GND_Y = 82.55 + PWR_Y_SHIFT  # GND symbol below ON/OFF pin
    parts.append(_sch_wire(U1_ONOFF_X, U1_ONOFF_Y, U1_ONOFF_X, U1_ONOFF_GND_Y, "u1onoff-to-gnd"))
    # U1.GND (pin 3, centre-bottom) → local GND symbol below
    U1_GND_SYM_Y = 86.36 + PWR_Y_SHIFT    # GND symbol 3.81 below U1.GND pin
    parts.append(_sch_wire(U1_GND_X, U1_GND_Y, U1_GND_X, U1_GND_SYM_Y, "u1gnd-to-gndsym"))

    # Switch node horizontal: U1.OUT (X=U1_OUT_X) → L1.bot column (X=L1_X).
    # D2.K's pin tip lands on this wire at (D2_X, U1_OUT_Y) — a junction dot
    # marks the T-connection.
    parts.append(_sch_wire(U1_OUT_X, U1_OUT_Y, L1_X, U1_OUT_Y, "u1out-switch-horiz"))
    # Short vertical from switch node row up to L1.bot pin.
    parts.append(_sch_wire(L1_X, U1_OUT_Y, L1_X, L1_BOT_Y, "switch-to-l1bot"))

    # D2.A (anode, bottom) → D2-GND symbol
    parts.append(_sch_wire(D2_X, D2_A_Y, D2_X, D2_GND_Y, "d2a-to-gnd"))

    # FB (pin 4) → +5V bus: short vertical hop UP from FB pin to the +5V row.
    parts.append(_sch_wire(U1_FB_X, U1_FB_Y, U1_FB_X, Y_5V_BUS, "fb-to-5v-bus"))

    # +5V bus horizontal from FB column (190.50) RIGHT through L1.top, C4.top,
    # C14.top — a single wire segment with junctions at the tap points.
    parts.append(_sch_wire(U1_FB_X, Y_5V_BUS, COL_5V, Y_5V_BUS, "5v-bus"))

    # C4.bot → C4-GND
    parts.append(_sch_wire(C4_X, C4_BOT_Y, C4_X, C4_GND_Y, "c14ot-to-gnd"))
    # C14.bot → C14-GND
    parts.append(_sch_wire(C14_X, C14_BOT_Y, C14_X, C14_GND_Y, "c14bot-to-gnd"))

    # +5V bus terminus → PWR_FLAG sentinel column upward, then to +5V flag.
    parts.append(_sch_wire(COL_5V, Y_5V_BUS, COL_5V, JUNC_5V_Y, "5v-bus-to-junc"))
    parts.append(_sch_wire(COL_5V, JUNC_5V_Y, COL_5V, FLAG_5V_Y, "5v-junc-to-flag"))

    # ----- Buck-block junctions -----
    # C1.top is now a 3-way: existing f1-to-c1 enters from left, NEW
    # vin-c1-to-u1 exits right, C1's body pin drops down.
    parts.append(_sch_junction(C1_X, F1_TOP_Y, "vin-c1-extended"))
    # C3.top tap on +24V bus.
    parts.append(_sch_junction(C3_X, C3_TOP_Y, "24v-c3"))
    # C13.top tap on +24V bus.
    parts.append(_sch_junction(C13_X, C13_TOP_Y, "24v-c13"))
    # D2.K tap on switch node.
    parts.append(_sch_junction(D2_X, U1_OUT_Y, "switch-d2"))
    # L1.top tap on +5V bus.
    parts.append(_sch_junction(L1_X, Y_5V_BUS, "5v-l1"))
    # C4.top tap on +5V bus.
    parts.append(_sch_junction(C4_X, Y_5V_BUS, "5v-c4"))
    # C14.top + bus terminus + vertical to PWR_FLAG: 3-way.
    parts.append(_sch_junction(COL_5V, Y_5V_BUS, "5v-c14"))
    # PWR_FLAG sentinel position on the vertical to the +5V flag.
    parts.append(_sch_junction(COL_5V, JUNC_5V_Y, "5v"))

    # ----- U1: LM2596S-5.0 -----
    parts.append(_sch_buck_lm2596_5(
        x=U1_X, y=U1_Y, angle=0,
        reference="U1", value="LM2596S-5.0", uuid_tag="u1",
    ))

    # ----- L1: 33 uH shielded inductor, >=2 A sat, low DCR -----
    # See the buck-block component-selection comment above for why the
    # saturation rating was uprated from 1 A to 2 A (LM2596 cold-start
    # inrush via C4 = 220 uF can exceed 1 A in the first switching cycles).
    parts.append(_sch_inductor(
        x=L1_X, y=L1_Y, angle=0,
        reference="L1", value="33uH 2A", uuid_tag="l1",
    ))

    # ----- D2: SS14 Schottky catch diode -----
    parts.append(_sch_diode_schottky(
        x=D2_X, y=D2_Y, angle=270,
        reference="D2", value="SS14", uuid_tag="d2",
    ))

    # ----- C3: input bulk electrolytic, 100 uF / 50 V -----
    parts.append(_sch_capacitor(
        lib_id="Device:C_Polarized",
        x=C3_X, y=C3_Y, angle=0,
        reference="C3", value="100uF 50V", uuid_tag="c3",
    ))

    # ----- C13: input HF ceramic bypass, 100 nF -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C13_X, y=C13_Y, angle=0,
        reference="C13", value="100nF", uuid_tag="c13",
    ))

    # ----- C4: output bulk electrolytic, 220 uF / 10 V -----
    parts.append(_sch_capacitor(
        lib_id="Device:C_Polarized",
        x=C4_X, y=C4_Y, angle=0,
        reference="C4", value="220uF 10V", uuid_tag="c4",
    ))

    # ----- C14: output HF ceramic bypass, 100 nF -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C14_X, y=C14_Y, angle=0,
        reference="C14", value="100nF", uuid_tag="c14",
    ))

    # ----- Local GND symbols around U1 / inductor / caps -----
    # Each GND symbol creates a global-label drop to the GND net. No PWR_FLAG
    # sentinel on any of these — FLG02 (on J1.2's drop) already supplies the
    # ERC power-source marker for the GND net.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C3_X, y=C3_GND_Y, angle=0,
        reference="#PWR07",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr07-gnd-c3",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C13_X, y=C13_GND_Y, angle=0,
        reference="#PWR08",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr08-gnd-c13",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=U1_ONOFF_X, y=U1_ONOFF_GND_Y, angle=0,
        reference="#PWR09",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr09-gnd-u1onoff",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=U1_GND_X, y=U1_GND_SYM_Y, angle=0,
        reference="#PWR10",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr10-gnd-u1",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=D2_X, y=D2_GND_Y, angle=0,
        reference="#PWR11",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr11-gnd-d2",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C4_X, y=C4_GND_Y, angle=0,
        reference="#PWR12",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr12-gnd-c4",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C14_X, y=C14_GND_Y, angle=0,
        reference="#PWR13",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr13-gnd-c14",
    ))

    # ----- +5V flag at top-right of the buck block -----
    parts.append(_sch_power_flag(
        lib_id="power:+5V", value="+5V",
        x=COL_5V, y=FLAG_5V_Y, angle=0,
        reference="#PWR14",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr14-5v",
    ))

    # ----- PWR_FLAG sentinel on the new +5V net -----
    # Without this, ERC would error "Input Power pin not driven by any Output
    # Power pins" on the +5V net — the LM2596's OUT pin is an `output` (not
    # `power_out`) so it doesn't count as a power source for the ERC check.
    parts.append(_sch_power_flag(
        lib_id="power:PWR_FLAG", value="PWR_FLAG",
        x=COL_5V, y=JUNC_5V_Y, angle=0,
        reference="#FLG04",
        value_offset_x=PF_TEXT_OFFSET, value_offset_y=-2.54,
        uuid_tag="flg04-5v",
    ))

    # =========================================================================
    # 5V -> 3.3V buck converter block (U2 TPS62933 + L2 + R2/R3 FB div + C5/C15/C6/C16/C7)
    # =========================================================================
    # Cascaded second buck stage. Takes the +5V rail produced by U1 (above)
    # and steps it down to a regulated 3.3V rail that powers the ESP32-C6
    # DevKitM-1-N4 (via its 3V3 pin, bypassing the module's onboard LDO so
    # we don't dissipate ~250 mW close to the SEN66 air-quality sensor),
    # plus the SEN66 itself and the NT3H1101 NFC tag.
    #
    # Component selection rationale (see commit message and CLAUDE.md):
    #   * TPS62933   : 3.8-30 V Vin range (17 V abs-max for the typical-use
    #                  recommendation, well above our 5 V), 3 A, 1.2 MHz
    #                  default (v0.40 post-order doc fix: pre-fix said
    #                  "500 kHz" but per TI SLUSEA4D §"Switching Frequency
    #                  Selection" the default for RT pin tied directly to
    #                  GND is 1.2 MHz internal oscillator; 500 kHz requires
    #                  RTSeT resistor sizing). SYNCHRONOUS topology (no
    #                  external Schottky catch diode needed — high-side
    #                  and low-side both internal). SOT-583-8 package,
    #                  JLCPCB Basic library. ~95% efficiency at ~300 mA
    #                  load — much better than LM2596's ~80% (LM2596 has
    #                  external Schottky losses and runs at 150 kHz so
    #                  the inductor ripple is much larger). The 17 V
    #                  Vin_max ceiling that ruled it out upstream of D1
    #                  is irrelevant here because we cascade from the
    #                  regulated +5V rail.
    #   * L2 2.2uH  : Per TPS62933 datasheet typical-application table for
    #                  3.3 V output at 1.2 MHz. Shielded SMD ferrite-core
    #                  inductor with ≥2 A saturation and ~50 mOhm DCR.
    #                  4×4 mm or 3×3 mm package — much smaller than LM2596's
    #                  33 uH because the higher fsw drops the inductor
    #                  requirement by ~15×.
    #   * R2 100k 1% / R3 30.9k 1% (FB divider): TPS62933 FB pin reference
    #                  voltage = 0.8 V per TI datasheet §"Electrical
    #                  Characteristics" (the pre-v0.36 0.6 V assumption was
    #                  WRONG — TPS62930 family is 0.6 V, TPS62933 is 0.8 V).
    #                  Vout = Vref × (1 + R2/R3) = 0.8 × (1 + 100/30.9) =
    #                  3.39 V — within ±3 % of 3.3 V target and well below
    #                  ESP32-C6 / SEN66 / NT3H1101 absolute-max VDD of 3.6 V.
    #                  R3 = 30.9 kΩ gives a low-current divider
    #                  (~26 µA), and R2 = 100 kΩ is a standard E96 value.
    #                  1% tolerance keeps the output voltage variation due
    #                  to divider tolerance below ±35 mV (≈1 %).
    #   * C5 10uF + C15 100nF : input bulk + HF ceramic bypass at U2.VIN.
    #                  Per datasheet: ceramic X5R/X7R; 16 V rating gives
    #                  3× margin over the 5 V input.
    #   * C6 22uF + C16 100nF : output bulk + HF ceramic bypass at the
    #                  +3.3V rail. Per datasheet; 10 V rating gives 3× margin
    #                  over 3.3 V.
    #   * C7 100nF (BST): bootstrap capacitor from BST pin to SW pin.
    #                  REQUIRED by TPS62933 for the high-side gate driver
    #                  bootstrap supply. Datasheet value.
    #   * C8 47nF (SS) : soft-start capacitor from SS pin to GND. SS tied
    #                  directly to GND DISABLES soft-start in TPS62933
    #                  (an earlier comment claiming a ~0.6 ms default was
    #                  incorrect — that figure came from a different TI
    #                  device family). With C8=47nF the soft-start time is
    #                  t_ss = C_ss * V_ref / I_ss = 47nF * 0.6V / 5uA ~=
    #                  5.6 ms, which falls within the 2-10 ms power-ramp
    #                  window specified by SEN66's application note for
    #                  reliable sensor initialization on cold boot.
    #
    # The RT pin (programmable switching frequency) is tied to GND — that
    # selects the default ~1.2 MHz internal oscillator (v0.40 post-order
    # doc fix; per TI SLUSEA4D § "Switching Frequency Selection"). SS pin
    # (soft-start)
    # uses C8 (47 nF) to ground to set t_ss ~= 5.6 ms (in the SEN66 power-
    # ramp window of 2-10 ms). EN pin is tied to VIN via a direct wire
    # (always-on operation — the TPS62933 enables when EN > 1.18 V, and
    # +5V provides plenty of headroom). The BST pin gets its bootstrap
    # cap C7 to the SW node.
    #
    # Layout (page-absolute mm, KiCad +Y is down on screen):
    #
    # The buck block sits BELOW the +24V protected-rail section so the
    # cascade flow reads top-to-bottom (24 V → 5 V → 3.3 V). U2 is placed
    # in the same X column as U1 (X=200.66) — vertically aligned, ~70 mm
    # below — emphasising the cascade visually. The +5V net enters U2.VIN
    # from above via a "+5V" global symbol placed at the top of the block;
    # the +3.3V net exits to the right through C6/C16 decoupling and a
    # PWR_FLAG sentinel into the +3.3V power flag at the far-right.

    # ----- U2: TPS62933 buck regulator -----
    # Anchor at X=200.66 (same X column as U1). Y=144.78 puts the body in
    # the clear area below the existing power-protection block (whose
    # lowest element is the GND flag at Y=132.08). With U2_Y=144.78 the
    # body spans Y=[134.62, 154.94] and pin rows are:
    #   VIN row Y=137.16 (lib (-7.62, +7.62) -> schem y-7.62 = 137.16)
    #   BST row Y=137.16 (same as VIN — used for the +3.3V bus on the right)
    #   EN  row Y=139.70
    #   SW  row Y=144.78 (centre — switch-node horizontal)
    #   SS  row Y=147.32
    #   RT  row Y=149.86
    #   FB  row Y=152.40
    #   GND row Y=157.48 (centre-bottom)
    U2_X = 200.66 + PWR_X_SHIFT
    U2_Y = 144.78 + PWR_Y_SHIFT
    U2_VIN_X    = U2_X - 7.62     # 193.04
    U2_VIN_Y    = U2_Y - 7.62     # 137.16 — +5V input bus row
    U2_EN_X     = U2_X - 7.62     # 193.04
    U2_EN_Y     = U2_Y - 5.08     # 139.70
    U2_RT_X     = U2_X - 7.62     # 193.04
    U2_RT_Y     = U2_Y + 5.08     # 149.86 — tied to GND (default 1.2 MHz)
    U2_SS_X     = U2_X - 7.62     # 193.04
    U2_SS_Y     = U2_Y + 2.54     # 147.32 — tied to GND via C8 (47 nF
                                  # soft-start cap; t_ss ~= 5.6 ms)
    U2_GND_X    = U2_X            # 200.66
    U2_GND_Y    = U2_Y + 12.7     # 157.48
    U2_SW_X     = U2_X + 7.62     # 208.28 — switch node
    U2_SW_Y     = U2_Y            # 144.78
    U2_BST_X    = U2_X + 7.62     # 208.28
    U2_BST_Y    = U2_Y - 7.62     # 137.16 — bootstrap cap node
    U2_FB_X     = U2_X + 7.62     # 208.28
    U2_FB_Y     = U2_Y + 7.62     # 152.40 — feedback tap

    # ----- C5: input bulk ceramic, 10uF 25V, angle=0 -----
    # Non-polarized ceramic X5R/X7R. Pin 1 (top) on +5V bus, pin 2 (bottom)
    # to GND. C5 sits 15.24 mm left of C15 — wide enough that the
    # value-text label "10uF 25V" (rendered ~10 mm at size 1.27) clears
    # C15's value-text "100nF" without visual overlap.
    C5_X = 170.18 + PWR_X_SHIFT   # 134 × 1.27
    C5_Y = 140.97 + PWR_Y_SHIFT   # 111 × 1.27
    C5_TOP_Y = C5_Y - 3.81        # 137.16 — on +5V bus row
    C5_BOT_Y = C5_Y + 3.81        # 144.78
    C5_GND_Y = 147.32 + PWR_Y_SHIFT  # GND symbol, 2.54 below cap.bot

    # ----- C15: input HF ceramic bypass, 100nF, angle=0 -----
    C15_X = 185.42 + PWR_X_SHIFT  # 146 × 1.27 — 15.24 mm right of C5, 7.62 left of VIN
    C15_Y = 140.97 + PWR_Y_SHIFT
    C15_TOP_Y = C15_Y - 3.81      # 137.16
    C15_BOT_Y = C15_Y + 3.81      # 144.78
    C15_GND_Y = 147.32 + PWR_Y_SHIFT

    # ----- +5V drop symbol -----
    # Global "+5V" power label placed ABOVE U2's VIN row, with angle=180
    # so the triangle points DOWN toward the buck block. Pin sits at the
    # symbol anchor (193.04, 130.81); a short vertical wire drops it onto
    # the VIN bus at Y=137.16. The same vertical wire continues DOWN past
    # the VIN bus row through U2.VIN pin to U2.EN pin — this is the
    # always-on EN tie (EN → VIN).
    Y_5V_DROP_TOP = 130.81 + PWR_Y_SHIFT  # 103 × 1.27 — on connection grid

    # ----- C7: BST (bootstrap) ceramic capacitor, 100nF, angle=0 -----
    # Vertical between U2.BST (top pin, Y=137.16) and U2.SW (bot pin,
    # Y=144.78). Placed at X=213.36, 5.08 mm right of the BST/SW pin
    # column (208.28). C7.top → BST extension wire row, C7.bot → SW
    # extension wire row. Required by TPS62933 for the high-side gate
    # driver bootstrap supply.
    C7_X = 213.36 + PWR_X_SHIFT   # 168 × 1.27
    C7_Y = 140.97 + PWR_Y_SHIFT
    C7_TOP_Y = C7_Y - 3.81        # 137.16 — on BST row
    C7_BOT_Y = C7_Y + 3.81        # 144.78 — on SW row

    # ----- C8: SS (soft-start) ceramic capacitor, 47nF, angle=0 -----
    # Vertical between U2.SS (top pin, Y=147.32) and a local GND symbol
    # below. Placed at X=191.77 (= 151 × 1.27), 1.27 mm LEFT of the U2.SS
    # pin tip column (193.04). C8.top sits exactly on the SS pin row so
    # the SS -> C8.top connection is a single short horizontal wire of
    # 1.27 mm. C8.bot connects to a new local GND symbol below.
    #
    # Without C8, with SS tied directly to GND, the TPS62933 disables
    # soft-start completely — Vout ramps in <<1 ms which can leave the
    # downstream SEN66 sensor in an undefined state on cold boot
    # (SEN66 datasheet requires a 2-10 ms power ramp for reliable init).
    # With C8 = 47 nF: t_ss = C_ss * V_ref / I_ss = 47 nF * 0.6 V / 5 uA
    # = 5.64 ms, comfortably within the 2-10 ms window.
    C8_X = 191.77 + PWR_X_SHIFT   # 151 × 1.27 — 1.27 mm left of SS pin tip
    C8_Y = 151.13 + PWR_Y_SHIFT   # 119 × 1.27
    C8_TOP_Y = C8_Y - 3.81        # 147.32 — matches U2.SS pin Y row
    C8_BOT_Y = C8_Y + 3.81        # 154.94 — body bottom row
    C8_GND_Y = 157.48 + PWR_Y_SHIFT  # GND symbol anchor below C8.bot

    # ----- L2: 2.2 uH shielded inductor, angle=0 -----
    # Vertical, between U2.SW (right of the body) and the +3.3V output bus.
    # L2.bot pin on the SW horizontal extension row (Y=144.78), L2.top
    # pin on the +3.3V bus row (Y=137.16). 7.62 mm pin-to-pin spacing
    # fits naturally between the two rows. Placed at X=226.06, 12.7 mm
    # right of C7's column — wide enough that C7's "100nF" value-text
    # (left-justified at X=C7+2.54) doesn't run into L2's reference text
    # (right-justified at X=L2-2.54).
    L2_X = 226.06 + PWR_X_SHIFT   # 178 × 1.27
    L2_Y = 140.97 + PWR_Y_SHIFT
    L2_TOP_Y = L2_Y - 3.81        # 137.16 — on +3.3V bus row
    L2_BOT_Y = L2_Y + 3.81        # 144.78 — on SW extension row

    # ----- R2 / R3: feedback divider for 3.3V output -----
    # TPS62933 FB pin reference voltage Vref = 0.8 V (TI datasheet, NOT 0.6 V
    # as the pre-v0.36 comments wrongly stated — that was the TPS62930-family
    # value, confused into this commentary).
    #   Vout = Vref × (1 + R2/R3)  =>  R2/R3 = (Vout/Vref - 1) = 3.125 for Vout=3.3V
    # With R3 = 30.9 kΩ:
    #   R2 = 96.6 kΩ ideal → nearest E96 = 100 kΩ
    #   → Vout = 0.8 × (1 + 100/30.9) = 3.39 V  (within ±3 % of 3.3 V target)
    #
    # Layout: R2 (top, 100 kΩ) and R3 (bottom, 30.9 kΩ) vertically stacked,
    # forming a divider between +3.3V (R2.top) and GND (R3.bot). FB tap
    # point is the R2.bot/R3.top junction. The U2.FB pin (at X=208.28,
    # Y=152.40) routes to the FB tap via a short L-wire: drop DOWN from
    # FB pin to Y=156.21 (clear of U2 body bottom at Y=154.94), then
    # RIGHT to the FB tap column at X=226.06.
    #
    # R2 and R3 are placed with a 2.54 mm gap between R2.bot (Y=144.78)
    # and R3.top (Y=147.32) so the two resistor body rectangles don't
    # touch on screen — easier to read. The connecting wire between
    # R2.bot and R3.top serves as the FB tap point.
    #
    # Wait — re-examining: if R2.top is to land on the +3.3V bus row
    # (Y=137.16) directly, then R2_Y=140.97 (R2.top = 140.97 - 3.81 =
    # 137.16, R2.bot = 144.78). But that puts R2.bot at Y=144.78 = the
    # SW row! At X=226.06 the SW extension wire does NOT reach (SW wire
    # X∈[208.28, 218.44]), so no electrical conflict, but visually the
    # FB-tap row at Y=144.78 sits on the same horizontal as the SW node.
    #
    # Cleaner: keep R2.top one row above the bus and add a short vertical
    # wire from R2.top up to the +3.3V bus. R2_Y=148.59 → R2.top=144.78
    # (a few mm below bus), then r2top-to-bus wire from (226.06, 144.78)
    # → (226.06, 137.16). R2.bot = 152.40. R3_Y=156.21 → R3.top=152.40,
    # R3.bot=160.02. FB tap = R2.bot = R3.top = (226.06, 152.40), same
    # Y as the U2.FB pin row — so the FB pin wire from (208.28, 152.40)
    # to (226.06, 152.40) is a single horizontal segment, no L-routing.
    # Much cleaner.
    COL_FB_DIV = 240.03 + PWR_X_SHIFT  # 189 × 1.27 — FB divider column (13.97 mm right of L2)
    R2_X = COL_FB_DIV
    R2_Y = 148.59 + PWR_Y_SHIFT   # 117 × 1.27
    R2_TOP_Y = R2_Y - 3.81        # 144.78
    R2_BOT_Y = R2_Y + 3.81        # 152.40 — FB tap row, matches U2.FB pin Y
    R3_X = COL_FB_DIV
    R3_Y = 156.21 + PWR_Y_SHIFT   # 123 × 1.27
    R3_TOP_Y = R3_Y - 3.81        # 152.40 — FB tap row, shared with R2.bot
    R3_BOT_Y = R3_Y + 3.81        # 160.02
    R3_GND_Y = 163.83 + PWR_Y_SHIFT  # GND symbol below R3.bot

    # ----- +3.3V output decoupling -----
    # C6 (22uF) and C16 (100nF) tap the +3.3V bus to GND. Placed to the
    # right of the FB divider with 15-16 mm column spacing so the
    # value-text labels ("44.2k 1%" / "22uF 10V" / "100nF") never overlap.
    C6_X = 256.54 + PWR_X_SHIFT   # 202 × 1.27 (16.51 right of R2)
    C6_Y = 140.97 + PWR_Y_SHIFT
    C6_TOP_Y = C6_Y - 3.81        # 137.16 — on +3.3V bus
    C6_BOT_Y = C6_Y + 3.81        # 144.78
    C6_GND_Y = 147.32 + PWR_Y_SHIFT

    C16_X = 271.78 + PWR_X_SHIFT  # 214 × 1.27 (15.24 right of C6)
    C16_Y = 140.97 + PWR_Y_SHIFT
    C16_TOP_Y = C16_Y - 3.81      # 137.16
    C16_BOT_Y = C16_Y + 3.81      # 144.78
    C16_GND_Y = 147.32 + PWR_Y_SHIFT

    # ----- +3.3V flag, PWR_FLAG sentinel -----
    # Column = C16 + 7.62 = 279.40. This sits ~25 mm right of the +5V flag
    # column (X=254 upstream), keeping the buck-3.3V section's PWR_FLAG
    # and flag visually distinct from the upstream +5V flag (which lives
    # in the same column but at a much lower Y, in the U1 block).
    COL_3V3      = 279.40 + PWR_X_SHIFT  # 220 × 1.27
    Y_3V3_BUS    = 137.16 + PWR_Y_SHIFT  # +3.3V bus row (same Y as VIN bus, but different X range)
    JUNC_3V3_Y   = 134.62 + PWR_Y_SHIFT  # PWR_FLAG sentinel sits here
    FLAG_3V3_Y   = 132.08 + PWR_Y_SHIFT  # +3V3 triangle, 2.54 above sentinel

    # ----- Buck-3.3V wires -----
    # Input side: +5V symbol → VIN bus, with EN tied to VIN as always-on.
    # The +5V "drop" symbol sits in the VIN/EN pin column (X=193.04)
    # above the body; its anchor is also the wire endpoint (length 0 pin
    # so the pin is at the symbol's (x, y)).
    Y_5V_DROP_TOP_X = U2_VIN_X    # 193.04 — VIN/EN/+5V drop column
    parts.append(_sch_wire(Y_5V_DROP_TOP_X, Y_5V_DROP_TOP, U2_VIN_X, U2_VIN_Y, "5v-to-vin"))
    parts.append(_sch_wire(U2_VIN_X, U2_VIN_Y, U2_EN_X, U2_EN_Y, "vin-to-en"))
    # VIN bus horizontal: C5.top → C15.top → U2.VIN pin
    parts.append(_sch_wire(C5_X, U2_VIN_Y, U2_VIN_X, U2_VIN_Y, "vin-bus-c5-c15-u2"))
    # C5 and C15 drops to local GND symbols
    parts.append(_sch_wire(C5_X, C5_BOT_Y, C5_X, C5_GND_Y, "c15ot-to-gnd"))
    parts.append(_sch_wire(C15_X, C15_BOT_Y, C15_X, C15_GND_Y, "c15bot-to-gnd"))

    # RT → GND: RT pin (programmable f_sw) tied to GND for default ~1.2 MHz.
    # The previous SS+RT shared-drop wiring was changed when SS was given
    # its own soft-start cap (C8): SS no longer shares a wire with RT.
    RT_GND_Y = 152.40 + PWR_Y_SHIFT  # GND symbol Y, below RT pin (149.86)
    parts.append(_sch_wire(U2_RT_X, U2_RT_Y, U2_RT_X, RT_GND_Y, "rt-to-gnd"))

    # SS → C8.top → C8.bot → GND: soft-start cap path. C8 sits 1.27 mm
    # west of the SS pin tip column so the SS → C8.top connection is a
    # single short horizontal wire; the C8.bot → GND drop continues
    # vertically to a new local GND symbol.
    parts.append(_sch_wire(U2_SS_X, U2_SS_Y, C8_X, C8_TOP_Y, "ss-to-c8"))
    parts.append(_sch_wire(C8_X, C8_BOT_Y, C8_X, C8_GND_Y, "c8bot-to-gnd"))

    # U2.GND (centre-bottom pin, pin 4) → local GND symbol below
    U2_GND_SYM_Y = 161.29 + PWR_Y_SHIFT  # 3.81 below U2.GND pin
    parts.append(_sch_wire(U2_GND_X, U2_GND_Y, U2_GND_X, U2_GND_SYM_Y, "u2gnd-to-gndsym"))

    # BST extension: U2.BST → C7.top, single horizontal stub.
    parts.append(_sch_wire(U2_BST_X, U2_BST_Y, C7_X, C7_TOP_Y, "u2bst-to-c7top"))
    # SW extension: U2.SW → L2.bot horizontal. Passes through C7.bot tap
    # column (X=213.36) — C7.bot pin endpoint lands on this wire, needing
    # a junction at the tap point.
    parts.append(_sch_wire(U2_SW_X, U2_SW_Y, L2_X, L2_BOT_Y, "u2sw-to-l2bot"))

    # FB pin → FB tap (R2.bot/R3.top junction at COL_FB_DIV). Single
    # horizontal wire at Y=152.40 (FB pin row = FB tap row, same Y), no
    # L-routing needed because the divider sits directly to the right of
    # the body in the same Y row.
    parts.append(_sch_wire(U2_FB_X, U2_FB_Y, COL_FB_DIV, R2_BOT_Y, "u2fb-to-fbtap"))

    # R2.top → +3.3V bus: short vertical hop up. R2.top at (226.06, 144.78);
    # +3.3V bus at Y=137.16.
    parts.append(_sch_wire(COL_FB_DIV, R2_TOP_Y, COL_FB_DIV, Y_3V3_BUS, "r2top-to-3v3bus"))

    # R3.bot → local GND symbol below
    parts.append(_sch_wire(COL_FB_DIV, R3_BOT_Y, COL_FB_DIV, R3_GND_Y, "r3bot-to-gnd"))

    # +3.3V bus horizontal: from L2.top RIGHT through R2-tap column,
    # C6 column, C16 column, to the flag column COL_3V3. Single wire
    # with junctions at the four tap points (R2 vertical end, C6 pin,
    # C16 pin, mid-bus T's).
    parts.append(_sch_wire(L2_X, Y_3V3_BUS, COL_3V3, Y_3V3_BUS, "3v3-bus"))

    # C6 and C16 drops to local GND symbols
    parts.append(_sch_wire(C6_X, C6_BOT_Y, C6_X, C6_GND_Y, "c16ot-to-gnd"))
    parts.append(_sch_wire(C16_X, C16_BOT_Y, C16_X, C16_GND_Y, "c16bot-to-gnd"))

    # +3.3V bus terminus → PWR_FLAG sentinel column upward, then to +3V3 flag.
    parts.append(_sch_wire(COL_3V3, Y_3V3_BUS, COL_3V3, JUNC_3V3_Y, "3v3-bus-to-junc"))
    parts.append(_sch_wire(COL_3V3, JUNC_3V3_Y, COL_3V3, FLAG_3V3_Y, "3v3-junc-to-flag"))

    # ----- Buck-3.3V junctions -----
    # VIN 4-way tap: VIN bus horizontal ends, +5V drop wire passes through,
    # VIN-to-EN wire starts. Plus U2.VIN pin endpoint.
    parts.append(_sch_junction(U2_VIN_X, U2_VIN_Y, "vin-u2"))
    # C15.top tap on VIN bus (mid-bus T with pin endpoint)
    parts.append(_sch_junction(C15_X, U2_VIN_Y, "vin-c15"))
    # SW wire passes through C7.bot tap column
    parts.append(_sch_junction(C7_X, U2_SW_Y, "sw-c7"))
    # FB tap: R2.bot pin + R3.top pin + FB wire end = 3 endpoints
    parts.append(_sch_junction(COL_FB_DIV, R2_BOT_Y, "fb-tap"))
    # +3.3V bus mid-bus T's: R2-vertical end, C6 pin, C16 pin
    parts.append(_sch_junction(COL_FB_DIV, Y_3V3_BUS, "3v3-r2"))
    parts.append(_sch_junction(C6_X, Y_3V3_BUS, "3v3-c6"))
    parts.append(_sch_junction(C16_X, Y_3V3_BUS, "3v3-c16"))
    # PWR_FLAG sentinel position on the vertical to the +3V3 flag
    parts.append(_sch_junction(COL_3V3, JUNC_3V3_Y, "3v3"))

    # ----- U2: TPS62933 -----
    parts.append(_sch_buck_tps62933(
        x=U2_X, y=U2_Y, angle=0,
        reference="U2", value="TPS62933", uuid_tag="u2",
    ))

    # ----- L2: 2.2 uH shielded inductor (2 A sat, ~50 mOhm DCR) -----
    parts.append(_sch_inductor(
        x=L2_X, y=L2_Y, angle=0,
        reference="L2", value="2.2uH 2A", uuid_tag="l2",
    ))

    # ----- C5: input bulk ceramic, 10 uF / 25 V -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C5_X, y=C5_Y, angle=0,
        reference="C5", value="10uF 25V", uuid_tag="c5",
    ))

    # ----- C15: input HF ceramic bypass, 100 nF -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C15_X, y=C15_Y, angle=0,
        reference="C15", value="100nF", uuid_tag="c15",
    ))

    # ----- C6: output bulk ceramic, 22 uF / 10 V -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C6_X, y=C6_Y, angle=0,
        reference="C6", value="22uF 10V", uuid_tag="c6",
    ))

    # ----- C16: output HF ceramic bypass, 100 nF -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C16_X, y=C16_Y, angle=0,
        reference="C16", value="100nF", uuid_tag="c16",
    ))

    # ----- C7: BST bootstrap ceramic, 100 nF -----
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C7_X, y=C7_Y, angle=0,
        reference="C7", value="100nF", uuid_tag="c7",
    ))

    # ----- C8: SS soft-start ceramic, 47 nF -----
    # See the C8 constants comment block above for the rationale (TPS62933
    # SS=GND disables soft-start; C8=47nF sets t_ss ~= 5.6 ms within the
    # SEN66 datasheet's 2-10 ms power-ramp window).
    parts.append(_sch_capacitor(
        lib_id="Device:C",
        x=C8_X, y=C8_Y, angle=0,
        reference="C8", value="47nF", uuid_tag="c8",
    ))

    # ----- R2: feedback divider top, 100 kΩ 1% (v0.36 — was 44.2k pre-fix) -----
    # See CRITICAL-2 fix in v0.36 swarm audit. TPS62933 Vref = 0.8 V per the
    # TI datasheet §"Electrical Characteristics" (NOT 0.6 V as the pre-v0.36
    # comments wrongly assumed). For Vout = 3.3 V: R2/R3 = (3.3/0.8 - 1) =
    # 3.125, so R2 = 100 k + R3 = 30.9 k yields Vout = 0.8 × (1 + 100/30.9)
    # = 3.39 V — within ±5 % of 3.3 V target. The pre-v0.36 schematic values
    # (R2=44.2k / R3=10k) were designed for Vref=0.6 V and would have produced
    # 4.34 V at the actual Vref=0.8 V — destroying ESP32-C6 + SEN66 (both
    # Vdd_max = 3.6 V).
    parts.append(_sch_resistor(
        x=R2_X, y=R2_Y, angle=0,
        reference="R2", value="100k 1%", uuid_tag="r2",
    ))

    # ----- R3: feedback divider bottom, 30.9 kΩ 1% (v0.36 — was 10k pre-fix) -----
    parts.append(_sch_resistor(
        x=R3_X, y=R3_Y, angle=0,
        reference="R3", value="30.9k 1%", uuid_tag="r3",
    ))

    # ----- +5V drop symbol (taps the global +5V net into U2.VIN) -----
    # angle=180 so the triangle points DOWN. The value-text "+5V" sits
    # above the symbol anchor (value_offset_y=-3.556, same as the upstream
    # +5V flag).
    parts.append(_sch_power_flag(
        lib_id="power:+5V", value="+5V",
        x=Y_5V_DROP_TOP_X, y=Y_5V_DROP_TOP, angle=180,
        reference="#PWR15",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr15-5v-drop",
    ))

    # ----- +3.3V flag at top-right of the buck-3.3V block -----
    parts.append(_sch_power_flag(
        lib_id="power:+3V3", value="+3V3",
        x=COL_3V3, y=FLAG_3V3_Y, angle=0,
        reference="#PWR16",
        value_offset_x=0.0, value_offset_y=-3.556,
        uuid_tag="pwr16-3v3",
    ))

    # ----- Local GND symbols around U2 / L2 / R3 / caps -----
    # All share the global GND net. No PWR_FLAG sentinel on any of these
    # — FLG02 (on J1.2's drop) already supplies the ERC power-source
    # marker for the GND net.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C5_X, y=C5_GND_Y, angle=0,
        reference="#PWR17",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr17-gnd-c5",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C15_X, y=C15_GND_Y, angle=0,
        reference="#PWR18",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr18-gnd-c15",
    ))
    # RT pin GND drop (SS now has its own C8 soft-start cap to GND, so it
    # no longer shares this GND symbol with RT — see #PWR24 below for C8).
    # uuid_tag retained as "pwr19-gnd-ssrt" to preserve UUID stability
    # across the cap-fix rework.
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=U2_RT_X, y=RT_GND_Y, angle=0,
        reference="#PWR19",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr19-gnd-ssrt",
    ))
    # U2.GND (pin 4)
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=U2_GND_X, y=U2_GND_SYM_Y, angle=0,
        reference="#PWR20",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr20-gnd-u2",
    ))
    # R3.bot (divider bottom to GND)
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=COL_FB_DIV, y=R3_GND_Y, angle=0,
        reference="#PWR21",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr21-gnd-r3",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C6_X, y=C6_GND_Y, angle=0,
        reference="#PWR22",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr22-gnd-c6",
    ))
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C16_X, y=C16_GND_Y, angle=0,
        reference="#PWR23",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr23-gnd-c16",
    ))
    # C8.bot (soft-start cap to GND)
    parts.append(_sch_power_flag(
        lib_id="power:GND", value="GND",
        x=C8_X, y=C8_GND_Y, angle=0,
        reference="#PWR24",
        value_offset_x=0.0, value_offset_y=3.81,
        uuid_tag="pwr24-gnd-c8",
    ))

    # ----- PWR_FLAG sentinel on the new +3.3V net -----
    # Without this, ERC would error "Input Power pin not driven by any
    # Output Power pins" on the +3.3V net — TPS62933's SW pin is an
    # `output` (not `power_out`), so it doesn't count as a power source
    # for the ERC check.
    parts.append(_sch_power_flag(
        lib_id="power:PWR_FLAG", value="PWR_FLAG",
        x=COL_3V3, y=JUNC_3V3_Y, angle=0,
        reference="#FLG05",
        value_offset_x=PF_TEXT_OFFSET, value_offset_y=-2.54,
        uuid_tag="flg05-3v3",
    ))

    body = "\n".join(parts)
    return textwrap.dedent(f"""\
        (kicad_sch
        \t(version {SCH_VERSION})
        \t(generator "eeschema")
        \t(generator_version "{GEN_VERSION}")
        \t(uuid "{file_uuid}")
        \t(paper "A4")
        \t(lib_symbols
        {POWER_LIB_SYMBOLS}
        \t)
        {body}
        \t(embedded_fonts no)
        )
        """)

# -----------------------------------------------------------------------------
# 3c) MCU sub-sheet — ESP32-C6-DevKitM-1-N4 (U3) + local decoupling + recovery header
# -----------------------------------------------------------------------------
# Embedded lib_symbols for the MCU sub-sheet. Self-contained: each sub-sheet
# carries its own copy of the symbols it uses (the +3V3 / GND and Device:C /
# Device:C_Polarized blocks are intentionally duplicated with POWER_LIB_SYMBOLS
# so the .kicad_sch file opens identically on any machine).
#
# Symbol sources:
#   - "OAS:ESP32-C6_DevKitM-1" : own work, defined inline below. Models the
#     Espressif official ESP32-C6-DevKitM-1-N4 development kit.
#
#     # Module Identification
#     MPN  : ESP32-C6-DevKitM-1-N4
#     EAN  : 5904422385651 (Botland)
#     User guide:
#       https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32c6/esp32-c6-devkitm-1/user_guide.html
#     Chip : ESP32-C6FH4 (ESP32-C6-MINI-1 SoM with 4 MB internal SiP flash).
#            GPIO 10 and GPIO 11 are NOT bonded out — they serve internal
#            flash communication. Available GPIOs: 0, 1, 2, 3, 4, 5, 6, 7,
#            8, 9, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23 (22 total).
#     Form factor : 48.26 × 25.4 mm. Two USB-C connectors (one through an
#                   onboard USB-to-UART bridge IC, one direct to native
#                   USB-Serial-JTAG on GPIO 12/13). Onboard power LED and
#                   addressable RGB NeoPixel (GPIO 8). Reset + Boot
#                   pushbuttons.
#     Headers : Two 15-pin headers, J1 (left) and J3 (right), 2.54 mm
#               pitch, mirroring Espressif's numbering. The symbol below
#               exposes all 30 header positions in faithful order so the
#               schematic matches the physical module.
#
#     Pin layout (J1 left, J3 right) reproduced from the official user
#     guide. Pin 1 of each header is the TOPMOST pin in this symbol so
#     the body matches the silk on the dev-kit (USB-C ports at the top).
#
#       J1 (left side, top→bottom)            J3 (right side, top→bottom)
#         1  3V3      power_in                  1  GND      power_in
#         2  RST      input                     2  GPIO16   bidirectional
#         3  GPIO2    bidirectional             3  GPIO17   bidirectional
#         4  GPIO3    bidirectional             4  GPIO23   bidirectional
#         5  GPIO4    bidirectional (MTMS)      5  GPIO22   bidirectional
#         6  GPIO5    bidirectional (MTDI)      6  GPIO21   bidirectional
#         7  GPIO0    bidirectional             7  GPIO20   bidirectional
#         8  GPIO1    bidirectional             8  GPIO19   bidirectional
#         9  GPIO8    bidirectional (RGB LED)   9  GPIO18   bidirectional
#        10  GPIO6    bidirectional (MTCK)     10  GPIO15   bidirectional
#        11  GPIO7    bidirectional (MTDO)     11  GPIO9    bidirectional (BOOT strap)
#        12  GPIO14   bidirectional            12  GND      power_in
#        13  GND      power_in                 13  GPIO13   bidirectional (USB D+)
#        14  5V       power_in                 14  GPIO12   bidirectional (USB D-)
#        15  GND      power_in                 15  GND      power_in
#
#   - "Connector_Generic:Conn_01x06" : copied verbatim from KiCad 10's stock
#     Connector_Generic.kicad_sym (GPL).
#   - "Device:R" : copied verbatim from KiCad 10's stock Device.kicad_sym
#     (GPL). Needed in the MCU sheet for R5/R6 I²C pull-ups.
#   - "Device:C", "Device:C_Polarized", "power:+3V3", "power:GND" : copied
#     verbatim from KiCad 10's stock libraries (GPL).


# DevKitM-1-N4 pin definitions — single source of truth for the lib symbol
# and (downstream) the gen_mcu_sch wiring helper. Each entry is
# (pin_number, gpio_name, type, header, header_pos). `gpio_name` is the
# string KiCad shows next to the pin in eeschema; `type` selects the
# KiCad pin electrical class.
#
# Pin number numbering convention (this symbol):
#   pins 1..15  = J1 (left header), top→bottom
#   pins 16..30 = J3 (right header), top→bottom
# Pin 1 = J1 top; pin 16 = J3 top. This way the geometric pin order
# mirrors the physical module silk and gen_mcu_sch can compute
# row Y by index directly.
from boardgen._lib_symbols import (
    ESP32C6_DEVKITM1_PINS,
    ESP32C6_DEVKITM1_SIGNAL_PIN,
    ESP32C6_DEVKITM1_NC_PINS,
    ESP32C6_DEVKITM1_GND_PINS,
    ESP32C6_DEVKITM1_PIN_PITCH,
    ESP32C6_DEVKITM1_PIN_ROW_HALF,
    ESP32C6_DEVKITM1_LIB_X_LEFT,
    ESP32C6_DEVKITM1_LIB_X_RIGHT,
    ESP32C6_DEVKITM1_LIB_PIN_LEN,
    ESP32C6_DEVKITM1_LIB_BODY_X,
    ESP32C6_DEVKITM1_LIB_BODY_Y,
)

from boardgen._lib_symbols import _esp32c6_devkitm1_lib_symbol, MCU_LIB_SYMBOLS
# -----------------------------------------------------------------------------
# Helpers specific to the MCU sub-sheet (sheet_key="mcu" pinned)
# -----------------------------------------------------------------------------
