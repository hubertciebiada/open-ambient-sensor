# OAS — Open Ambient Sensor

DIY multi-sensor environmental monitor for indoor spaces. Measures air quality and presence. Mounts on a standard wall-recessed electrical box (60 mm screw pitch). Powered from 24 V DC. Integrates with Home Assistant via ESPHome.

---

## Design philosophy

The open-source DIY space offers many indoor air quality projects. Most optimize aggressively for cost. **OAS holds two priorities non-negotiable**, even at the cost of a higher per-unit BOM:

1. **Measurement quality.** Sensirion SEN66 (calibrated combo NDIR / laser PM / MOX VOC + NOx / SHT) over cheap MOX-only alternatives. LD2410 mmWave (stillness detection) over PIR. PCB layout enforces thermal separation between heat sources and sensor inlets.

2. **Aesthetic acceptability.** The device lives in inhabited rooms. A commercial-grade injection-molded enclosure (SZOMK AK-N-94, white perforated ABS) replaces the typical 3D-printed box. No protruding modules, no exposed wiring, no fan whine.

OAS sits between bargain DIY kits and premium commercial sensors; both compromises are rejected. When evaluating any future component or design change, it must clear both bars — flag anything that breaks either pillar.

---

## Lessons learned (v0.40 audit-16)

Concrete, mandatory practices distilled from the v0.40 JLCPCB rejection saga + the 78-agent paranoid sweep + the audit-16 follow-up. Every item below is a real failure mode the project hit and recovered from.

### 1. NEVER write custom footprint stubs by approximation

Always parse-and-emit from the KiCad stock library verbatim via `_emit_stock_lib_footprint(src_path=…, lib_nickname=…)`. The pattern: stub generators are ~15-line wrappers that delegate to the helper — they MUST NOT contain hand-coded pad coordinates / sizes / silk geometry.

Root cause behind the v0.40 JLCPCB rejection (U1 LM2596S TO-263-5 emitted a 90°-rotated, miniaturized land pattern) AND ~24 SMD passive deviations caught later (0402 / 0603 / 0805 caps, 0603 resistors, SMA / SMB / SOD-323 diodes, 5×5 inductors, 2920 polyfuse, SOT-23). Q1 SOT-23 was particularly bad: custom "⊥" pad pattern vs canonical stock "E" pattern → the AO3401A would have been physically rotated 90° relative to the pads after JLCPCB's tape-feeder orientation lookup, swapping G/S/D nets and silently destroying reverse-polarity protection on first power-up.

The audit-16 sweep eliminated EVERY hand-coded pad geometry. The current header inventory of `oas.kicad_pcb` is listed under "Deviation budget" further down — every entry is either canonical KiCad stock (`<lib>:<name>`) or a project-local mechanical / NPTH / LED reference.

### 2. Footprint property string MUST be canonical `Lib:Name`

Never bare names ("PinHeader_1x06_P2.54mm_Vertical" without `Connector_PinHeader_2.54mm:` prefix). Never custom names ("TO-263-5_LM2596" instead of stock `Package_TO_SOT_SMD:TO-263-5_TabPin3`).

The `(footprint "Lib:Name"` header inside `oas.kicad_pcb` is what JLCPCB's matchers AND KiCad's `lib_footprint_mismatch` ERC both resolve against. Audit-16 caught FOUR additional canonical-name defects that audit-15 (which focused on pad geometry) had missed: U1 / U2 non-canonical headers, J2 missing lib prefix, ZT1..ZT4 missing `oas:` prefix.

### 3. NO `rule_severities` suppression — fix the cause, never paper over the warning

The audit-15 fix for Q1's `lib_footprint_mismatch` was wrong-class: it suppressed the warning via `rule_severities: {"lib_footprint_mismatch": "ignore"}` because the schematic used `Device:Q_PMOS` (letter pin numbers D/G/S) paired with a `pin_name_map` remapping stock SOT-23 pads "1"/"2"/"3" → "G"/"S"/"D".

The right fix (audit-16) was structural: create project-local `OAS:Q_PMOS_GDS` schematic symbol with NUMERIC pin numbers 1/2/3 (pin NAMES still G/S/D for readability) so the netlist binds Q1.1/Q1.2/Q1.3 canonically to stock SOT-23 pads "1"/"2"/"3" with NO remap. `gen_pro()` `rule_severities` now empty `{}` — no special-case overrides anywhere in the project.

### 4. JLCPCB DFM machine check ≠ JLCPCB human review

The v0.40 board held a stable JLCPCB DFM result of **0 DANGER / 193 W** (warnings only, fully manufacturable) — but the DFM machine did NOT catch the U1 / U2 broken footprint geometry. JLCPCB's human parts-placement reviewer caught them at the manual stage AFTER payment, and rejected the order.

Plan defensively: verbatim stock library is the only way to be safe at BOTH check layers. DFM PASS is necessary but not sufficient.

### 5. JLCPCB Assembly Order XLS pre-payment cross-check is mandatory

"Smart-match by LCSC SKU" can silently substitute wrong parts even with an explicit LCSC# specified. The v0.40 order caught THREE catastrophic near-misses at this step:
- **R3 (30.9 k 1%)**: `lcsc-mapping.csv` had `C23116` but JLCPCB's database mapped that SKU to `0603WAF8060T5E = 806 Ω` (three orders of magnitude wrong). At 806 Ω in the TPS62933 FB divider, Vout target ≈ 100 V → buck saturates at Vin → 22 V on the 3V3 rail → ESP32-C6 + SEN66 destroyed instantly. Correct SKU is `C23022`.
- **D3 (10 V Zener BZT52C10S, SOD-323)**: `lcsc-mapping.csv` had `C8492` but JLCPCB returned LRC `LBSS84LT1G` P-Channel MOSFET in SOT-23 (wrong device class AND wrong footprint). Correct LCSC is `C19334`.
- **C2 (Y2 safety cap, 0805)**: Walsin part went out of stock between mapping and order; JLCPCB auto-substituted to Murata GRM21BR72A103KA01L (100 V instead of 250 V — still safe for 24 V SELV but a different part).

**Workflow**: always set Parts Selection = "By Customer" (not "By JLCPCB"). Download Assembly Order XLS preview AFTER matching, BEFORE submitting payment. Diff the Description column row-by-row against `hardware/kicad/lcsc_mapping.py`. Verify part class (Zener vs MOSFET, capacitor vs resistor) AND numeric value parses cleanly (`30.9 kΩ` not `806 Ω`). LCSC# alone is not sufficient evidence.

### 6. Don't hallucinate datasheet pinouts from memory

The audit-16 sweep almost mis-recorded the TPS62933 pinout as "1=SW, 2=PG..." until pdftotext extraction of TI SLUSEA4D Rev D Table 7-1 revealed the truth: "1=RT, 2=EN, 3=VIN, 4=GND, 5=SW, 6=BST, 7=SS, 8=FB". When in doubt, extract from the authoritative source.

The same class of mistake hit ESP32-C6 GPIO 10 / 11 (v0.3 prescribed them as pin reassignment targets — but those pins are physically NOT bonded out on any ESP32-C6 SiP-flash variant); the LD2410 pin order (pre-v0.15.8 had VCC ↔ OUT reversed — see Lesson 20); the Q1 D3 dissipation math (off by 100×); and the AO3401A Vgs_max value (one audit doc said ±20 V, datasheet says ±12 V).

### 7. Per-component paranoid audit catches what batch-grouped audits miss

The 78-agent swarm in audit-15 (one agent per BOM line — `_cleanup-reports/15-*.md`) found the Q1 90° pad rotation that previous class-level reviews and 6-agent passes had not. For pre-fab safety, paranoia-level matters: budget the agent-time, send one expert per part.

### 8. Schematic symbol pin numbers should match footprint pad numbers natively, no remap

`Device:Q_PMOS` lib_symbol has letter pin numbers (D/G/S); stock SOT-23 footprint has numeric pad names (1/2/3). The naive "fix" (`pin_names=("G","S","D")` remap inside the footprint stub) created `lib_footprint_mismatch` warnings AND introduced rotation risk on JLCPCB's tape feeder.

Right pattern (audit-16): project-local `OAS:Q_PMOS_GDS` lib_symbol with numeric pin numbers + letter pin NAMES. Pin 1 binds to stock pad "1" canonically. Same approach should be reused for any future stock-letter-pin symbol that needs to land on a stock-numeric-pad footprint.

### 9. Determinism guardrail must always pass

Boardgen output must be bit-identical across consecutive runs (17 source files: `oas.kicad_pro`, `oas.kicad_sch`, 4 sub-sheets, `oas.kicad_pcb`, the two project libraries `OAS.kicad_sym` + `oas.pretty/*.kicad_mod`, etc.). Hash-randomized dict iteration, time-based content, etc. all break this. `build.py` runs the boardgen walker (`pipeline/generic/01_emit_sources.py`) twice in fresh subprocesses and aborts on any drift — step 1b is non-negotiable.

### 10. Module identification (mandatory rule for ANY board / module / dev-kit)

Never use a generic module name alone ("ESP32-C6 SuperMini", "Arduino Nano"). Generic names refer to clones from many vendors with **different pinouts and capabilities**. Every module decision MUST include AT LEAST ONE of:
- **EAN / GTIN** (preferred for Polish/EU retail) — e.g. `EAN 5904422385651`
- **Manufacturer part number (MPN)** — e.g. `ESP32-C6-DevKitM-1-N4`, `Seeed SKU 113991254`
- **Direct supplier URL** to a specific listing

Before assigning signals: read the official datasheet of the SPECIFIC model (NOT the first random pinout from a web search). Verify which GPIOs are physically exposed on the external pads. Watch for chip-level pin omissions — ESP32-C6 with internal SiP flash physically does NOT bond out GPIO 10 or GPIO 11.

---

## Lessons learned (v0.50 DFM clean)

Five concrete failure modes the v0.50 routing rework + JLCDFM clean-up exposed and recovered from. Each is a real trap the project hit.

### 11. Routing-snapshot checkpoints MUST be replay-verified before commit

The v0.50 checkpoint commit (`53e4ea9`) captured a Freerouting 89/89 snapshot into `oas_routes.py` but `build.py` was run only with `ROUTING_CHUNKS=("gnd",)` at commit time — so the snapshot's REPLAY onto the committed boardgen placement was never validated. The next session flipped `ROUTING_CHUNKS=("gnd","autoroute")`, rebuilt, and DRC went from 0 to **87 violations**: the snapshot had been extracted against a pre-Task-3 buck placement, ~2 mm off the committed pad positions, every buck-section track shorting an unrelated pad. A 30-minute checkpoint cost an entire re-route.

Rule: a routing-snapshot commit is not committable until `build.py` runs the SAME `ROUTING_CHUNKS` config that consumes it, DRC PASSES on that replay, and the captured snapshot demonstrably lands on the committed pad positions.

### 12. `tools/extract_routes.py` reads KiCad-saved boards ONLY

`extract_routes.py` parses `(net N "name")` from segment/via blocks — the modern format KiCad's interactive `Save` writes. `boardgen` emits `(net N)` (integer code only, no quoted name). Running extract against a **boardgen-emitted** `oas.kicad_pcb` silently returns **0 segments + 0 vias** and overwrites `oas_routes.py` with an empty file — catastrophic data loss with no visible error. Hit twice in one session, both times rescued by `git checkout HEAD -- oas_routes.py`.

Run extract after the routing tool has written tracks into the board (interactive route, SES import via MCP, hand-routed fix). **FIXED in v0.52**: `extract_routes.py` now resolves net references in BOTH formats — `(net N "name")` (KiCad interactive save) directly, and boardgen's `(net N)` via the board's top-level net-declaration table (unknown codes fail loudly) — and refuses to overwrite `oas_routes.py` when extraction yields zero records. A round-trip regression test (`tests/test_extract_routes.py`) asserts the committed board re-extracts byte-identically. The lesson stays as history: any future rewrite of the extractor must preserve both the dual-format parsing and the zero-record guard.

### 13. Internal-cutout "Component to board edge" — shrink the cutout, not the components

JLCDFM flagged 5 LED-ring decoupling caps (C20/C24/C25/C26/C27) at cap radius 7.0 mm as "Component to board edge distance 0.75 mm" against the **central Ø12 mm cable hole** — an INTERNAL cutout, not a panel edge. The reflex (move the caps outward) cascaded into a re-route: a 0.6 mm radial shift on tiny 0402 caps left the +5V and GND tracks crossing inside the cap's pad pair (22 DRC violations on a naive endpoint-shift transform).

The correct fix was the **opposite move**: shrink the cutout (Ø12 → Ø10, `CABLE_HOLE_DIAMETER` in `boardgen/_project.py`), which lifted cap-to-edge clearance to ~1.7 mm with **zero routing impact**. Rule of thumb: when component-to-edge fires against an INTERNAL hole (not a depaneling edge), prefer shrinking the hole first — the supply cable still passes if the slack permits, and no routing has to follow. Move components only for panel-edge clearance issues.

### 14. Via-in-pad is silent in DRC but tripped as Danger by JLCDFM

A user-placed GND stitching via at PCB-local (18.95, −40.7) sat **dead-centre on C2 pad 2** (an SMD GND pad). DRC was silent — a same-net via on an SMD pad is geometrically legal (no clearance violation) — but JLCDFM tripped two Dangers: "Lead to hole distance 0 mm" (the via's drill is *through* the SMD pad, breaking the solder land) and "Silkscreen to hole 0 mm" (silk over the via hole near C2). The same pattern hit `via:0032` sitting under a footprint silk line at X=22.15.

When placing a GND stitch via near an SMD pad, ALWAYS offset it adjacent to the pad (typically 0.6 mm centre-to-centre from the pad copper edge), never overlapping. DRC silence on same-net is NOT a DFM pass. Use `tools/jlcdfm_upload.py` to catch these before the order.

### 15. `kicad-cli` re-saves `kicad_pro` with KiCad's default `rule_severities` populated

Stage 10 `render_2d` invokes `kicad-cli pcb export svg`. The CLI loads the project, populates `board.design_settings.rule_severities` with KiCad's INTERNAL DEFAULTS (the full ~60-entry dict — `clearance: error`, `copper_edge_clearance: error`, `missing_courtyard: ignore`, etc.), and re-saves the project file. None of these are user-authored suppressions; they are just defaults made explicit by the round-trip. Stage 17 `lint_kicad_pro` (the Lesson 3 enforcement that `rule_severities == {}`) then sees the polluted dict and false-positives.

Fix: the lint re-emits `oas.kicad_pro` from `boardgen._project_files.gen_pro()` (canonical, always empty) at its start, so it always checks the source-of-truth state, not whatever `kicad-cli` last wrote. **Lesson 3 itself remains intact** — any user-authored suppression in `boardgen` survives the re-emit and trips the lint. Generalisation: any pipeline check that reads `kicad_pro` should compare against the boardgen-emitted canonical state, not against post-`kicad-cli` content.

---

## Lessons learned (v0.51 CI expansion)

Four patterns from the post-v0.50 CI expansion (pipeline grew 29 → 35 stages; +5 new OAS checks + cascade extension to stage 08).

### 16. Worst-case SPICE deck for ONE question ≠ realistic deck for another

Stage 27 surge runs TWO simulations in one stage. **Sim 1 (worst-case for Q1)**: C1=1 µF, F1 omitted, drain isolated — stresses Vds(Q1), got 2.77 V vs 30 V limit (comfortable PASS). **Sim 2 (realistic for LM2596)**: C1=100 µF with 50 mΩ ESR + F1 cold-R=0.1 Ω + C5+C6=32 µF input bypass — got vlm_peak=27.0 V vs 40 V abs max. The drain spike from Sim 1 (67.6 V) was **mostly model artifact** — 40 V of it absorbed by the realistic bulk caps + F1 in Sim 2.

When a SPICE finding looks alarming, re-check whether the parameters were deliberately stressed in a direction orthogonal to the new question. If yes: write a second sim with parameters tuned to the new question — don't trust the worst-case numbers across question boundaries.

### 17. TypedDict + NotRequired for shared metadata dicts

`POWER_BUDGET: list[PowerBudgetEntry]` (TypedDict in `boardgen/_project.py`) with `NotRequired[str]` on optional keys (`note`, `radio_group`). Consumers import via `if TYPE_CHECKING: from boardgen._project import PowerBudgetEntry` to keep static typing without runtime import cycles.

Without TypedDict, mypy treats dict values as `object` → consumer-site coercions (`float(e["peak_ma"])`, `setdefault(rail, [])`) trip `arg-type` errors. Stage 15 mypy lint (`--check-untyped-defs --warn-unreachable`) is the enforcer. Side effect: defensive runtime `not isinstance(entry, dict)` checks become statically unreachable — delete them; the TypedDict enforces structure at type-check time.

### 18. Shared SPICE infrastructure goes in `pipeline/oas/_spice.py` (underscore-prefixed)

The `_` prefix excludes it from `build.py::discover_stages` glob `*/[0-9][0-9]_*.py` (same trick `pipeline/jlcpcb/_rotations.py` uses). Generic ngspice helpers extracted there — `ensure_ngspice()`, `_download()`, `parse_meas()`, `CheckResult`, `run_ngspice()`, `write_spice_init()` — now consumed by stages 08, 27, 28. Topology-/model-specific code (LM2596 model fetch, render functions, acceptance windows) stays in the consuming stage.

Pattern for any future ngspice consumer: import from `_spice.py` first; if a helper is genuinely cross-stage, it belongs there. ONE cross-stage primitive per concern — no kitchen-sink module.

### 19. Behavioural fallback when TI PSpice models don't fit ngspice

Stage 08 cascade buck simulation needed TPS62933 on the 3V3 rail. TI's encrypted `slum790.zip` (the actual fixed-SS variant we use, U2 = TPS62933DRLR) does not load in ngspice — encrypted PSpice. The plaintext `slum818.zip` (TPS62933**P** ext-SS variant) loads via `set ngbehavior=ps`, but **timestep-collapses around 60 µs of sim time** under ngspice 46 — the internal SS state machine triggers step explosion before useful output.

Fallback: behavioural averaged model (~40 SPICE lines) with datasheet-derived parameters — SS τ=1.4 ms, UVLO=3.0 V, η=95 %, Vref=0.8 V, LC filter 22 µF / 2.2 µH. Document the proxy clearly in the stage docstring. The cascade dynamics question (does 3V3 dip during LM2596 ramp?) is identical for both real and behavioural; the model is approximate, but the answer is robust.

The same trick applies the other direction: stage 08's LM2596-alone check uses the REAL TI PSpice model (small 3 ms window — converges fine); the cascade portion switches to a behavioural LM2596 too (60 ms window with switching detail = millions of timesteps, exceeds the 300 s ngspice timeout).

### 20. A pin order is meaningless without the orientation it is read against — and it changes when the PART changes (LD2410C, GitHub issue #9)

**Orientation convention (this is the definition; the pin order below is only valid against it).** The HLK-LD2410C mounts with its two copper patch antennas facing **UP** — away from the OAS PCB, toward the AK-N-94 perforated cover — because the radar has to look into the room. Viewed antenna-face-toward-the-observer with the pin row along the module's NORTH edge (which is exactly the ordinary PCB top view, looking down at the board), the pins run **FROM LEFT (west)**:

**pin 1 = UART Tx, pin 2 = UART Rx, pin 3 = OUT, pin 4 = GND, pin 5 = VCC**

On the OAS PCB that means: the J4 hole row runs east–west along PCB +X with pin 1 at the WEST end, and the module body extends SOUTH from the row. Authority: board owner, 2026-07-21, plus Hi-Link HLK-LD2410C manual V1.00 (2022-11-07) Table 1 / §4.2 — pin 1 carries the **square** pad, pins 2..5 are round; there is no printed "1". The mapping is enforced by stage 19 check D against the `j4-p1-tx` … `j4-p5-vcc-down` wire uuid tags in `boardgen/_sch_sensors.py` plus `J4_PCB_ROTATION == 90` in `boardgen/_project.py`. Note the net-name crossover: J4 pin 1 = module TX lands on the `LD2410_UART_RX` net (it arrives at the ESP32's RX, GPIO 0), pin 2 = module RX on `LD2410_UART_TX` (driven by GPIO 1). The pair carried the bare names `UART_TX` / `UART_RX` while it sat on GPIO 16/17; those names now belong to the console at J2 (Lesson 23).

**This is the MIRROR of what this Lesson said until v0.53.** The HLK-LD2410B ran `1 = OUT, 2 = TX, 3 = RX, 4 = GND, 5 = VCC` on a 1.27 mm castellated edge. Same manufacturer, same radar, same 256000-baud protocol — different pin order, because the -B and the -C are different boards. Anything quoting the -B mapping for the current design is wrong, and so is espboards.dev's "VCC, GND, TX, RX, OUT", which is the -C row read from the far end (the failure this Lesson is about: a row of pins has two ends, and a bare list of names does not say which one it starts at).

Two independent ways this project has been bitten here, both worth remembering:
- **Reading a row from the wrong end.** The pre-v0.15.8 -B schematic had VCC ↔ OUT reversed. The v0.15.8 "fix" reversed the SCHEMATIC nets — wrong layer; the real defect was the J4 footprint rotation putting pad 1 at the wrong physical end. Corrected structurally at the footprint layer in v0.43.
- **Assuming a variant suffix is cosmetic.** The -B → -C swap changes pin order, pitch (1.27 → 2.54 mm), body (35 × 7 → 22 × 16 mm) and mounting style. Re-read the manual for the exact variant; do not carry a mapping across a part change.

Do NOT rely on memory or a web snippet for LD2410 pin order. Quote this Lesson plus the manual for the specific variant, and state the viewing orientation alongside the order.

⚠ **Open verification (issue #9 acceptance criterion).** The physical LD2410C had not been delivered when the J4 rework landed. Body 22 × 16 mm, 2.54 mm pitch and Ø0.9 mm holes are datasheet-stated; the pin-row inset from the pinned edge (1.42 mm), the pin-1 end inset (5.92 mm, derived from "row centred"), the antenna-patch rectangle and the module thickness are MEASURED off the manual's Figure 5 or estimated. Check them with calipers on the delivered module before the next PCB order — see the ⚠ block at `LD2410_BODY_W` in `boardgen/_project.py` for what each one would cost if wrong (all silk-only except the standoff budget).

---

## Lessons learned (v0.53 prototype bring-up)

### 21. J3 (SEN66) board-side pinout MIRRORS SEN6x Table 16 — a flat JST GH lead reverses pin positions end-to-end (bench-confirmed 2026-06-30)

Sensirion SEN6x datasheet v0.92 (Dec 2025) Table 16 (p. 15) specifies the **MODULE-side** receptacle: 1=VDD, 2=GND, 3=SDA, 4=SCL, 5=GND (tied to 2), 6=VDD (tied to 1). The OAS board-side J3 must be wired as that table's positional MIRROR — **1=VDD, 2=GND, 3=SCL, 4=SDA, 5=GND, 6=VDD**. Mechanism, in three steps: (a) both cable ends are polarized GH-family connectors — the latch/shroud keying makes reversed insertion impossible, so housing position N always mates header pin N (JST GH datasheet p. 1, "housings are designed to prevent incorrect mating"); (b) a standard flat parallel-wire GH lead has both housings crimped on the same face of the wire row, which between two face-to-face headers maps header-A pin k ↔ header-B pin 7−k — a full positional mirror (1↔6, 2↔5, 3↔4); (c) Sensirion's pinout is deliberately power-symmetric (pins 1/6 and 2/5 internally tied), so the mirror is invisible on the power pins and manifests ONLY as an SDA↔SCL swap. The v0.51 boards copied Table 16 pin-for-pin onto J3 → SEN66 powered up but never ACKed at 0x6B; swapping the I²C pins in firmware (`sda: GPIO7 / scl: GPIO6`) made it fully functional with a straight cable — the bench proof of the crossing (issue #6). Fix (this Lesson's origin): J3 pins 3/4 swapped in `boardgen/_sch_sensors.py` (wire tags `j3-p3-scl` / `j3-p4-sda`); on copper, the corridor nets swap at the two I²C bridge vias, which made the pre-existing west-end braid (each via fed the OPPOSITE F.Cu trunk) unnecessary — replaced by two direct via→trunk connectors (−4/+3 segments); firmware defaults back to `sda: GPIO6 / scl: GPIO7` with a substitution override for v0.51 boards (`firmware/esphome/examples/v0.51-board.yaml`). Enforced by stage 19 **check E** anchored to the `j3-p*` wire tags. Any future audit asserting "J3 pin 3 must be SDA because Table 16 says pin 3 = SDA" is WRONG — Table 16 is the module side; the host side mirrors. CAVEAT: the design standardizes on the flat parallel-wire GH lead (the style verified on the bench); an opposite-crimp lead (housings on opposite faces of the wire row — electrically position-1:1, the Qwiic-cable style) would re-cross SDA/SCL on the fixed board. Check the crimp style when sourcing replacement cables.

### 22. A dimension VALUE reused for the wrong feature survives circular sum-checks — measure the drawing, and treat bench collisions as evidence against the model

`ESP32_PIN_START_OFFSET` was recorded as 5.37 mm (pin 1 → antenna edge) from v0.15 until the issue-#3 review. 5.37 IS on the Espressif DevKitM-1 dimensions drawing — but it dimensions the **antenna-tab protrusion** (module sticking out past the board edge), not the pin inset. The correct pin-1 inset is **1.575 mm**, derived from the dimension the drawing actually provides on the pin axis: last pin → USB edge = 11.125, so 48.26 − 14×2.54 − 11.125 = 1.575. The wrong value survived for months because its "verification" was circular: the complementary 7.33 inset was back-derived from the wrong 5.37 (5.37 + 35.56 + 7.33 = 48.26 ✓) instead of read from the PDF, so the sum-check could never fail. Two tells were missed: (a) the SAME number appearing for two different features on one drawing is a red flag, not a coincidence to be annotated; (b) **the bench symptom was issue #3 itself** — the physical module sat 3.795 mm further toward the caps than the drawn shadow, which is exactly why C1/C3/C4 "unexpectedly" blocked seating while the layout showed clearance. When physical reality contradicts the drawn model, suspect the model's anchor dimensions before rearranging the board. Corollary for all mech-ref daughterboards: the connector/socket positions are the PHYSICAL datum (they define where the real module sits); body outlines must be derived from them, and a placement test should pin the datum (socket X), not the derived anchor.

### 23. A devkit's console pins carry a SECOND driver — releasing the SoC's UART peripheral does not release the bridge chip soldered to the same pads (bench-confirmed 2026-07-22)

The LD2410's UART sat on **GPIO 16/17** from v0.4 to v0.53 on the reasoning that they are "just the default UART0 pins" and the ESP32-C6's GPIO matrix can route UART0 elsewhere. That reasoning is about the SoC only. On the **ESP32-C6-DevKitM-1** those two pads are also wired, through **populated 0 Ω links R9 → CP2102N RXD (pin 25) and R7 → CP2102N TXD (pin 26)**, to the onboard USB-UART bridge — and the bridge's **VDD (6) + REGIN (7) are tied to `VCC_3V3`**, i.e. to the BOARD 3.3 V rail OAS drives at J5.1, *not* to USB VBUS (pin 8 only sees an R19/R18 sense divider). All read first-hand off `esp32-c6-devkitm-1-schematics.pdf` page 2. So the bridge is powered whenever the unit is, and its TXD is a push-pull output permanently parked on the ESP's RX net. Bench proof on a v0.51 board with the radar unpowered (24 V off) and the bridge's own USB port EMPTY, probing with internal pulls: `GPIO2 pu=1/pd=0 FLOATING`, `GPIO16 pu=1/pd=0 FLOATING`, **`GPIO17 pu=1/pd=1 DRIVEN`** — GPIO 17 held HIGH against its own pull-down, with nothing on that net but CP2102N TXD. Two push-pull outputs on one node; the radar's Tx had been fighting the bridge since the first prototype. Fix: the pair moved to **GPIO 1 (TX) / GPIO 0 (RX)** — free, adjacent, non-strap pads on J5, the socket row nearest J4 — nets renamed `LD2410_UART_TX` / `LD2410_UART_RX`, and `UART_TX` / `UART_RX` kept for the true console, which stays on GPIO 16/17 and reaches only the DNP recovery header **J2** (that header exists to serial-flash a module whose USB ports are dead, so it belongs on the ROM bootloader's own pins and must NOT follow a peripheral around). GPIO 16/17 are now in `GPIO_RESERVED`, and stage 06 grew a **console-pin check** that fails if any refdes other than J6/J2 appears on either console net — a dict entry is a comment, a check is a guarantee. Two generalisations, both cheap: (a) for any dev module, read its schematic for what ELSE hangs on a pin — not just the SoC datasheet's alternate-function table, and note that populated 0 Ω links are wires, not options; (b) when a pin misbehaves, probe it with the peripheral **unpowered and every cable unplugged** — whatever still drives it is on the module. Sanity-check of the replacement pins by the same method: GPIO 0/1 double as XTAL_32K_P/N and the DevKitM-1 *does* carry the whole 32.768 kHz network — but Y1, C4/C5 (12 pF) and R1 (10 M) are all annotated `(NC)` on that schematic and only the 0 Ω links R3/R2 to the header are populated, so the pads are electrically bare.

### 24. A GND pad can sit inside the pour and still be unconnected — thermal-relief spokes need room the dense corners don't have

The v0.53 re-route kept reporting a handful of `unconnected_items` between the GND zone and an SMD GND pad, and **the set changed every single time the board was re-routed**: `{C8.2, J3.2, J3.5}` → `{U2.1}` → `{C15.2}` → `{D14.4, U2.4, C20.2, D12.4}` → `{D15.4, C25.2, J5.13, J9.1}`. Chasing them one at a time is whack-a-mole and never converges.

Cause: the GND zone connected pads with **thermal reliefs** (`thermal_gap 0.5`, `thermal_bridge_width 0.5`). A spoke needs 0.5 mm of clear width through the pad's 0.3 mm clearance ring; in the crowded corners the signal tracks leave less than that, so the pour surrounds the pad but never bonds to it. **Which** pads lose their spoke is a property of how the routing happens to crowd them — hence a fresh orphan set per route. Diagnostic that pins it down: fill the board with **no signal routing at all** and re-run DRC — 0 unreachable GND pads, proving the pour geometry is fine and the routing is what starves the spokes.

Fix at the source: `(connect_pads thru_hole_only)` on the GND zones — solid fill onto SMD pads, thermal reliefs kept for PTH. That removed the entire class in one change (9 orphans → 0 SMD orphans). PTH keeps reliefs deliberately: J1 / J4 / J5 / J6 / C1 / C3 / C4 are hand-soldered and a pin bonded solid to both ground planes is miserable to heat. Do NOT "fix" this class by adding rescue vias per pad; that treats the symptom and the next re-route invents new ones.

### 25. Pre-place GND rescues BEFORE routing — a pad boxed in by its neighbours' escape tracks cannot be rescued afterwards

J3 pin 5 (GND) sits between pin 4 (SDA) and pin 6 (+3V3) at 1.25 mm pitch. Once those two nets are routed, their escape tracks close every side of pin 5: measured slack 0.25–0.29 mm against a 0.325 mm requirement, and **no via spot within 7 mm** in any direction. Routed last it is unreachable; placed first, a straight 1.46 mm run due east is free. Same for U2.1 / C15.2 in the buck corner.

So GND rescue track+via pairs go on the board FIRST, then the DSN is exported, then Freerouting routes the signals around them. Two gotchas: (a) KiCad does **not** export GND copper into the DSN (GND is a plane; the `(wiring)` section comes out empty), so the rescues are invisible to the router — feed them back as injected keepouts covering the via body and the track corridor; (b) an existing DSN keepout's coordinate list **wraps over many lines**, so inserting after its first newline lands mid-polygon and Freerouting dies with `Cannot read field "shape_list" because "p_area" is null` — walk balanced parens to find the real end.

Rescue-geometry rules, both of which DRC will NOT enforce for you because it ignores same-net conflicts: a via must clear every pad's **copper edge** (≥0.60 mm centre-to-edge, Lesson 14) — measuring from the pad CENTRE silently puts the via on top of its own pad — and two vias must stay ≥0.90 mm apart centre-to-centre, or two same-net GND stitches will share a drill.

### 26. Nobody checks same-net geometry for you — and a local audit that models pads as boxes will invent findings instead

Two halves, learned in one JLCDFM cycle on the post-#9 re-route.

**The fab's DFM is not a backstop for same-net defects.** A GND stitch via sat with its **drill 0.07 mm inside D18.4's pad copper** — a broken solder land. JLCDFM scored **0/0/0 on BOTH** "Via to pad" and "Via placed within a pad", and DRC is silent by definition (same net is not a clearance conflict). It surfaced only in an offline audit. The same scan *did* catch a via ring overlapping C17.2 and two vias under silk, so the scanner is not blind in general — it is blind on this class. Anything that places copper programmatically (the island stitcher here, which only asks "is this point inside GND on both layers" and knows nothing about pads or silk) must be audited locally against pad copper edges, silk strokes, foreign copper and via-to-via spacing before the gerbers go out.

**But the audit itself is where the traps are**, and all of them push the same way — toward fake findings:
- **Pad shape.** A rotated-rectangle model turns a circular THT pad into its circumscribed square, whose corners stick out 0.207·d beyond real copper. Every 45° fanout track clips that phantom corner: ten "traces crossing a mask opening", all ten diagonals, all ten false. Roundrect pads have the same bug more mildly — enough to fabricate sub-0.20 mm foreign-net gaps on a board DRC calls clean. The rect hull is the right *conservative* model for placing a via (it over-reserves space); it is the wrong model for *judging* an existing feature.
- **Track end caps.** Where segment A ends and segment B begins, both round caps are the *same disc at the same point*. If A legitimately lands on a pad, B "penetrating" that pad adds **zero** copper — flagging B fires on every corner just outside a land, which is how fanout normally leaves a pad.

**The cheap sanity check that catches all of it:** if a computed FOREIGN-net gap comes out below the DRC clearance rule while DRC reports zero violations, the computation is wrong, not the board. DRC does the geometry properly; disagreement means the model is broken. Reach for that check before reporting anything, and never hand a "finding" to the user without it.

**A third way to get it wrong, found by review of the check itself:** the first version of `Pad.distance_to()` applied the FORWARD rotation where the inverse was needed. Composing the same matrix twice is a rotation by 2θ — invisible at 0/90/180/270 (every pad shape is symmetric under 180°) and therefore invisible in a board-wide run, but at 45/135/225/315 it SWAPS w and h. It biased **optimistic**, understating distances to exactly the LED-ring pads where the stitcher drops GND vias. Note the asymmetry with the two traps above: those invent findings and get ignored; this one hides them and gets trusted. Whenever a geometry helper takes an angle, test it at 45° — the cardinal angles cannot distinguish a transform from its inverse.

**Now enforced, not just documented:** `tests/test_via_geometry.py` (pytest, so it runs in stage 16 on every `build.py`) asserts that no via's copper ring reaches any pad's copper edge on ANY net, and that no two vias sit closer than 0.90 mm. It models circle / oval / rect / roundrect pads in closed form — deliberately no bounding boxes, per the trap above — and carries a parse guard (a regex that stops matching would otherwise make every assertion vacuously true, the Lesson 12 failure mode). The threshold is the manufacturing hazard (0.05 mm between the via's 0.35 mm ring and pad copper), NOT Lesson 25's 0.60 mm placement target: two vias on the current board sit at 0.563 / 0.600 mm centre-to-edge and are physically fine, and churning good geometry to satisfy a round number is not a fix. Verified to bite: re-injecting the exact via JLCDFM scored 0/0/0 on reports −0.2736 mm and fails the suite. Silkscreen-to-hole is deliberately NOT covered — it needs stroke-rendered text from the silk gerber, which does not exist until stage 20, and JLCDFM has caught that class reliably on every pass.

Corollary on reading a scanner: JLCDFM's "Solder mask opening exposing trace" reports ~0.045 mm *less* than the true copper-to-copper gap (it applies its own mask expansion — the July pass said 0.15 mm for a track measured at 0.196 mm). So with a 0.20 mm clearance rule, a track routed at exactly the design clearance necessarily trips it. Calibrate a vendor metric against a known case before chasing it.

---

## Lessons learned (v0.54 firmware)

### 27. An LED brightness scale is only as fine as its 8-bit output AFTER gamma — design the scale and the effects in LED-output steps

The ring ran at 25-30 % on the light's scale — LED output 5-9 of 255. Two complaints came from that one fact. (a) The 0-255 slider was "too big": light brightness 1..40 of 255 (the bottom 16 %) all land on the same dimmest step — output 1 on ESPHome 2026.9+, whose gamma LUT never returns 0 for a non-zero input; on 2026.8 part of that band rounds to 0, i.e. dark. "Ring Max Brightness" plus a hidden 5 % night multiplier on top of that scale was opaque — night mode resolved to that dimmest step (or off), which read as "the ring turns itself off". (b) "AQI Breathing" (colour × cosine envelope, left to the gamma table) had only ~5 distinct outputs between trough and peak — visible jumps — and its 15 % pre-gamma floor sat on the dimmest step for ~40 % of each cycle, so every swell seemed to start late. Fix: the light entity went **internal** and the user-facing controls became plain entities in the order the owner specified (on/off, mode, brightness, night mode, night brightness ≤ brightness, night hours); brightness is **ten levels matched to distinct LED outputs over the full range** (1, 2, 3, 5, 10, 19, 36, 69, 133, 255 — geometric, ~1.9x per step, level 4 anchored at the old 25 % = the temperature-calibration setting), each level's light brightness = the top of its output band computed against ESPHome's own integer pipeline (`esp_scale8_twice` + the uint16 gamma LUT; identical on 2026.8 and 2026.9); the breathing effect computes final LED values itself: peak read back through the light's pipeline (`get_*_raw()`), a perceptually even envelope with a floor at 20 % of peak output (never below 1 step), **spatial dithering across the 7 LEDs** (1/7-step resolution behind the diffuser), written through an identity `ESPColorCorrection`. Rules: never offer a raw 0-255 control for a dim indicator; simulate the exact integer pipeline before choosing numbers (and check it across ESPHome versions — the rounding changed between 2026.8 and 2026.9); and when a smooth animation must run at a handful of output steps, dither across LEDs rather than trusting the gamma table.

---

## 🔴 Public repository rules

**This is a PUBLIC repository.** Every committed file MUST follow these rules. No exceptions.

1. **English only.** All committed content (documentation, source comments, identifiers, schematics, BOM, commit messages, PR / issue text) is written in English. Chat with the assistant can happen in any language; the assistant writes repo content in English regardless.

2. **No personal information.** No names, addresses, room counts, specific buildings, SSIDs / MAC addresses / hostnames, specific tariffs / utility providers, or photos showing identifiable backgrounds or people. Geographic references limited to what is technically necessary (e.g. "230 V AC / 50 Hz mains" is fine; "house in [town]" is not).

3. **Generic framing.** Describe design decisions in technical terms, not personal ones. ✗ "10 rooms in the user's house" → ✓ "multi-unit deployment (typical: 5–20 units)".

4. **Default to redaction.** When in doubt, remove the information. Once pushed to a public repo, a privacy leak is permanent (git history, mirrors, archive.org, AI training datasets).

5. **Secrets handling.** `secrets.yaml` is gitignored — only `secrets.yaml.example` with placeholders is committed. No API keys / tokens / passwords in any committed file (including comments, commit messages, screenshots). WiFi credentials live only in the user's local `secrets.yaml`.

6. **Third-party intellectual property is NOT redistributable through this repo** unless explicitly under a permissive license. This includes manufacturer DXF / STEP / datasheets, vendor reference schematics, supplier-provided photos / renders. Reference by URL or part number, derive your own work from measurements, or keep locally with a gitignored pattern.

---

## Status

**v0.54 — BUILT, VALIDATED, RELEASED (2026-09-14).** The v0.54 boards were manufactured (JLCPCB SMT), delivered 2026-09-04 and brought up with the repeatable bench check (`firmware/tools/bringup_check.py`); units are deployed and feed Home Assistant automations. Firmware `project_version` is `v0.54` (matches the silkscreen). Bench findings folded into the firmware: SEN66 STAR temperature compensation inside the module, LD2410C per-gate thresholds with gate 0 disabled and the radar's Bluetooth kept off, OTA-rollback timing, dashboard grouping. Two limitations found on the built units: (1) the SEN66 needs an air duct from the perforated cover to its inlet, and that duct sits in front of part of the LED ring — the light effect is weaker than intended (this settles the "foam shroud / cover baffle" TODO in favour of a duct; the duct design is not in the repository yet); (2) detecting a sleeping person relies on the presence timeout, not on the still-target thresholds (see `packages/presence.yaml`). The GitHub release for this revision carries the production files. The paragraph below records the order-approval state as it stood on 2026-07-23.

**v0.54 — ORDER-APPROVED (2026-07-23, historical).** The board is the `599b8a6` copper — the Q1 reverse-polarity fix (drain-on-input / source-on-load, `d24d855`, issue #10) plus the full signal re-route it forced (373 seg / 37 via) — with the silkscreen version bumped `v0.53 → v0.54`. A second five-reviewer GO/NO-GO panel returned **5 × ACCEPT** (electrical / routing-DFM / BOM-CPL / verification-integrity / holistic), reversing the 2026-07-22 panel's 4-REJECT verdict now that its only copper blocker (Q1 S/D swap + F1 order) is fixed and independently re-verified (each reviewer proved its own gate non-vacuous — e.g. `05_check_dc` fires `V_24V_PROT = −23.1 V` on a re-swapped Q1). `build.py` **35/35 PASS**, DRC 0/0, 78/78 pytest, JLCDFM on `599b8a6` = PCB 0 Danger / 5 explained Warning + SMT 0/0.

**Three order-time gates remain (NOT board changes — do them right before clicking order):** (1) **Fresh JLCDFM on the v0.54 gerbers** — the version bump changed the silk by one glyph (the board-id text block in the far-west pocket, nowhere near copper/holes/edges), so the JLCDFM-clean result above is owed a re-confirm on the exact v0.54 ZIP. (2) **Assembly Order XLS diff must explicitly cover the 7 SKUs `34_check_lcsc_offline.py` silently skips** — above all the two regulators **C116713 (LM2596)** and **C3200405 (TPS62933)**; the stage validates only 16/23 SKUs and prints success without disclosing the gap (footprint-pattern bugs — Lesson 5's exact failure mode). (3) **U2 Confirm Parts Placement + Photo Confirmation** — the SOT-583-8 land is 180°-symmetric so no file check can prove orientation; the CPL `+180` is owner-confirmed, and the pin-1 dot must read **NW** on the placement photo. **Owner-waived, do not re-open:** issue #9 LD2410C radar bench/caliper gate (presence may not work — accepted); component stock.

**v0.53 routing — COMPLETE (re-routed after GitHub issues #9 + the GPIO16/17 UART re-pin).** The board is fully routed and DRC-clean on the current placement: `ROUTING_CHUNKS = ("gnd", "autoroute")`, DRC **0 violations / 0 unconnected pads**, `EXPECTED_UNCONNECTED = 0` in `pipeline/generic/03_drc.py`, `build.py` **35/35 PASS**. Snapshot in `oas_routes.py`: **375 segments + 38 vias**. Flow (all helper scripts kept under the session scratchpad, not committed): export DSN → **grow the Edge.Cuts keepouts 0.12 mm** (the DSN carries only the 0.20 mm copper clearance, so the router otherwise parks tracks ~0.21 mm off the cable-hole rim and trips the 0.30 mm 'Trace to Outline' rule) → Freerouting 2.2.4 (Docker `eclipse-temurin:25-jre`), 83/83 nets → SES → snapshot → island-to-plane GND stitch vias → hand-close whatever the router left short. Two structural findings from this pass are recorded as **Lesson 24** (GND-pad thermal-relief orphans — the reason the zone now uses `connect_pads thru_hole_only`) and **Lesson 25** (pre-place GND rescues BEFORE routing; a pad boxed in by its neighbours' escape tracks has no via spot afterwards). **The earlier issue-#8 re-route (390 seg + 45 via) is superseded** — it predates the J4 rework and the UART move. Historical detail of that pass follows, since its placement lessons still hold: it ran against the then-committed placement — **100% coverage, 0 unrouted nets** — using the "stitch-then-route" flow (GND stitch vias pre-placed on the unrouted board so Freerouting routes signals around them), then the fragmented F.Cu GND pour was reconnected to the continuous B.Cu plane by island-to-plane stitch vias (each dropped at an isolated island's interior point that also sits inside the other layer's main pour — see `tools/` helper scripts). Final snapshot in `oas_routes.py`: **390 segments + 45 vias**. One placement change was needed to relieve congestion that boxed the buck decoupling-cap GND pads into un-viable pour islands: the buck 2-row grid corridor was widened from 5.7 mm → 9.0 mm (Row N Y −33.5→−32.5, Row S Y −40.7→−41.5; see `boardgen/_footprints_placement.py`). `oas.kicad_dru` JLCDFM-strict rules (0.20 mm clearance, 0.70/0.30 mm vias, 0.25 mm track) held throughout. Route-dependent checks/tests (stage 26 I2C rise-time, extract-routes round-trip, snapshot-sanity suites) all re-armed and pass — no skips remain. The manual `tools/jlcdfm_upload.py` pass is DONE (2026-07-19): PCB **0 Danger** after the silk-to-hole + mask-exposing-trace fixes; the only remaining findings are the 4 proven-phantom mask-expansion warnings (see the TODO entry below). Both Edge.Cuts internal openings and the LED-ring caps came through clean.

**v0.51 boards ordered at JLCPCB on 2026-05-24** (prototype run, 5 units, full SMT assembly, PCBA Standard tier with Confirm Parts Placement + Photo Confirmation enabled per Lesson 5; Assembly Order XLS diff verified clean against `lcsc_mapping.py` before payment — awaiting delivery). Bare PCB carries the v0.51 silkscreen on top of the v0.50 routing snapshot (89/89 + hand-stitched GND). One BOM deviation accepted at order time: **J3 = XY-SM06B-GHS-TB clone** (genuine JST GH SM06B-GHS-TB C133065 was out of stock at LCSC; XY clone is mechanically equivalent for the 1.25 mm JST GH cable mate — accepted for the 5-unit prototype; if the SEN66 cable latch proves unreliable in the clone, genuine JST will be swapped in by hand from TME/Mouser). Schematic + PCB layout closed. Every placed footprint header uses canonical `<lib>:<name>` from KiCad stock or `oas:<name>` from the project-local library — zero bare names. Custom `oas:` geometry is used only where a stock entry is absent OR geometrically wrong for the exact ordered part; every such case is enumerated in the "Deviation budget" with a technical reason.

**v0.50 routing — COMPLETE.** The board is fully routed and DRC-clean: `ROUTING_CHUNKS = ("gnd", "autoroute")`, `build.py` **35/35 PASS** (post-v0.51 CI expansion), DRC **0 violations / 0 unconnected pads**. The signal routing was re-run with Freerouting 2.2.4 (Docker) against the *current* committed placement — full **89/89** coverage, 0 unrouted nets — then imported, and the fragmented F.Cu GND pour was hand-stitched in KiCad (GND pour fragments reconnected to the continuous B.Cu pour by stitching vias + short GND tracks). Final snapshot in `oas_routes.py`: **613 segments + 42 vias** (two GND stitch vias removed by the post-v0.50 DFM fixes — Lesson 14 via-in-pad + the J4 UART_RX re-route; `tools/extract_routes.py`). `EXPECTED_UNCONNECTED` in `pipeline/generic/03_drc.py` is now `0` (the board is fully routed; any non-zero count is a regression).

Note on the GND pour: Freerouting sees GND as an idealised `plane` (every pad on the plane = connected), so it never routes GND stitches. The F.Cu pour only fragments later, when KiCad re-fills the zone around all 89 signal nets — a zone-fill artifact downstream of Freerouting. Hand-stitching the fragments is the standard remedy and does not degrade the GND plane (the stitches are supplementary to the pour).

Firmware skeleton (5-package ESPHome config) landed v0.40-post-order; awaiting hardware delivery for actual flashing.

---

## Project goals

Per-room sensor measures:
- **Air quality**: CO2, PM1 / 2.5 / 4 / 10, VOC index, NOx index, temperature, humidity (Sensirion SEN66)
- **Occupancy / presence**: mmWave radar with stillness detection (HiLink HLK-LD2410C)

Additional features:
- RGB AQI status ring (7 × SK6812-SIDE LEDs) with breathing effect; color reflects aggregated air quality index
- Bluetooth proxy (software-only) — extends BLE range across the deployment for Home Assistant BLE integrations
- Qwiic / Stemma QT expansion port — future sensors without PCB respin

---

## Hardware

### Enclosure
- **SZOMK AK-N-94** — Ø128 mm perforated white ABS, smoke-detector form factor.
- Manufacturer DXF / datasheet are third-party files and **not committed to this repo** (Rule 6). Keep locally; everything outside `hardware/kicad/` / `hardware/output/` / `hardware/renders/` is gitignored.
- Derived dimensions (own work, used in KiCad):
  - PCB: **Ø120 mm D-shape** (arc R = 60 mm), flat chord 82.6545 mm.
  - 3 × M3 mounting holes (Ø3.8 mm, **NPTH**) on Ø110 mm pitch circle: positions (±47.631, +27.500) and (0, −55.000).
  - **Central Ø12 mm cable pass-through hole** for 24 V supply entering from the rear of the enclosure.
- **Front-side height limit**: 17 mm default, **22 mm in the SEN66 zone** (per AK-N-94 physical-sample verification). Back side: 5 mm max (with 2 mm washers under the M3 mounting screws lifting the PCB off the bosses).

### Module list (v0.40 final)

> Authoritative metadata (EAN, MPN, datasheet URLs, sourcing notes, derived dimensions) lives in `hardware/kicad/boardgen/_project.py::EXTERNAL_MODULES`. The table below is a quick-reference summary.

| Function | Component | LCSC / source | Interface |
|---|---|---|---|
| MCU | **ESP32-C6-DevKitM-1-N4** (Espressif, EAN 5904422385651) | Botland | USB / GPIO |
| Air quality combo | Sensirion **SEN66-SIN-T** (material 3.001.030) + JST GH 6-pin cable accessory (50 cm AWG26, separately ordered — Sensirion ships SEN66 without cable) | Sensirion / LaskaKit / ThePiHut | I²C 0x6B |
| Presence | **HiLink HLK-LD2410C** (-C variant specifically — the -B has a different pin order, pitch and body; see Lesson 20) | HiLink direct / reputable distributor | UART 256000 baud |
| Visual indicator | **7 × SK6812-SIDE** (OPSCO SK6812SIDE-A, 4020 side-emit) on Ø26 mm pitch ring, 8 slots at 45° pitch with D13 skipped for J1 cable area | LCSC C5378721 | 1-wire WS281x |
| Power input | Phoenix Contact MSTBA 2,5/3-G-5,08 3-pos terminal | THT hand-solder | 24 V DC |
| Reverse-polarity | **AO3401A** P-MOSFET (SOT-23) + BZT52C10S Zener clamp (SOD-323) + 100 k pull-down + 1 k gate series | LCSC C15127 / C19334 / C25803 / C21190 | — |
| TVS | **Brightking SMBJ24A** (SMB, unidirectional 24 V) | LCSC C87268 | — |
| PTC fuse | **Littelfuse 1812L075/33DR** (750 mA hold, 1.5 A trip, 33 V) | LCSC C151170 | — |
| Buck 24 V → 5 V | **TI LM2596S-5.0/NOPB** (async, TO-263-5) + CENKER CKCS5040-33µH/M (C354612) + MDD SS14 (C2480, freewheel) | LCSC C116713 | ~76% η |
| Buck 5 V → 3.3 V | **TI TPS62933DRLR** (sync, SOT-583-8) + CENKER CKCS5040-2.2µH/M (C354602) + UNI-ROYAL 100 k / 30.9 k FB pair | LCSC C3200405 | ~95% η |
| 24 V terminal | J1 Phoenix MSTBA 2,5/3-G-5,08 (THT hand-solder) | — | — |
| Qwiic expansion | J9 genuine JST SH SM04B-SRSS-TB (4-pin horiz SMD) | LCSC C160404 | I²C |
| SEN66 socket | J3 genuine JST GH SM06B-GHS-TB (6-pin horiz SMD) | LCSC C133065 | I²C via cable |
| Flashing | Either of DevKitM-1's two onboard USB-C ports (USB-UART bridge or native USB-Serial-JTAG) | — | USB 2.0 |

ESP32-C6-DevKitM-1-N4 is the Espressif official devkit (ESP32-C6-MINI-1 SoM + two USB-C ports + buttons + onboard RGB NeoPixel + power LED). Form factor 48.26 × 25.4 mm. Chosen over generic "SuperMini" clones for deterministic pinout, full Espressif documentation, and verified Polish-distributor availability.

### ESP32-C6-DevKitM-1-N4 pinout (final)

> Authoritative pin assignment lives in `hardware/kicad/boardgen/_project.py::GPIO_ASSIGNMENTS` and `GPIO_RESERVED`. The table below is a quick-reference summary. `pipeline/oas/06_check_boot.py` cross-checks the schematic against the dict on every build.

| Pin | Function | Notes |
|---|---|---|
| GPIO 6 | I²C SDA | shared bus: SEN66 (0x6B), J9 Qwiic |
| GPIO 7 | I²C SCL | shared bus, **4.7 kΩ pull-ups on MCU side** (220 mm total bus length — see "Shared I²C bus" below) |
| GPIO 1 | UART1 TX → LD2410 RX (J4 pin 2) | 256000 baud; J5 pin 8 |
| GPIO 0 | UART1 RX ← LD2410 TX (J4 pin 1) | 256000 baud; J5 pin 7 (adjacent pair, socket row nearest J4 — moved off GPIO 16/17, see Lesson 23) |
| GPIO 2 | LD2410 OUT (presence interrupt) | safe non-strap input |
| GPIO 8 | WS2812 DIN → external SK6812-SIDE AQI ring | strap pin (LED idles low — OK); **R7 = 10 kΩ external pull-up to +3V3 required** (DevKitM-1's onboard pull-up depends on VCC_5V which floats in OAS) |
| GPIO 12 / 13 | Native USB-Serial-JTAG D+ / D− | one of the two USB-C ports |

**Reserved / unavailable**:
- **GPIO 10, GPIO 11**: physically NOT bonded out on ESP32-C6FH4 (internal SiP flash uses these pins). Unavailable on every MINI-1 / SuperMini / XIAO / DevKitM-1 variant.
- **GPIO 16, GPIO 17**: U0TXD / U0RXD — and on the DevKitM-1 they are hard-wired through **populated 0 Ω links** (R9 / R7) to the onboard **CP2102N** bridge, whose VDD + REGIN sit on the board 3.3 V rail. The bridge drives the GPIO 17 net continuously, with or without a USB cable, so no peripheral may share these pins. Reserved for the serial console; the only board-side tap is the DNP recovery header **J2**. See **Lesson 23**; enforced by the console-pin checks in `pipeline/oas/06_check_boot.py`.
- **Strap pins (avoid for general I/O)**: GPIO 4 (MTMS), 5 (MTDI), 9 (BOOT button on DevKitM-1), 15 (boot-mode select).

**Available safe-non-strap spare GPIOs** (for future expansion): 3, 14, 18, 19, 20, 21, 22, 23 — eight pins free. (GPIO 3 freed when the NFC tag was removed — GitHub issue #7. GPIO 1 was freed in v0.53 when the SW1 push-button was removed — GitHub issue #5 — and both GPIO 0 and GPIO 1 left the spare list again when the LD2410C UART moved onto them.)

### Architectural decisions

- **SEN66 RECESSES through a real PCB cutout** (v0.53, GitHub issue #2). Earlier revisions sat the module flat on the PCB with its 21.5 mm body sticking straight up; the assembly was too tall for the AK-N-94 lid to close. The board now carries a rounded-rectangle opening (Edge.Cuts) under the module so it drops into the enclosure REAR space, air-side face UP toward the perforated cover. The opening is DERIVED from the anchor + body (`SEN66_CUTOUT_*` in `boardgen/_project.py`): X 20.50..47.85, Y −33.95..23.0 — a 27.35 × 56.95 mm hole, asymmetric margins (W 1.0 / E 0.75 / N 0.75 / S 1.0 mm — E/N held small to protect the R60 rim), corner radius 1.5 mm. Slack over the 25.6 × 55.2 mm body is 1.75 mm on both axes (bench finding: cutting at the body outline is 1–2 mm too tight to press the module in). The NE cutout corner sits 1.33 mm inside the R60 outline (why the anchor moved 2 mm west vs the v0.51 board — a symmetric widen would have breached the arc). **Zip-tie retention** through 4 NPTH holes (Ø ~3 mm) now flanks the cutout on the two short-axis sides (PCB X 16.5 / 52.1, ≥2.5 mm FR4 web to the cutout edge); with the module recessed the ties cross UNDER its protruding back, counting against the 5 mm back-side budget (recess depth is set by the enclosure rear gap — physical verification pending at the next order). PCB-mounted JST GH socket (J3) sits in the pocket SOUTH of the cutout, rotated 90° (cable mouth faces WEST). J3 is wired as the positional MIRROR of the SEN6x Table 16 module pinout (1=VDD, 2=GND, **3=SCL, 4=SDA**, 5=GND, 6=VDD) so a straight flat JST GH lead lands SDA→SDA / SCL→SCL — see Lesson 21; enforced by stage 19 check E (pin NET order is independent of J3's rotation). **J3 cable pass-through slot** (v0.53 bench finding): with the module recessed, its GH receptacle sits BELOW the PCB plane, so the lead leaves the module on the back side and must return to the front face — an 11 × 5 mm rounded slot (`J3_CABLE_SLOT_*` in `boardgen/_project.py`; X 24.70..29.70, Y 28.0..39.0, corner R 1.5) EAST of J3 passes the GHR-06V plug up from below; the lead then loops west into J3's mouth across the 5 mm FR4 web (which carries a vertical "SEN66 lead" silk hint). Webs: 5.0 mm to the recess cutout (N), 4.5 mm to the chord (S), 5.0 mm to J3's courtyard (W). The slot edges passed the 2026-07-19 JLCDFM run clean (Lesson-13 class, checked alongside the recess cutout edges).
- **Hard limit #1 (≥22 mm in the SEN66 zone, default 17 mm elsewhere)** — verified against physical AK-N-94 sample. With the v0.53 recess the module protrudes LESS above the front side (it drops rearward into the cutout), so this remains a conservative bound.
- **PCB keeps F.CrtYd on the SEN66 mech-ref footprint** as a programmatic guardrail. Pre-v0.53 this enforced zero standoff (the body lay flat on the PCB, so no SMD could sit under it); post-v0.53 the body shadow is a cutout, so nothing can be placed there anyway — the courtyard is retained deliberately (documents the shadow, harmless over a hole). The mech-ref's own F.SilkS body outline + connector text were dropped in v0.53 (they fell inside the cutout — silk over an internal opening drops at fab); the F.Fab body/opening art is kept as an accurate assembly drawing of the recessed module.
- **AQI LED ring** (7 × SK6812-SIDE on a Ø26 mm base pitch circle around the central cable hole; per-slot radius overrides 11.0 / 16.5 mm, historically set to clear J1 and the since-removed MOD2 — see `LED_RING_RADIUS` + overrides in `boardgen/_project.py`). LEDs emit radially outward, parallel to the PCB — the cover never sees the die in line-of-sight, no "dot-through-perforation" artifact. The D13 slot (θ = 90°) is vacated for the J1 24 V terminal block on the SOUTH side. Each LED carries a 100 nF 0402 decoupling cap; the ring is powered from the LM2596S +5 V rail.
- **Shared I²C bus**: SEN66 + Qwiic expansion. Realized bus length ~140 mm PCB MST + ~80 mm SEN66 JST GH cable = **~220 mm total**. Exceeds Sensirion's "< 100 mm recommended" envelope but stays within their "< 500 mm with shielding" hard limit. 4.7 kΩ pull-ups give t_r ≈ 1 µs at 100 kHz (within standard-mode spec); 10 kΩ would have failed the rise-time check.
- **GPIO 8 external pull-up R7 = 10 kΩ to +3V3** — required because the DevKitM-1's onboard pull-up relies on VCC_5V (which OAS leaves floating; we feed +3V3 directly into J5.1).
- **Onboard DevKitM-1 NeoPixel is unreachable** in deployed units (its VDD ties to VCC_5V). The external SK6812-SIDE ring is the active indicator; the onboard pixel is a no-op in firmware.
- **ESP32-C6 DevKitM-1 placement** (v0.53, GitHub issue #3 + its review): the J5/J6 pin sockets sit a net 6.5 mm WEST of the v0.51 position (pin 1 at PCB X = −28.89 — the sockets are the PHYSICAL datum; the user measured a 7.5 mm move then trimmed 1.0 mm back east after a live fit check, for west-side safety margin since the room toward the THT caps / SEN66 was ample). Seating the module next to the THT bulk caps — the body east edge (+17.795) clears the C3 Ø8 mm can's west rim (+21.75) by 3.955 mm, and the SEN66 cutout west edge (+20.50) by 2.7 mm. The DevKitM-1 is NOT a plain rectangle: the ESP32-C6-MINI-1 PCB antenna adds a 13.20 × 5.37 mm tab overhanging the west short edge (both dimensions read from the Espressif dimensions PDF; see Lesson 22 for the pin-1 offset the same review corrected). `ESP32_ANCHOR_X = −30.465` is DERIVED (pin-1 datum − 1.575 pin offset); body X −30.465..+17.795. **No board-edge overhang**: the body NW corner sits 1.364 mm INSIDE the R60 outline and the antenna tab far corner 3.25 mm inside (the earlier "1.26 mm accepted overhang" was an artifact of the wrong pin offset — Lesson 22). The mech-ref draws the FULL true outline (body + tab) on F.Fab and four corner L-ticks on F.SilkS (a full silk rect is impossible there — the short edges would cross the U1 lead-pad ends and the J5/J6 socket-frame ends on the west, and skirt the C2 pad column on the east; the ticks mark the corners and skip the congested mid-spans). It carries NO F.CrtYd (daughterboards sit ~8.6 mm up on their sockets, so SMDs live under them — U1 TO-263 4.83 mm < the 5.5 mm socket budget); the Z-clearance guardrail's MOD1 shadow is extended west over the tab so U1 is actually checked (and passes).
- **LD2410C mounts board-to-board on a plain 2.54 mm gold-pin header, antennas UP** (v0.53, GitHub issue #9). The module's five Ø0.9 mm plated holes drop over the pins of a stock 1×5 P2.54 header at J4 (`Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical`) and are soldered on its top face; the joints are both the electrical and the mechanical retention. This replaces the HLK-LD2410B, whose 5-pad 1.27 mm castellated edge was hand-soldered directly into a P1.27 header — miserable to work with (the project was burned twice: a cold VCC joint at bring-up, then repeated resolder cycles) and the trigger for the swap was that **two independent -B units from different sellers, both on firmware build 2.44.25070917, had a permanently mute UART TX** (board side exhaustively exonerated with a standalone ESP-IDF test firmware). Antenna face points AWAY from the OAS PCB toward the perforated cover, per HiLink §5.5 — the main PCB stays *behind* the antenna where there is no detection requirement. **Placement**: J4 pin 1 at PCB (−37.0, +12.0), row running east to (−26.84, +12.0); the body (22 × 16 mm) hangs SOUTH of it over PCB X −42.92..−20.92 / Y +10.58..+26.58, in the south-west pocket. J4 is the PHYSICAL DATUM and the body anchor is DERIVED from it (Lesson 22 corollary). What fixes the position: the body cannot reach over the **H2** mounting hole (1.86 mm clear of its courtyard — the module sits only ~2.5 mm up, well below an M3 screw head), which stops it moving west, and it must stay out of the **AQI ring's** annulus (7.5 mm clear of D14's courtyard), which stops it moving east. Nothing is placed under the body shadow at all: the -C carries its LDO, two crystals and an inductor on its UNDERSIDE, so the under-board budget dropped to 1.0 mm (`DAUGHTERBOARD_Z_CLEARANCE["LDR1"]`); C11, the module's +5 V decoupling cap, sits just north of the pin row. **Silk**: all five holes carry the module's own pin names (TX / RX / OUT / GND / VCC) in a vertical-text row 3.8 mm north of the holes, the "J4" designator at that row's west end, an F.SilkS body outline whose north edge breaks into two corner stubs around the J4 silk frame, "antennas up" inside the outline (assembly-time orientation hint) and the MPN "HLK-LD2410C" printed just south of it, outside the body so it stays readable on a populated board.
- **Bluetooth proxy** = software-only; no extra hardware.

### Deviation budget — components not under KiCad stock library

Every placed footprint is verbatim KiCad stock OR a project-local OAS footprint with a documented technical reason. The complete deviation list:

| Designator(s) | Footprint | Reason |
|---|---|---|
| MOD1 | `oas:ESP32-C6-DevKitM-1_Reference` | Mechanical reference for the ESP32-C6-DevKitM-1 daughterboard (no pads, body shadow only). No KiCad stock entry exists. |
| LDR1 | `oas:LD2410_Mechanical_Reference` | Mechanical reference for the HLK-LD2410C daughterboard (no pads, body shadow only — 22 × 16 mm outline + the two antenna patches on F.Fab). No KiCad stock entry exists. Name kept variant-neutral across the v0.53 -B → -C swap. |
| SENS1 | `oas:SEN66_Mechanical_Reference` | Mechanical reference for the Sensirion SEN66 module (no pads, body shadow only). No KiCad stock entry exists. |
| H1..H3 | `oas:MountingHole_3.8mm_M3` | Custom Ø3.8 mm NPTH for SZOMK AK-N-94 manufacturer spec (between stock Ø3.2 mm and Ø4.0 mm sizes). |
| ZT1..ZT4 | `oas:ZipTieHole_3mm_NPTH` | Custom Ø3.0 mm NPTH for SEN66 zip-tie retention. |
| D11..D18 (D13 vacated) | `oas:SK6812-SIDE` | OAS-custom 4020 side-emit LED footprint matching OPSCO / Normand SK6812 SIDE-A datasheet pinout (1=DIN, 2=VDD, 3=DOUT, 4=GND — DIFFERENT from KiCad stock `LED:SK6812` which is the PLCC4 5050 with 1=VSS, 2=DIN, 3=VDD, 4=DOUT). |
| F1 | `oas:Fuse_1812L_4532Metric` | OAS-custom 1812 PTC-fuse land matching the Littelfuse 1812L-series termination geometry (verbatim EasyEDA F1812 / LCSC C151170: pad gap 2.30 mm). KiCad stock `Fuse:Fuse_1812_4532Metric` is a generic IPC chip-fuse land (gap 3.15 mm) — its pads leave the part's pin inner edge 0.43 mm off the copper → JLCPCB DFM "pin inner edge". 3D model: stock `R_1812_4532Metric.step` surrogate. |
| U1 | `oas:TO-263-5_LM2596` | OAS-custom TO-263-5 land matching the LM2596S-5.0/NOPB (LCSC C116713) geometry — verbatim EasyEDA C116713 pads: leads 3.50×1.02 mm, tab 8.705×10.587 mm, lead-tab pitch 10.252 mm. KiCad stock `Package_TO_SOT_SMD:TO-263-5_TabPin3` is a generic IPC TO-263-5 land (9.15 mm lead-tab pitch) — the 1.1 mm pitch mismatch left U1's thermal tab only ~25% overlapped on JLCPCB DFM ("Lead area overlapping pad" Danger). Silk / courtyard / F.Fab body / 3D model are kept verbatim from the stock `TO-263-5_TabPin3` donor; only the 6 pads (5 leads + tab, all full F.Paste — a single tab paste aperture, matching C116713: a windowpane tripped JLCPCB DFM lead/paste overlap) are swapped for the C116713 land. The placed `gen_to263_5_pcb_footprint` still parses verbatim via `_emit_stock_lib_footprint` (Lesson 1 compliant). |
| Q1 | `Package_TO_SOT_SMD:SOT-23` (stock) | Schematic uses project-local `OAS:Q_PMOS_GDS` symbol with numeric pin numbers 1/2/3 (pin NAMES G/S/D for readability). Footprint geometry is verbatim stock. |

No "hand-solder friendly" deviations remain anywhere in the design.

---

## Software

- **Framework**: ESPHome (YAML configuration)
- **HA integration**: native API
- **OTA**: ESPHome + HA
- **BLE proxy**: ESPHome `bluetooth_proxy:` component

Current firmware skeleton (added v0.40-post-order):
- `firmware/esphome/oas.yaml` top-level + 5 packages in `packages/`: core, leds, air-quality, presence, bt-proxy.
- LED ring (`packages/leds.yaml`): the light entity is **internal**; the dashboard card shows, in this order, Ring (switch), Ring Mode (select: AQI Breathing / AQI Solid / Dot Chase), Ring Brightness (1-10 = the LEDs' full range in ~1.9x steps; default 4 = the old 25 %, the setting the SEN66 temperature offset was calibrated with), Ring Night Mode (switch), Ring Night Brightness (0..Ring Brightness, snapped back if set higher), Ring Night Start / End (`datetime` time entities, 22:00 → 07:00), then a Ring Status line. A 1 s schedule tick is the light's only writer: it derives on/off, effect and brightness from those settings, the clock (last known day/night kept across reboots) and the critical-air flag (solid red, at least brightness 7 by day, the night brightness at night). Home Assistant gets exactly the seven controls (all `entity_category: config`); Ring Status is `internal` and reaches only the dashboard via `web_server: include_internal: true` (core.yaml) — so any future internal entity also shows on the dashboard unless it is `disabled_by_default` (behind "Show All", as the ring's light is). See Lesson 27.
- SEN66 sensor offsets (temperature, humidity, CO2) exposed as `number:` entities preserved across reboots.
- STAR-Engine IAQM Light preset (T1=1000, T2=3000, K=200, P=200 raw I²C 16-bit, ×10 of post-scale display values) re-uploaded on every boot via `on_boot:` lambda (Sensirion params are volatile per datasheet).
- LD2410 per-gate sensitivity, max-distance, and timeout exposed as `number:` / `select:` entities.
- Bluetooth proxy RE-ENABLED (issue #4 closed 2026-07-19). The bring-up crash-loop was NOT an ESPHome bug: the package's own "BLE Proxy" kill-switch (`restore_mode: RESTORE_DEFAULT_ON` + raw `global_esp32_ble_tracker->start_scan()` lambda) fired during the template switch's setup() at priority 798, while the BLE globals are only assigned in the BLE components' setup() at priority 350/300 — null-deref (MTVAL 0xc) before WiFi init. Fixed by switching to the null-guarded native `ble.enable` / `ble.disable` actions, `restore_mode: DISABLED`, and a state lambda reading `id(oas_ble).is_active()`. Bench-verified on a v0.51 board: stable boot, BLE active after every reboot, kill-switch toggles both ways. Rule: never call BLE `global_*` singletons from YAML lambdas that can fire at boot (see the kill-switch note in `packages/bt-proxy.yaml`).

Documentation: `firmware/README.md`.

---

## Hard constraints (do not violate without an explicit, documented decision)

1. **Front-side component height**: 17 mm default; **≥22 mm in the SEN66 zone** (verified per AK-N-94 physical sample).
2. **Back side**: max 5 mm (solder fillets + pin-header bottoms; no SMD on back).
3. **Ø120 mm D-shape PCB outline** from the manufacturer DXF.
4. **3 × M3 mounting holes** at the DXF positions.
5. **24 V DC input only** (no 12 V, no external 5 V).
6. **ESP32-C6** as MCU, specifically **ESP32-C6-DevKitM-1-N4** (EAN 5904422385651). No fallback to C3 / S3 or generic clones.
7. **AK-N-94** enclosure as the integration target (do not redesign for another case).
8. **Both design pillars** — no change degrades measurement quality or aesthetic acceptability.

---

## Out of scope (decisions already made)

Do not propose these again without new information:

- ❌ Battery / alternative power source (24 V mains only)
- ❌ Buzzer or audio output
- ❌ Capacitive touch input
- ❌ External temperature probe terminal (DS18B20 / NTC) — SEN66 is sufficient
- ❌ Input current monitoring (INA219)
- ❌ Display (OLED / LCD round) — researched mid-2026; Waveshare 1.28" GC9A01 clears Pillar #1 but fails Pillar #2 (permanent dark grey circle on the white cover breaks the smoke-detector silhouette). LED ring + HA dashboard already cover the "see the data" need.
- ❌ Dynamic NFC tag (NXP NT3H1101 on MIKROE-2462) — removed after v0.51 bring-up (GitHub issue #7). The I²C side worked, but RF coupling through the AK-N-94 cover was unusable (ground plane under the antenna + distance to the cover); the only workable fix (antenna glued inside the cover) breaks Pillar #2, and the feature only saved ~3 phone taps. Do not re-propose without a cover-integrated antenna concept that keeps the backlit-perforation look.
- ❌ External USB-C connector on the case wall (use DevKitM-1's own USB-C for programming; OTA after first flash)
- ❌ IR transmitter / receiver
- ❌ Microphone / acoustic sensor
- ❌ Ambient light sensor (VEML7700) — removed v0.10. Shielding from the onboard NeoPixel + power LED inside the perforated case would require additional 3D-printed parts; not core to OAS mission.

---

## Open work / TODO

### Hardware
- [x] **Routing rework (v0.50) — DONE.** Board fully routed, `ROUTING_CHUNKS = ("gnd", "autoroute")`, `build.py` 30/30 PASS, DRC 0/0. Snapshot in `oas_routes.py` (613 seg + 42 via after the post-v0.50 DFM via removals). (Superseded by the issue-#8 v0.53 re-route: 390 seg + 45 via.)
- [x] **JLCDFM on the fully-routed v0.53 gerbers — DONE (2026-07-19): PCB 0 Danger.** Two real finding classes fixed (13× silkscreen-to-hole from route vias — 4 via moves + the J10 "BOOT" label nudge; 1× mask-opening-exposing-trace — +3V3 chain shifted 0.13 mm east). Remaining 4× "Negative soldermask expansion 0.04 mm" is a PROVEN scanner-side phantom, closed by a CONTROL EXPERIMENT: the byte-identical May ZIP (commit 4618d36) that scanned **0 Danger / 0 Warning on 2026-05-21** was re-uploaded on 2026-07-19 and scanned **0 Danger / 6 Warning** — same file, two verdicts, so the scanner changed, not the board. Local evidence agrees: the flagged mask and copper apertures are bit-identical RoundRects (0.95×0.8, R1/R4 pads) and a flash-by-flash gerber audit shows zero pads with mask < copper. Do NOT chase it with global mask expansion (would shrink U2 SOT-583 mask webs toward a real soldermask-bridge warning). Treat 0 D + these mask-expansion phantoms as the clean baseline for any future scan. **SUPERSEDED by issue #9** — that result belongs to the pre-#9 gerbers. The J4 rework changed the drill file (Ø1.0 mm holes at new positions), moved C11, and added a whole silk block beside the new hole row, so a FRESH JLCDFM pass is owed before the next order. Run it after the re-route, not before (the re-route changes the copper again).
- [x] **JLCDFM re-run on the post-issue-#9 gerbers — DONE (2026-07-22): PCB 0 Danger / 5 Warning, SMT 0 Danger / 0 Warning.** Two passes were needed. The FIRST scan of the re-routed board regressed off the 0-Danger floor to **7 Danger / 7 Warning**: the island stitcher that drops GND vias has no pad or silk awareness (it only asks "is this point inside GND copper on both layers"), so it parked one via's ring 0.18 mm over C17.2 and two more within 0.017 / 0.064 mm of the J2 "BOOT" and J10 silk blocks — those two vias alone produced 6 Danger + 2 Warning. Four vias were relocated 0.9–1.2 mm in `78d2aab` (positions only; counts stayed 375/38) and the SECOND scan confirmed every Danger cleared. **JLCDFM MISSED a real defect in the first pass**: a via with its drill 0.07 mm INSIDE D18.4's pad copper scored 0/0/0 on both "Via to pad" and "Via placed within a pad", and DRC is silent because it is the same net — it was caught only by an offline audit. The fab's DFM is not a complete backstop for same-net via-in-pad; audit locally (Lesson 14, Lesson 26). SMT DFM ran clean including the Lesson-13 "Component to board edge distance" class (0/0/0 — the Ø10 cable hole and the caps at r7.0 leave ~1.7 mm). The 4× "Negative soldermask expansion 0.04 mm" phantoms are unchanged, and the 1× "Solder mask opening exposing trace" Warning is understood rather than fixed: the check measures copper-to-mask-opening clearance and the scanner adds ~0.045 mm of its own mask expansion (in the July pass it reported 0.15 mm for a track measured locally at 0.196 mm), so with DRC clean at the 0.20 mm rule a track routed at exactly the design clearance necessarily lands under the scanner's threshold. Treat **0 Danger + these 5 Warnings** as the clean baseline.
- [x] **JLCDFM re-run on the post-issue-#10 gerbers — DONE (2026-07-23): PCB 0 Danger / 5 Warning, SMT 0 Danger / 0 Warning.** Full run (fresh upload + BOM/CPL match + SMT DFM) on `599b8a6` — the board after the Q1 reverse-polarity fix (`d24d855`, issue #10) and the full signal re-route it forced (`599b8a6`, 373 seg / 37 via). The verdict **reproduced the 78d2aab baseline byte-for-byte in meaning**: 0 Danger, and the SAME 5 explained Warnings (4× "Negative soldermask expansion 0.04 mm" scanner phantoms on the R1/R4 `RoundRect.d47`/`d49` apertures + 1× "Solder mask opening exposing trace" from a track at exactly the 0.20 mm design clearance under the scanner's ~0.045 mm self-expansion). So the Q1 rework + re-route introduced ZERO DFM regression — no new Danger, and the two vias worth watching (the WS2812_DIN via, the GND stitch 0.0957 mm from C2.2) did not trip silk-to-hole. SMT clean including the Lesson-13 component-to-board-edge class. The same-net via-in-pad class JLCDFM structurally misses (Lesson 26) is now guarded offline by `tests/test_via_geometry.py` (stage 16), which passed 37/37 vias on this snapshot (tightest ring-to-pad 0.0957 mm ≥ 0.05 mm hazard floor). **This is the copper-clean order gate met on the current board** — the 78d2aab result is superseded (pre-Q1-fix, pre-re-route). Cached artefacts under `.cache/dfm/` (gitignored): `dfm-results.json`, `dfm-pcb.png`, `dfm-smt.png`.
- [x] Receive prototypes from JLCPCB; hand-solder the 7 THT components (J1 / J4 / J5 / J6 / C1 / C3 / C4) — done on the v0.51 batch and again on the v0.54 batch (delivered 2026-09-04).
- [ ] Optional v2 substitutions (deferred): Q1 → AON7415 for actual positive Vds margin (-40 V vs SMBJ24A 38.9 V clamp); L1 → 6045 / 1264 body if production load grows beyond 1.2 A continuous.
- [x] Foam shroud / cover baffle separating SEN66 inlet zone from outlet zone — settled on the built units: an air duct from the perforated cover to the SEN66 inlet is required for correct readings. It sits in front of part of the LED ring (Pillar #2 cost, accepted). The duct design is not in the repository yet.

### Firmware
- [x] First-flash on delivered prototype.
- [x] LD2410 UART integration shakedown (LD2410C on the v0.54 boards; per-gate thresholds, gate 0 disabled, sleep-detection notes in `packages/presence.yaml`).
- [x] OTA setup against real hardware (Home Assistant ESPHome add-on; leave the unit powered ≥1 min after OTA — app rollback).
- [x] HA discovery / device class metadata validation.

### Logistics
- [x] Receive ordered AK-N-94 enclosure + SEN66 + LD2410C samples — received; the LD2410C runs on the v0.54 boards (the flying-lead pre-test from issue #9 was owner-waived).
- [ ] Optional re-order at higher quantity if v1 validates.

---

## Repository layout

```
open-ambient-sensor/
├── README.md
├── CLAUDE.md                       # this file
├── GPLv3-LICENSE.md
├── .gitignore
├── firmware/
│   ├── README.md                   # flashing + Home Assistant integration
│   ├── esphome/
│   │   ├── oas.yaml                # top-level ESPHome config
│   │   ├── packages/               # core / leds / air-quality / presence / bt-proxy
│   │   └── examples/               # anonymized per-device override examples
│   └── secrets.yaml.example
└── hardware/
    ├── kicad/
    │   ├── build.py                # THE ONLY top-level entrypoint — runs every pipeline/<subdir>/NN_*.py in order (AI-agent harness)
    │   ├── boardgen/               # KiCad source-file generators — one numbered stage per output
    │   │   ├── _common.py          # UUID system (U, sheet_context), fmt, Context dataclass, sub-sheet IDs
    │   │   ├── _project.py         # OAS-specific: EXTERNAL_MODULES, GPIO_*, geometry, daughterboard placement
    │   │   ├── _footprints.py      # public facade re-exports for gen_*_footprint + gen_*_pcb_footprint
    │   │   ├── _footprints_stock.py    # stock KiCad-library footprint emitters (parse-and-emit via _emit_stock_lib_footprint)
    │   │   ├── _footprints_custom.py   # OAS-custom footprint emitters (9 entries in Deviation budget)
    │   │   ├── _footprints_placement.py # placement orchestrators (PCB-side layout helpers)
    │   │   ├── data/               # inline KiCad source snippets consumed by _lib_symbols.py
    │   │   ├── _pcb.py             # gen_pcb (oas.kicad_pcb assembler)
    │   │   ├── _schematic-related: _sch_helpers (shared primitives), _sch_root / _sch_power /
    │   │   │                       _sch_mcu / _sch_sensors / _sch_io (per-sheet generators)
    │   │   ├── _lib_symbols.py     # POWER_LIB_SYMBOLS + MCU_LIB_SYMBOLS + SENSORS_LIB_SYMBOLS + IO_LIB_SYMBOLS
    │   │   ├── _routing.py         # _RouteEmitter + ROUTING_CHUNKS + apply_routing_to_pcb
    │   │   ├── _postprocess.py     # netlist sync + Z-clearance audit + LCSC metadata injection
    │   │   ├── _project_files.py   # gen_pro + gen_fp_lib_table + gen_sym_lib_table + gen_oas_symbol_library
    │   │   ├── 01_custom_footprints.py … 14_design_rules.py   # numbered stages, each ~15-30 lines
    │   │   └── _design_rules.py    # generates oas.kicad_dru (JLCPCB-tuned custom DRC rules)
    │   ├── oas_routes.py           # derived — routing snapshot replayed by boardgen/_routing.py
    │   ├── lcsc_mapping.py         # SOT for SMD LCSC SKUs — Python dict (Value, Footprint) -> entry
    │   ├── oas.kicad_pro / .kicad_sch / .kicad_pcb / .kicad_dru / sub-sheets  # generated artefacts
    │   ├── libraries/              # generated project libraries (OAS.kicad_sym + oas.pretty/)
    │   ├── third_party/            # git submodules (manual-trigger tools NOT auto-invoked by build.py)
    │   │   ├── JLCKicadTools/         # CPL rotations DB (legacy reference)
    │   │   ├── kicad-skip/            # schematic semantic API (stage 09)
    │   │   ├── InteractiveHtmlBom/    # HTML BOM generator (stage 22)
    │   │   ├── kicad-jlcpcb-dru/      # rules template adapted into _design_rules.py
    │   │   └── jlcparts/              # offline JLCPCB catalogue (stage 34 cache source)
    │   ├── pipeline/               # one stage per file (NN_<name>.py); each standalone-runnable
    │   │   ├── _common.py          # PROJECT-AGNOSTIC helpers (Stage, find_kicad_cli, run, sha256)
    │   │   ├── _project.py         # OAS config + vendor-agnostic + per-vendor output paths
    │   │   ├── generic/            # VENDOR-AGNOSTIC + REUSABLE across KiCad projects
    │   │   │   ├── 01_emit_sources.py    # walk boardgen/[0-9][0-9]_*.py — emit every KiCad source file
    │   │   │   ├── 02_determinism.py     # bit-identity self-check (re-runs stage 01 in fresh subprocess)
    │   │   │   ├── 03_drc.py             # kicad-cli pcb drc strict (+ .kicad_dru auto-loaded)
    │   │   │   ├── 04_erc.py             # kicad-cli sch erc strict
    │   │   │   ├── 10_render_2d.py       # PCB top/cutouts/bottom SVG
    │   │   │   ├── 11_render_sch.py      # schematic root + sub-sheets SVG
    │   │   │   ├── 12_render_png.py      # cairosvg batch SVG -> PNG (hard FAIL if cairosvg missing)
    │   │   │   ├── 13_render_3d.py       # 3D top + iso renders
    │   │   │   ├── 15_lint_typecheck.py  # mypy on boardgen/ + pipeline/ (real-bug flags)
    │   │   │   ├── 16_lint_compileall.py # compileall sanity check + pytest unit suite (tests/)
    │   │   │   ├── 17_lint_kicad_pro.py  # rule_severities=={} enforcement (Lesson 3)
    │   │   │   ├── 20_export_gerbers.py  # Protel gerbers + Excellon drill -> hardware/build/gerbers/
    │   │   │   ├── 22_export_ibom.py     # InteractiveHtmlBom -> hardware/output/oas-ibom.html
    │   │   │   └── 24_preflight_gerbers.py  # pygerber integrity + drill stats + composite render
    │   │   ├── oas/                # OAS-only verification (hardcoded to this circuit)
    │   │   │   ├── _spice.py             # SHARED ngspice harness — consumed by 08 / 27 / 28 (Lesson 18)
    │   │   │   ├── 05_check_dc.py        # DC voltage propagation analytical model
    │   │   │   ├── 06_check_boot.py      # ESP32-C6 strap + signal pin audit
    │   │   │   ├── 07_check_ampacity.py  # IPC-2221 trace width verifier
    │   │   │   ├── 08_check_switching.py # ngspice LM2596 soft-start + cascade 24V→5V→3V3 (behavioural TPS62933 — Lesson 19)
    │   │   │   ├── 09_check_semantic.py  # I2C pull-ups, GPIO 8 pull-up, no_connect coverage (kicad-skip)
    │   │   │   ├── 14_check_refdes_unique.py  # designator uniqueness across schematic
    │   │   │   ├── 18_lint_no_hand_pads.py    # forbid hand-coded pad geometry (Lesson 1)
    │   │   │   ├── 19_check_oas_metadata.py   # EXTERNAL_MODULES + lcsc_mapping + POWER_BUDGET schema lint + J4 pin order (Lesson 20)
    │   │   │   ├── 21_check_polarity_silk.py  # radial-cap polarity-band silk audit
    │   │   │   ├── 23_check_power_budget.py   # per-rail current sum vs derated protector limits
    │   │   │   ├── 25_check_thermal.py        # LM2596 Tj from POWER_BUDGET Iout + extrapolated RthJA
    │   │   │   ├── 26_check_i2c_rise_time.py  # SDA/SCL t_r + C_bus per UM10204 Standard-mode
    │   │   │   ├── 27_check_surge.py          # ngspice IEC 61000-4-5 — TWO sims (Q1 Vds + LM2596 Vin — Lesson 16)
    │   │   │   └── 28_check_reverse_polarity.py  # ngspice reverse-polarity Vgs clamp (sustained + arc transient)
    │   │   └── jlcpcb/             # VENDOR — JLCPCB-specific stages; deliverables -> hardware/output/jlcpcb/
    │   │       ├── _rotations.py             # tape-feeder rotation offsets (upstream + OAS gap-fillers)
    │   │       ├── 29_check_bom_consistency.py  # LCSC# bijection check
    │   │       ├── 30_export_pos.py          # CPL header + rotation corrections
    │   │       ├── 31_export_bom.py          # BOM template + LCSC + library tier + THT detection
    │   │       ├── 32_bundle.py              # ZIP gerbers + drill -> oas-jlcpcb.zip
    │   │       ├── 33_check_dnp_consistency.py  # DNP refdes leak audit (BOM + CPL)
    │   │       ├── 34_check_lcsc_offline.py  # LCSC# class/value match vs jlcparts SQLite (Lesson 5)
    │   │       └── 35_audit_zip_content.py   # oas-jlcpcb.zip inventory + non-empty assert
    │   ├── tests/                  # pytest unit suite (UUID determinism, geometry invariants, POWER_BUDGET, routes snapshot, extract_routes round-trip, via geometry) — run by stage 16
    │   └── tools/                  # MANUAL-trigger scripts (extract_routes, jlcdfm_upload, setup_jlcparts_cache)
    ├── build/                      # INTERMEDIATE artifacts (gitignored)
    │   └── gerbers/                # raw Protel gerbers + Excellon drill + drill_map PDF
    ├── renders/                    # generated previews (PNG + SVG, sibling of kicad/)
    ├── photos/                     # photos of built units — EXIF stripped before commit (Rule 2)
    │   ├── pcb/                    # 2D / 3D / pygerber preflight
    │   └── sch/                    # schematic root + 4 sub-sheets
    └── output/                     # production deliverables (vendor-neutral + per-vendor)
        ├── oas-ibom.html              # vendor-neutral InteractiveHtmlBom artefact
        └── jlcpcb/                    # EXACTLY 4 files, all committed
            ├── oas-jlcpcb.zip      # gerbers + drill bundle for JLCPCB upload
            ├── oas-BOM.csv         # BOM (JLCPCB template + LCSC + library tier)
            ├── oas-top-CPL.csv     # CPL top (JLCPCB header + rotation offsets)
            └── oas-bottom-CPL.csv  # CPL bottom
```

`.gitignore` highlights:
```
# secrets
**/secrets.yaml

# build artifacts + caches
**/build/  **/.cache/  **/__pycache__/  *.bak  *-backups/

# auto-downloaded external tools (ngspice + LM2596 PSpice model, etc.)
/.tmp/

# vendor-specific production output lives under hardware/output/<vendor>/
# — committed per vendor: exactly 4 files (ZIP + BOM + 2× CPL). The
# intermediate raw fab data (gerbers + drill + drill_map) lives under
# hardware/build/gerbers/ and is gitignored via **/build/.

# freerouting (manual download by user; not redistributable)
hardware/kicad/freerouting.jar
hardware/kicad/freerouting.json
hardware/kicad/freerouting.log
```

---

## PCB design workflow

The KiCad project in `hardware/kicad/` is **script-driven**. The source of truth lives across `boardgen/` (the per-stage Python modules that emit every `.kicad_*` file), `lcsc_mapping.py` (SMD LCSC SKUs), and `oas_routes.py` (routing snapshot). The `oas.kicad_pcb` / `oas.kicad_sch` / `oas.kicad_pro` / `libraries/*` files are **derived artefacts** — regenerated bit-identically from `boardgen/`.

The boardgen walker lives at `pipeline/generic/01_emit_sources.py` (stage 01 of `build.py`). It iterates `boardgen/[0-9][0-9]_*.py` via importlib, instantiates a shared `Context` dataclass, and runs each stage's `run(ctx)`. The 13 numbered boardgen stages (`01_custom_footprints` … `13_apply_routing`) each run standalone for debug (`python boardgen/02_pcb_board.py`).

**There is no `generate.py` at the repo root.** `build.py` is the ONLY top-level entrypoint — that is the AI-agent harness. An autonomous agent cannot "just rebuild the sources" while skipping DRC / ERC / determinism / DC / ampacity / boot-strap / preflight / vendor-export checks, because the only way to invoke the walker is through `build.py` (which always runs every later stage too). Individual pipeline files remain debug-runnable in isolation (`python pipeline/generic/03_drc.py`), but that is for diagnosing a specific stage in flight, not for skipping verification on a commit.

### How we work

1. The user describes a desired change (geometry tweak, new component, routing fix, etc.).
2. The assistant edits the appropriate constant / function inside `boardgen/_project.py` (geometry, placements, GPIO map), `boardgen/_footprints.py` (any footprint), `boardgen/_sch_*.py` (per-sheet schematic), or one of the other helper modules. `oas_routes.py` / `lcsc_mapping.py` for routing / BOM tweaks.
3. The assistant runs `python build.py`. That command is a thin orchestrator that dispatches each `pipeline/<subdir>/NN_*.py` script in numeric order. The stages are:
   - `01_emit_sources` — walks `boardgen/[0-9][0-9]_*.py` to rebuild every KiCad source file (which internally runs the Z-clearance guardrail on 76 footprints).
   - `02_determinism` — re-runs `01_emit_sources.py` in a fresh subprocess and checks 18 source files are bit-identical (fresh interpreter so `PYTHONHASHSEED` randomization exposes any dict-order leak).
   - `03_drc` — `kicad-cli pcb drc` strict (`--severity-error --severity-warning --refill-zones`). Auto-loads `oas.kicad_dru` (custom JLCPCB-tuned rules emitted by boardgen stage 14).
   - `04_erc` — `kicad-cli sch erc` strict (`--severity-error --severity-warning --exit-code-violations`).
   - `05_check_dc` / `06_check_boot` / `07_check_ampacity` — DC voltage propagation, boot-strap audit, trace ampacity. Pure-Python analytical.
   - `08_check_switching` — ngspice LM2596 soft-start (real TI PSpice model, ~3 ms window) + cascade 24V→LM2596→5V→TPS62933→3V3 soft-start (behavioural averaged models for both bucks — see Lesson 19). Auto-downloads ngspice + LM2596 + TPS62933P into `.tmp/spice/` on first run via the shared `pipeline/oas/_spice.py` harness (Lesson 18); hard-fails on any download / `py7zr` failure.
   - `09_check_semantic` — schematic semantic invariants via `kicad-skip` (I²C pull-ups R5/R6 = 4.7 kΩ, GPIO 8 pull-up R7 = 10 kΩ, no_connect coverage). Hard-fails if the kicad-skip submodule isn't initialized.
   - `10_render_2d` / `11_render_sch` / `12_render_png` / `13_render_3d` — re-renders SVG + PNG + 3D into `renders/`. `12_render_png` hard-fails if `cairosvg` is not importable (committed PNGs must never silently drift from their SVGs).
   - `14_check_refdes_unique` — designator uniqueness across the schematic.
   - `15_lint_typecheck` — `mypy` on `boardgen/` + `pipeline/` (real-bug flags: `--check-untyped-defs --warn-unused-ignores --warn-redundant-casts --warn-unreachable --no-implicit-optional`). Hard-fails if mypy missing.
   - `16_lint_compileall` — `python -m compileall` over `boardgen/` + `pipeline/` + `tools/` + `tests/` (catches syntax errors in modules not on the happy path), then runs the pytest unit suite in `tests/` (UUID determinism, geometry invariants, POWER_BUDGET sums, routing-snapshot sanity, extract_routes round-trip, **via geometry**). Hard-fails if `pytest` is not importable.
   - `17_lint_kicad_pro` — Lesson 3 enforcement: `board.design_settings.rule_severities` and `erc.rule_severities` MUST be empty in `oas.kicad_pro`. Hard-fails on any suppression entry.
   - `18_lint_no_hand_pads` — Lesson 1 enforcement: every `gen_*_pcb_footprint` delegates to `_emit_stock_lib_footprint` or parses a `_*_lib_footprint_path` file. Whitelist: 8 documented OAS custom footprints in CLAUDE.md "Deviation budget".
   - `19_check_oas_metadata` — Lesson 10 + Gap H + Lesson 6: every `EXTERNAL_MODULES` entry has at least one identifier (`mpn` / `ean` / `material` / `supplier_*`); every `lcsc_mapping` entry matches the expected schema (LCSC# `^C\d+$`, library tier ∈ {Basic, Extended, N/A}, manufacturer + MPN non-empty); every `POWER_BUDGET` entry has a non-empty HTTP(S) datasheet URL; J4 pin-1..5 order matches the Lesson 20 canon (check D — anchored to the `j4-p*` wire tags in `_sch_sensors.py` + `J4_PCB_ROTATION`, fails loudly if the anchors vanish).
   - `20_export_gerbers` — vendor-neutral raw fab data (Protel gerbers + Excellon drill + drill_map PDFs) written to `hardware/build/gerbers/` (gitignored, intermediate).
   - `21_check_polarity_silk` — radial-cap polarity-band silk audit (catches missing "+" or wrong-side wedge on electrolytic caps).
   - `22_export_ibom` — InteractiveHtmlBom HTML artefact `hardware/output/oas-ibom.html`. Vendor-neutral; primary use is the JLCPCB Assembly XLS pre-payment cross-check (Lesson 5). Hard-fails if InteractiveHtmlBom submodule or KiCad-bundled python missing.
   - `23_check_power_budget` — reads `POWER_BUDGET` from `boardgen/_project.py` (TypedDict; Lesson 17); per-rail typ + peak current sum (radio-group-aware for ESP32-C6 Wi-Fi/BLE Coex time-share); checks each rail vs `POWER_BUDGET_SAFETY_DERATING × POWER_BUDGET_RAIL_LIMITS_MA` (LM2596 3 A / TPS62933 2 A / F1 750 mA hold).
   - `24_preflight_gerbers` — pygerber integrity + drill statistics + composite renders (smoke test on the raw fab data, vendor-neutral).
   - `25_check_thermal` — LM2596 junction temperature `Tj = Tamb + Pdiss × RthJA`. RthJA piecewise-linear-extrapolated from TI SNVS124N anchors at the actual U1 tab Cu area (92 mm² parsed from `oas.kicad_pcb`). Pdiss derived from POWER_BUDGET 5V rail Iout via `Pdiss ≈ Vout × Iout × (1/η - 1)`. Hard-fail at Tj > 125 °C, warn at > 110 °C.
   - `26_check_i2c_rise_time` — t_r and C_bus on shared I²C (SEN66 + Qwiic). Parses SDA/SCL track lengths from `oas_routes.py`; budgets device input C per UM10204 ceiling. Hard-fail on `t_r > 1000 ns` (Standard-mode 100 kHz) or `C_bus > 400 pF`.
   - `27_check_surge` — ngspice IEC 61000-4-5 1.2/50 µs voltage / 8/20 µs current combination wave, 200 V peak, 2 Ω source. TWO sims (Lesson 16): Sim 1 worst-case Q1 (1 µF C1, no F1) checks `vds_peak ≤ 30 V` (AO3401A abs max); Sim 2 realistic LM2596 (100 µF C1 + 0.1 Ω F1 + 32 µF input bypass) checks `vlm_peak ≤ 40 V` (LM2596 SNVS124N Vin abs max). Each sim sweeps L_trace = 12.5 / 25 / 37.5 nH.
   - `28_check_reverse_polarity` — ngspice reverse-polarity transients: sustained −24 V (100 ns edge, 5 ms hold) + arc-during-mating pulse (−60 V / 1 µs). Verifies BZT52C10S Zener + R4 + R1 hold `|Vgs(Q1)| ≤ 11 V` (1 V buffer under AO3401A 12 V hard max per Lesson 6).
   - `29_check_bom_consistency` — LCSC# bijection check across `lcsc_mapping.py` (catches copy-paste bugs before any vendor export).
   - `30_export_pos` / `31_export_bom` / `32_bundle` (in `pipeline/jlcpcb/`) — JLCPCB-specific deliverables: CPL header `Designator, Mid X, Mid Y, Layer, Rotation` + rotation offsets; BOM with LCSC mapping + range expansion + THT detection; ZIP bundle. All four output files land in `hardware/output/jlcpcb/`.
   - `33_check_dnp_consistency` — DNP attribute audit: PCB attrs `dnp` + `exclude_from_bom` + `exclude_from_pos_files` must travel together; DNP refdes must not leak into BOM or CPL files.
   - `34_check_lcsc_offline` — Lesson 5 enforcement: every LCSC# in `lcsc_mapping.py` is queried against the offline jlcparts SQLite cache and verified for category match (Resistor vs Capacitor vs MOSFET — would have caught the v0.40 R3 C23116 = 806 Ω near-miss). Hard-fails if the cache is missing — run `python hardware/kicad/tools/setup_jlcparts_cache.py` once to populate it (~2 GiB compressed download, ~26 GiB SQLite).
   - `35_audit_zip_content` — verifies `oas-jlcpcb.zip` contains exactly the 11 expected files (9 gerber + 2 drill), every file > 0 bytes, no unexpected leftovers.
   Numbers in the range gaps (`36`–`39`) remain reserved for future jlcpcb extensions. Slots 23, 25-28 were used by the v0.51 CI expansion (power_budget, thermal, i2c_rise_time, surge, reverse_polarity); slot 21 by polarity_silk. Each vendor gets a 10-number range (jlcpcb 29–39; future oshpark would take 40–49). **Aborts on any violation or determinism drift** (fail-fast — later stages don't run). Since v0.52 stage exit codes carry meaning: `1` = validation failure, `2` = missing dependency (SUMMARY shows `FAIL-DEP`), `3` = network/IO failure (`FAIL-IO`); `build.py` stays fail-fast on all non-zero codes. Each `pipeline/<subdir>/NN_*.py` is also independently runnable for debug (`python pipeline/generic/03_drc.py`).
4. The assistant commits the resulting diff (sources + KiCad files + renders + vendor deliverables together).
5. JLCPCB upload: `hardware/output/jlcpcb/oas-jlcpcb.zip` (bare board) + `oas-top-CPL.csv` + `oas-BOM.csv` (SMT assembly). Drill review: `hardware/build/gerbers/oas-PTH-drl_map.pdf` / `oas-NPTH-drl_map.pdf` (regenerable, gitignored). All files produced by stages 20-33 on every `build.py` run.

### Rules

- **Never edit `.kicad_pcb`, `.kicad_sch`, `.kicad_pro`, or `*.kicad_mod` directly.** The next `build.py` run will overwrite the edit. If you find yourself wanting to hand-edit one of those, add a new constant / function to the appropriate `boardgen/_*.py` module instead.
- **`boardgen/` is the source-of-truth package; the walker (`pipeline/generic/01_emit_sources.py`) is just glue.** Each output file maps to exactly one `boardgen/NN_*.py` stage. Helper modules (`_common.py`, `_project.py`, `_footprints.py`, `_pcb.py`, `_lib_symbols.py`, `_routing.py`, `_postprocess.py`, `_project_files.py`, `_sch_helpers.py`, `_sch_root.py` / `_power` / `_mcu` / `_sensors` / `_io`) form an acyclic dependency DAG — never import from a stage file into a helper. Each numbered stage is independently runnable for debug (`python boardgen/02_pcb_board.py`).
- **All UUIDs are deterministic v5** (namespaced under the OAS project). Two consecutive runs with no source changes produce a bit-identical PCB → empty `git diff`.
- **`renders/` is committed** as a visual changelog. Reviewers can see geometry changes in PRs without launching KiCad.
- **External services run MANUALLY only.** `tools/jlcdfm_upload.py` and any future TI-WEBENCH / LCSC-stock-check / OSHPark-upload tool must be invoked by explicit user request — never from `build.py` or any CI loop. JLCPCB's `/checkIp` endpoint tracks upload volume per IP; running on every build would risk rate-limiting.
- **JLCPCB-specific tape-feeder rotation offsets live in `pipeline/jlcpcb/_rotations.py` and apply only in stage `30_export_pos`.** `oas.kicad_pcb` and every 3D / 2D / preflight render show KiCad's natural rotation — visual verification reflects placement intent, not JLCPCB's tape geometry. Only `hardware/output/jlcpcb/oas-top-CPL.csv` (the file uploaded to JLCPCB) carries the compensated rotations. Same separation applies to gerbers (which don't encode component rotation at all).
- **Vendor isolation.** The KiCad project is vendor-neutral. JLCPCB-specific tweaks (rotation offsets, CPL header reformat, BOM template with LCSC + library tier, ZIP bundle naming) live ONLY under `pipeline/jlcpcb/` and ONLY write into `hardware/output/jlcpcb/`. The vendor folder under `hardware/output/<vendor>/` carries EXACTLY 4 files: ZIP + BOM + 2× CPL — nothing else. Adding a new fabricator = create `pipeline/<vendor>/` sibling to `generic/`, `oas/`, `jlcpcb/` + a new `hardware/output/<vendor>/` folder. Zero edits to `generic/` or `oas/` stages. NEVER compensate for a fabricator quirk by deforming `oas.kicad_pcb` or any schematic — the project's KiCad ground truth must match the datasheet, and the per-vendor stage compensates at export emit time.

### Freerouting (autorouter) — JRE runs in Docker

The host JDK is Java 1.8 — too old for Freerouting 2.x (needs Java 21+). Run Java from a container instead: `eclipse-temurin:25-jre` (and `:21-jre`) are pulled locally as Docker images. Mount `hardware/kicad/` into the container and invoke `java -jar freerouting.jar …` there. `freerouting.jar` is gitignored (`hardware/kicad/freerouting.jar`) — not committed.

Freerouting is used as a congestion **diagnostic**, not as the routing source of truth — see the v0.50 revert (commit `dd98a8b`, reverted): a raw autoroute snapshot must never be committed as the final routing. The autorouter's failures (nets it cannot close, via blow-ups, long detours) point to where placement is too tight; placement is then fixed by hand and re-transcribed into `boardgen/_project.py`.

---

## Working conventions for the assistant

### Communication
- Match the user's chat language. Repo content stays English regardless.
- Be concise. No padding, no unnecessary disclaimers.

### Privacy hygiene
- Scan every file mentally for "Public repository rules" before writing.
- Reject requests that would commit personal data; suggest gitignored local alternatives.
- If the user pastes PII, sanitize before committing and warn.

### Component selection
- Apply both design pillars (measurement quality, aesthetic acceptability) as filters BEFORE cost.
- For SMD parts through JLCPCB assembly: prefer Basic Parts Library (free assembly); Extended Library (~$3 setup per unique part) acceptable when needed.
- For manual-mount components (ESP32 module, SEN66, LD2410, terminal blocks, headers): pick on technical merit; sourcing is secondary.
- Report part numbers AND current availability when proposing components.
- Module identification (Lesson 10 above): mandatory for any dev module / breakout.

### KiCad schematic conventions
- `no_connect` markers on intentionally-unused IC pins (documents "this is deliberate, not an oversight").
- `(dnp yes)` flag for footprints that appear on the PCB but NOT in the assembly BOM (e.g. J2 / J10 recovery headers).
- Hierarchical labels for inter-sheet signals.
- ERC must be zero across the full project. Suppression via `rule_severities` is forbidden — fix the cause.

### PCB silkscreen conventions
- Every major component (sensor, connector, mounting hole class) carries a short F.SilkS text label identifying it. End user sees only silk; F.Fab is for machine-readable assembly drawings.
- **Board-id block** lives in the west pocket (freed by the NFC removal), centred on the central hole's horizontal axis (Y=0): five stacked text rows — board name, version, and the public repo URL split at its slashes (`github.com/` / `hubertciebiada/` / `open-ambient-sensor`; one 53-char line at the 1.0 mm `min_text_height` would be ~72 mm wide). Strings in `boardgen/_common.py` (`OAS_NAME_SHORT` / `OAS_VERSION_LINE` / `OAS_REPO_URL_SILK_LINES`), placement in `BOARD_ID_*` (`boardgen/_project.py`). A QR code was tried first and replaced by plain text per user decision (the QR needed a filled-poly exemption in the stage-13 silk lifter + scan-polarity care; text needs nothing). Note for text-width budgeting: KiCad stroke-font advance ≈1.36 mm/char at size 1.0 (empirical, from a DRC silk_overlap hit).
- Designators on hidden-Reference footprints (mounting holes, zip-tie holes, often Reference-hidden 2-pad SMD) emit as board-level `gr_text` from `gen_designator_labels()` so each instance can be positioned independently to avoid silk_overlap with nearby footprints.
- Cable-direction hints (`"-> J3"`, `"to SEN66"`) on both ends of cable-mating connectors.
- Over-document silkscreen — ink is free, an unlabeled board costs assembler time.

### Footprint generators
- Stub generators are 15-line wrappers around `_emit_stock_lib_footprint(src_path, lib_nickname, ...)`. Never contain hand-coded pad coordinates.
- For project-local footprints (`oas:*`), the same wrapper helper applies — the `lib_nickname` parameter selects either `Capacitor_SMD` / `Resistor_SMD` / etc. (KiCad stock) or `oas` (project library).
- Footprint property string MUST be canonical `Lib:Name`. Bare names trip `lib_footprint_mismatch` ERC.

### JLCPCB ordering (workflow distilled from v0.40 saga)
1. Parts Selection = **By Customer** (NOT By JLCPCB) so `lcsc_mapping.py` choices stick.
2. Download Assembly Order XLS preview AFTER matching, BEFORE submitting payment.
3. Diff Description column row-by-row against `lcsc_mapping.py`. Verify part class (Zener vs MOSFET) AND numeric value (`30.9 kΩ` not `806 Ω`). LCSC# alone is not sufficient evidence.
4. Iterate: any wrong row → "Replace Part" in UI → re-download XLS → re-diff. Loop until zero discrepancies.
5. Verify stock count per part is ≥ `qty × board_count × 2` (live JLCPCB stock can be consumed by parallel orders).
6. PCBA Standard tier (required for Extended Library parts). Confirm Parts Placement = YES ($1, strongly recommended for first-prototype). Photo Confirmation = YES.

### Validation
- Schematic: ERC zero, no warnings.
- PCB: DRC zero at production rules; verify 3D view against the 22 mm SEN66-zone / 17 mm default height.
- BOM: cross-check `lcsc_mapping.py` against current JLCPCB stock on the day of ordering.
- Firmware: ESPHome config compiles cleanly before tagging.

---

## Reference links

- AirGradient ONE (open-source inspiration): https://github.com/airgradienthq/arduino
- Sensirion SEN66 product page: https://sensirion.com/products/catalog/SEN66
- Sensirion SEN6x datasheet: https://sensirion.com/resource/datasheet/SEN6x
- HiLink LD2410C product page: https://www.hlktech.net/index.php?id=1095
- SZOMK AK-N-94 enclosure: https://www.chinaenclosure.com
- ESPHome documentation: https://esphome.io
- JLCPCB component library: https://jlcpcb.com/parts

---

## Memory rules (assistant)

- **Always git push after commit** in this repo. `git push origin main` runs automatically after every commit; no confirmation prompt.

---

## Changelog summary

Full historical detail lives in `git log --tags`. Highlights of the most recent milestones:

### Tag naming policy

Tags MUST be plain semver: `v<major>.<minor>` (e.g. `v0.51`) — or `v<major>.<minor>.<patch>` if it really is a patch (e.g. `v0.51.1`). **NO descriptive suffixes.** Forbidden: `v0.50-dfm-clean`, `v0.50-routing-rework`, `v0.40-validation-tighten`, etc. — those were legacy mistakes. A tag is an immutable version label, not a commit message; the description belongs in the changelog entry and the commit body. If it's a patch, it's `v0.51.1`. If it's a minor, it's `v0.52`. Nothing else.

The legacy suffixed tags listed below stay as-is (rewriting history is worse than the original mistake), but every new tag MUST be plain semver.

### Recent milestones

- **v0.54 — public release** (2026-09-14): repository prepared for public visibility and the GitHub release for the v0.54 board published with the production files (`oas-jlcpcb.zip`, BOM, CPL ×2, ibom). No hardware change since the order-approved `599b8a6` copper; firmware `project_version` bumped `v0.53-dev → v0.54` to match the silkscreen; README / firmware README / Status refreshed to the built-and-validated state; PII sweep of the working tree and the full git history clean (public-repository rules). Firmware commits between the design freeze and the release are the v0.54 bring-up: bench check script + fleet registry, LD2410C thresholds / Bluetooth-off hook, SEN66 STAR compensation, OTA-rollback note, dashboard grouping, Restart buttons.
- **v0.54** (2026-07-23): **Order-approved release.** No new PCB design work of its own — v0.54 is the `599b8a6` copper (the issue-#10 Q1 reverse-polarity fix `d24d855` + the full re-route it forced, 373 seg / 37 via) with `OAS_VERSION_LINE` bumped `v0.53 → v0.54` (one-glyph silk change in the board-id text block). Milestone: a SECOND five-reviewer GO/NO-GO panel returned **5 × ACCEPT** (electrical / routing-DFM / BOM-CPL / verification-integrity / holistic), reversing the 2026-07-22 panel's 4-REJECT verdict. What changed between the two panels: the sole copper blocker — Q1 source/drain swapped (reverse-polarity protection defeated) + F1 downstream of D1/Q1 — was fixed in `d24d855` and the board fully re-routed; U2 `+180` CPL rotation was owner-confirmed correct; JLCDFM re-ran clean on `599b8a6`. Each reviewer proved its own gate NON-VACUOUS by experiment (the headline: `05_check_dc.py` PASSes on the committed board but computes `V_24V_PROT = −23.1 V → exit 1` on a copy with Q1's S/D nets re-swapped; the via-geometry test's parse guards trip on an empty board; the historical D18.4 via-in-pad at rot 135° would re-fail the suite). `build.py` 35/35, DRC 0/0, 78/78 pytest. **Three order-time gates carried forward** (recorded in Status): fresh JLCDFM on the v0.54 gerbers (silk changed); the pre-payment Assembly XLS diff must explicitly cover the 7 SKUs stage 34 silently skips (esp. both regulators C116713 / C3200405 — Lesson 5); U2 Confirm-Parts-Placement + Photo Confirmation (pin-1 dot NW). Owner-waived: issue #9 radar bench gate, component stock. Implementation: 2 agents (Q1 logical fix; full re-route) + a 5-agent verification panel, then the version bump in the main session.
- **v0.52** (2026-06-09): Code-review remediation — tooling + CI hardening, **no PCB design change** (zero edits under `boardgen/`; emitted KiCad sources untouched). (1) **Lesson 12 closed**: `tools/extract_routes.py` resolves net references in both formats (`(net N "name")` KiCad-save AND boardgen's `(net N)` via the net-declaration table, loud failure on unknown codes) and refuses to overwrite `oas_routes.py` on a zero-record extraction; byte-identical round-trip on the committed board verified. (2) **First unit-test suite**: `hardware/kicad/tests/` — 48 tests covering deterministic-UUID guarantees (Lesson 9), `fmt()` formatting, D-shape / mounting-hole / LED-ring geometry invariants, POWER_BUDGET schema + derated rail sums (radio-group aware), routing-snapshot sanity, and the extract_routes round-trip — wired into stage 16 (compileall + pytest; hard-fail if pytest missing). (3) **Lesson 20 enforced**: stage 19 check D verifies J4 pins 1..5 = OUT/TX/RX/GND/VCC against the real anchors (`j4-p1-out`…`j4-p5-vcc-down` wire tags in `_sch_sensors.py` + `J4_PCB_ROTATION == 90`); the `J4_PIN_MAP` constant Lesson 20 previously cited never existed — reference corrected. (4) **Exit-code semantics**: `EXIT_VALIDATION=1` / `EXIT_MISSING_DEP=2` / `EXIT_IO=3` in `pipeline/_common.py`; missing-dep hard-fails in stages 09/12/15/22/34 and IO failures in `_spice.py` now exit 2/3; `build.py` SUMMARY prints `FAIL-DEP` / `FAIL-IO`. (5) README refreshed: v0.51-ordered status, "Can I build one today?" honesty section, rebuild-from-source instructions with full requirements. Doc corrections from test findings: routing snapshot is 613 seg + **42** vias (two GND vias removed by post-v0.50 DFM fixes), LED ring base pitch **Ø26 mm** (not Ø22), **7** LEDs (not 11), vacated slot is **D13** (not D14). Implementation: 5 parallel agents with exclusive file ownership; verification in-container: 48/48 pytest, compileall clean, mypy clean (73 files), pure-Python stages 05/07/14/16/19/29 PASS standalone (03/04/06/17 etc. require kicad-cli, absent in the session container — unchanged code paths).

- **v0.51** (2026-05-23): CI expansion — pipeline grew 29 → 35 stages (+5 new OAS checks + cascade extension to stage 08, ~58 s added to build time, no PCB design change). Stages added: **23** `check_power_budget` (per-rail current vs derated limits, single source of truth `POWER_BUDGET` TypedDict in `boardgen/_project.py` — Lesson 17); **25** `check_thermal` (LM2596 Tj=72.7 °C in 45 °C ambient — comfortable, 52 °C margin under TI Tj_max=125 °C); **26** `check_i2c_rise_time` (t_r=306/305 ns vs 1000 ns Standard-mode ceiling, ×3.3 margin); **27** `check_surge` (TWO ngspice IEC 61000-4-5 sims — Lesson 16: Sim 1 worst-case Q1 Vds=2.77 V vs 30 V, Sim 2 realistic LM2596 Vin=27.0 V vs 40 V abs max, with C1+F1+input bypass absorbing 40 V of the conservative-deck spike — confirms the alarming 67.6 V drain peak from Sim 1 was MODEL ARTIFACT); **28** `check_reverse_polarity` (D3 BZT52C10S forward-biased clamp holds |Vgs|=0.5 V vs 11 V threshold — 1 V buffer under AO3401A 12 V hard max). Stage **08** refactored to import from new shared `pipeline/oas/_spice.py` harness (Lesson 18); cascade 24V→5V→3V3 soft-start sim added (behavioural fallback for TPS62933 — Lesson 19). Implementation: 7 Opus agents in 3 dependency-ordered batches via the multi-agent dispatch pattern (POWER_BUDGET → thermal; `_spice.py` → surge/reverse-pol/cascade); each agent strictly scoped to one file to avoid conflicts. Board passes every new check on first run — no design changes triggered. 35/35 PASS in ~173 s.

- **v0.50-routing-rework** (2026-05-22): Placement + routing rework on a clean baseline (the bad raw-autoroute `dd98a8b` had been reverted). **Placement** (all committed, DRC 0, build 30/30): (1) USB-C case-wall cutout made non-blocking for the autorouter — `gen_cutouts()` emits a keepout only for pad-less cutouts; (2) input-protection cluster (D1/F1/Q1/D3/R4/R1) rotated into two vertical columns under ZT1; (3) the 20-part buck section under the ESP32 re-spread from 3 cramped bands into a clean 2-row grid in the J5↔J6 gap — west→east power flow, ~5.7 mm routing corridor between rows, courtyards ≥3.6 mm from the THT pin rows (the old layout tripped a JLCPCB-DFM Danger at 1.26 mm); (4) C12 NFC decoupling moved next to J7 pin 7 (+3V3) — it had been ~13 mm away at the INT-pin level (a stale-comment pin-numbering bug from the v0.43 J7/J8 flip); (5) five LED-ring decoupling caps (C20/C24/C25/C26/C27) pulled to cap-radius 7.0 mm to free the inner annulus. JLCDFM-strict design rules (0.20 mm clearance, 0.70/0.30 mm vias, 0.25 mm track). **Routing — COMPLETED**: the earlier checkpoint snapshot (405 seg + 22 via) turned out **stale** — it had been extracted against a pre-Task-3 buck placement, so replaying it onto the committed placement shorted the buck section (87 DRC violations). The routing was re-run from scratch: Freerouting 2.2.4 (Docker `eclipse-temurin:25-jre`) against the *current* committed placement, on a DSN patched to JLCDFM-strict rules (clearance 0.20 mm, via 0.70/0.30 mm) — full **89/89 coverage, 0 unrouted nets**. After SES import, the F.Cu GND pour (which KiCad's zone-fill fragments into ~19 islands around the 89 signal nets — an artifact downstream of Freerouting, which sees GND as an idealised plane) was hand-stitched in KiCad: stitching vias + short GND tracks reconnecting every fragment to the continuous B.Cu pour. Final snapshot `oas_routes.py` = **613 seg + 44 via**; `ROUTING_CHUNKS = ("gnd", "autoroute")`; `pipeline/generic/03_drc.py` `EXPECTED_UNCONNECTED = 0`; `build.py` **30/30 PASS**, DRC **0 violations / 0 unconnected**.

- **v0.42-F1-fuse-fix** (2026-05-20): F1 PTC fuse — corrected both a wrong BOM part and a mismatched footprint, flagged by JLCPCB DFM ("pin inner edge"). (1) **Wrong part (Lesson 5):** `lcsc_mapping.py` carried LCSC `C262023` labelled "Littelfuse 1812L075THDR / 75 V" — but `C262023` is actually **TLC-MSMD050, a 15 V / 500 mA fuse** (confirmed via the EasyEDA component API + the LCSC product page), under-rated for the 24 V rail. Corrected to **`C151170` = Littelfuse 1812L075/33DR** (33 V / 750 mA hold / 1.5 A trip) — verified part identity from two sources before any order. 33 V clears the 24 V SELV rail with margin (the 1812L075 family tops out at 33 V; 60 V needs the larger 2920 body). (2) **Mismatched footprint:** F1 used KiCad stock `Fuse:Fuse_1812_4532Metric`, a generic IPC chip-fuse land (pad gap 3.15 mm). The Littelfuse 1812L termination bands are wide and the part wants a tighter land (gap 2.30 mm) — the stock pads left the part's pin inner edge 0.43 mm off the copper. New project-local footprint **`oas:Fuse_1812L_4532Metric`** — pad geometry is the verbatim EasyEDA F1812 land of `C151170` (the exact data JLCPCB DFM resolves against). 3D model keeps the KiCad-stock `R_1812_4532Metric.step` 1812-chip surrogate. Whitelist in stage 18 grows to 10 documented OAS customs. Schematic value `PTC 750mA / 75V` → `33V`.

- **v0.40-validation-tighten** (2026-05-20): Pipeline grew from 20 to 29 stages — 9 new checks closing real failure modes from the v0.40 lessons-learned. Key additions: `oas.kicad_dru` JLCPCB-tuned custom DRC rules emitted by new boardgen stage 14 (auto-loaded by kicad-cli pcb drc); stage 09 schematic semantic invariants via kicad-skip (I²C pull-ups R5/R6, GPIO 8 pull-up R7, no_connect coverage); stage 15 mypy on pipeline/; stage 16 compileall sanity; stage 17 rule_severities=={} enforcement (Lesson 3); stage 18 hand-coded pad geometry forbid (Lesson 1) with whitelist for 9 documented OAS customs; stage 19 EXTERNAL_MODULES + lcsc_mapping schema lint (Lessons 10 + Gap H); stage 22 InteractiveHtmlBom artefact (vendor-neutral `hardware/output/oas-ibom.html`); stage 34 LCSC# class/value match vs offline jlcparts SQLite cache (Lesson 5 — would have caught the v0.40 R3 C23116 = 806 Ω near-miss before payment); stage 35 oas-jlcpcb.zip content audit (Gap D). 4 new git submodules under `hardware/kicad/third_party/`: kicad-skip, InteractiveHtmlBom, jlcparts, kicad-jlcpcb-dru. Setup helper `tools/setup_jlcparts_cache.py` downloads the upstream 41-volume split-ZIP catalogue and extracts to `.tmp/jlcparts/cache.sqlite3` (manual one-time action, ~2 GiB → ~26 GiB SQLite). Soft-skips removed — every new stage hard-fails on missing dependency with explicit setup instructions. 29/29 PASS in ~185 s.

- **v0.40-build-harness** (2026-05-19): Renamed the top-level orchestrator `regenerate.py` → `build.py` and removed the `generate.py` shortcut at the repo root. The boardgen walker now lives at `pipeline/generic/01_emit_sources.py` (stage 01 of `build.py`); the former `pipeline/generic/01_generate.py` subprocess wrapper is gone. Motivation: AI-agent harness — when there were two top-level entrypoints (the fast-but-incomplete `generate.py` and the comprehensive `regenerate.py`), an autonomous agent could rationalize "I'll just rebuild the sources" and silently commit a board state that had never seen DRC / ERC / determinism / DC / ampacity / boot-strap / preflight / vendor-export checks. With a single entrypoint, the harness always runs the full pipeline. Also renamed `hardware/output/jlcpcb/oas-bom.csv` → `oas-BOM.csv` for consistency with the already-uppercased `oas-{top,bottom}-CPL.csv` (manufacturer acronyms uppercase). 20/20 PASS post-refactor; boardgen output bit-identical pre vs post.

- **v0.40-vendor-split** (2026-05-19): Reorganized production pipeline around vendor isolation. New `pipeline/jlcpcb/` sibling to `generic/` and `oas/` holds every JLCPCB-specific stage (29 BOM consistency, 30 CPL export with rotation offsets, 31 BOM with LCSC + library tier, 32 ZIP bundle, 33 DNP consistency) plus `_rotations.py` (moved from `hardware/kicad/jlcpcb_rotations.py`). Stage 20 now emits raw vendor-neutral gerbers + drill to `hardware/build/gerbers/` (gitignored intermediate), and stage 24 preflight verifies that raw data without touching any vendor ZIP. Output reorganized: `hardware/output/jlcpcb/` carries EXACTLY 4 committed deliverables (ZIP + BOM + 2× CPL). Position files renamed `oas-{top,bottom}-pos.csv` → `oas-{top,bottom}-CPL.csv` to match JLCPCB's own terminology. Adding a second fabricator now reduces to creating a sibling `pipeline/<vendor>/` + `hardware/output/<vendor>/` with zero edits to existing `generic/` or `oas/` stages. boardgen output (`oas.kicad_pcb`, `oas.kicad_sch`, 4 sub-sheets, `OAS.kicad_sym`, 7 `.kicad_mod`, lib tables) byte-identical pre vs post; 20/20 PASS in ~115 s.

- **v0.40-audit-16** (2026-05-17): Full canonical-name + ERC-clean sweep. Audit-16 caught four classes of canonical-name defects the audit-15 swarm had missed (focusing on pad geometry, not on the `(footprint "Lib:Name"` header itself): U1 / U2 non-canonical headers, J2 missing lib prefix, ZT1..ZT4 missing `oas:` prefix. Q1's `lib_footprint_mismatch` workaround (`rule_severities: {"...": "ignore"}` + `pin_name_map` G/S/D remap) eliminated by creating project-local `OAS:Q_PMOS_GDS` schematic symbol with numeric pin numbers 1/2/3 + letter pin NAMES. Final state: DRC 0, ERC 0 / 0 errors / 0 warnings, `rule_severities` empty `{}`, determinism PASS, Z-clearance PASS, every footprint header uses canonical `<lib>:<name>` or `oas:<name>`.

- **v0.40-post-order footprint sweep** (2026-05): 78-agent paranoid audit found ~24 SMD passive footprints sharing the same custom-stub deviation root cause as the v0.40 JLCPCB U1 / U2 rejection. Refactored 9 generators (`gen_capacitor_0402/0603/0805`, `gen_resistor_0603`, `gen_diode_sma/smb/sod323`, `gen_inductor_smd_5x5`, `gen_polyfuse_smd`) + Q1 SOT-23 + radial THT to verbatim stock-library parsing via `_emit_stock_lib_footprint`. L1 / L2 footprint name corrected from `L_APV_ANR5040` to `L_Cenker_CKCS5040` (matching actual LCSC parts).

- **v0.40-post-order**: Production firmware skeleton added (5-package ESPHome config + web_server dashboard) so the user can flash on day 1 of hardware delivery. JLCPCB rejected the original v0.40 SMT order (5 prototypes, ~712 PLN) due to U1 LM2596S TO-263-5 + U2 TPS62933 SOT-583 footprints emitting non-stock pad geometry; immediate surgical refactor of `gen_to263_5_pcb_footprint` and `gen_sot583_pcb_footprint` to verbatim stock parsing, followed by the wider audit-15 / audit-16 sweep.
