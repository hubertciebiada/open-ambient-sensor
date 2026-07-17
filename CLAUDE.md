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

The same class of mistake hit ESP32-C6 GPIO 10 / 11 (v0.3 prescribed them as pin reassignment targets — but those pins are physically NOT bonded out on any ESP32-C6 SiP-flash variant); the LD2410 pin order (pre-v0.15.8 had VCC ↔ OUT reversed); the Q1 D3 dissipation math (off by 100×); and the AO3401A Vgs_max value (one audit doc said ±20 V, datasheet says ±12 V).

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

### 20. LD2410B pin order — authoritative confirmation (user-verified 2026-05-23)

J4 pin numbering on OAS, FROM LEFT (as physically soldered) when looking at the LD2410B daughterboard face-up: **pin 1 = OUT, pin 2 = UART TX, pin 3 = UART RX, pin 4 = GND, pin 5 = VCC**. This matches the `J4_PCB_X / J4_PCB_Y / J4_PCB_ROTATION` block in `boardgen/_project.py` and the J4 wiring block in `boardgen/_sch_sensors.py` (wire uuid tags `j4-p1-out` … `j4-p5-vcc-down`) exactly — enforced automatically since v0.52 by stage 19 check D (note the net-name crossover: J4 pin 2 = LD2410 TX lands on the `UART_RX` net, pin 3 = LD2410 RX on `UART_TX`). The historical v0.15.8 schematic-reversal + v0.43 footprint-flip + re-revert was a CORRECTED sequence — current state is right. Do NOT rely on memory or web snippets for LD2410 pin order — quote this Lesson + the HLK V1.04 datasheet Table 1 (page 7) as the authoritative source. Any future audit-prompt that asserts a different mapping (e.g. "1=VCC..5=OUT") is wrong.

---

## Lessons learned (v0.53 prototype bring-up)

### 21. J3 (SEN66) board-side pinout MIRRORS SEN6x Table 16 — a flat JST GH lead reverses pin positions end-to-end (bench-confirmed 2026-06-30)

Sensirion SEN6x datasheet v0.92 (Dec 2025) Table 16 (p. 15) specifies the **MODULE-side** receptacle: 1=VDD, 2=GND, 3=SDA, 4=SCL, 5=GND (tied to 2), 6=VDD (tied to 1). The OAS board-side J3 must be wired as that table's positional MIRROR — **1=VDD, 2=GND, 3=SCL, 4=SDA, 5=GND, 6=VDD**. Mechanism, in three steps: (a) both cable ends are polarized GH-family connectors — the latch/shroud keying makes reversed insertion impossible, so housing position N always mates header pin N (JST GH datasheet p. 1, "housings are designed to prevent incorrect mating"); (b) a standard flat parallel-wire GH lead has both housings crimped on the same face of the wire row, which between two face-to-face headers maps header-A pin k ↔ header-B pin 7−k — a full positional mirror (1↔6, 2↔5, 3↔4); (c) Sensirion's pinout is deliberately power-symmetric (pins 1/6 and 2/5 internally tied), so the mirror is invisible on the power pins and manifests ONLY as an SDA↔SCL swap. The v0.51 boards copied Table 16 pin-for-pin onto J3 → SEN66 powered up but never ACKed at 0x6B; swapping the I²C pins in firmware (`sda: GPIO7 / scl: GPIO6`) made it fully functional with a straight cable — the bench proof of the crossing (issue #6). Fix (this Lesson's origin): J3 pins 3/4 swapped in `boardgen/_sch_sensors.py` (wire tags `j3-p3-scl` / `j3-p4-sda`); on copper, the corridor nets swap at the two I²C bridge vias, which made the pre-existing west-end braid (each via fed the OPPOSITE F.Cu trunk) unnecessary — replaced by two direct via→trunk connectors (−4/+3 segments); firmware defaults back to `sda: GPIO6 / scl: GPIO7` with a substitution override for v0.51 boards (`firmware/esphome/examples/v0.51-board.yaml`). Enforced by stage 19 **check E** anchored to the `j3-p*` wire tags. Any future audit asserting "J3 pin 3 must be SDA because Table 16 says pin 3 = SDA" is WRONG — Table 16 is the module side; the host side mirrors. CAVEAT: the design standardizes on the flat parallel-wire GH lead (the style verified on the bench); an opposite-crimp lead (housings on opposite faces of the wire row — electrically position-1:1, the Qwiic-cable style) would re-cross SDA/SCL on the fixed board. Check the crimp style when sourcing replacement cables.

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

**v0.51 boards ordered at JLCPCB on 2026-05-24** (prototype run, 5 units, full SMT assembly, PCBA Standard tier with Confirm Parts Placement + Photo Confirmation enabled per Lesson 5; Assembly Order XLS diff verified clean against `lcsc_mapping.py` before payment — awaiting delivery). Bare PCB carries the v0.51 silkscreen on top of the v0.50 routing snapshot (89/89 + hand-stitched GND). One BOM deviation accepted at order time: **J3 = XY-SM06B-GHS-TB clone** (genuine JST GH SM06B-GHS-TB C133065 was out of stock at LCSC; XY clone is mechanically equivalent for the 1.25 mm JST GH cable mate — accepted for the 5-unit prototype; if the SEN66 cable latch proves unreliable in the clone, genuine JST will be swapped in by hand from TME/Mouser). Schematic + PCB layout closed. Every placed footprint header uses canonical `<lib>:<name>` from KiCad stock or `oas:<name>` from the project-local library — zero bare names. Custom `oas:` geometry is used only where a stock entry is absent OR geometrically wrong for the exact ordered part; every such case is enumerated in the "Deviation budget" with a technical reason.

**v0.50 routing — COMPLETE.** The board is fully routed and DRC-clean: `ROUTING_CHUNKS = ("gnd", "autoroute")`, `build.py` **35/35 PASS** (post-v0.51 CI expansion), DRC **0 violations / 0 unconnected pads**. The signal routing was re-run with Freerouting 2.2.4 (Docker) against the *current* committed placement — full **89/89** coverage, 0 unrouted nets — then imported, and the fragmented F.Cu GND pour was hand-stitched in KiCad (GND pour fragments reconnected to the continuous B.Cu pour by stitching vias + short GND tracks). Final snapshot in `oas_routes.py`: **613 segments + 42 vias** (two GND stitch vias removed by the post-v0.50 DFM fixes — Lesson 14 via-in-pad + the J4 UART_RX re-route; `tools/extract_routes.py`). `EXPECTED_UNCONNECTED` in `pipeline/generic/03_drc.py` is now `0` (the board is fully routed; any non-zero count is a regression).

Note on the GND pour: Freerouting sees GND as an idealised `plane` (every pad on the plane = connected), so it never routes GND stitches. The F.Cu pour only fragments later, when KiCad re-fills the zone around all 89 signal nets — a zone-fill artifact downstream of Freerouting. Hand-stitching the fragments is the standard remedy and does not degrade the GND plane (the stitches are supplementary to the pour).

Firmware skeleton (5-package ESPHome config) landed v0.40-post-order; awaiting hardware delivery for actual flashing.

---

## Project goals

Per-room sensor measures:
- **Air quality**: CO2, PM1 / 2.5 / 4 / 10, VOC index, NOx index, temperature, humidity (Sensirion SEN66)
- **Occupancy / presence**: mmWave radar with stillness detection (HiLink HLK-LD2410B)

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
| Presence | **HiLink HLK-LD2410B** (-B variant specifically — NOT -C; pin order and body dims differ per HLK datasheet) | HiLink / TME / AliExpress | UART 256000 baud |
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
| GPIO 16 | UART1 TX → LD2410 RX | 256000 baud |
| GPIO 17 | UART1 RX ← LD2410 TX | 256000 baud |
| GPIO 2 | LD2410 OUT (presence interrupt) | safe non-strap input |
| GPIO 8 | WS2812 DIN → external SK6812-SIDE AQI ring | strap pin (LED idles low — OK); **R7 = 10 kΩ external pull-up to +3V3 required** (DevKitM-1's onboard pull-up depends on VCC_5V which floats in OAS) |
| GPIO 12 / 13 | Native USB-Serial-JTAG D+ / D− | one of the two USB-C ports |

**Reserved / unavailable**:
- **GPIO 10, GPIO 11**: physically NOT bonded out on ESP32-C6FH4 (internal SiP flash uses these pins). Unavailable on every MINI-1 / SuperMini / XIAO / DevKitM-1 variant.
- **Strap pins (avoid for general I/O)**: GPIO 4 (MTMS), 5 (MTDI), 9 (BOOT button on DevKitM-1), 15 (boot-mode select).

**Available safe-non-strap spare GPIOs** (for future expansion): 0, 1, 3, 14, 18, 19, 20, 21, 22, 23 — ten pins free. (GPIO 1 freed in v0.53 when the SW1 push-button was removed — GitHub issue #5; GPIO 3 freed when the NFC tag was removed — GitHub issue #7.)

### Architectural decisions

- **SEN66 mounts on the PCB**, flat on its 55.2 × 25.6 mm back face with the air-side face UP toward the AK-N-94 perforated cover. Body sticks 21.5 mm above PCB. **Zip-tie retention** through 4 NPTH holes (Ø ~3 mm) along the two long edges. PCB-mounted JST GH socket (J3) on the SEN66's +X short edge. J3 is wired as the positional MIRROR of the SEN6x Table 16 module pinout (1=VDD, 2=GND, **3=SCL, 4=SDA**, 5=GND, 6=VDD) so a straight flat JST GH lead lands SDA→SDA / SCL→SCL — see Lesson 21; enforced by stage 19 check E.
- **Hard limit #1 lifted to ≥22 mm in the SEN66 zone** (default 17 mm elsewhere) — verified against physical AK-N-94 sample.
- **PCB has F.CrtYd on the SEN66 mech-ref footprint** (zero standoff — body lies flat on PCB) as a programmatic guardrail. The v0.21→v0.22 misconception "SEN66 floats above PCB" cost an entire iteration; the F.CrtYd now mechanically prevents SMD placement under the SEN66 body shadow.
- **AQI LED ring** (7 × SK6812-SIDE on a Ø26 mm base pitch circle around the central cable hole; per-slot radius overrides 11.0 / 16.5 mm, historically set to clear J1 and the since-removed MOD2 — see `LED_RING_RADIUS` + overrides in `boardgen/_project.py`). LEDs emit radially outward, parallel to the PCB — the cover never sees the die in line-of-sight, no "dot-through-perforation" artifact. The D13 slot (θ = 90°) is vacated for the J1 24 V terminal block on the SOUTH side. Each LED carries a 100 nF 0402 decoupling cap; the ring is powered from the LM2596S +5 V rail.
- **Shared I²C bus**: SEN66 + Qwiic expansion. Realized bus length ~140 mm PCB MST + ~80 mm SEN66 JST GH cable = **~220 mm total**. Exceeds Sensirion's "< 100 mm recommended" envelope but stays within their "< 500 mm with shielding" hard limit. 4.7 kΩ pull-ups give t_r ≈ 1 µs at 100 kHz (within standard-mode spec); 10 kΩ would have failed the rise-time check.
- **GPIO 8 external pull-up R7 = 10 kΩ to +3V3** — required because the DevKitM-1's onboard pull-up relies on VCC_5V (which OAS leaves floating; we feed +3V3 directly into J5.1).
- **Onboard DevKitM-1 NeoPixel is unreachable** in deployed units (its VDD ties to VCC_5V). The external SK6812-SIDE ring is the active indicator; the onboard pixel is a no-op in firmware.
- **Bluetooth proxy** = software-only; no extra hardware.

### Deviation budget — components not under KiCad stock library

Every placed footprint is verbatim KiCad stock OR a project-local OAS footprint with a documented technical reason. The complete deviation list:

| Designator(s) | Footprint | Reason |
|---|---|---|
| MOD1 | `oas:ESP32-C6-DevKitM-1_Reference` | Mechanical reference for the ESP32-C6-DevKitM-1 daughterboard (no pads, body shadow only). No KiCad stock entry exists. |
| LDR1 | `oas:LD2410_Mechanical_Reference` | Mechanical reference for the HLK-LD2410B daughterboard (no pads, body shadow only). No KiCad stock entry exists. |
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
- 8+ LED effects with web_server-driven brightness / effect / mode (Auto-AQI / Manual / Off / Test-Rainbow). Day-night auto-dim.
- SEN66 sensor offsets (temperature, humidity, CO2) exposed as `number:` entities preserved across reboots.
- STAR-Engine IAQM Light preset (T1=1000, T2=3000, K=200, P=200 raw I²C 16-bit, ×10 of post-scale display values) re-uploaded on every boot via `on_boot:` lambda (Sensirion params are volatile per datasheet).
- LD2410 per-gate sensitivity, max-distance, and timeout exposed as `number:` / `select:` entities.
- Bluetooth proxy enabled.

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
- [x] **Routing rework (v0.50) — DONE.** Board fully routed, `ROUTING_CHUNKS = ("gnd", "autoroute")`, `build.py` 30/30 PASS, DRC 0/0. Snapshot in `oas_routes.py` (613 seg + 42 via after the post-v0.50 DFM via removals).
- [ ] Re-run the JLCPCB DFM check on the fully-routed gerbers (target 0 Danger / 0 Warning).
- [ ] Receive v0.40 prototypes from JLCPCB; hand-solder the 7 THT components (J1 / J4 / J5 / J6 / C1 / C3 / C4).
- [ ] Optional v2 substitutions (deferred): Q1 → AON7415 for actual positive Vds margin (-40 V vs SMBJ24A 38.9 V clamp); L1 → 6045 / 1264 body if production load grows beyond 1.2 A continuous.
- [ ] Foam shroud / cover baffle separating SEN66 inlet zone from outlet zone (open mitigation; decision pending physical-prototype recirculation measurement).

### Firmware
- [ ] First-flash on delivered prototype.
- [ ] LD2410 UART integration shakedown.
- [ ] OTA setup against real hardware.
- [ ] HA discovery / device class metadata validation.

### Logistics
- [ ] Receive ordered AK-N-94 enclosure + SEN66 + LD2410B samples.
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
    │   ├── tests/                  # pytest unit suite (UUID determinism, geometry invariants, POWER_BUDGET, routes snapshot, extract_routes round-trip) — run by stage 16
    │   └── tools/                  # MANUAL-trigger scripts (extract_routes, jlcdfm_upload, setup_jlcparts_cache)
    ├── build/                      # INTERMEDIATE artifacts (gitignored)
    │   └── gerbers/                # raw Protel gerbers + Excellon drill + drill_map PDF
    ├── renders/                    # generated previews (PNG + SVG, sibling of kicad/)
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
   - `16_lint_compileall` — `python -m compileall` over `boardgen/` + `pipeline/` + `tools/` + `tests/` (catches syntax errors in modules not on the happy path), then runs the pytest unit suite in `tests/` (UUID determinism, geometry invariants, POWER_BUDGET sums, routing-snapshot sanity, extract_routes round-trip). Hard-fails if `pytest` is not importable.
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
- HiLink LD2410 documentation: https://www.hlktech.net
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
