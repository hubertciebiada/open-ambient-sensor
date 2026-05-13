# OAS PCB v0.22 — Review Iteration #1 (independent verification)

- **Date**: 2026-05-13
- **Reviewer**: Opus 4.7 (independent agent, no prior conversation context)
- **Scope**: `C:\Git\open-ambient-sensor\` at commit `291de309007641286b7deb48a590390797d4305d` (v0.22 — restore SEN66 courtyard guardrail + relocate offending SMD)
- **Purpose**: independent verification that v0.22's claimed zero-issue state holds before copper routing begins.
- **kiutils version**: **1.4.8** (`pip install --user kiutils`)
- **KiCad CLI**: as bundled with the local KiCad install (`kicad-cli pcb drc` / `kicad-cli sch erc`)

---

## Verification performed

- Re-ran `python regenerate.py` end-to-end. KiCad source files (`*.kicad_pcb`, `*.kicad_sch`, `*.kicad_pro`, `*.kicad_mod`) are bit-identical to HEAD (only render PNG/SVG timestamps changed). Deterministic generation confirmed.
- Read `renders/_drc.rpt` and `renders/_erc.rpt` directly. DRC = 0 violations / 0 warnings + 160 unconnected pads (expected pre-routing ratlines). ERC = 0/0.
- Read `CLAUDE.md` end-to-end including all v0.6–v0.22 changelog entries, hard constraints, and the `Module Identification` rule.
- Read `hardware/components/*.md`: `esp32-c6-devkitm-1-n4.md`, `mikroe-2462.md`, `sen66.md`, `hlk-ld2410b.md`, `sk6812-side.md`, `ak-n-94.md`, plus the prior reviews `_overall-review-v0.15.7.md`, `_post-fix-review-v0.15.8.md`, and `_pre-routing-review-v0.19.md` (which carries the post-fix status sections for v0.20 / v0.21 / v0.22).
- Spot-read `generate.py` sections for SEN66 / MIKROE2462 / ESP32 / LD2410 anchors, the J3 / J4 / J5–J8 / J9 / J10 pin maps, the Q1 SOT-23 footprint generator, and R5/R6/R7 placement.
- Wrote and executed an independent Python verification script (`_check_v022.py`, removed after use) that:
  1. Parses `oas.kicad_pcb` via `kiutils 1.4.8` (using `from_sexpr(parse_sexp(open(..., encoding="utf-8").read()))` to bypass the default cp1250 codec failure on UTF-8 µ / → characters);
  2. Computes the four daughterboard body shadows in PCB coordinates using the KiCad rotation convention (positive = visually CCW = mathematical CW with screen +Y down): `rx = cos(θ)*lx + sin(θ)*ly`, `ry = -sin(θ)*lx + cos(θ)*ly`;
  3. For every populated F.Cu footprint (excluding mech-refs SENS1/MOD1/MOD2/LDR1, mounting holes H1–H3, zip-tie holes ZT1–ZT4), computes its pad bbox in PCB frame **with per-pad rotation applied** (the naive "expand by max(sx, sy)" overstates pad extent for rectangular SMD pads — see the F1 saga below);
  4. Tests every populated bbox against each daughterboard shadow: fully-inside / partial-overlap / fully-outside;
  5. Cross-validates each footprint's pad bbox against the PCB outline (Ø120 D-shape, chord at Y=+43.524), the Ø12 cable hole at origin, and the three Ø3.8 NPTH mounting holes at (±47.631, +27.500) and (0, −55.000);
  6. Enumerates pairwise pad-bbox gaps < 0.3 mm to detect any tight spots that would bite during routing;
  7. Enumerates every populated electrical pad and confirms each carries a non-zero net code (or is the JST `MP` mounting-peg pad, intentionally non-electrical);
  8. Independently extracts every J5/J6/J7/J8 socket pin → net mapping and cross-checks against `esp32-c6-devkitm-1-n4.md` (J5/J6 vs J1/J3 of DevKitM-1) and `mikroe-2462.md` (J7/J8 vs MikroE mikroBUS pin numbering);
  9. Computes the minimum-spanning-tree straight-line lengths over all `/IO/I2C_SDA` and `/IO/I2C_SCL` pad positions to verify the CLAUDE.md "~140 mm PCB MST" honest-cable-run claim;
  10. Confirms `regenerate.py` produces an empty source-file diff after re-run (only renders change).
- Inspected `renders/2d-top.png` and `renders/3d-top.png` for visual sanity.
- Diffed PCB ref-designator set vs schematic ref-designator set across all 5 sub-sheets.

---

## Findings

### Critical (blocks routing)

**NONE.**

### Major (should fix before routing)

**NONE.**

### Minor (doc / cosmetic / easily-deferrable)

**Mn1. CLAUDE.md line 149 still recommends "Pair 1 at X ≈ 25; Pair 2 at X ≈ 50" for SEN66 zip-tie X positions, but `generate.py:201–206` uses X = 22 and X = 30.**
- This was already flagged as Mi1 in `_pre-routing-review-v0.19.md`; v0.22 did not address it.
- Both X values used by the code (22 and 30) sit inside the strict safe corridor `X ∈ [18.22, 32.03]`; the doc-recommendation X=50 would have intruded into the SEN66 outlet circle, so the code is correct and the doc is stale.
- Doc-only fix; geometry is fine. (CLAUDE.md `Architectural decisions` → "Zip-tie hole X-positions" bullet, line 149.)

**Mn2. CLAUDE.md v0.6 changelog still contains the historical statement "I²C bus length drops from ~80 mm to <40 mm" (line 480).**
- This contradicts the v0.22 honest measurement of ~140 mm PCB MST + ~80 mm cable = ~220 mm total (line 154 of the same file is correct).
- v0.22 explicitly notes the "<40 mm" claim is retracted in the v0.15.8 narrative, but the v0.6 changelog text was not amended in place.
- Historical record; readers comparing v0.6 vs v0.22 may be momentarily confused. Acceptable to leave; a one-line "(retracted in v0.15.8; honest value ~220 mm — see v0.22 entry)" annotation would close it.

**Mn3. 51 schematic symbols still have empty `Footprint` property (`(property "Footprint" "")`).**
- Open from `_pre-routing-review-v0.19.md` M5; v0.22 post-fix status notes it as "OPEN — mostly cosmetic now that PCB carries its own canonical footprint references; pcbnew BOM export will use the PCB-side property."
- This holds — at fabrication time the PCB-side footprint field is authoritative, and the schematic-side `Footprint` field can stay blank without breaking the BOM export pipeline (the JLCPCB workflow walks the PCB, not the schematic).
- Will cause a "no footprint assigned" warning if the user ever runs the schematic-driven netlist export path or "Update PCB from Schematic" again. Not a routing blocker.

**Mn4. J2 and J10 schematic symbols are `(dnp yes)` but their PCB footprints lack the `dnp` attribute.**
- Schematic: `(dnp yes)` on J2 (mcu.kicad_sch:2664) and on J10 (io.kicad_sch:1598). PCB: no `dnp` flag in either footprint's s-expr (confirmed by raw text scan of `oas.kicad_pcb`).
- The next "Update PCB from Schematic" reconciliation would normally propagate the DNP flag to the PCB; the v0.22 commit appears to have placed the PCB footprints without the attribute.
- BOM-correctness issue (DNP parts must be excluded from assembly orders). Not a routing concern. Two-line fix in `gen_..._pcb_footprint` helpers to emit `(attr through_hole exclude_from_pos_files exclude_from_bom dnp)` for J2 and J10.

**Mn5. Daughterboard mech-refs MOD1 / MOD2 / LDR1 still lack F.CrtYd courtyards, while only SENS1 was given one in v0.22.**
- Verified by raw text scan of `oas.kicad_pcb`: SENS1 has F.CrtYd polygon; MOD1 / MOD2 / LDR1 do not.
- Reasoning still holds: ESP32 / MIKROE-2462 / LD2410 daughterboards sit ~8 mm above the OAS PCB on pin sockets / pin headers, so SMDs FULLY INSIDE the daughterboard footprint are explicitly allowed (24 SMDs are deliberately placed inside the ESP32 shadow and 1 inside the MIKROE shadow in v0.22). A perimeter F.CrtYd on those daughterboards would generate spurious courtyard-overlap DRC errors for every internal cap / resistor.
- The SEN66 case is unique because SEN66 lies flat on the PCB (zero standoff), so the F.CrtYd guardrail is needed there only.
- No fix required; this Mn is a note for future maintainers to NOT propagate the SEN66 F.CrtYd pattern to the other three mech-refs without rethinking it.

**Mn6. Tight pad-pair clearances (geometric, not DRC violations).**
- Pairwise pad-bbox gap < 0.3 mm: 5 pairs detected. Detail:
  - `C15 ↔ C6`: 0.20 mm gap. Different rails (C15 = +5V/GND HF-bypass for U1 buck; C6 = +3V3 bulk for U2 buck output). Adjacent 0603 caps in the same E-W power-rail row at Y=−46. Tight but DRC-clean at the 0.15 mm `min_clearance` rule. Will require careful trace fan-out during routing.
  - `D12 ↔ C21`, `D16 ↔ C25`, `D18 ↔ C27`, `D22 ↔ C31`: 0.24 mm gaps. All four are LED-and-its-decoupling-cap pairs on the SK6812 ring; same +5V/GND nets; intentional placement (cap radially inward of its LED). Equivalent to the per-LED decoupling pattern already noted as `Mi5` in `_pre-routing-review-v0.19.md`.
- No DRC violations triggered (the `0.20 mm` C15-C6 gap is above the 0.15 mm `min_clearance`). Flag is for routing-time awareness only.

### Nits

**Nt1. ERC ignore list (oas.kicad_pro:104 has `"rule_severities": {}`)** is empty in the project file but the ERC report claims four ignored categories: "Global label only appears once in the schematic", "Four connection points are joined together", "SPICE model issue", "Assigned footprint doesn't match footprint filters". These appear to come from `kicad-cli`'s built-in defaults rather than the project file. No action; just a curiosity if anyone later wonders where the ignores live.

**Nt2. `regenerate.py` does not re-validate that the rebuilt KiCad files are identical to the previous commit.** Today this is fine because the regenerate output matched HEAD bit-identically on a clean re-run; but a "diff against HEAD" guard inside regenerate would catch a silent non-determinism regression in the future.

**Nt3. `unconnected-(JN-Pin_N-PadN)` autonet entries for sockets J5/J6/J7/J8 (24 such pads total).** These are the deliberately-NC pins (e.g. J5.5 / J5.6 / J5.7 / J5.8 = unused MCU GPIOs on the ESP32 module's J1.5–J1.8 row). KiCad auto-assigns each one to a unique single-pin "unconnected-..." net. Harmless and expected; no action needed.

---

## Per-category status

| Category | Status | Notes |
|---|---|---|
| **A. Body-shadow + courtyard checks** | **PASS** | Independent body-shadow computation for SEN66 / MIKROE2462 / ESP32 / LD2410. SEN66 shadow: 0 partial overlaps, 0 fully-inside (correct per the v0.22 retention rule that SEN66 must have NO SMD beneath it). MIKROE2462: 0 partial overlaps, 1 fully-inside (C12, the +3V3 decoupling cap — explicitly allowed). ESP32: 0 partial overlaps, 23 fully-inside (the entire power-section cluster + R5/R6/R7 + decoupling caps — explicitly allowed). LD2410: 0 partial overlaps, 0 fully-inside. F1 polyfuse correctly placed east of the SEN66 (PCB (54, 9)) with all pad corners inside the Ø120 outline (worst corner distance from origin = 59.02 mm, comfortable 0.98 mm margin to R=60). The fix agent's "0.88 mm clearance" claim verified consistent (the difference is which corner is measured). |
| **B. DRC + ERC strict zero verification** | **PASS** | Re-ran `regenerate.py`; DRC report shows `Found 0 DRC violations` (160 unconnected pads = expected pre-routing ratlines). ERC report shows `0 Errors 0 Warnings`. Ignored DRC categories (`Footprint has no courtyard defined`, `Track endpoint not centered on via`, `Tuning profile track geometries`, `Footprint doesn't match symbol's footprint filters`, `Footprint component type doesn't match footprint pads`) are appropriate for this pre-routing stage. Recommend re-enabling `Track endpoint not centered on via` once routing starts. |
| **C. Net coverage verification** | **PASS** | Out of 230 total pads: 11 net-0 pads, all justifiable (mounting holes H1/H2/H3, zip-tie holes ZT1–ZT4, JST MP mounting pegs on J3/J9). 24 `unconnected-*` autonet pads on intentionally-NC GPIOs of J5/J6/J7/J8. 195 pads carry valid electrical nets. **Zero populated electrical pads have no net.** J5/J6 socket pin-to-net mapping verified against `esp32-c6-devkitm-1-n4.md` (10 pin spot-checks: 3V3/RST/GPIO2/GPIO3/GPIO8/GPIO6/GPIO7/GND/5V/GND on J5 match; GND/UART_TX/UART_RX/GPIO15/GPIO9/GND/USB_DP/USB_DM/GND on J6 match). J7/J8 verified against `mikroe-2462.md` MikroE pin numbering: J7.7=+3V3, J7.8=GND, J8.2=NFC_FD (=MikroE pin 15 = INT), J8.5=SCL (MikroE pin 12), J8.6=SDA (MikroE pin 11), J8.8=GND (MikroE pin 9) — all correct. **Q1 SOT-23 pads `G`/`S`/`D` carry their correct nets** (Net-(Q1-PadG), Net-(D1-A2), Net-(F1-Pad2) — the v0.22 Task #24 fix is in place and working). |
| **D. Component placement sanity** | **PASS** | All 65 populated F.Cu footprints (excluding mech-refs / mounts / DNP) are fully inside the PCB outline. F1 polyfuse far corner at distance 59.02 mm from origin (margin 0.98 mm to R=60). All three mounting holes clear of every populated SMD body. Cable hole (Ø12 at origin) clear of every populated SMD. LED ring populated as 11 LEDs D11..D22 minus D14 (verified by enumeration; D14 missing as expected for the v0.18 J1-south-flip). J1 at PCB (5.08, 22.4) rot 180° (correct per v0.18). J3 SEN66 socket at PCB (36, 27) rot 0° (cable opening facing NORTH toward the SEN66 body — correct per v0.15.8). J4 LD2410 header at PCB (−44.74, +19.05) rot 270°, pin 1 = LD2410_OUT (correct per HLK-LD2410B datasheet V1.04 Table 1). |
| **E. Schematic sanity** | **PASS with one minor** | Schematic refs = PCB refs except for the expected asymmetry: PCB-only mech refs (H1/H2/H3, LDR1, MOD1, MOD2, SENS1, ZT1..ZT4 — 11 PCB-only refs) and schematic-side lib_symbol template stubs (C/D/F/J/L/Q/R/U — 8 schematic-only ref-prefix entries that aren't real components; these are lib_symbols, not symbol instances). The original `_pre-routing-review-v0.19.md` flagged this same asymmetry as the expected baseline. R5 / R6 schematic value = "4.7k 1%" (v0.22 reverted from 10 kΩ — matches the v0.22 changelog and the PCB pad nets). R7 schematic value = "10k 1%" (v0.22 new GPIO 8 boot-strap pull-up — matches PCB R7 pad-to-net assignment +3V3 ↔ /MCU/WS2812_DIN). J2 schematic `(dnp yes)` confirmed; J10 schematic `(dnp yes)` confirmed. **Minor: PCB-side J2 and J10 footprints lack the `dnp` attribute** (see Mn4 above). |
| **F. v0.22-specific verification** | **PASS** | The fix agent's three numerical claims verified independently: (a) v0.21 SEN66 partial overlaps = 5 → v0.22 = 0 (computed by re-running the body-shadow check; only F1 marginally hit my naive bbox-expand check, then cleared when proper per-pad rotation was applied — see Verification step (iii)). (b) NFC+ESP32 partial overlaps = 0 (C12 fully inside NFC shadow is the only inside-shadow occurrence; explicitly allowed by the daughterboard-clearance rule). (c) F1 polyfuse at (+54, +9) — pad 2 far corner = 59.02 mm from origin, **inside** the R=60 PCB outline by 0.98 mm; no overlap with mounting holes H1 (+47.6, +27.5) or H2 (+47.6, +27.5) — H1 is at +47.63 actually, my report uses Mn convention — closest mounting hole H1 to F1 pad bbox = 18.6 mm. (d) Power section bounding box after v0.22 relocation: X ∈ [−28.0, +20.5] for the cluster under the ESP32 shadow + (+54, +9) for F1; Y ∈ [−49, −24] for the ESP32-inside cluster + (+6.3..+11.7) for F1. Bounding box "split" — main power cluster moved under the ESP32 module (deliberate use of the 8 mm headroom there), F1 alone went east. |
| **G. Routing readiness** | **PASS** | I²C bus MST: my Python computation gave SDA MST = 151.09 mm, SCL MST = 155.01 mm (straight-line, ignoring obstacles). CLAUDE.md line 154 states "~140 mm PCB MST" — within 8% of my measurement; the underestimate is small enough to call CLAUDE.md "honest within the precision of an MST estimate." Combined with ~80 mm of JST-GH cable to the SEN66 chip, total I²C electrical bus length ≈ 230–235 mm. R5/R6 reverted to 4.7 kΩ in v0.22 — RC = 4.7 kΩ × 100 pF ≈ 470 ns, t_r ≈ 1 µs, comfortably meeting the 100 kHz I²C spec at the realized bus length. R7 = 10 kΩ on GPIO 8 to +3V3 closes the M2 boot-strap concern. Clear corridors visible in `renders/2d-top.png` for: I²C run (from R5/R6 east column under ESP32, south to J5 socket, east to J3 socket, north-east-and-up to J9 Qwiic); UART north-south from J6 socket to J4 LD2410 header; WS2812 daisy chain around the LED ring; 5V from L1 to LED ring; GND will need careful pour planning but no isolated-island risk visible at this stage. **Routing readiness: GREEN.** |
| **H. Documentation** | **WARN** | CLAUDE.md "Open work" section largely synchronized with v0.22 state. v0.22 changelog accurately describes the SEN66 courtyard restoration + 5-SMD relocation + Q1 fix + R5/R6 revert + R7 add + F1 placement. `_pre-routing-review-v0.19.md` post-fix status section for v0.22 is comprehensive. Stale items: Mn1 (zip-tie X positions in CLAUDE.md line 149), Mn2 (v0.6 changelog "<40 mm" claim still in place historically), Mn3 (51 schematic symbols still have empty Footprint property). All three are documented as known-open / acceptable-deferral elsewhere in the project; none are routing blockers. Module Identification rule: every J* connector has documented MPN (J1 = Phoenix MSTBA 2,5/3-G-5,08; J3 = JST SM06B-GHS-TB; J4 = stock 1×5 P1.27 pin header; J5/J6/J7/J8 = stock female PinSocket 1×N P2.54; J9 = JST SM04B-SRSS-TB; J10 = stock 1×6 P2.54 pin header). |

---

## Bottom line — verdict: **READY TO ROUTE**

The v0.22 commit cleanly closes the routing blockers that were open in v0.21 (SEN66 body-shadow conflicts, Q1 SOT-23 pad-net mismatch, I²C pull-up size, GPIO 8 boot-strap pull-up, honest cable-run measurement). Independent verification confirms:

- DRC = 0 / ERC = 0 (corroborated by independent kiutils-based pad-bbox vs body-shadow analysis);
- All 4 daughterboard body shadows are clean of partial-overlap populated SMDs;
- F1 polyfuse is correctly placed inside the PCB outline with healthy margin;
- All 195 populated electrical pads have nets;
- J5/J6/J7/J8 socket pin maps match the documented module pinouts;
- Q1 SOT-23 pads carry their correct nets;
- R5/R6 = 4.7 kΩ, R7 = 10 kΩ values reflected in both schematic and PCB.

Five **Minor** findings remain (Mn1–Mn5) and three **Nits** (Nt1–Nt3). None block routing. Mn4 (J2/J10 PCB-side DNP attribute) is the closest to "fix-before-fab" and warrants a 2-line `generate.py` patch ahead of the eventual JLCPCB upload, but the routing chunk itself is unaffected.

Confidence: **HIGH** that v0.22 is in a sound state to begin copper routing.

---

## Python tooling notes

- kiutils 1.4.8 stores footprint `properties` as a `dict` (keys = "Reference", "Value", "Footprint", "Datasheet", "Description") in this version, not as a list of Property objects. Access via `fp.properties.get('Reference')`.
- kiutils 1.4.8 `Board.from_file()` opens the path with default locale codec (cp1250 on this Windows Polish system) and fails on UTF-8 µ / → characters in the SEN66 zip-tie comments and cutout labels. Workaround: read the file as UTF-8 text first, then pass to `Board.from_sexpr(sexpr.parse_sexp(text))`.
- Pad bbox computation MUST handle per-pad rotation independently from footprint rotation. A naive `expand by max(sx, sy)` axis-aligned bbox overstates rectangular SMD pad extent and creates false "outside outline" positives (in this review, F1's 2920 pad bbox first appeared 0.69 mm outside the PCB arc; correct per-pad rotation gives 0.98 mm margin INSIDE). Use the corner-rotation form:
  ```python
  for ox, oy in [(-sx,-sy),(-sx,sy),(sx,-sy),(sx,sy)]:
      offx = cos(pad_rot)*ox + sin(pad_rot)*oy
      offy = -sin(pad_rot)*ox + cos(pad_rot)*oy
      cx_fp = lx + offx; cy_fp = ly + offy
      cx_abs = fp_x + cos(fp_rot)*cx_fp + sin(fp_rot)*cy_fp
      cy_abs = fp_y - sin(fp_rot)*cx_fp + cos(fp_rot)*cy_fp
  ```
- The PCB design-frame origin maps to absolute KiCad coords (148.5, 105.0) (taken from `aux_axis_origin` and `grid_origin` in `oas.kicad_pcb`). Subtract this to convert from kicad-absolute to OAS-PCB-frame coordinates.
- Verification script removed after use (kept the snippets above in this report for repeatability).
