# OAS PCB v0.15.7 — Independent Code Review

Date: 2026-05-13
Reviewer: Opus 4.7 (independent agent, no conversation context)
Scope: `C:\Git\open-ambient-sensor\` at commit `4e11ec2`

## Verification performed

- Read `CLAUDE.md` (full), `generate.py` (geometry constants + footprint placement + schematic generation)
- Visual inspection of `2d-top.png`, `3d-top.png`, `3d-iso.png`, `2d-bottom.png`
- DRC=0, ERC=0 corroborated by independent geometric checks
- Cross-checked rotation transforms for ESP32, LD2410, MIKROE-2462, SEN66
- Verified J5/J6/J7/J8 pin-socket pad positions match daughterboard pin-row dots
- Validated `ESP32C6_DEVKITM1_SIGNAL_PIN` and `ESP32C6_DEVKITM1_NC_PINS` classification
- Spot-checked `oas.kicad_pcb` placed footprint coordinates against the Python source

## Findings

### Critical

None that block fabrication outright. DRC=0/ERC=0 is corroborated by independent geometric checks.

### Major

**M1. SEN66↔J3 cable run is 2-2.5× longer than CLAUDE.md claims.**
- Sensirion datasheet §3 / Figure 4: SEN66 JST GH connector is on the +X short edge adjacent to the air outlet.
- With `SEN66_ANCHOR = (23.5, 22)` + `SEN66_ROTATION = 90`, the +X short edge lands at **PCB Y = -33.2** (body's NORTHERN edge).
- J3 sits at PCB ~(36, 27) — 3 mm SOUTH of the body.
- Realized cable run: ~60 mm straight-line, ~95-105 mm routed around body east/west side.
- CLAUDE.md line 154 claim of "<40 mm total bus length" is **not achieved**.
- Cable cannot route OVER the SEN66 top face (blocks inlets/outlet; violates Sensirion mech §3).
- Compounded by `J3_ROTATION = 180`: cable opening faces south, forces 180° bend.
- Fix: (a) flip `J3_ROTATION` to 0 (cable enters from north), or (b) re-anchor SEN66 so connector faces chord.

**M2. SEN66 mech-ref description is stale (v0.5-era).**
- `generate.py` lines 702-703, 1511, 1541: descriptions still say "Mounts on enclosure cover, NOT on the PCB". Per v0.6 SEN66 is PCB-mounted.
- ZipTie helper line 1215, 2672: says "retain SEN66 against the enclosure cover" (now retains to PCB).
- Doc-only — no geometry effect.

**M3. Stale code comment in `generate.py` line 194-198 (J3 region).**
- References pre-v0.6 cover-mount coordinate "(22.8, -15.2)". Current SEN66 connector at (36.3, -33.2).

**M4. CLAUDE.md internal inconsistency on I²C pull-up value.**
- Pinout table line 162 says "4.7 kΩ pull-ups on MCU side".
- Actual schematic (R5/R6 in `gen_mcu_sch()`) uses **10 kΩ** per SEN66 datasheet §3.1.
- Schematic is correct; CLAUDE.md text not updated when v0.6 bumped 4.7→10 kΩ.

### Minor

**Mi1. Body labels render vertically / upside-down due to combined footprint+text rotation.**
- "SEN66 SIN-T": fp_text rot 0 + footprint rot 90 = 90° vertical.
- "ESP32-C6 DevKitM-1": fp_text rot 90 + footprint rot 90 = 180° upside-down.
- "MIKROE-2462": fp_text rot 90 + footprint rot 180 = 270° vertical top-to-bottom.
- "HLK-LD2410B": fp_text rot 0 + footprint rot 270 = 270° vertical top-to-bottom.
- CLAUDE.md silkscreen-convention recommends labels be "self-explanatory in isolation" — better to use board-level `gr_text` (rotation-independent) for major labels.

**Mi2. ESP32 short-edge labels "antenna"/"USB" also rotate upside-down.**
- Same root cause as Mi1.

**Mi3. ESP32 mech-ref description offset numbers (`generate.py` 2710 vs 2750).**
- "pin block offset 0.98 mm toward antenna end" vs "5.37 mm from antenna short edge". Both correct but describe same geometry from different references — worth a clarifying comment.

**Mi4. IO sub-sheet still empty.**
- `SUBSHEET_PINS["io"] = []`. Qwiic expansion not yet placed (listed under "open work" in CLAUDE.md, not a regression).

**Mi5. SEN66 zone front-clearance ≥22 mm unverified.**
- Hard Constraint #1 (SEN66 zone exception) depends on physical AK-N-94 sample measurement (CASE-VERIFICATION-CHECKLIST §1). Cannot fabricate to final spec until confirmed. Flagged explicitly in CLAUDE.md.

### Nits

**N1.** `generate.py` line 320-326 comment in `_ld2410_local_to_pcb` says "Currently LD2410_ROTATION = 0 so this is just a translation". Current value is **270**.

**N2.** `generate.py` line 257-271 has duplicate stale text on `LD2410_SILK_INSET_CONN` — second half describes old positive-inset variant.

**N3.** v0.15.7 not in CLAUDE.md changelog (text ends at v0.15.6).

## Pinout / strap-pin / chip-pinout — PASS

All ESP32-C6 GPIO assignments per CLAUDE.md v0.4 verified against the Python pin classification:
- GPIO 2 (LD2410_OUT), GPIO 3 (NFC_FD), GPIO 6/7 (I²C), GPIO 8 (NeoPixel), GPIO 16/17 (UART1), GPIO 12/13 (USB-Serial-JTAG) — all correctly classified.
- GPIO 10/11 correctly NOT referenced (not bonded on C6FH4 SiP-flash variant).
- Strap pins GPIO 4, 5, 9, 15 either NC or only the GPIO 9 → J2 BOOT recovery (DNP), strap undisturbed in normal operation.
- Five GND pins all tied to global GND. 5V (J1.14) NC since we feed 3V3 directly to J1.1.
- Assertion at line 9343 enforces "every pin classified exactly once" — strong correctness guarantee.

## Schematic ERC label-direction sanity — PASS

`SUBSHEET_PINS` directions consistent (output↔input matched between sheets).

## DRC ignores — independent check for what they hide — PASS

Ignored: "Footprint has no courtyard defined" — applies to mech-refs (no F.CrtYd by design to avoid spurious overlap warnings against pin sockets). Acceptable.

Independent body-to-body / body-to-outline / body-to-mounting-hole / silk-to-silk distance calculations all found ≥ 0.4 mm clearance — no hidden geometric violations.

## Bottom line

DRC=0/ERC=0 reflects geometry truthfully — no fabrication blockers in script-generated artefacts.

Main concrete concern: **M1** (SEN66 cable length 2-2.5× longer than stated, fixable by `J3_ROTATION` flip).

Other findings are stale documentation (M2/M3/N3), CLAUDE.md inconsistencies (M4), and label-rotation readability (Mi1/Mi2). All resolvable cheaply.
