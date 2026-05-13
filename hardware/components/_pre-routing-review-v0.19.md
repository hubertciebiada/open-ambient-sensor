# OAS PCB v0.19 — Pre-Routing Independent Review

Date: 2026-05-13
Reviewer: Opus 4.7 (independent agent, no prior conversation context)
Scope: `C:\Git\open-ambient-sensor\` at commit `0ea56b6` (v0.19 — IO sub-sheet populated, J9 Qwiic + J10 native-USB recovery DNP)
Purpose: last review opportunity before full PCB copper routing begins.

---

## Verification performed

- Read `CLAUDE.md` end-to-end, including the v0.6 SEN66 PCB-mount narrative, the v0.15.8 review fixes (J4 pin order, LD2410 body, J3 rotation), and the v0.16–v0.19 changelog entries (SK6812 ring, J1 N→S flip, IO sub-sheet).
- Read all `hardware/components/*.md` files: `esp32-c6-devkitm-1-n4.md`, `hlk-ld2410b.md`, `sen66.md`, `mikroe-2462.md`, `sk6812-side.md`, `ak-n-94.md`, prior reviews `_overall-review-v0.15.7.md` and `_post-fix-review-v0.15.8.md`, plus the two background research notes (`_research-led-diffuse-ring.md`, `_research-round-display.md`).
- Read the full `generate.py` (14887 lines) — geometric constants, footprint generators, `SUBSHEET_PINS`, `ESP32C6_DEVKITM1_SIGNAL_PIN`, `ESP32C6_DEVKITM1_NC_PINS`, `LED_RING_SKIP_INDICES`, J3/J4/J9/J10 pin maps, the LED daisy chain, MCU schematic wiring, U4 NFC daughterboard wiring.
- Spot-read `oas.kicad_pcb`, `oas.kicad_sch`, `power.kicad_sch`, `mcu.kicad_sch`, `sensors.kicad_sch`, `io.kicad_sch`.
- Inspected `renders/2d-top.png`, `renders/3d-top.png` for visual sanity.
- Re-read `renders/_drc.rpt` (DRC = 0/0, with 5 ignored rules) and `renders/_erc.rpt` (ERC = 0/0).
- Installed `kiutils` 1.4.8 (`pip install --user kiutils`) and wrote three short Python scripts to:
  1. Extract every footprint's PCB-frame courtyard bbox via the standard KiCad rotation matrix (positive angle = visually CCW = math CW with Y-down screen), and compute pairwise courtyard gaps.
  2. Verify pad positions of J1, J3, J4, J9, J10, the LED ring, and the zip-tie holes against the design rules (`min_copper_edge_clearance = 0.3 mm`, chord at Y = +43.524, cable hole at R=6).
  3. Compute straight-line and Manhattan distances between the four I²C bus tap points (MCU socket, J3 SEN66 socket, J7/J8 MIKROE socket, J9 Qwiic socket) plus a minimum-spanning-tree estimate of the realized bus length.
- Ran `kicad-cli sch export bom oas.kicad_sch` for the BOM and diffed it against the PCB footprint set.
- Verified `SUBSHEET_PINS` hierarchical-label direction matrix (every cross-sheet net has a matched output↔input pair).
- Cross-checked the schematic J3 (SEN66) pin numbering against `sen66.md` Table 16, the J4 (LD2410) pin numbering against `hlk-ld2410b.md` Table 1 V1.04, the U4 NFC mikroBUS pin numbering against `mikroe-2462.md` (MikroE numbering vs Zephyr numbering), and the J9 (Qwiic) pin order against the Qwiic standard.
- Read `regenerate.py` to understand the build chain.

---

## Findings

### Critical (blocks routing or fabrication)

**C1. The PCB has zero nets — schematic has not been imported into PCB yet.**
- Verified by inspecting `oas.kicad_pcb` directly: only `(net 0 "")` exists; every pad has `net=(no net)`; 0 tracks; 0 ratlines.
- The PCB exists today purely as a geometry placeholder (mechanical-reference footprints + sockets + LED ring + zip-tie holes), with no electrical netlist linkage to the schematic.
- Before routing can start, the user must open `oas.kicad_pcb` in pcbnew and run **Tools → Update PCB from Schematic** (F8 in KiCad 10). That step will (a) place every schematic-only footprint listed under C2 below, and (b) attach nets to every pad. Until then, no copper routing is possible.
- Note: this is not a bug per se — it is the natural state for a script-generated PCB before user interaction. But it MUST be performed before any routing chunk.

**C2. 35 schematic components have no PCB footprint placed.**
- Diff of schematic refs vs PCB refs (script-extracted) gives 35 components on the schematic side that do not exist on the PCB side:
  - **Power section**: C1, C2, C3, C3b, C4, C4b, C5, C5b, C6, C6b, C7, C8, C9, C9b, D1 (TVS), D2 (Schottky), D3 (Zener), F1 (PTC), L1, L2, Q1 (P-MOSFET), R1, R2, R3, R4, U1 (LM2596S), U2 (TPS62933).
  - **MCU section**: R5, R6 (I²C pull-ups), U3 (ESP32-C6 socket — schematic references `Conn_01x15` symbols for J1/J3 headers but the PCB-side female sockets J5/J6 are mech-only PCB footprints with no schematic counterpart), J2 (DNP UART recovery header on MCU sheet — distinct from J10).
  - **NFC**: U4 (the MIKROE-2462 schematic symbol — the matching PCB-side female sockets are J7/J8, which are PCB-only mech footprints), C10, C11, C12.
- These are ALL the discrete passives, all 3 ICs, both P-MOSFETs, the TVS/PTC/diodes, the U3/U4 daughterboard symbols, and the optional DNP recovery header.
- After step C1 above, KiCad will offer to place them all on the PCB outside the board outline. The user will then drag each into a sensible position. Routing CANNOT begin before this placement step.
- This is the v0.20+ scope — the user is about to start it. The review flags it as a *blocking precondition* for routing, not as a defect in v0.19's deliverable.

**C3. Schematic has annotation errors: C3b, C4b, C5b, C6b, C9b emit BOM lines as `C3b?` / `C4b?` / etc.**
- `kicad-cli sch export bom` produced 5 entries with a trailing `?` on the reference field. KiCad's BOM annotator treats `C3b` as an un-annotated `C3` plus a suffix-letter, not a legitimate distinct reference.
- This breaks JLCPCB / Mouser BOM upload — the supplier tool will reject `C3b?` as an invalid designator.
- `generate.py` lines 10071 / 10085 / 10515 / 10529 / 13112 deliberately use `reference="C3b"` etc. to pair an HF-bypass 100 nF with its bulk cap (e.g. C3=100 µF // C3b=100 nF on +24 V).
- Verified at the source level: `generate.py:9853` "C3 100uF/50V + C3b 100 nF: input bulk + HF bypass", `:9856` "C4 220uF/10V + C4b 100 nF: output bulk + HF bypass", `:9908` comment block.
- **Fix**: renumber these caps to plain numeric refs (e.g. C3b → C13, C4b → C14, C5b → C15, C6b → C16, C9b → C17), update wire labels, and re-run `regenerate.py`. Or update `reference=` to use plain numeric IDs in `generate.py` directly. Pure search-and-replace, no electrical change.

### Major (should fix before routing — will bite once routing starts)

**M1. CLAUDE.md's "I²C bus < 40 mm" / "~60 mm realized" is unattainable with current daughterboard placements.**
- The shared I²C bus has 4 tap points: ESP32 socket pin (PCB ~(+0.5, -26)), SEN66 socket J3 pin 3 (PCB ~(+35.4, +25.2)), NFC socket J8 pin 6 (PCB ~(-36.9, +25.4)), Qwiic socket J9 pin 3 (PCB ~(+31.2, +41.7)).
- Computed minimum spanning tree across the four nodes (straight-line, ignoring obstacles): **142.5 mm**. Manhattan (more realistic for L-routes): **195.5 mm**.
- Even the most efficient tree (MCU↔SEN66 = 61.9 mm, MCU↔NFC = 63.5 mm, SEN66↔Qwiic = 17.1 mm) is well over 100 mm total.
- Sensirion SEN66 datasheet §3.1 specifies bus length **< 10 cm strongly recommended**, max 50 cm with shielding. At 142 mm straight-line, OAS is past the strong-recommendation line and into the "needs care" zone. With 10 kΩ pull-ups and ~100 pF total bus capacitance, the rise time τ = 10kΩ·100pF = 1 µs gives 10–90 % rise time ~2.2 µs, which **does not meet** the standard-mode I²C 100 kHz `t_r ≤ 1 µs` spec.
- CLAUDE.md line 154 ("~60 mm realized") and the older v0.15.8 changelog entry should be updated to acknowledge the realistic length is more like 100–150 mm depending on routing, and the corresponding `I2C` block in `mcu.kicad_sch` may need pull-up resistors **dropped to 4.7 kΩ** to keep the rise time inside spec (drops τ to ~470 ns, fits comfortably).
- Note: SEN66 datasheet §3.1 specifically calls out 10 kΩ as the *Sensirion-side* spec; lower values are explicitly allowed. The 4.7 kΩ that v0.5 had before the v0.6 bump-to-10kΩ may be the right choice for this geometry.

**M2. GPIO 8 boot-strap pull-up disappears in deployed OAS units.**
- Per `esp32-c6-devkitm-1-n4.md` "Strap pins summary": GPIO 8 needs to be HIGH at boot for SPI boot. The DevKitM-1's onboard pull-up is "via R3 0 Ω + WS2812 D6" — i.e., R3 ties GPIO 8 to the onboard WS2812B's DIN, which in turn presents a high-impedance input pulled to VDD=VCC_5V via the WS2812 chip's internal protection.
- OAS deliberately doesn't drive VCC_5V at the DevKitM-1 (the LDO is bypassed; we feed 3V3 directly into J1.1). VCC_5V floats. **The onboard "pull-up" on GPIO 8 is therefore not a real pull-up in OAS.**
- OAS adds an external SK6812-SIDE chain on GPIO 8 (driven from OAS's own +5V rail, which is alive). At boot, the external D11 SK6812's VDD is up (LM2596S delivers +5V) and its DIN sees a CMOS input with weak pull-down protection — not a clear HIGH.
- ESP32-C6 *does* have an internal weak pull-up that activates during boot strap sampling per the TRM, so this may not actually break boot in practice. But it is no longer guaranteed by external circuitry the way Espressif intended.
- **Recommendation**: add an explicit `10 kΩ` resistor from GPIO 8 to VCC_3V3 in the MCU sub-sheet, parallel to (or replacing the assumption of) the disappeared onboard pull-up. Trivial 1-resistor schematic change; eliminates any boot-strap-marginal-behaviour risk.

**M3. ESP32 dev-kit female socket (J5/J6) and MIKROE socket (J7/J8) have NO schematic symbol.**
- The PCB carries 4 female-pin-socket footprints (J5 row A of ESP32, J6 row B of ESP32, J7 row A of MIKROE-2462, J8 row B of MIKROE-2462).
- The schematic has U3 (ESP32-C6 DevKitM-1 symbol) and U4 (Conn_02x08 mikroBUS symbol), but no schematic representation of the female sockets themselves.
- When the user runs "Update PCB from Schematic" (step C1), KiCad will see J5/J6/J7/J8 as **PCB-only orphans** with no schematic linkage, which will either (a) delete them, or (b) prompt to remove them depending on KiCad's import options. **Both outcomes are wrong.**
- The fix is to either:
  - (a) Match the pad numbering of J5/J6 to U3's pin numbers (1..30) and the pad numbering of J7/J8 to U4's pin numbers (1..16), then *manually* link the schematic symbol's footprint property to a footprint that contains all 30 (or 16) pads. The current PCB splits ESP32 into J5 (pins 1-15, row A) and J6 (pins 16-30, row B), which cannot map to a single U3 symbol with 30 pads.
  - (b) Replace J5/J6 with a single 2x15 socket footprint that maps 1:1 to U3's 30 pins; same for J7/J8 → 2x8.
- v0.15.6 changelog notes "Female pin sockets added for ESP32 and MIKROE-2462 daughterboards"; the schematic side of this addition is the missing step.

**M4. J2 (MCU sub-sheet's local SWD/UART Recovery header, DNP) is not placed on the PCB.**
- Schematic ref J2 exists in `mcu.kicad_sch` (gen_mcu_sch ~lines 12822-12839, 6-pin DNP header for SWD/UART recovery, distinct from J10 which is the IO-sheet native-USB recovery).
- BOM lists `J2 SWD/UART Recovery (DNP)` quantity 1.
- PCB has no J2 footprint anywhere.
- This is intentional per v0.18 / v0.19 narrative (J10 supersedes J2's role for native-USB recovery), BUT the schematic still carries J2 as DNP. After C1's "Update PCB from Schematic" step, J2 will appear in the "place outside board" pile alongside the 34 missing schematic-only parts. The user then has to decide whether to:
  - (a) Delete the J2 symbol from `mcu.kicad_sch` (remove it from `gen_mcu_sch`) — clean.
  - (b) Place a J2 footprint somewhere on the PCB and leave it DNP — clutters PCB.
- Recommend (a) — delete J2 from the schematic. J10 covers the recovery use case.

**M5. Schematic-only passive components carry empty "Footprint" property.**
- 68 / 23 / 83 / 12 instances of `(property "Footprint" "")` in `power / mcu / sensors / io` sub-sheets respectively. Inspection shows: U1 (LM2596S) and U2 (TPS62933) and J1 (Phoenix MSTBA) have their Footprint property set; **every other discrete component has an empty Footprint field**.
- When step C1 runs, KiCad will warn "Component has no footprint assigned" for all 30+ parts and refuse to attach a PCB footprint until each schematic symbol's `Footprint` property is populated.
- The fix is to extend the schematic generators (in `gen_power_sch`, `gen_mcu_sch`, `gen_sensors_sch` for J3/J4) to set the `Footprint` field on every component — typically:
  - 0402 100nF caps: `Capacitor_SMD:C_0402_1005Metric`
  - 0603 1% resistors: `Resistor_SMD:R_0603_1608Metric`
  - SS14 Schottky: `Diode_SMD:D_SMA`
  - SMBJ24A TVS: `Diode_SMD:D_SMC` or similar
  - PTC fuse: `Resistor_SMD:R_2920_7351Metric` (for MF-RHT075/60-2 or equivalent surface-mount PTC)
  - Bulk electrolytics: vendor-specific footprint (Panasonic FK / Wurth WCAP)
  - DMP4015SK3 (P-MOSFET): SOT-23 footprint
  - L1 / L2: shielded inductor footprints sized for 33 µH 2A and 2.2 µH 2A
- Without this metadata in the schematic, the user must manually attach a footprint to every part inside pcbnew's "Update PCB" dialog before routing.

**M6. SEN66 socket J3 ↔ SEN66 connector physical cable run is 80–100 mm, not "<40 mm".**
- v0.15.8 acknowledged the J3 rotation flip (180→0) shortens the routing, and the changelog correctly notes "realized I²C bus length is ~60 mm" (which is now itself wrong per M1).
- Physical cable run: SEN66 +X short edge plug at PCB Y=-33.2; J3 socket at PCB Y=+27. The straight-line spatial distance (cable goes around the body's +X face) is ~63.8 mm, but the cable must arc back from PCB Y=-33.2 to PCB Y=+27 around the body's east or west edge with a finite bend radius (~10 mm minimum for the JST GH 6-pin cable per JST datasheet). Realistic cable length: 80–100 mm.
- Plus the on-PCB I²C trace from J3 pin 3/4 to MCU socket and to NFC/Qwiic taps (per M1, ~140 mm).
- **Total electrical bus length from MCU to SEN66 pins inside the SEN66 chip: ~140 mm PCB + ~80 mm cable = ~220 mm.** That's just under Sensirion's "max 0.5 m with shielding" — not within the "< 10 cm strongly recommended" envelope. The JST GH cable is shielded only if you pay for a shielded variant; the standard Sensirion 50 cm cable is unshielded twisted ribbon.
- Pillar #1 (measurement quality) is the project's anchor. Recommend the user explicitly accept this trade-off, OR re-evaluate J3 placement to shorten the on-PCB I²C run (e.g. move J3 to the LEFT half of the board so SEN66 cable wraps once around the west edge of the body).

### Minor (doc / cosmetic / future-revisit)

**Mi1. CLAUDE.md still has stale text on the SEN66 zip-tie X positions.**
- CLAUDE.md line 149 (architectural decisions section): "Recommended: Pair 1 at X ≈ 25 (mid-safe corridor); Pair 2 at X ≈ 50 (post-outlet, minor outlet rim shading <10% acceptable)."
- `generate.py` `SEN66_ZIPTIE_LOCAL` uses X=22 and X=30 (both inside the safe corridor X ∈ [18.22, 32.03]). The v0.6 changelog acknowledged that X=50 was inside the outlet circle (would have blocked ~8% of outlet area) and was corrected; the architectural-decisions paragraph in CLAUDE.md was not synced.
- Doc-only; geometry is fine.

**Mi2. CLAUDE.md "Module list" line for the LD2410 still says "HiLink LD2410B/C".**
- Per `hlk-ld2410b.md` "Variant — B vs C" section, B and C have **different pin orders** (B: Pin 1 = OUT; C: Pin 3 = OUT) and **different dimensions** (B: 7×35 mm 1.27 mm; C: 16×22 mm 2.54 mm). They are NOT drop-in substitutes; pin 5 (VCC) is in the same place on both but pins 1–3 are different.
- `generate.py` is pinned to LD2410**B** geometry (body 7.62 × 35.56 mm, J4 1×5 P1.27 mm). CLAUDE.md should commit to "HLK-LD2410B" alone and drop the "/C" fallback to satisfy the Module Identification rule explicitly (currently the rule is satisfied at the implementation level but violated at the CLAUDE.md "Module list" table level).

**Mi3. CLAUDE.md NFC chip-ID note: "chip ID v0.15.8" reads as confusing date stamp.**
- The line at the top of the architectural-decisions table says "MIKROE-2462 NFC Tag 2 Click (NXP NT3H1101 + onboard PCB antenna, mikroBUS) ... confirmed v0.12 (chip ID v0.15.8)". The "v0.15.8" is the revision where chip ID was fixed (NT3H2111 → NT3H1101) — not a chip version. Reads as "the NFC chip is at hardware-revision 0.15.8" if you don't have the changelog context.
- Cosmetic; consider rephrasing to "confirmed v0.12 (NT3H1101 ID corrected in v0.15.8)".

**Mi4. CLAUDE.md "ESP32-C6 ... ~5 mW vs ~30 mW" doc inconsistency — already noted in v0.15.8 changelog but lingers in earlier v0.4/v0.5 narrative.**
- The v0.4 / v0.5 entries still call out "+5–10 mW always-on power-LED dissipation" estimates that conflict with the v0.15.8 corrected ~5 mW. Future readers diff-checking these may be confused. Optional: add an "after v0.15.8 correction" marker to the historic entries.

**Mi5. Per-LED 100 nF decoupling caps (C20..C31) overlap with their LED's courtyard.**
- The script-extracted pairwise courtyard analysis shows C21–D12, C22–D13, C24–D15, C25–D16, C27–D18, C28–D19, C30–D21, C31–D22 all have "courtyard overlap" (gap = -1 sentinel, meaning the bboxes intersect). This is by design — each cap is intentionally placed inside its LED's courtyard radial-inward of the LED body.
- **Today this is fine** because the `Footprint has no courtyard defined` DRC rule is ignored. But if the user ever turns that ignore off, every LED-cap pair will produce a courtyard-overlap warning.
- Not a routing blocker; flagged for awareness.

**Mi6. The C3 cutout's J10 pad 6 (BOOT) is north of the cutout's north edge.**
- C3 cutout Y range: +28.998 to +43.524. J10 pad 6 center: PCB (+9.40, +28.30). Pad outer radius 0.85 → pad south edge at Y=+29.15. The pad is **0.85 mm north** of the cutout's north edge (i.e., 0.85 mm outside the case-wall opening accessible to a pogopin from outside).
- v0.19 design intent (generate.py:706-715) explicitly accepts this: "pin 6 (BOOT, the least frequently accessed) extends beyond the cutout into the PCB-side keepout-free region." Then a second revision moved pad 1 north by 1 mm so pin-1 silk clears the chord; the consequence is pad 6 ends up outside the cutout.
- **Practical question**: with the recovery header DNP and pogopin used through a case-wall opening, can the pogopin physically reach a pad that sits 0.85 mm north of the opening? Probably yes for a flexible pogopin, marginal for a rigid jig. Worth a single physical-prototype test once a JLC sample arrives.

**Mi7. 11 mm body height for MIKROE-2462 daughterboard (per components doc) vs CLAUDE.md's "~7 mm".**
- `mikroe-2462.md` "Body Z-height above the OAS PCB" section computes 10–11 mm (8.5 mm pin socket + 1.6 mm Click PCB + ~1 mm slack), whereas `MIKROE2462_BODY_Z = 7.0` in generate.py and CLAUDE.md's hardware section state ~7 mm.
- Both numbers fit under the 17 mm peripheral height constraint with healthy margin. But `generate.py` should be updated to 11 mm for accurate 3D rendering, OR the user should commit to using low-profile (~5 mm body) pin sockets to keep the 7 mm budget.

### Nits

**N1. Stale comment in `generate.py:194-198`.**
- Comment in the SEN66 zip-tie section says "Recommended: Pair 1 at X ≈ 25 (mid-safe corridor); Pair 2 at X ≈ 50 (post-outlet, minor outlet rim shading <10% acceptable)." The actual code below uses X=22, X=30 — both inside the strict safe corridor. Same stale info as Mi1, but propagated into a code comment.

**N2. `oas.kicad_pro` design rule has `silk_clearance: None` but `min_silk_clearance: 0.15`.**
- Both fields exist; the `None` one is unused redundant data. Cosmetic only.

**N3. ESPHome version & sen6x component release date in CLAUDE.md is "2026.3.0 (March 2026)".**
- Today's date is 2026-05-13 so 2026.3.0 should be available. CLAUDE.md "Software" section line still says "verify native availability; fallback to custom" — verify-step is now resolvable. Drop the "verify" hedge.

**N4. SEN66 cable accessory price not in BOM.**
- The 50 cm JST-GH cable accessory is sold separately by Sensirion (~€7 retail) but doesn't appear in any BOM line. Add to BOM under "ordered separately" notes.

---

## Per-category status

| Category | Status | Notes |
|---|---|---|
| **A. Geometric sanity (PCB)** | **WARN** | Mi5 (cap-LED courtyard overlap by design), Mi6 (J10 BOOT pad 0.85 mm north of C3 cutout). All other geometry clean. DRC=0/0 corroborated by independent kiutils-based bbox check; pad-vs-PCB-outline clearances all ≥ 0.3 mm; cable hole clearances ≥ 0.76 mm. |
| **B. Schematic sanity** | **FAIL** | C2 (35 sch-only parts not on PCB), C3 (BOM annotation errors), M3 (PCB-only J5/J6/J7/J8 sockets), M4 (J2 ghost), M5 (empty Footprint fields). ERC=0/0 corroborated; cross-sheet net direction matrix verified consistent. |
| **C. Electrical** | **WARN** | M1 (I²C bus length over Sensirion spec), M2 (GPIO 8 boot-strap pull-up disappears), M6 (SEN66 cable run 80-100 mm). Power budget (3.3 V / 5 V / 24 V rail margins) all healthy: TPS62933 3× margin, LM2596S 2.7× margin, F1 PTC 2.7× margin. Strap pin avoidance correct everywhere else; ESP32 5V pin J1.14 correctly NC. |
| **D. Specification consistency** | **PASS** | All MPN/EAN/dimensions in `hardware/components/*.md` match generate.py constants. v0.15.8 fixes (J4 pin order, LD2410 body 7.62 mm, J3 rotation 0, NT3H1101 chip ID, board-level gr_text labels) all in place. CLAUDE.md hard constraints reflected in code. Module Identification rule satisfied for every component (only Mi2 cosmetic on LD2410B/C). |
| **E. DRC / ERC ignore audit** | **WARN** | Five rules ignored: `Footprint has no courtyard defined`, `Track endpoint not centered on via`, `Tuning profile track geometries`, `Footprint doesn't match symbol's footprint filters`, `Footprint component type doesn't match footprint pads`. Justified for mech-only refs (LDR1, MOD1, MOD2, SENS1) and pre-route (no tracks/vias to check). **Once routing starts**, the via-centering rule must be re-enabled — leave the ignore for now. The footprint-filter and component-type ignores apply to symbols that lack a strict footprint-filter list and to the wide-pad TVS/MOSFET parts; revisit when assigning footprints in step C2. |
| **F. BOM completeness** | **FAIL** | C3 (5 annotation errors `Cnb?`), M5 (empty Footprint fields preventing JLCPCB upload), missing pin-socket entries (M3). LED ring quantities correct: 11 SK6812-SIDE D11-D22 (D14 skipped per v0.18), 11 × 100 nF C20-C31 (C23 skipped). DNP flag on J10 correct; J2 also flagged DNP (but absent from PCB per M4). U3 / U4 listed under MPN. F1, L1, L2, R1-R6, D1-D3 lack MPN / footprint metadata. |
| **G. Routing readiness** | **NOT READY** | Cannot route without first completing C1 + C2 + M3 + M5. Once those are done, M1 (I²C bus length) and the v0.18 0.234 mm D13/D15-J1 courtyard pinch will require attention during routing — there's enough copper clearance (~12 mm between pad rows) but the routing will need to thread carefully through the courtyard collision area. Power section completely unplaced — entire upper-left quadrant of the PCB will receive 30+ new components once the user runs "Update PCB from Schematic". |

---

## Bottom line — verdict: **NOT READY to route**

This is NOT a defect in v0.19's delivered work — the v0.19 commit cleanly added the IO sub-sheet (J9 Qwiic + J10 recovery DNP) and passes DRC=0/0 ERC=0/0. The v0.19 commit message itself flags this state.

What blocks routing is the **gap between schematic and PCB**: the schematic has 30+ discrete components (entire power section + I²C pull-ups + decoupling caps + ESP32/NFC daughterboard symbols + DNP J2 recovery) that have **never been placed on the PCB**. Routing copper before those components are placed and netlisted produces a meaningless PCB — copper traces will connect to ghost pads that move when the actual footprints land.

**Recommended order of operations before the first routing chunk (v0.20):**

1. **Fix C3** — renumber `C3b/C4b/C5b/C6b/C9b` to plain numeric refs in `generate.py`, regen, commit.
2. **Fix M5** — populate the `Footprint` field on every schematic symbol that currently has it empty (helper: emit `Footprint` property in the `_sch_capacitor`, `_sch_resistor`, etc. helpers in generate.py).
3. **Decide M3** — either match J5/J6 pad numbering to U3 pin numbering (and similar for J7/J8 ↔ U4), or rebuild ESP32 socket as a single 2×15 footprint and MIKROE socket as 2×8. The first option is less geometry change.
4. **Decide M4** — delete J2 from the schematic OR add a J2 footprint to the PCB.
5. **Decide M2** — add 10 kΩ pull-up on GPIO 8 → +3V3 in mcu sub-sheet (1 resistor change).
6. **Decide M1** — drop I²C pull-ups from 10 kΩ → 4.7 kΩ to give the elongated bus enough rise-time margin, OR accept the longer rise time and move to fast-mode-tolerant device drivers (SEN66 supports 100 kHz only; this affects only the design margin).
7. **Run regenerate.py** — confirm ERC/DRC still clean.
8. **Open `oas.kicad_pcb` in pcbnew → Tools → Update PCB from Schematic** — populate nets and pull in the 30+ now-correctly-annotated discrete components.
9. **Manually place** the new components in the upper-left "power" zone of the PCB, respecting:
   - LM2596S body extents per TO-263-5 footprint (~7×9 mm + tab),
   - L1 / L2 inductors per their wound-core dimensions (~7×7 mm typical),
   - The 0.234 mm D13/D15-J1 courtyard pinch (already acknowledged in v0.18; copper routing will be tight here).
10. Re-run regenerate.py — DRC should now warn about unrouted nets; ratlines should appear.
11. **Then** start routing.

Once items 1–10 are done, the PCB will be in a true ready-to-route state. The geometric work in v0.19 and earlier (PCB outline, mounting holes, cable hole, cutouts, mech-refs, LED ring, daughterboard sockets, zip-tie holes) is **all correct and routable**; the gap is the missing schematic-to-PCB import that the user has explicitly held off on until the v0.19 IO connector layout settled.

**Routing-readiness verdict: NOT READY.** Estimated effort to reach READY: 4–8 hours of `generate.py` work (C3 + M5 + M3 + M4 + M2) plus 1–2 hours of manual PCB placement (step 9) before the first track is drawn.

---

## Python tooling notes

- Installed `kiutils 1.4.8` via `pip install --user kiutils`. PCB parsing required passing UTF-8 encoded text since `kiutils.board.Board.from_file()` opens in the default locale (cp1250 on this Windows Polish system) and chokes on the µ character in `220µF` and the → in cutout labels. Workaround: `parse_sexp(open(path, encoding="utf-8").read())` then `Board.from_sexpr(...)`.
- Coordinate transform: KiCad rotation in `.kicad_pcb` is positive = visually CCW = mathematical CW (because screen +Y is down). The matrix to map footprint-local (lx, ly) to board (rx, ry) given footprint rotation θ is:
  ```python
  a = math.radians(theta)
  ca, sa = math.cos(a), math.sin(a)
  rx = ca*lx + sa*ly
  ry = -sa*lx + ca*ly
  # then translate by fp.position
  ```
  This matches `_sen66_local_to_pcb` / `_ld2410_local_to_pcb` in generate.py.

No `requirements.txt` change recommended — kiutils is a review-only tool, not part of the regenerate.py chain. The `pip install --user` keeps it isolated to the reviewer's profile.

---

## Post-fix status (after v0.20)

Routing-readiness reassessment: **READY for first routing chunk** (modulo M3 deferral; see below).

| Finding | Status | Fix commits |
|---|---|---|
| **C1** — PCB nets empty | **RESOLVED**. New `sync_pcb_nets_from_schematic()` post-process in `generate.py` exports a `kicad-cli` netlist, parses it with a minimalist S-expression parser, and rewrites `oas.kicad_pcb` so every populated pad whose `(reference, pin)` matches a schematic node receives the `(net <code> "<name>")` clause; PCB header carries a `(net N "<name>")` declaration for every schematic net. 188 pad-net assignments applied. ERC=0 still. DRC=15 SOFT (no shorts, no clearance failures, 134 unconnected ratlines expected pre-routing). | `45648fc` |
| **C2** — 35 schematic-only components | **RESOLVED for 27** (all schematic-side power passives + ICs + sensor decoupling + J2 DNP recovery). 13 new stub footprint generators added (Resistor 0603, Capacitor 0603 / 0805, Diode SMA / SMB / SOD-323, Inductor SMD, Polyfuse 2920, polarized radial cap, SOT-23, TO-263-5, SOT-583, 1×6 P2.54 THT). Placement in upper-right PCB quadrant; user will refine during routing iterations. Remaining 8 of the original 35 are absorbed into the M3 reconciliation (U3 + U4 schematic placeholders that map onto the PCB-only J5..J8 sockets) — deferred. | `5d67ee1` |
| **C3** — `Cnb?` BOM annotation errors | **RESOLVED**. Mechanical rename `C3b → C13`, `C4b → C14`, `C5b → C15`, `C6b → C16`, `C9b → C17` across schematic refs, wire labels, junction tags, and Python local identifiers. Verified `kicad-cli sch export bom` produces clean numeric designators with no `?` suffix. | `e72d58f` |
| **M1** — I²C bus length / pull-up margin | OPEN. Defer until copper routing is complete and actual bus length is known. |  |
| **M2** — GPIO 8 boot-strap pull-up | OPEN. 1-resistor schematic change (add 10 kΩ to +3V3 on GPIO 8) — to be folded into the M3 schematic rework. |  |
| **M3** — J5..J8 PCB sockets have no schematic counterpart | **RESOLVED (v0.21)**. `gen_mcu_sch()` and `gen_sensors_sch()` now instantiate `J5` + `J6` as two `Connector_Generic:Conn_01x15` symbols (replacing U3) and `J7` + `J8` as two `Connector_Generic:Conn_01x08` symbols (replacing U4). Schematic pin numbers 1..15 / 1..8 match the PCB pad numbering 1:1 for each socket. `sync_pcb_nets_from_schematic` now applies 216 pad-net assignments (up from 188 in v0.20). All J5..J8 pads have valid nets; 0 socket pads on net 0. The previous `_sch_esp32c6_devkitm1` and `_sch_conn_02x08_top_bottom` instances are removed from the schematic (helpers kept in source as dead code documentation). J2 DNP recovery header rotated 180° so its TX/RX pin rows align with J6's reversed pin Y order. | v0.21 commits below |
| **M4** — J2 DNP ghost | PARTIALLY RESOLVED — v0.20 placed a J2 PCB footprint (DNP per BOM); user must still decide between (a) deleting J2 from the schematic entirely, or (b) keeping J2 as documented-DNP redundancy. |  |
| **M5** — empty `Footprint` properties | OPEN. Mostly cosmetic now that PCB carries its own canonical footprint references; pcbnew BOM export will use the PCB-side property. Schematic-side `Footprint` field can be filled in alongside M3. |  |
| **M6** — SEN66 cable run > 60 mm | OPEN. Same as M1 — re-evaluate after routing. |  |
| **Mi1..Mi7, N1..N4** | OPEN — cosmetic / future-revisit. No routing impact. |  |
| **Pre-existing root-sheet bridge** (spotted during C1 verification — not in original review) | **RESOLVED (v0.21)**. Root cause: `_root_wire` for `UART_TX` ran east at Y=97.79 from sensors right edge to vertical leg at X=143.51; the IO sub-sheet's `USB_DP` west-into-io wire ran west at the SAME Y=97.79 from X=156.21 to X=101.6. Overlapping X range [101.6, 143.51] at Y=97.79 made KiCad merge the two wires onto one net. Same pattern for UART_RX (Y=100.33) bridging with EN (Y=100.33). Fix in `gen_root_sch()`: re-route UART_TX east stub to first go south of the IO block (Y=110.49 / 113.03) before going east; UART_TX vertical leg moved from X=143.51 to be reached via intermediate (95.25, 110.49); UART_RX moved via (97.79, 113.03). Netlist verified clean: `/MCU/UART_TX` = {J2.3, J4.3, J6.2}, `/MCU/UART_RX` = {J2.4, J4.2, J6.3}, `/IO/USB_DP` = {J10.4, J6.13}, `/IO/EN` = {J10.5, J2.5, J5.2}. | v0.21 |

**Final routing-readiness verdict: READY**. All previously-flagged blockers are closed: schematic-PCB net sync (C1), schematic-only component placement (C2), BOM annotation errors (C3), M3 daughterboard sockets, and the pre-existing root-sheet UART/USB crossover bug. The 5 SEN66 mech-ref `courtyards_overlap` DRC false positives were also eliminated by removing the F.CrtYd from the SEN66 mech-ref footprint (consistent with MOD1/MOD2 daughterboard mech-refs). Post-v0.21 DRC = 10 violations (1 courtyards_overlap C4-D2 and 9 silk_over_copper warnings, all localized to v0.20 stub footprint placements that the user will refine during routing — none are electrical errors). 155 unconnected ratlines are the expected pre-routing state. ERC = 0.

## Post-fix status (after v0.22)

The v0.21 reasoning that *"SEN66 sits 21.5 mm above the OAS PCB ... PCB-level components beneath its body shadow are perfectly clear"* was **WRONG**. SEN66 lies FLAT on the PCB on its 25.6 × 55.2 mm back face — ZERO clearance under it. v0.22 restores the SEN66 mech-ref F.CrtYd rectangle as a programmatic DRC guardrail and relocates 5 SMD components (Q1, F1, D3, R1, R4) that the v0.21 placements had under the SEN66 body shadow. Additionally:

| Finding | Status | Fix |
|---|---|---|
| **SEN66 body-shadow guardrail** | **RESOLVED**. F.CrtYd rectangle restored on the SEN66 mech-ref footprint (both library and embedded-instance copies in generate.py). Multi-line comment block explains the rationale and head off the v0.21 misconception class-of-error from recurring. |
| **SEN66 body shadow SMD relocations** | **RESOLVED**. 5 partial-overlap SMD (Q1, F1, D3, R1, R4) moved out of SEN66 body shadow into the north-of-SEN66 cluster + far-east-of-SEN66 zone (for F1). All 5 verified by independent kiutils check (`_check_shadows.py`). |
| **NFC daughterboard partial overlaps** | **RESOLVED**. 3 NFC-partial SMD (U1, C3, C1) moved fully outside the NFC body shadow (south of NFC y_min=-16.51). C12 (already inside NFC) remains inside — explicitly allowed by the daughterboard-shadow rule. |
| **ESP32 daughterboard partial overlaps** | **RESOLVED**. 10 ESP32-partial SMD relocated into a clean column-based layout fully inside the ESP32 body shadow. Pin row pad zones (J5 at Y∈[-27.74,-24.20] and J6 at Y∈[-50.60,-47.06]) are properly avoided. |
| **M1 — I²C pull-up size** | **RESOLVED**. R5/R6 value 10 kΩ → 4.7 kΩ. Sized for the realized ~140 mm PCB MST + ~80 mm cable bus length. |
| **M2 — GPIO 8 boot-strap pull-up** | **RESOLVED**. R7 = 10 kΩ to +3V3 added in MCU schematic + PCB. |
| **M5 — SEN66 cable run honest measurement** | **RESOLVED**. CLAUDE.md updated to "~140 mm PCB MST + ~80 mm cable = ~220 mm total electrical length"; the prior "<40 mm" and "~60 mm" claims retracted. |
| **Task #24 — Q1 SOT-23 pad name mismatch** | **RESOLVED**. `gen_sot23_3pin_pcb_footprint` accepts `pin_names=("G", "S", "D")` to align footprint pad numbers with the Device:Q_PMOS schematic symbol's letter pin numbers. Q1 pads will now bind to nets via `sync_pcb_nets_from_schematic`. |
| **F1 polyfuse placement** | **RESOLVED**. F1 doesn't fit in any small strip (south-of-cable-hole zone is 5.9 mm tall but F1 is 8 mm wide at rot 0; west-of-J3 zone too narrow). Placed at (+54, +9) in the open EAST-of-SEN66 zone with 0.88 mm clearance to PCB outline at the south corner. |
| **DRC residue (silk_over_copper)** | **RESOLVED**. "ESP32-C6 DevKitM-1" + "USB" board-level gr_text labels moved from F.SilkS to F.Fab (assembly-drawing-only; not silkscreen-printed). The ESP32 daughterboard physically covers this region at assembly time, so the silk text underneath would be invisible to the user — F.Fab preserves the documentation value without DRC noise. C11 LD2410 decoupling cap shifted +2 mm east to clear the LDR1 silk-frame long-edge-1 line. |
| **DRC verdict** | **0 violations**. 160 unconnected pads remain (expected pre-routing ratlines, up from 155 in v0.21 because R7 + Q1 moved pads add new ratlines). |
| **ERC verdict** | **0 violations**. |

**Final v0.22 routing-readiness verdict: READY**.

