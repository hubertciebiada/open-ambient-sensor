# OAS pre-fab audit — 30-agent read-only swarm

**Date**: 2026-05-14
**Repo state**: v0.35, commit `2472aeb` on `main`
**Scope**: pin-by-pin verification of every component + cross-cutting checks against published datasheets BEFORE sending board to JLCPCB
**Method**: 30 specialized read-only `feature-dev:code-reviewer` agents, each auditing one component group. Tool set physically excluded Edit/Write. Every claim cited (datasheet section / file:line / PCB pad coordinate).

## Result summary

| Severity | Count | Status |
|---|---|---|
| **CRITICAL — block fab** | **4** | board WILL FAIL if shipped as-is |
| **IMPORTANT — should fix** | **10** | functional issues / assembler risks |
| Warnings (informational) | ~15 | non-blocking, mostly documentation |
| PASS (no concerns) | majority of audits | wiring/footprint/pinout correct |

**VERDICT: DO NOT SEND TO JLCPCB. Four critical issues must be fixed first.**

---

## 🚨 CRITICAL — board WILL fail if shipped

These four issues mean the assembled board either won't work, will destroy components, or won't provide its protection function.

### CRITICAL-1 — D1 SMBJ24A TVS wired BACKWARDS (Audit #15)

**Severity**: surge protection fully disabled.

KiCad `Diode_SMD:D_SMB` footprint convention: **pad 1 = cathode**. In `oas.kicad_pcb`:
- D1 pad 1 (cathode) → net 16 `GND`
- D1 pad 2 (anode) → net 17 `Net-(D1-A2)` = +24V input

For a unidirectional TVS protecting a positive supply rail, cathode MUST be on +24V and anode on GND. As emitted, D1 is reverse-biased in normal operation, draws only µA leakage, and **provides zero clamping during a surge**. The entire protection chain (D1 → Q1 → F1) has no TVS function.

**Mechanism**: `Device:D_TVS` schematic symbol has two "A1/A2" pins (bidirectional naming convention). Pin 1 (lib at (-3.81, 0)) maps to the GND wire on the schematic, pin 2 (lib at (+3.81, 0)) maps to the +24V wire. KiCad's `sync_pcb_nets_from_schematic` then writes pad 1 = GND on the PCB. But the D_SMB footprint expects pad 1 = cathode.

**Fix**: in `generate.py` `gen_power_sch()`, swap the D1 wire connections so pin 1 (A1) goes to VIN and pin 2 (A2) goes to GND. Alternatively rotate the PCB footprint 180°. Then re-run regenerate.py + export_production.py + preflight_gerbers.py.

**Files**: `generate.py` lines 10056, 4772-4776 (D1 emitters); `oas.kicad_pcb` D1 pad nets; CLAUDE.md v0.2 changelog entry.

### CRITICAL-2 — TPS62933 feedback divider mismatch between schematic and PCB-generator (Audit #12, #24)

**Severity**: BOM-as-built may produce 4.34 V on the 3.3 V rail. **This destroys ESP32-C6 and SEN66** (both have Vdd_abs_max = 3.6 V).

**Root cause — Vref**: TPS62933 Vref = **0.8 V** (per TI datasheet + LCSC listing line 24 "800mV-22V output adjustable"). Project comments in `generate.py` (lines 11833, 11855, 11960, 11982-11986) and `lcsc-mapping.csv` line 15 use **0.6 V**. The schematic divider was designed for the wrong Vref.

**Component-by-component**:

| Resistor | Schematic value | PCB generator value | LCSC BOM lists | Correct for Vout=3.3V at Vref=0.8V |
|---|---|---|---|---|
| R2 | 44.2 k | **100 k** | 44.2 k | needs ~100 k |
| R3 | 10 k | **30.9 k** | 10 k | needs ~31.6 k |

**With schematic values + correct Vref**: Vout = 0.8 × (1 + 44.2/10) = **4.34 V** → destroys downstream ICs.
**With PCB-generator values + correct Vref**: Vout = 0.8 × (1 + 100/30.9) = **3.39 V** → within ±5% of 3.3 V (acceptable).

**The schematic and PCB-generator disagree**. Whichever BOM the user uploads to JLCPCB determines what gets soldered. If they upload `oas-bom.csv` (which inherits values from `kicad-cli sch export bom` → schematic values), JLCPCB ships R2=44.2k + R3=10k → board death.

**Fix**: in `generate.py`, update schematic R2 to "100k 1%", R3 to "30.9k 1%" (or similar E96 pair correct for Vref=0.8V). Update `lcsc-mapping.csv` R2 entry (currently flagged but wrong value). Re-run regenerate.py + export_production.py. Cross-check that the new BOM matches.

**Files**: `generate.py` line 4962 (PCB R2=100k), 4968 (PCB R3=30.9k); `power.kicad_sch` line 6776 (sch R2=44.2k), 6846 (sch R3=10k); `lcsc-mapping.csv` line 15 (wrong Vref note); TI datasheet https://www.ti.com/lit/ds/symlink/tps62933.pdf §"Electrical Characteristics".

### CRITICAL-3 — C7/C8 roles and values swapped between schematic and PCB-generator (Audit #12, #23)

**Severity**: TPS62933 won't start, OR soft-start time wrong.

| Cap | Schematic value | PCB generator value | LCSC BOM note | Role per TPS62933 datasheet |
|---|---|---|---|---|
| C7 | 100 nF | **22 pF** ("FB feedforward") | 100 nF labeled "C7 + C10..C17 decoupling" | should be BST bootstrap (100 nF) |
| C8 | 47 nF | **100 nF** ("BST bootstrap") | 47 nF labeled "C8 buck-2 BOOT cap" | should be SS soft-start (47 nF) |

**Three-way contradiction**: schematic, PCB-generator, and LCSC BOM each name different components.

If JLCPCB ships C7=22 pF on the BST pin: high-side gate driver supply severely undersized, converter **won't start**.
If C8=100 nF on SS pin: soft-start time ~12 ms (vs spec 2-10 ms for SEN66 power ramp).
If BOM ordered from schematic: C7=100 nF goes to BST (correct), C8=47 nF to SS (correct) — **but then there is no 22 pF cap anywhere for the FB feedforward function** the PCB-generator description claims is needed.

**Resolution required**: decide if a 22 pF FB feedforward cap is needed at all (TPS62933 datasheet does not require one for default operation). If no — align PCB-generator to match schematic (C7=100 nF BST, C8=47 nF SS). If yes — add 22 pF to BOM as separate part, rename C7/C8 to unambiguous designators.

**Files**: `generate.py` lines 5055-5063 (PCB BOM annotations); `power.kicad_sch` lines 6636, 6706 (schematic values); inline comments lines 11847-11850 mismatch the placement code.

### CRITICAL-4 — Q1 PMV65XP Vds_max insufficient for TVS clamp (Audit #13)

**Severity**: Q1 may pop during a TVS clamp event.

PMV65XP datasheet (Nexperia, Farnell, TME confirm): **Vds_max = −20 V, Vgs_max = ±12 V**. The `generate.py` line 4803 description string says "Vds=-50 V / Vgs=±20 V" — both wrong. `lcsc-mapping.csv` line 19 correctly flags Vds=-20V but quotes Vgs_max=±20V (also wrong, actual ±12V).

**Worst case Vds during a TVS clamp event** (SMBJ24A clamps at Vc=38.9 V): Q1.D = 38.9 V (raw input clamped by D1), Q1.S ≈ 0 V if downstream bulk caps discharged. Vds = -38.9 V → **exceeds -20 V Vds_max by 19 V**.

Steady-state Vds is fine (FET conducting, Vds ≈ 0). The risk is only during a surge event. For continuous indoor 24V SELV operation this is unlikely to fire — but the protection circuit's purpose is to survive surges.

**Steady-state Vgs concern (Audit #17 corroborates)**: D3 Zener clamps Vgs at -18 V (R1 100k pulls gate toward GND through R4). With Vgs_max=±12 V (not ±20), -18V Vgs **also exceeds** Q1's gate-source rating. D3 conducts continuously at ~108 mW (close to its 200 mW SOD-323 rating).

**Fix options** (in order of effort):
1. **Drop-in substitute AO3401A** (LCSC C15127, same SOT-23 footprint, Vds=-30V, Vgs=±20V). Solves Vgs issue, gives 8.9V Vds margin (tight but better). Cheapest fix.
2. **Switch to DMP4015SK3** (Vds=-40V, Vgs=±20V) — but TO-252 package needs footprint change + PCB respin.
3. **Add Vgs clamp Zener with lower Vz** (e.g. 10V) so Vgs ≤ -10V → within ±12V — protects PMV65XP gate but does nothing for Vds.

**Files**: `generate.py` line 4803 (wrong descr); `lcsc-mapping.csv` line 19; Nexperia PMV65XP datasheet https://assets.nexperia.com/documents/data-sheet/PMV65XP.pdf.

---

## ⚠️ IMPORTANT — should fix before fab

These are functional issues, assembler risks, or BOM inconsistencies that won't necessarily kill the board but reduce reliability or yield.

### I1 — No polarity markers on F.SilkS for D1/D2/D3/C1/C3/C4 (Audits #15, #16, #17, #20, #21)

The custom footprint generators (`_emit_two_pad_smd_footprint`, `gen_diode_sma/_smb/_sod323`, `gen_capacitor_polarized_radial`) emit only an F.Fab body outline. They do **NOT** draw a cathode bar (for diodes) or "+" cross-hair (for radial electrolytics) on F.SilkS.

Stock KiCad footprints include these by default. The custom generators silently omit them.

**Assembly risk**:
- Hand-assembler installing C1/C3/C4 (radial electrolytics on 24V rail) backwards → **electrolytic vents/fires under reverse bias**.
- D1/D2/D3 backwards → no protection function (D1 - audit #15 is this exact failure) or short circuit (D2 freewheel would short SW to +5V if reversed).

**Fix**: add `fp_line` cathode bars on F.SilkS to diode emitters; add `fp_arc` polarity stripes to radial electrolytic emitter. Or replace custom emitters with `_emit_stock_lib_footprint()` (pattern already in use for J1/J3/J4/J9).

### I2 — J10 pad 6 (BOOT) sits 0.70 mm outside cutout C3 (Audit #9)

J10 anchor at PCB (+9.4, +41.0), rotation 180°, pin pitch 2.54 mm → pad 6 at PCB Y=+28.30. Cutout C3 north wall at Y=+28.998. Difference: 0.70 mm.

**Effect**: pogopin jig accessing J10 from outside the case **cannot reach BOOT pad**. BOOT only matters during emergency reflashing (case open), so use case is preserved. But the v0.19 CLAUDE.md description claimed "pad 1 at Y=+41.0, pad 6 at Y=+25.78" — the current Y=+28.30 indicates the position was shifted later without doc update.

**Fix**: relocate J10 south by 0.7+ mm so pad 6 sits inside C3, OR document explicitly that BOOT requires case-open access (already the case).

### I3 — J2 schematic has `(dnp yes)` but `(in_bom yes)` (Audit #10)

`mcu.kicad_sch` line 2662: `(in_bom yes)`. Line 2664: `(dnp yes)`. KiCad's BOM export from the schematic reads `in_bom`, not `dnp`. PCB-side `exclude_from_bom` correctly hides J2 from `oas-top-pos.csv` / `oas-bom.csv`, but a schematic-BOM export would include J2.

**Fix**: in `generate.py`'s J2 instantiation, pass `in_bom=False` so the schematic carries `(in_bom no)`.

### I4 — Power rails (+24V, +5V, +3V3) routed at 0.25 mm instead of designed 0.5/0.4 mm (Audit #29)

`_NET_TRACK_WIDTH` declares 0.5 mm for +24V/+5V and 0.4 mm for +3V3. But Freerouting was invoked without per-net width constraints, so `oas_routes.py` carries every segment at 0.25 mm.

**Effect at OAS realistic load**:
- +5V at 500 mA peak through 0.25 mm: ~8 K rise (within 10 K design margin, but at design floor)
- +24V/+3V3 currents are lower; 0.25 mm is fine

**Fix**: assign +24V / +5V / +3V3 / Net-(D2-K) / Net-(U2-SW) to the Power netclass via `netclass_patterns` in `gen_pro()`, then re-run Freerouting OR manually widen those segments in `oas_routes.py`. The 0.25 mm fallback is acceptable for the v1 prototype but should be fixed for production.

### I5 — Duplicate routing on Net-(U2-SW) (TPS62933 switch node) (Audit #29)

`_route_local_decoupling` emits a hand-coded 0.4 mm direct U2.5→L2.2 segment. `oas_routes.py` ALSO carries 9 Freerouting segments at 0.25 mm with multi-bend path for the same net. Both are injected into `oas.kicad_pcb`.

**Effect**: two parallel paths on switch node. The longer 16 mm Freerouting path adds EMI radiation area unnecessarily.

**Fix**: remove Net-(U2-SW) segments from `oas_routes.py` and let the hand-coded direct route handle it.

### I6 — F1 polyfuse custom footprint pad pitch wrong (Audit #14)

Custom 2920 footprint uses pad pitch 5.7 mm vs KiCad stock `Fuse:Fuse_2920_7451Metric` which uses 6.775 mm (centers at ±3.3875 mm). IPC-7351 land pattern for 2920 expects outer pad edge ~4.4 mm from center; custom emits 3.85 mm.

**Effect**: pads sit ~0.175 mm outside the Littelfuse 2920L075/60MR body (7.35 mm long), creating sub-optimal solder fillets at the body-pad interface. Cosmetic + small dewetting risk during reflow. Not a functional failure.

**Fix**: switch F1 to `_emit_stock_lib_footprint("Fuse:Fuse_2920_7451Metric")` pattern (same approach as J1/J3/J4/J9).

### I7 — D3 schematic value text says "500mW" but BZT52C18S is 200mW (Audit #17)

`power.kicad_sch` line 3589: `(property "Value" "18V Zener 500mW")`. BZT52C18S in SOD-323 is rated **200 mW** (Farnell, evelta confirm; lcsc-mapping.csv flags this).

**Effect**: BOM exported from schematic shows wrong rating. JLCPCB smart-match could substitute a 500 mW SOD-123 part (wrong footprint). Steady-state Pz = 108 mW vs 200 mW rating gives 1.85× margin — OK if the right part is ordered.

**Fix**: update `generate.py` D3 emit to value="18V Zener 200mW".

### I8 — L1 Isat margin only 50 mA at full OAS load (Audit #18)

CKCS5040-33uH/M (LCSC C354612): Irms=1.2 A, Isat=1.3 A. At full OAS load (~850 mA + 400 mA ripple half-swing): peak inductor current = 1.25 A — only 50 mA margin to Isat.

**Effect under SEN66 fan burst (350 mA peak) + warm LED ring (120 mA) + LD2410 startup**: brief peak may exceed Isat → inductor saturates → high di/dt pulse stresses U1 and D2. Acceptable for prototype with typical breathing-animation LEDs; risky for production with sustained full-white LED ring.

**Fix for production**: substitute Bourns SRR1260-330M (LCSC C840528, 3 A, 33 µH, 12×12 mm body) + change footprint to `L_1260_12x12Metric`. Not blocking for 5-unit prototype.

### I9 — USB D+/D− not routed as differential pair (Audit #30)

USB_DM at X=22.5, USB_DP at X=18.5 → 4 mm spacing (vs ≤0.5 mm for proper 90 Ω diff pair). Length mismatch ~8 mm (vs ≤5 mm tolerance). Asymmetric via count (DM: 2 vias, DP: 1).

**Effect**: cannot certify as USB 2.0 compliant routing. At 12 Mbps Full-Speed over short trace it physically works but with no differential noise rejection.

**Acceptable for**: J10 is DNP emergency recovery header only used with case open + USB cable to PC. Not for continuous data.

**Fix (for production)**: re-route as proper diff pair, OR document that J10 is recovery-only.

### I10 — Single "+24V" net name spans raw input AND protected rail (Audit #11)

KiCad PCB net table shows ONE net 3 "+24V" connecting J1 pin 1 (raw, unprotected), Q1 source/drain, F1 input/output, C1/C3/C13, and U1.VIN. There is no separate net named `V_24V_PROT` despite CLAUDE.md v0.2 stating the topology that way.

**Effect**: electrically correct (Q1 + F1 are series elements in normal operation). But a future ERC/DRC custom rule cannot verify "U1.VIN is downstream of Q1" because there's no distinct net name.

**Fix (cosmetic)**: split into `+24V_UNPROT` (J1.1 → D1.cathode → Q1.D) and `+24V_PROT` (Q1.S → F1 → U1.VIN). Or accept the naming.

---

## Warnings (informational, non-blocking)

| Audit | Item | File |
|---|---|---|
| #1 | sen66.md stale text says "<40mm bus length" — actual ~220mm (v0.22 retraction) | hardware/components/sen66.md line 154 |
| #2 | hlk-ld2410b.md still describes OLD reversed J4 pinout as current — fix in code, doc not updated | hardware/components/hlk-ld2410b.md lines 145-188 |
| #2 | J4 PCB descr property has stale "VCC/GND/TX/RX/OUT" wording (old order) | oas.kicad_pcb line 1314 |
| #4 | BOOT hier label has `(shape output)` annotation — should be input, but KiCad ignores | mcu.kicad_sch line 1783 |
| #5 | C12 NFC decoupling at 11 mm from J7.7 — > 5 mm guideline but no electrical issue | generate.py lines 5107-5112 |
| #6 | mikroBUS pin numbering convention conflict (Zephyr vs MikroE) — docs only, wiring correct | hardware/components/mikroe-2462.md lines 155, 176-195 |
| #7 | CLAUDE.md v0.2 says F1 between J1 and D1; actually F1 is downstream of Q1. F1 placement description error | CLAUDE.md v0.2 |
| #7 | Phoenix Contact 1757255 pin-1 physical marking unverifiable from web (datasheet PDF returned 403) | — verify on physical part |
| #8 | J9 schematic Datasheet property empty (only Footprint backfilled per v0.23 Mn3) | io.kicad_sch line 1552 |
| #11 | C4 220µF aluminum ESR likely above LM2596 preferred 50 mΩ upper bound (~100-200 mΩ typical) | generate.py line 11498-11500 |
| #16 | SS14 1A rating thin under worst-case 11-LED full-white + sensor load (~980 mA) | lcsc-mapping.csv SS14 entry |
| #17 | D3 conducts continuously at 108 mW DC (not just transient on R1 failure) — within rating but adds ~54°C self-heating | power.kicad_sch + audit #17 thermal calculation |
| #19 | gen_sot583_pcb_footprint docstring wrong pin map (says pin 1=SW, actual pin 1=RT) — comment only | generate.py line 4202 |
| #20 | C1/C3 50V/24V derating = 1.28× (below preferred 1.5× rule of thumb, above 1.2× minimum) | v0.2 acknowledges |
| #21 | C4 10V/5V derating = 2× (at TI's floor; 16V or 25V part would give better aging margin) | generate.py line 11499 |
| #22 | C2 substituted X7R for Y2 — electrically equivalent in SELV system, fails strict CE certification | lcsc-mapping.csv line 8 |
| #23 | C10 SEN66 decoupling at 11 mm from J3.1 — > 5 mm guideline but acceptable for sensor rail | generate.py 5082-5088 |
| #23 | C11 LD2410 decoupling at 10.5 mm from J4.5 (not the 5.6 mm audit #2 said — different calculation methods) | generate.py + v0.22 |
| #25 | sk6812-side.md still says "12 LEDs" — actual is 11 (D14 vacated for J1 in v0.18) | hardware/components/sk6812-side.md line 149 |
| #28 | `generate.py` line 46 comment says Y_chord ≈ 43.5237 mm — actual is 43.498 mm | generate.py line 46 |
| #29 | UART_TX/UART_RX run parallel on B.Cu for ~35 mm at 6 mm spacing — no functional concern at 256000 baud | oas_routes.py segs 0286, 0295 |
| #30 | I²C SDA/SCL run parallel on F.Cu for ~60 mm at 1 mm spacing — irrelevant at 100 kHz | oas_routes.py segs 0239, 0260 |

---

## Pass audits (no concerns at confidence ≥80)

All other audits returned PASS overall:

- **#1 SEN66 + J3 socket** — all 6 pins correct, +3V3 rail in spec, I²C addr 0x6B
- **#2 LD2410B + J4** — v0.15.8 reversal bug correctly fixed in current state
- **#3 ESP32 J5 socket** — all 15 pins correct, R7 GPIO 8 pull-up present
- **#4 ESP32 J6 socket** — all 15 pins correct, USB pinout (GPIO 12/13) verified
- **#5 MIKROE-2462 J7** — 6 unused pins no_connect, +3V3/GND correct
- **#6 MIKROE-2462 J8** — INT/SCL/SDA paths complete, +5V correctly NOT connected
- **#7 J1 Phoenix MSTBA** — 24V/GND/PE assignments correct, rotation per v0.18
- **#8 J9 Qwiic JST SH** — all 4 pins correct, cutout C5 covers pads
- **#10 J2 DNP recovery** — all 6 pins correct (J2 still present)
- **#15 D1 polarity** — ❌ FAILED (see CRITICAL-1)
- **#16 D2 SS14 polarity** — cathode=SW, anode=GND correct
- **#22 C2 Y2 substitute** — pad nets PE/GND correct; substitution OK for SELV
- **#25 SK6812 LED chain** — all 11 LEDs, all pins, D14 skip, chain continuity all correct
- **#26 C20-C31 LED bypass** — 11 caps, correct nets, ~2.55 mm from each LED VDD
- **#27 GPIO assignment cross-check** — all 11 signals + 9 spares + 3 straps + 5 GND match CLAUDE.md ↔ generate.py ↔ schematic ↔ PCB
- **#28 PCB outline + mechanical** — D-shape, 3× M3 mounts, Ø12 cable hole, 4× zip-tie holes all match AK-N-94 manufacturer DXF

---

## Recommended action sequence

1. **Fix CRITICAL-1 (D1 polarity)** — single most important. Without TVS protection, the board has no surge protection against the 24V supply. ~10 minutes in `generate.py`.
2. **Fix CRITICAL-2 (TPS62933 divider + Vref)** — align schematic R2/R3 to 100k/30.9k. Update lcsc-mapping.csv. ~20 minutes.
3. **Fix CRITICAL-3 (C7/C8 roles)** — decide whether FB feedforward cap is needed; align schematic with PCB-generator. ~20 minutes.
4. **Fix CRITICAL-4 (Q1 substitution)** — order AO3401A instead of PMV65XP (same SOT-23 footprint, no PCB changes needed). Update `generate.py` Q1 value + `lcsc-mapping.csv`. ~10 minutes.
5. **Fix I1 (silk polarity markers)** — add cathode bars + electrolytic + marks to custom footprints. ~30 minutes.
6. **Fix I2-I3 (J10 cutout + J2 in_bom)** — minor cleanup. ~15 minutes.
7. (Optional, non-blocking) Fix I4-I10 documentation + non-critical items.
8. **Re-run** `regenerate.py` + `export_production.py` + `tools/preflight_gerbers.py` + visual diff against this report's expected geometry.
9. **Spawn a second 5-agent re-audit** of only the 4 critical fixes + I1 silk markers + I2-I3 to confirm regression-free.
10. **Then** upload `oas-jlcpcb.zip` + `oas-top-pos.csv` + `oas-bom.csv` to JLCPCB.

Total fix time estimate: ~2 hours of careful edits + regeneration cycles.

---

## Methodology notes

- 30 agents ran in parallel using `feature-dev:code-reviewer` subagent type (tools physically exclude Edit/Write).
- Each agent: pin-by-pin verification, every claim cited (datasheet section / file:line / pad coordinate).
- Sources fetched: official manufacturer datasheets (TI, Nexperia, Sensirion, HLK, MikroE, Espressif, Phoenix Contact, Littelfuse, Walsin, OPSCO, Brightking, Yageo, Diodes Inc, CENKER, Samsung Electro-Mechanics, JST); KiCad stock footprint libraries; LCSC product pages; existing project documentation (CLAUDE.md, hardware/components/*.md).
- Each audit produced an evidence-citation table — no "MASZ ABSOLUTNĄ RACJĘ!" guesswork.
- Cross-references: audit #2 (J4 LD2410) + audit #4 (J6 ESP32 GPIO 16/17) corroborate UART direction. Audit #13 (Q1) + audit #15 (D1) + audit #17 (D3) all interact on the Q1 protection circuit. Audit #12 (U2) + audit #24 (R2/R3) cross-validate the TPS62933 feedback divider math. Audit #25 (LEDs) + audit #26 (caps) corroborate the LED ring layout.
- Critical issues confirmed by multiple agents independently: TPS62933 Vref discrepancy (audits #12 and #24); Q1 Vds insufficient (audits #13 and #17); D1 polarity reversal (audit #15 alone, but supported by audit #11 and audit #15 cross-reference of net names).
