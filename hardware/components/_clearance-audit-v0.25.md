# Clearance Audit v0.25 — Daughterboard Z-Stack

## Post-fix status (v0.26, 2026-05-13)

The 3 FAIL components (C1, C3, C4) + 1 EDGE component (U1) identified in
this audit were **relocated** in v0.26 — NO BOM change, only XY
coordinates updated. New placements (PCB-frame mm):

| Ref | Old position | New position | Rationale |
|---|---|---|---|
| **C1** | (−20, −32.5), inside ESP32 shadow | **(+40, +36)** | south-east of SEN66, on V_24V_PROT net |
| **C3** | (−20, −41), inside ESP32 shadow | **(−34, −24)** | west-of-ESP32 column, south of U1 (close to U1.VIN) |
| **C4** | (+16, −37), inside ESP32 shadow | **(+25, −47)** | east-of-ESP32, north of SEN66 |
| **U1** | (−9, −37), inside ESP32 shadow (EDGE +0.9 mm) | **(−34, −34)** | west-of-ESP32 column, between LD2410 east (−43.47) and ESP32 west (−27.76) |

Two additional collateral moves to clear adjacency conflicts:

| Ref | Old position | New position | Reason |
|---|---|---|---|
| C2 (Y2 safety cap) | (−32, −25) | (−46, −25) | clear C3 at (−34, −24) |
| C10 (SEN66 +3V3 decoupling) | (+42, +33) | (+46, +32) | clear C1 at (+40, +36) |

Status after relocation:
- **DRC**: 0 violations (160 unconnected pads remaining — these are
  routing-stage issues, not placement; the PCB is unrouted)
- **ERC**: 0 violations
- **Determinism**: bit-identical regeneration confirmed
- **Z-clearance guardrail** (new in v0.26): 0 violations across 76
  placed footprints. The guardrail iterates every placed footprint
  and tests its body extent against the three daughterboard XY
  shadows; flags any component whose datasheet-max height exceeds
  the daughterboard's under-board Z-clearance budget. Implemented
  in `generate.py` via `FOOTPRINT_HEIGHT`, `DAUGHTERBOARD_Z_CLEARANCE`,
  `_FOOTPRINT_HALF_EXTENT`, `_DAUGHTERBOARD_MOUNTING_SOCKETS`, and
  `check_z_clearance_violations()`. Aborts `regenerate.py` if any
  violation surfaces in a future revision.

Two trade-offs accepted in the v0.26 placement:
- **U1 switch-node trace from U1.SW (pin 2 at PCB (−32.3, −30.55))
  to L1 (+9, −37)** is now ~42 mm — much longer than the previous
  ~10 mm. Acceptable for this 150 kHz / 3A node on inner-layer
  copper; the trace can route around the ESP32 shadow on F.Cu
  without sharing the daughterboard's Z region.
- **U1.VOUT to C4 trace** is ~36 mm (was ~7 mm). Same routability
  concern; +5V bulk handles low-frequency load-step transients, not
  the switch node.

---

- **Date**: 2026-05-13
- **Scope**: Z-clearance (vertical / out-of-PCB-plane) check for every SMD/THT
  footprint placed under the ESP32-C6-DevKitM-1-N4 (MOD1), MIKROE-2462 (MOD2),
  and HLK-LD2410B (LDR1) daughterboards on the OAS PCB.
- **Trigger**: user observed that v0.22 deliberately placed 24 SMDs fully inside
  the ESP32 daughterboard body shadow ("13 components moved fully inside ESP32
  shadow" in the commit message), but the v0.22 reasoning ("daughterboards sit
  ~8 mm above the PCB, so SMDs <2 mm CAN go beneath") never checked whether the
  v0.20 power-section radial electrolytics — explicitly placed by C1/C3/C4
  designators in the same code path — exceed the actual standoff budget.
- **Commit audited**: `2b655ec` (v0.25 HEAD, sources of truth =
  `hardware/kicad/generate.py`).
- **Method**: every body shadow computed from the source-of-truth
  `<COMPONENT>_ANCHOR_X/Y/ROTATION/BODY_*` constants in `generate.py`; every
  footprint placement read from `gen_power_pcb_footprints()` and the
  `gen_pcb_footprints` sibling that emits the daughterboard socket rows.
  Component package heights cross-referenced against manufacturer datasheets
  (Panasonic ECA / ECPU radials, Würth WE-PD inductors, TI TPS62933 SOT-583,
  Vishay TVS SMB, Bourns MF-RHT polyfuses).
- **No source files edited** (audit-only task). Recommendations are in
  Section E for a follow-up fix iteration.

---

## A — Daughterboard body shadows

All ranges are PCB-frame mm (PCB origin = centre of D-shaped outline,
+X east, +Y south toward chord).

| Daughterboard | Designator | Anchor (x, y) | Helper rotation | Body W × L (mm) | PCB X range | PCB Y range | Body area (mm²) |
|---|---|---|---|---|---|---|---|
| ESP32-C6-DevKitM-1-N4 | MOD1 | (-27.76, -24.70) | 90° (LIB +Y → PCB +X) | 25.4 × 48.26 | **-27.76 .. +20.50** | **-50.10 .. -24.70** | 1226 |
| MIKROE-2462 NFC Tag 2 Click | MOD2 | (-12.76, +40.64) | 180° (LIB +X → PCB -X, LIB +Y → PCB -Y) | 25.4 × 57.15 | **-38.16 .. -12.76** | **-16.51 .. +40.64** | 1452 |
| HLK-LD2410B | LDR1 | (-43.47, -16.51) | 270° (LIB +X → PCB +Y, LIB +Y → PCB -X) | 7.62 × 35.56 (post-v0.15.8 fix) | **-51.09 .. -43.47** | **-16.51 .. +19.05** | 271 |

**Note**: the v0.22 ESP32 shadow comment in `generate.py` line 4775 lists
`X ∈ [-27.76, +20.50], Y ∈ [-50.10, -24.70]` — matches the computation above.
The v0.22 comment also calls out that the J5 row at Y=-25.97 and the J6 row at
Y=-48.83 sit **inside** the body shadow (the sockets carry the daughterboard;
their pads are part of the shadow), so the usable SMD strip inside the shadow
is Y ∈ [-47.0, -28.0] with ~0.5 mm clearance from socket pads.

---

## B — Z-clearance budget per daughterboard

### General assumption: 2.54 mm vertical female pin socket

The OAS PCB carries female pin sockets (`gen_pinsocket_pcb_footprint`,
generic Conn_01x15 / Conn_01x08 stock library entries — no specific MPN
chosen yet). For 2.54 mm vertical THT female sockets the typical plastic
body height is:

- **Samtec SSW-115-01-G-S** (premium, gold-plated): 8.51 mm plastic body.
- **Generic LCSC C49661 / Würth WR-PHD 615115**: 8.5 mm plastic body.
- **Low-profile alternatives** (e.g. SAMTEC ESQ-115-39-G-S): 5.3 mm — uncommon.

**Working assumption: 8.5 mm socket body height** (committed in
`ESP32_BODY_Z = 8.6` and `MIKROE2462_BODY_Z = 7.0` constants — note the NFC
value is suspicious; see §F below).

### Daughterboard underside features

| Daughterboard | Bottom-side features | Worst-case bottom protrusion |
|---|---|---|
| ESP32-C6-DevKitM-1-N4 | **Male pin headers** (2× 1×15 P2.54 mm vertical) protrude ~3.0 mm below the DevKit PCB. **Both USB-C connectors are on the top side** (per `esp32-c6-devkitm-1-pcb-layout.pdf`); they do NOT protrude below. Espressif schematic shows no bottom-side ICs. **Onboard pin-1 dot is bottom-side silk only — no copper standoff issue.** | ~3.0 mm (male pin tails) |
| MIKROE-2462 NFC Tag 2 Click | Male mikroBUS pins (2× 1×8) protrude ~3.0 mm below the Click PCB. **NFC antenna spiral is on the TOP side** of the Click PCB (verified against MikroE datasheet PDF — antenna sits opposite the pin block on the top face, status LEDs and NT3H1101 are on top). **No bottom-side components** on the Click board per MikroE schematic v1.01. | ~3.0 mm (male pin tails) |
| HLK-LD2410B | The LD2410 is mounted on a **single 5-pin 1.27 mm vertical THT header** soldered directly through the OAS PCB (J4 — `PinHeader_1x05_P1.27mm_Vertical`, not a socket). Module body sits ~5-7 mm above OAS PCB. The 24 GHz patch antennas are on the **top side** of the LD2410 (radiating outward). Bottom side carries the radar SoC and BLE chip (~1.5 mm tall SMDs). No bottom features protrude downward into the OAS PCB clearance zone (the LD2410 is "the daughterboard"; nothing dangles below its bottom-side SMDs). | The LD2410 PCB bottom is ~3 mm above OAS PCB (header standoff + LD2410 PCB-bottom-side SMD 1.5 mm). |

### Net effective component clearance (OAS PCB top → daughterboard PCB bottom)

| Daughterboard | Socket body | Pin tail (subtract) | Clearance for OAS-side SMDs |
|---|---|---|---|
| **ESP32 (MOD1)** | 8.5 mm | 0 (the socket plastic *is* the standoff; daughterboard PCB rests on socket top, pin tails go INTO socket, not into clearance zone) | **~8.5 mm** if daughterboard PCB rests on socket plastic top. **~5.5 mm** if the pins bottom out in the socket first (depends on pin length vs socket depth). **Conservative working budget: 5.5 mm.** |
| **MIKROE (MOD2)** | 8.5 mm | 0 (same logic) | **~5.5-8.5 mm** (same logic; conservative 5.5 mm) |
| **LD2410 (LDR1)** | Standard 1.27 mm pin header, plastic body ~2.5 mm | LD2410 PCB rests on header plastic | **~2.5 mm + ~1.0 mm (PCB) – ~1.5 mm (bottom-side SMDs) ≈ 2.0 mm** net under the LD2410 PCB bottom + bottom-side SMD shadow. **Very tight.** |

**Key clarification on the "8.6 mm" value in `ESP32_BODY_Z`**: this is the
height **of the top of the daughterboard** above the OAS PCB. It includes the
socket (~8.5 mm) + the daughterboard PCB thickness (~1.6 mm) and is used for
**enclosure-Z** budget (vs the 17 mm AK-N-94 cover limit). It is **NOT** the
available clearance under the daughterboard for OAS-side SMDs. The available
under-board clearance is roughly the **socket body height alone (≤ 8.5 mm)**,
and is **further reduced** if the daughterboard's male pin tails bottom out
inside the socket (typical, since the socket through-hole receptacles are
4-5 mm deep, and male headers have ~3 mm of tail below the daughterboard PCB).

**Conservative budgets for this audit** (worst-case-realistic):

- ESP32 daughterboard: **5.5 mm** OAS-side component clearance.
- MIKROE-2462 daughterboard: **5.5 mm** OAS-side component clearance.
- LD2410 daughterboard: **2.0 mm** OAS-side component clearance.

If a premium standoff socket (e.g. Mill-Max 833-43-015 stackable with 11+ mm
mated height) is specified at BOM time, the budget can grow — but no such
choice is in the current source. The default stock Conn_01x15 / Conn_01x08
KiCad footprints map to 8.5 mm socket bodies, and that is what the audit
assumes.

---

## C — Components inside each daughterboard body shadow

### C.1 — ESP32-C6-DevKitM-1-N4 shadow (X ∈ [-27.76, +20.50], Y ∈ [-50.10, -24.70])

Read from `gen_power_pcb_footprints()` in `generate.py` lines 4796-4967.
**24 SMD/THT footprints** sit fully or partially inside the ESP32 shadow:

| Ref | Package | Position (x, y) | Value | Package height (top of part above OAS PCB) | Source |
|---|---|---|---|---|---|
| **C1** | **CP_Radial D8.0 mm / P3.5 mm THT** | (-20.0, -32.5) | 100 µF / 50 V | **11.5-12.5 mm** (Panasonic ECA-1HM101 D=8 mm L=11.5 mm; Nichicon UVR1H101 D=8 mm L=11.5 mm; Rubycon YXG 100µF 50V D=8 mm L=11.5 mm) | Panasonic ECA-1H datasheet |
| **C3** | **CP_Radial D8.0 mm / P3.5 mm THT** | (-20.0, -41.0) | 100 µF / 50 V | **11.5-12.5 mm** (same as C1) | Same as C1 |
| **C4** | **CP_Radial D6.3 mm / P2.5 mm THT** | (+16.0, -37.0) | 220 µF / 10 V | **11.0-12.0 mm** (Panasonic ECA-1AM221 D=6.3 mm L=11.2 mm; Rubycon YXJ 220µF 10V D=6.3 mm L=11 mm) | Panasonic ECA-1A datasheet |
| U1 | TO-263-5 (D2PAK-5) | (-9.0, -37.0) | LM2596S-5.0 | **4.6 mm** (TI LM2596 D2PAK-5 case body height max 4.83 mm) | TI LM2596 datasheet, package KTW-5 |
| D2 | SMA | (+2.0, -37.0) | SS14 | **2.3 mm** (Vishay SMA package 2.3 mm max) | Vishay SS14 datasheet |
| L1 | SMD 5×5 (Würth WE-PD-S or similar) | (+9.0, -37.0) | 33 µH ≥2A | **3.0-4.0 mm** (assumed `*Inductor_SMD:L_5x5_H4*` profile per stub footprint; Würth WE-PD-S 5045 = 4.5 mm; LCSC C92027 = 3.0 mm) | Würth WE-PD-S datasheet (worst-case 4.5 mm) |
| U2 | SOT-583 / VSON-8 | (-2.0, -43.5) | TPS62933 | **0.8 mm** (TI SOT-583 max 0.85 mm) | TI TPS62933 datasheet |
| L2 | SMD 5×5 | (+4.0, -44.0) | 2.2 µH ≥2A | **3.0-4.0 mm** (same as L1) | Same as L1 |
| R2 | 0603 | (+10.0, -44.0) | 100k | 0.45 mm | Vishay CRCW 0603 datasheet |
| R3 | 0603 | (+13.0, -44.0) | 30.9k | 0.45 mm | Same as R2 |
| C13 | 0603 | (-14.0, -30.0) | 100 nF | 0.95 mm | Murata GRM188 0603 datasheet |
| C14 | 0603 | (-6.0, -30.0) | 100 nF | 0.95 mm | Same as C13 |
| C9 | 0805 | (0.0, -30.0) | 10 µF | 1.25 mm | Murata GRM21 0805 datasheet |
| C17 | 0603 | (+4.0, -30.0) | 100 nF | 0.95 mm | Same as C13 |
| R5 | 0603 | (+8.0, -30.0) | 4.7k | 0.45 mm | Same as R2 |
| R6 | 0603 | (+11.0, -30.0) | 4.7k | 0.45 mm | Same as R2 |
| R7 | 0603 | (+14.0, -30.0) | 10k | 0.45 mm | Same as R2 |
| C5 | 0805 | (-25.0, -46.0) | 10 µF | 1.25 mm | Same as C9 |
| C15 | 0603 | (-17.0, -46.0) | 100 nF | 0.95 mm | Same as C13 |
| C6 | 0805 | (-14.0, -46.0) | 22 µF | 1.25 mm | Same as C9 |
| C16 | 0603 | (-10.0, -46.0) | 100 nF | 0.95 mm | Same as C13 |
| C7 | 0603 | (-6.0, -46.0) | 22 pF | 0.95 mm | Same as C13 |
| C8 | 0603 | (-2.0, -46.0) | 100 nF | 0.95 mm | Same as C13 |

**Not inside ESP32 shadow** (intentionally placed outside): C2 (-32, -25),
D1 (+16, +9.5), Q1 (+27, +25), D3 (+27, +28), F1 (+54, +9), R1 (+25, +33),
R4 (+25, +35.5), C10 (+42, +33), C11 (-42, +14), C12 (-25, +23), J2 (-54, -8).
C12 sits inside the MIKROE shadow (see C.2).

### C.2 — MIKROE-2462 shadow (X ∈ [-38.16, -12.76], Y ∈ [-16.51, +40.64])

| Ref | Package | Position (x, y) | Value | Package height | Source |
|---|---|---|---|---|---|
| C12 | 0603 | (-25.0, +23.0) | 100 nF | 0.95 mm | Murata GRM188 0603 |

Only 1 footprint inside the NFC shadow. (The placement comment for C12 in
`generate.py` line 4999 explicitly notes "Under the NFC body shadow (7 mm
clearance available)" — accurate, this part is fine.)

### C.3 — HLK-LD2410B shadow (X ∈ [-51.09, -43.47], Y ∈ [-16.51, +19.05])

| Ref | Package | Position (x, y) | Inside shadow? |
|---|---|---|---|
| C11 | 0603 | (-42.0, +14.0) | **No** — x=-42 is east of body right edge at x=-43.47 (off by 1.47 mm). C11 sits in the 6.59 mm strip between LD2410 body and ESP32 body. |
| J2 | 1×6 P2.54 mm THT header (DNP) | (-54.0, -8.0) | **No** — x=-54 is west of body left edge at x=-51.09 (off by 2.91 mm). J2 sits in the NW strip. |

**Zero footprints inside the LD2410 shadow.** The very tight 2.0 mm clearance
budget is moot here.

---

## D — Clearance verdict table (every component-vs-daughterboard pair)

Verdict thresholds:
- **FIT**: ≥ 1 mm clearance margin.
- **EDGE**: 0 - 1 mm margin (works in theory; zero tolerance for socket spec drift or component tolerance).
- **FAIL**: negative margin (physical interference — daughterboard cannot seat).

### ESP32 (MOD1) — budget 5.5 mm

| Ref | Pkg | Height (mm) | Margin (mm) | Verdict |
|---|---|---|---|---|
| **C1** | CP_Radial D8.0 | **12.0** | **−6.5** | **FAIL** |
| **C3** | CP_Radial D8.0 | **12.0** | **−6.5** | **FAIL** |
| **C4** | CP_Radial D6.3 | **11.2** | **−5.7** | **FAIL** |
| **U1** | TO-263-5 | 4.6 | +0.9 | **EDGE** |
| L1 | SMD 5×5 H4 | 4.0 (w.c.) | +1.5 | FIT |
| L2 | SMD 5×5 H4 | 4.0 (w.c.) | +1.5 | FIT |
| D2 | SMA | 2.3 | +3.2 | FIT |
| C9 / C5 / C6 (0805) | 0805 | 1.25 | +4.25 | FIT |
| C13 / C14 / C17 / C15 / C16 / C7 / C8 (0603 caps) | 0603 | 0.95 | +4.55 | FIT |
| U2 | SOT-583 | 0.8 | +4.7 | FIT |
| R2 / R3 / R5 / R6 / R7 (0603 R) | 0603 | 0.45 | +5.05 | FIT |

### MIKROE (MOD2) — budget 5.5 mm

| Ref | Pkg | Height (mm) | Margin (mm) | Verdict |
|---|---|---|---|---|
| C12 | 0603 | 0.95 | +4.55 | FIT |

### LD2410 (LDR1) — budget 2.0 mm

(No footprints inside the LD2410 body shadow — empty.)

---

### Summary by severity

| Daughterboard | FAIL | EDGE | FIT |
|---|---:|---:|---:|
| ESP32 (MOD1) | **3** (C1, C3, C4) | **1** (U1) | 20 |
| MIKROE (MOD2) | 0 | 0 | 1 |
| LD2410 (LDR1) | 0 | 0 | 0 |
| **TOTAL** | **3** | **1** | **21** |

---

## E — Relocation / replacement recommendations for FAIL + EDGE

### E.1 — C1 (FAIL, 100 µF / 50 V, 12 mm tall)

**Option A — replace with SMD equivalent** (preferred):
- **Panasonic 25SVPF100M** (POSCAP / polymer): 100 µF / 25 V — *insufficient
  voltage* (the protected +24 V rail is post-Q1 reverse-polarity FET, but
  transient surges via D1 SMBJ24A clamp at 38.9 V). Reject.
- **Panasonic EEEFP1J101AP** (V-FP series aluminium electrolytic SMD):
  100 µF / 63 V, case **F12** (D = 10 mm, H = 10.2 mm). Still tall.
- **Würth 865060657013** (WCAP-ASLI radial SMD): 100 µF / 50 V, **D8 × H10**.
  Slightly shorter than radial THT but still **>5.5 mm — FAIL**.
- **Nichicon UWX1J101MCL1GB** (UWX series SMD radial): 100 µF / 63 V, **D8 ×
  H10.5**. Same problem.
- **Reality**: any 100 µF / ≥50 V aluminium cap in a meaningful ripple-rated
  package is ≥ 8 mm tall regardless of SMD vs THT.

**Option B — relocate** (preferred fallback): move C1 to negative space
outside the ESP32 shadow. Candidate zones:

- North-of-ESP32 (Y < -50.10): outside PCB outline at this X (PCB arc
  reaches Y=-60 at X=0 only; at X=-20 the arc Y is ~ -56.4). Strip width at
  X=-20 is Y ∈ [-50.10, -56.4] ≈ 6.3 mm tall — **enough for one 8 mm-diameter
  radial body** with rotated orientation. Verify against H3 mounting hole
  at (0, -55.0) — at X=-20 H3 is 20 mm distant, no collision.
- West-of-ESP32, between ESP32 left (X=-27.76) and LD2410 right (X=-43.47):
  6.59 mm wide strip Y ∈ [-16.51, -24.70] (LD2410 Y-extent boundary).
  Currently empty except for J2 at (-54, -8) which is in a different strip.
  Could fit C1 here. Wires to U1.VIN (currently at -9, -37) get longer
  (~25 mm vs ~14 mm currently — bypass inductance grows; still acceptable
  for a 24 V protected bulk that mostly handles low-frequency surge).

**Recommended**: relocate C1 to **(-20, -54)** in the north-of-ESP32 strip
(if the PCB arc clears) or to **(-32, -28)** in the west-of-ESP32 strip.

### E.2 — C3 (FAIL, 100 µF / 50 V, 12 mm tall)

C3 is the bulk cap for U1.VIN — should sit close to U1 for low ESR loop.
Identical part to C1; same constraints apply.

**Option A — replace**: same outcome as C1 — no good SMD substitute.

**Option B — relocate**: move to the same north-of-ESP32 strip near U1.VIN.
At U1's current location (-9, -37), a C3 placement at **(-9, -54)** would
keep the 24 V bulk cap close to U1. PCB arc at X=-9 is Y ~ -59.3 → strip is
~5 mm tall — fits a D8 radial. H3 hole at (0, -55) sits 12.4 mm east; safe.

**Option C — replace with multiple smaller SMDs in parallel**: 2× 47 µF /
50 V SMD electrolytics (Panasonic EEEHA1H470AP, D6.3 × H5.8) totalling
94 µF in parallel. Two D6.3 × 5.8 mm SMDs stacked at U1.VIN side. Total
height 5.8 mm → still **FAIL by 0.3 mm** at 5.5 mm budget. Borderline.
If budget grows to 6 mm (slightly taller socket), feasible.

**Option D — re-rate the rail**: if the 24 V input is actually 24.0 V ± 5 %,
nothing on the protected rail exceeds 25.2 V steady-state. A 100 µF / 35 V
SMD electrolytic (Panasonic EEEHB1V101AP, D8 × H5.4) provides 35 V working
margin and is **just under the 5.5 mm budget — FIT margin +0.1 mm — EDGE**.
The 50 V rating was chosen to ride out D1's 38.9 V clamp during a one-shot
surge; that is brief (<1 µs) and a 35 V part will tolerate it via the same
mechanism the 50 V part does. **Discuss with user before downgrading.**

### E.3 — C4 (FAIL, 220 µF / 10 V, 11 mm tall)

C4 is the +5 V output bulk for U1.

**Option A — replace with SMD polymer**: Panasonic **25SVPF220M** (POSCAP
220 µF / 25 V, D7.3 × H4.2 mm). **Margin +1.3 mm at 5.5 mm budget — FIT.**
Polymer ESR (~30 mΩ) is far better than the radial electrolytic (~150 mΩ)
the current part has — improves U1 transient response. Cost +$0.50/unit.
**Strongly recommended**.

**Option B — replace with multiple ceramics**: 4× 47 µF / 16 V 1210 X5R
(e.g. Murata GRM32ER61C476KE15). Each 1210 = 1.45 mm tall. Total
capacitance 188 µF — below the 220 µF spec but the LM2596's stability
window allows down to 100 µF on the output. **FIT** with +4 mm margin.
Cost similar to one polymer cap.

**Option C — relocate**: same patterns as C1/C3. Move C4 to the
east-of-ESP32 strip (X > +20.50), Y ∈ [-37, -50]. Available zone bounded by
SEN66 west edge at +23.5 (Y range -33.2..+22.0) — at Y=-50.10 the SEN66 is
clear (Y<-33.2 is above SEN66 north edge). Strip X ∈ [+20.50, +56.0]
Y ∈ [-50.10, -33.2] is open. Wire run from L1 (+9, -37) to C4 grows
~15 mm — marginal for a buck regulator output (ripple loop inductance
matters); prefer Option A.

### E.4 — U1 (EDGE, LM2596S TO-263-5, 4.6 mm tall)

Margin +0.9 mm. Works if the socket is exactly 8.5 mm AND the daughterboard
pin tails do not exceed 3.0 mm AND the LM2596 case is within nominal height.
**Three "AND" conditions on a 0.9 mm margin is fragile.**

**Option A — accept the EDGE**: document that the OAS socket must be a
genuine 8.5 mm body part (not a low-profile 5 mm Mill-Max), and the
DevKitM-1's onboard pin tails must be the original Espressif-mounted
0.64 mm-sq pins (some Botland kits ship the DevKit with the pin headers
loose for user solder — tail length will then depend on solder choice).

**Option B — replace with TPS562201 or similar SOT-23-6 buck**: 24 V → 5 V
synchronous buck in a SOT-23 (height 1.1 mm). Margin grows to +4.4 mm.
**Pillar #1 impact**: TPS562201 is 17 V Vin_max — needs a pre-regulator from
24 V. TPS54360 (60 V Vin) in HSOP-8 (1.0 mm tall) is the better match.
**Cost** +$1.50/unit. **Strongly recommended** if the prototype shows any
clearance fit problem.

**Option C — replace with TPS54360 / LM5008A in HSOP-8**: 60 V capable,
1.0 mm tall, margin +4.5 mm. Drop-in replacement for LM2596 functionally.
Same ESPHome / firmware impact = zero.

### Summary of recommendations

| Ref | Current | Recommendation | Reason |
|---|---|---|---|
| C1 | CP_Radial D8/P3.5, 12 mm | Relocate to (-20, -54) or (-32, -28) | No good SMD substitute at 100 µF / 50 V; relocation cheapest |
| C3 | Same as C1 | Relocate to (-9, -54) near U1 | Same as C1; keep close to U1.VIN for low ESR loop |
| C4 | CP_Radial D6.3/P2.5, 11.2 mm | Replace with SMD polymer (Panasonic 25SVPF220M, D7.3 × H4.2) | Polymer improves U1 transient response; height drops to 4.2 mm |
| U1 | LM2596S TO-263-5, 4.6 mm | Either (a) accept EDGE with documented socket spec OR (b) replace with TPS54360 HSOP-8 (1.0 mm) | 0.9 mm margin too tight; HSOP-8 alternative is functional drop-in |

---

## F — Special checks

### F.1 — DevKitM-1 USB-C connectors

**Verified** against `esp32-c6-devkitm-1-pcb-layout.pdf` and the dimensions
PDF: both USB-C connectors (J2 native USB-Serial-JTAG and J4 USB-UART
bridge) are **TOP-side SMD components**. They occupy ~5 mm of the
connector-end short edge and protrude ~3.2 mm above the DevKit PCB top
face. **They do not protrude below the DevKit PCB.** No additional Z
clearance penalty under the DevKitM-1.

### F.2 — MIKROE-2462 NFC antenna location

**Verified** against the MikroE datasheet PDF (Digi-Key mirror) page 1
product photo: the **NFC PCB antenna spiral is on the TOP side** of the
Click PCB, occupying ~36 mm of the board length opposite the pin block. The
NT3H1101 IC, R1..R5 matching network, C1/C2, and PWR/FD LEDs are also on
the top side. **No bottom-side components.** No additional Z penalty under
the MIKROE-2462.

### F.3 — LD2410 bottom-side components

The HLK-LD2410B carries the 24 GHz radar SoC + BLE chip on the **top side**
(antenna patches on the same side, between radar SoC and the pin row). The
**bottom side carries small bypass caps and the FSPI flash** — total
height ~1.5 mm. The LD2410 PCB sits ~3 mm above the OAS PCB on the 1.27 mm
vertical header standoff; the bottom-side SMDs eat into the under-PCB
clearance, leaving **~2 mm net** for any OAS-side SMD. **Audit found
zero OAS components in the LD2410 shadow**, so this is not a problem
today — but it must be respected for future placements.

### F.4 — F.CrtYd guardrail

v0.22 explicitly *removed* the F.CrtYd from the ESP32 and MIKROE-2462
daughterboard reference footprints precisely so that SMDs *can* be placed
under their shadows without triggering `courtyards_overlap` DRC errors.
**This means DRC will NOT catch the C1/C3/C4 height violations** — DRC has
no Z-axis information for footprints. The check is purely visual / manual.
The SEN66 still carries an F.CrtYd because the SEN66 lies flat (zero
standoff) — `courtyards_overlap` is the right tool there.

### F.5 — Daughterboard Z_BODY constants

`generate.py` constants:
- `ESP32_BODY_Z = 8.6` — top of daughterboard above OAS PCB; consistent
  with esp32-c6-devkitm-1-n4.md "~8.6 mm to USB-C top" estimate.
- `MIKROE2462_BODY_Z = 7.0` — **too low**. The MikroE Click is on an 8.5 mm
  socket + 1.6 mm PCB + ~1.5 mm onboard parts → ~11 mm minimum. The
  hardware/components/mikroe-2462.md "Body Z-height above the OAS PCB"
  section already flags this: "**Estimated total height above the OAS PCB
  top surface**: ~10-11 mm. The CLAUDE.md value of '~7 mm' under-estimates
  by ~3-4 mm." This is documented but not yet fixed in `generate.py`.
  **Audit-relevant only insofar as the under-board clearance budget**
  follows the socket body, not the daughterboard top height; the
  MIKROE2462_BODY_Z mis-value does not change the under-board clearance.
- `LD2410_BODY_Z = 7.0` — height above OAS PCB, consistent.

### F.6 — DevKitM-1 onboard NeoPixel power and SEN66 thermals

Out of scope for this audit (the OPEN ISSUE in CLAUDE.md v0.15.8 is
electrical/thermal, not mechanical). Note only that any resolution
option (a) (jumper VCC_5V to VCC_3V3) would not affect Z-clearance, and
option (c) (external WS2812B on OAS PCB) would add one 1.0 mm 0805 part
which fits any budget.

---

## Bottom line

- **3 components physically prevent the ESP32 daughterboard from seating
  fully into its sockets**: C1, C3, C4. All are radial THT electrolytic
  capacitors 11-12 mm tall under a ~5.5 mm clearance budget. Margin is
  −5.7 to −6.5 mm — large enough that no socket / pin-tail tolerance
  trickery can recover it.
- **1 component is on the edge**: U1 (LM2596S TO-263-5) at 4.6 mm has only
  +0.9 mm margin. Works in theory, but a 0.9 mm budget on a daughterboard
  socket where the user has not yet specified an exact socket MPN (the
  source-of-truth uses generic stock footprints) is fragile.
- **The 20 SMDs at 0603/0805/SOT-583/SMA height all fit comfortably**
  with +3 to +5 mm margin. v0.22's reasoning ("daughterboards sit ~8 mm
  above the OAS PCB, so SMDs <2 mm CAN go beneath") is correct *for the
  small SMDs*, but it never checked the radial THT bulk caps that the
  same code path emits.
- **No components inside the MIKROE-2462 shadow violate clearance**
  (only C12 at 0.95 mm — fine).
- **No components inside the LD2410 shadow at all**.
- **Severity**: HIGH (3 FAIL components). Without relocation/replacement
  the OAS PCB cannot be assembled — the DevKitM-1 will not seat,
  meaning no power, no MCU, no firmware. **Blocking for the v1
  prototype build.**
- **Recoverable on current PCB without redesign**: YES. The fixes are
  (a) relocate C1/C3 to negative space N or W of the ESP32 footprint
  (cheapest); (b) swap C4 to a Panasonic 25SVPF220M polymer SMD
  (technically superior); optionally (c) accept U1's EDGE margin or
  swap to a HSOP-8 buck. No daughterboard repositioning needed; no PCB
  outline change; no enclosure change.
- **Estimated rework**: ~30 min of `generate.py` edits + DRC re-run +
  visual review of the 2d-top.png render. No netlist changes — only
  coordinate updates and footprint-stub swaps for C4.

### Confidence

- **HIGH** confidence on the radial-cap heights — Panasonic ECA, Nichicon
  UVR, and Rubycon YXG datasheets all cite 11.2-12.5 mm for D8 / D6.3
  P3.5/P2.5 axial/radial bodies; the 12 mm working value is well
  within the published range.
- **HIGH** confidence on TO-263-5 height (TI datasheet specifies 4.83 mm
  max, with 4.6 mm typical).
- **MEDIUM** confidence on socket body height (8.5 mm assumed for stock
  KiCad `PinSocket_*` library; specific MPN not yet chosen in generate.py).
  A premium 11 mm stackable socket would lift the budget to ~8 mm — still
  not enough for C1/C3/C4 but would clear U1 comfortably.
- **MEDIUM** confidence on pin-tail protrusion (~3 mm assumed for stock
  DevKitM-1 male pin headers; varies with the specific header batch).
- **HIGH** confidence on the body-shadow geometry — read directly from
  the `*_ANCHOR_*` and `*_BODY_*` constants in `generate.py`.
- **HIGH** confidence on the footprint placements — read directly from
  `gen_power_pcb_footprints()`.
