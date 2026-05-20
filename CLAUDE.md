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

**v0.40 boards in flight at JLCPCB** (first prototype run, 5 units, full SMT assembly, ordered post-audit-16 — awaiting delivery). Schematic + PCB layout closed. Every placed footprint header uses canonical `<lib>:<name>` from KiCad stock or `oas:<name>` from the project-local library — zero bare names, zero custom geometry for any component covered by a stock library entry.

Routing rework is pending (separate task) — the v0.40-post-order footprint refactor invalidated the autoroute snapshot in `oas_routes.py`; `ROUTING_CHUNKS` is currently reduced to `("gnd",)` only. The GND copper pour gives every GND pad a connection; non-GND signal nets show as unconnected pads (warning, not error).

Firmware skeleton (5-package ESPHome config) landed v0.40-post-order; awaiting hardware delivery for actual flashing.

---

## Project goals

Per-room sensor measures:
- **Air quality**: CO2, PM1 / 2.5 / 4 / 10, VOC index, NOx index, temperature, humidity (Sensirion SEN66)
- **Occupancy / presence**: mmWave radar with stillness detection (HiLink HLK-LD2410B)

Additional features:
- RGB AQI status ring (11 × SK6812-SIDE LEDs) with breathing effect; color reflects aggregated air quality index
- Dynamic NFC tag (NXP NT3H1101 on MIKROE-2462 daughterboard) — phone tap reads live data and serves URL to user's dashboard
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
| NFC dynamic tag | **MIKROE-2462 NFC Tag 2 Click** (NXP NT3H1101 + onboard PCB antenna, mikroBUS L) | MikroE / TME | I²C 0x55 + NFC |
| Power input | Phoenix Contact MSTBA 2,5/3-G-5,08 3-pos terminal | THT hand-solder | 24 V DC |
| Reverse-polarity | **AO3401A** P-MOSFET (SOT-23) + BZT52C10S Zener clamp (SOD-323) + 100 k pull-down + 1 k gate series | LCSC C15127 / C19334 / C25803 / C21190 | — |
| TVS | **Brightking SMBJ24A** (SMB, unidirectional 24 V) | LCSC C87268 | — |
| PTC fuse | **Littelfuse 1812L075THDR** (750 mA hold, 1.5 A trip, 75 V) | LCSC C262023 | — |
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
| GPIO 6 | I²C SDA | shared bus: SEN66 (0x6B), NT3H1101 (0x55, on MIKROE-2462), J9 Qwiic |
| GPIO 7 | I²C SCL | shared bus, **4.7 kΩ pull-ups on MCU side** (220 mm total bus length — see "Shared I²C bus" below) |
| GPIO 16 | UART1 TX → LD2410 RX | 256000 baud |
| GPIO 17 | UART1 RX ← LD2410 TX | 256000 baud |
| GPIO 2 | LD2410 OUT (presence interrupt) | safe non-strap input |
| GPIO 3 | NT3H1101 FD (NFC field-detect interrupt) | safe non-strap input |
| GPIO 8 | WS2812 DIN → external SK6812-SIDE AQI ring | strap pin (LED idles low — OK); **R7 = 10 kΩ external pull-up to +3V3 required** (DevKitM-1's onboard pull-up depends on VCC_5V which floats in OAS) |
| GPIO 12 / 13 | Native USB-Serial-JTAG D+ / D− | one of the two USB-C ports |

**Reserved / unavailable**:
- **GPIO 10, GPIO 11**: physically NOT bonded out on ESP32-C6FH4 (internal SiP flash uses these pins). Unavailable on every MINI-1 / SuperMini / XIAO / DevKitM-1 variant.
- **Strap pins (avoid for general I/O)**: GPIO 4 (MTMS), 5 (MTDI), 9 (BOOT button on DevKitM-1), 15 (boot-mode select).

**Available safe-non-strap spare GPIOs** (for future expansion): 0, 1, 14, 18, 19, 20, 21, 22, 23 — nine pins free.

### Architectural decisions

- **SEN66 mounts on the PCB**, flat on its 55.2 × 25.6 mm back face with the air-side face UP toward the AK-N-94 perforated cover. Body sticks 21.5 mm above PCB. **Zip-tie retention** through 4 NPTH holes (Ø ~3 mm) along the two long edges. PCB-mounted JST GH socket (J3) on the SEN66's +X short edge.
- **Hard limit #1 lifted to ≥22 mm in the SEN66 zone** (default 17 mm elsewhere) — verified against physical AK-N-94 sample.
- **PCB has F.CrtYd on the SEN66 mech-ref footprint** (zero standoff — body lies flat on PCB) as a programmatic guardrail. The v0.21→v0.22 misconception "SEN66 floats above PCB" cost an entire iteration; the F.CrtYd now mechanically prevents SMD placement under the SEN66 body shadow.
- **AQI LED ring** (11 × SK6812-SIDE on Ø22 mm pitch around the central cable hole). LEDs emit radially outward, parallel to the PCB — the cover never sees the die in line-of-sight, no "dot-through-perforation" artifact. The D14 slot (θ = 90°) is vacated for the J1 24 V terminal block on the SOUTH side. Each LED carries a 100 nF 0402 decoupling cap; the ring is powered from the LM2596S +5 V rail.
- **Shared I²C bus**: SEN66 + NT3H1101 + Qwiic expansion. Realized bus length ~140 mm PCB MST + ~80 mm SEN66 JST GH cable = **~220 mm total**. Exceeds Sensirion's "< 100 mm recommended" envelope but stays within their "< 500 mm with shielding" hard limit. 4.7 kΩ pull-ups give t_r ≈ 1 µs at 100 kHz (within standard-mode spec); 10 kΩ would have failed the rise-time check.
- **GPIO 8 external pull-up R7 = 10 kΩ to +3V3** — required because the DevKitM-1's onboard pull-up relies on VCC_5V (which OAS leaves floating; we feed +3V3 directly into J5.1).
- **Onboard DevKitM-1 NeoPixel is unreachable** in deployed units (its VDD ties to VCC_5V). The external SK6812-SIDE ring is the active indicator; the onboard pixel is a no-op in firmware.
- **Bluetooth proxy** = software-only; no extra hardware.

### Deviation budget — components not under KiCad stock library

Every placed footprint is verbatim KiCad stock OR a project-local OAS footprint with a documented technical reason. The complete deviation list:

| Designator(s) | Footprint | Reason |
|---|---|---|
| MOD1, MOD2, LDR1, SENS1 | `oas:*_Reference` | Mechanical references for daughterboards / SEN66 (no pads, body shadow only). No KiCad stock entry exists. |
| H1..H3 | `oas:MountingHole_3.8mm_M3` | Custom Ø3.8 mm NPTH for SZOMK AK-N-94 manufacturer spec (between stock Ø3.2 mm and Ø4.0 mm sizes). |
| ZT1..ZT4 | `oas:ZipTieHole_3mm_NPTH` | Custom Ø3.0 mm NPTH for SEN66 zip-tie retention. |
| D11..D22 | `oas:SK6812-SIDE` | OAS-custom 4020 side-emit LED footprint matching OPSCO / Normand SK6812 SIDE-A datasheet pinout (1=DIN, 2=VDD, 3=DOUT, 4=GND — DIFFERENT from KiCad stock `LED:SK6812` which is the PLCC4 5050 with 1=VSS, 2=DIN, 3=VDD, 4=DOUT). |
| Q1 | `Package_TO_SOT_SMD:SOT-23` (stock) | Schematic uses project-local `OAS:Q_PMOS_GDS` symbol with numeric pin numbers 1/2/3 (pin NAMES G/S/D for readability). Footprint geometry is verbatim stock. |

No "hand-solder friendly" deviations remain anywhere in the design.

---

## Software

- **Framework**: ESPHome (YAML configuration)
- **HA integration**: native API
- **OTA**: ESPHome + HA
- **BLE proxy**: ESPHome `bluetooth_proxy:` component
- **NFC dynamic content**: `nt3h*` external component wrapping the NT3H1101 register map

Current firmware skeleton (added v0.40-post-order):
- `firmware/esphome/oas.yaml` top-level + 5 packages in `packages/`: core, leds, air-quality, presence, nfc, bt-proxy.
- 8+ LED effects with web_server-driven brightness / effect / mode (Auto-AQI / Manual / Off / Test-Rainbow). Day-night auto-dim.
- SEN66 sensor offsets (temperature, humidity, CO2) exposed as `number:` entities preserved across reboots.
- STAR-Engine IAQM Light preset (T1=1000, T2=3000, K=200, P=200 raw I²C 16-bit, ×10 of post-scale display values) re-uploaded on every boot via `on_boot:` lambda (Sensirion params are volatile per datasheet).
- LD2410 per-gate sensitivity, max-distance, and timeout exposed as `number:` / `select:` entities.
- NT3H1101 NFC dynamic tag: live sensor JSON written to NTAG memory every 60 s; dashboard URL configurable via web_server text entity.
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
- ❌ Display (OLED / LCD round) — researched mid-2026; Waveshare 1.28" GC9A01 clears Pillar #1 but fails Pillar #2 (permanent dark grey circle on the white cover breaks the smoke-detector silhouette). NFC + LED ring + HA dashboard already cover the "see the data" need.
- ❌ External USB-C connector on the case wall (use DevKitM-1's own USB-C for programming; OTA after first flash)
- ❌ IR transmitter / receiver
- ❌ Microphone / acoustic sensor
- ❌ Ambient light sensor (VEML7700) — removed v0.10. Shielding from the onboard NeoPixel + power LED inside the perforated case would require additional 3D-printed parts; not core to OAS mission.

---

## Open work / TODO

### Hardware
- [ ] Routing rework — full re-route of the buck section + all I/O signals via Freerouting on a clean baseline. `ROUTING_CHUNKS` currently `("gnd",)` only; autoroute / io_finalize chunks remain disabled.
- [ ] Receive v0.40 prototypes from JLCPCB; hand-solder the 9 THT components (J1 / J4 / J5 / J6 / J7 / J8 / C1 / C3 / C4).
- [ ] Optional v2 substitutions (deferred): Q1 → AON7415 for actual positive Vds margin (-40 V vs SMBJ24A 38.9 V clamp); L1 → 6045 / 1264 body if production load grows beyond 1.2 A continuous.
- [ ] Foam shroud / cover baffle separating SEN66 inlet zone from outlet zone (open mitigation; decision pending physical-prototype recirculation measurement).

### Firmware
- [ ] First-flash on delivered prototype.
- [ ] LD2410 UART integration shakedown.
- [ ] NFC dynamic tag content updater verification.
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
│   │   ├── packages/               # core / leds / air-quality / presence / nfc / bt-proxy
│   │   └── examples/               # anonymized per-device override examples
│   └── secrets.yaml.example
└── hardware/
    ├── kicad/
    │   ├── build.py                # THE ONLY top-level entrypoint — runs every pipeline/<subdir>/NN_*.py in order (AI-agent harness)
    │   ├── boardgen/               # KiCad source-file generators — one numbered stage per output
    │   │   ├── _common.py          # UUID system (U, sheet_context), fmt, Context dataclass, sub-sheet IDs
    │   │   ├── _project.py         # OAS-specific: EXTERNAL_MODULES, GPIO_*, geometry, daughterboard placement
    │   │   ├── _footprints.py      # all gen_*_footprint + gen_*_pcb_footprint + placement orchestrators
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
    │   │   │   ├── 16_lint_compileall.py # python -m compileall sanity check
    │   │   │   ├── 17_lint_kicad_pro.py  # rule_severities=={} enforcement (Lesson 3)
    │   │   │   ├── 20_export_gerbers.py  # Protel gerbers + Excellon drill -> hardware/build/gerbers/
    │   │   │   ├── 22_export_ibom.py     # InteractiveHtmlBom -> hardware/output/oas-ibom.html
    │   │   │   └── 24_preflight_gerbers.py  # pygerber integrity + drill stats + composite render
    │   │   ├── oas/                # OAS-only verification (hardcoded to this circuit)
    │   │   │   ├── 05_check_dc.py        # DC voltage propagation analytical model
    │   │   │   ├── 06_check_boot.py      # ESP32-C6 strap + signal pin audit
    │   │   │   ├── 07_check_ampacity.py  # IPC-2221 trace width verifier
    │   │   │   ├── 08_check_switching.py # ngspice LM2596 soft-start (auto-downloads model; hard FAIL on download / py7zr failure)
    │   │   │   ├── 09_check_semantic.py  # I2C pull-ups, GPIO 8 pull-up, no_connect coverage (kicad-skip)
    │   │   │   ├── 14_check_refdes_unique.py  # designator uniqueness across schematic
    │   │   │   ├── 18_lint_no_hand_pads.py    # forbid hand-coded pad geometry (Lesson 1)
    │   │   │   └── 19_check_oas_metadata.py   # EXTERNAL_MODULES + lcsc_mapping schema lint
    │   │   └── jlcpcb/             # VENDOR — JLCPCB-specific stages; deliverables -> hardware/output/jlcpcb/
    │   │       ├── _rotations.py             # tape-feeder rotation offsets (upstream + OAS gap-fillers)
    │   │       ├── 29_check_bom_consistency.py  # LCSC# bijection check
    │   │       ├── 30_export_pos.py          # CPL header + rotation corrections
    │   │       ├── 31_export_bom.py          # BOM template + LCSC + library tier + THT detection
    │   │       ├── 32_bundle.py              # ZIP gerbers + drill -> oas-jlcpcb.zip
    │   │       ├── 33_check_dnp_consistency.py  # DNP refdes leak audit (BOM + CPL)
    │   │       ├── 34_check_lcsc_offline.py  # LCSC# class/value match vs jlcparts SQLite (Lesson 5)
    │   │       └── 35_audit_zip_content.py   # oas-jlcpcb.zip inventory + non-empty assert
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
   - `05_check_dc` / `06_check_boot` / `07_check_ampacity` / `08_check_switching` — DC voltage propagation, boot-strap audit, trace ampacity, ngspice transient (auto-downloads ngspice + the LM2596 PSpice model into `.tmp/spice/` on first run; hard-fails on any download / `py7zr` extraction failure — no soft-skip).
   - `09_check_semantic` — schematic semantic invariants via `kicad-skip` (I²C pull-ups R5/R6 = 4.7 kΩ, GPIO 8 pull-up R7 = 10 kΩ, no_connect coverage). Hard-fails if the kicad-skip submodule isn't initialized.
   - `10_render_2d` / `11_render_sch` / `12_render_png` / `13_render_3d` — re-renders SVG + PNG + 3D into `renders/`. `12_render_png` hard-fails if `cairosvg` is not importable (committed PNGs must never silently drift from their SVGs).
   - `14_check_refdes_unique` — designator uniqueness across the schematic.
   - `15_lint_typecheck` — `mypy` on `boardgen/` + `pipeline/` (real-bug flags: `--check-untyped-defs --warn-unused-ignores --warn-redundant-casts --warn-unreachable --no-implicit-optional`). Hard-fails if mypy missing.
   - `16_lint_compileall` — `python -m compileall` over `boardgen/` + `pipeline/` + `tools/` (catches syntax errors in modules not on the happy path).
   - `17_lint_kicad_pro` — Lesson 3 enforcement: `board.design_settings.rule_severities` and `erc.rule_severities` MUST be empty in `oas.kicad_pro`. Hard-fails on any suppression entry.
   - `18_lint_no_hand_pads` — Lesson 1 enforcement: every `gen_*_pcb_footprint` delegates to `_emit_stock_lib_footprint` or parses a `_*_lib_footprint_path` file. Whitelist: 9 documented OAS custom footprints in CLAUDE.md "Deviation budget".
   - `19_check_oas_metadata` — Lesson 10 + Gap H: every `EXTERNAL_MODULES` entry has at least one identifier (`mpn` / `ean` / `material` / `supplier_*`); every `lcsc_mapping` entry matches the expected schema (LCSC# `^C\d+$`, library tier ∈ {Basic, Extended, N/A}, manufacturer + MPN non-empty).
   - `20_export_gerbers` — vendor-neutral raw fab data (Protel gerbers + Excellon drill + drill_map PDFs) written to `hardware/build/gerbers/` (gitignored, intermediate).
   - `22_export_ibom` — InteractiveHtmlBom HTML artefact `hardware/output/oas-ibom.html`. Vendor-neutral; primary use is the JLCPCB Assembly XLS pre-payment cross-check (Lesson 5). Hard-fails if InteractiveHtmlBom submodule or KiCad-bundled python missing.
   - `24_preflight_gerbers` — pygerber integrity + drill statistics + composite renders (smoke test on the raw fab data, vendor-neutral).
   - `29_check_bom_consistency` — LCSC# bijection check across `lcsc_mapping.py` (catches copy-paste bugs before any vendor export).
   - `30_export_pos` / `31_export_bom` / `32_bundle` (in `pipeline/jlcpcb/`) — JLCPCB-specific deliverables: CPL header `Designator, Mid X, Mid Y, Layer, Rotation` + rotation offsets; BOM with LCSC mapping + range expansion + THT detection; ZIP bundle. All four output files land in `hardware/output/jlcpcb/`.
   - `33_check_dnp_consistency` — DNP attribute audit: PCB attrs `dnp` + `exclude_from_bom` + `exclude_from_pos_files` must travel together; DNP refdes must not leak into BOM or CPL files.
   - `34_check_lcsc_offline` — Lesson 5 enforcement: every LCSC# in `lcsc_mapping.py` is queried against the offline jlcparts SQLite cache and verified for category match (Resistor vs Capacitor vs MOSFET — would have caught the v0.40 R3 C23116 = 806 Ω near-miss). Hard-fails if the cache is missing — run `python hardware/kicad/tools/setup_jlcparts_cache.py` once to populate it (~2 GiB compressed download, ~250 MiB SQLite).
   - `35_audit_zip_content` — verifies `oas-jlcpcb.zip` contains exactly the 11 expected files (9 gerber + 2 drill), every file > 0 bytes, no unexpected leftovers.
   Numbers in the range gaps (`21`, `23`, `25`–`28`, `36`–`39`) remain reserved for future generic / OAS / JLCPCB extensions. Each vendor gets a 10-number range (jlcpcb 29–39; future oshpark would take 40–49). **Aborts on any violation or determinism drift** (fail-fast — later stages don't run). Each `pipeline/<subdir>/NN_*.py` is also independently runnable for debug (`python pipeline/generic/03_drc.py`).
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
- NXP NT3H1101 datasheet: https://www.nxp.com (search NT3H1101)
- MIKROE-2462 NFC Tag 2 Click: https://www.mikroe.com/nfc-tag-2-click
- SZOMK AK-N-94 enclosure: https://www.chinaenclosure.com
- ESPHome documentation: https://esphome.io
- JLCPCB component library: https://jlcpcb.com/parts

---

## Memory rules (assistant)

- **Always git push after commit** in this repo. `git push origin main` runs automatically after every commit; no confirmation prompt.

---

## Changelog summary

Full historical detail lives in `git log --tags`. Highlights of the most recent milestones:

- **v0.40-validation-tighten** (2026-05-20): Pipeline grew from 20 to 29 stages — 9 new checks closing real failure modes from the v0.40 lessons-learned. Key additions: `oas.kicad_dru` JLCPCB-tuned custom DRC rules emitted by new boardgen stage 14 (auto-loaded by kicad-cli pcb drc); stage 09 schematic semantic invariants via kicad-skip (I²C pull-ups R5/R6, GPIO 8 pull-up R7, no_connect coverage); stage 15 mypy on pipeline/; stage 16 compileall sanity; stage 17 rule_severities=={} enforcement (Lesson 3); stage 18 hand-coded pad geometry forbid (Lesson 1) with whitelist for 9 documented OAS customs; stage 19 EXTERNAL_MODULES + lcsc_mapping schema lint (Lessons 10 + Gap H); stage 22 InteractiveHtmlBom artefact (vendor-neutral `hardware/output/oas-ibom.html`); stage 34 LCSC# class/value match vs offline jlcparts SQLite cache (Lesson 5 — would have caught the v0.40 R3 C23116 = 806 Ω near-miss before payment); stage 35 oas-jlcpcb.zip content audit (Gap D). 4 new git submodules under `hardware/kicad/third_party/`: kicad-skip, InteractiveHtmlBom, jlcparts, kicad-jlcpcb-dru. Setup helper `tools/setup_jlcparts_cache.py` downloads the upstream 41-volume split-ZIP catalogue and extracts to `.tmp/jlcparts/cache.sqlite3` (manual one-time action, ~2 GiB → ~28 GiB SQLite). Soft-skips removed — every new stage hard-fails on missing dependency with explicit setup instructions. 29/29 PASS in ~185 s.

- **v0.40-build-harness** (2026-05-19): Renamed the top-level orchestrator `regenerate.py` → `build.py` and removed the `generate.py` shortcut at the repo root. The boardgen walker now lives at `pipeline/generic/01_emit_sources.py` (stage 01 of `build.py`); the former `pipeline/generic/01_generate.py` subprocess wrapper is gone. Motivation: AI-agent harness — when there were two top-level entrypoints (the fast-but-incomplete `generate.py` and the comprehensive `regenerate.py`), an autonomous agent could rationalize "I'll just rebuild the sources" and silently commit a board state that had never seen DRC / ERC / determinism / DC / ampacity / boot-strap / preflight / vendor-export checks. With a single entrypoint, the harness always runs the full pipeline. Also renamed `hardware/output/jlcpcb/oas-bom.csv` → `oas-BOM.csv` for consistency with the already-uppercased `oas-{top,bottom}-CPL.csv` (manufacturer acronyms uppercase). 20/20 PASS post-refactor; boardgen output bit-identical pre vs post.

- **v0.40-vendor-split** (2026-05-19): Reorganized production pipeline around vendor isolation. New `pipeline/jlcpcb/` sibling to `generic/` and `oas/` holds every JLCPCB-specific stage (29 BOM consistency, 30 CPL export with rotation offsets, 31 BOM with LCSC + library tier, 32 ZIP bundle, 33 DNP consistency) plus `_rotations.py` (moved from `hardware/kicad/jlcpcb_rotations.py`). Stage 20 now emits raw vendor-neutral gerbers + drill to `hardware/build/gerbers/` (gitignored intermediate), and stage 24 preflight verifies that raw data without touching any vendor ZIP. Output reorganized: `hardware/output/jlcpcb/` carries EXACTLY 4 committed deliverables (ZIP + BOM + 2× CPL). Position files renamed `oas-{top,bottom}-pos.csv` → `oas-{top,bottom}-CPL.csv` to match JLCPCB's own terminology. Adding a second fabricator now reduces to creating a sibling `pipeline/<vendor>/` + `hardware/output/<vendor>/` with zero edits to existing `generic/` or `oas/` stages. boardgen output (`oas.kicad_pcb`, `oas.kicad_sch`, 4 sub-sheets, `OAS.kicad_sym`, 7 `.kicad_mod`, lib tables) byte-identical pre vs post; 20/20 PASS in ~115 s.

- **v0.40-audit-16** (2026-05-17): Full canonical-name + ERC-clean sweep. Audit-16 caught four classes of canonical-name defects the audit-15 swarm had missed (focusing on pad geometry, not on the `(footprint "Lib:Name"` header itself): U1 / U2 non-canonical headers, J2 missing lib prefix, ZT1..ZT4 missing `oas:` prefix. Q1's `lib_footprint_mismatch` workaround (`rule_severities: {"...": "ignore"}` + `pin_name_map` G/S/D remap) eliminated by creating project-local `OAS:Q_PMOS_GDS` schematic symbol with numeric pin numbers 1/2/3 + letter pin NAMES. Final state: DRC 0, ERC 0 / 0 errors / 0 warnings, `rule_severities` empty `{}`, determinism PASS, Z-clearance PASS, every footprint header uses canonical `<lib>:<name>` or `oas:<name>`.

- **v0.40-post-order footprint sweep** (2026-05): 78-agent paranoid audit found ~24 SMD passive footprints sharing the same custom-stub deviation root cause as the v0.40 JLCPCB U1 / U2 rejection. Refactored 9 generators (`gen_capacitor_0402/0603/0805`, `gen_resistor_0603`, `gen_diode_sma/smb/sod323`, `gen_inductor_smd_5x5`, `gen_polyfuse_smd`) + Q1 SOT-23 + radial THT to verbatim stock-library parsing via `_emit_stock_lib_footprint`. L1 / L2 footprint name corrected from `L_APV_ANR5040` to `L_Cenker_CKCS5040` (matching actual LCSC parts).

- **v0.40-post-order**: Production firmware skeleton added (5-package ESPHome config + web_server dashboard) so the user can flash on day 1 of hardware delivery. JLCPCB rejected the original v0.40 SMT order (5 prototypes, ~712 PLN) due to U1 LM2596S TO-263-5 + U2 TPS62933 SOT-583 footprints emitting non-stock pad geometry; immediate surgical refactor of `gen_to263_5_pcb_footprint` and `gen_sot583_pcb_footprint` to verbatim stock parsing, followed by the wider audit-15 / audit-16 sweep.
