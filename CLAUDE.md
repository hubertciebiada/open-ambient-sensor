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

`generate.py` output must be bit-identical across consecutive runs (17 source files: `oas.kicad_pro`, `oas.kicad_sch`, 4 sub-sheets, `oas.kicad_pcb`, the two project libraries `OAS.kicad_sym` + `oas.pretty/*.kicad_mod`, etc.). Hash-randomized dict iteration, time-based content, etc. all break this. `regenerate.py` runs `generate.py` twice and aborts on any drift — step 1b is non-negotiable.

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

> Authoritative metadata (EAN, MPN, datasheet URLs, sourcing notes, derived dimensions) lives in `hardware/kicad/generate.py::EXTERNAL_MODULES`. The table below is a quick-reference summary.

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
| PTC fuse | **Littelfuse 2920L075/60MR** (750 mA hold, 1.5 A trip, 60 V) | LCSC C207083 | — |
| Buck 24 V → 5 V | **TI LM2596S-5.0/NOPB** (async, TO-263-5) + CENKER CKCS5040-33µH/M (C354612) + MDD SS14 (C2480, freewheel) | LCSC C116713 | ~76% η |
| Buck 5 V → 3.3 V | **TI TPS62933DRLR** (sync, SOT-583-8) + CENKER CKCS5040-2.2µH/M (C354602) + UNI-ROYAL 100 k / 30.9 k FB pair | LCSC C3200405 | ~95% η |
| 24 V terminal | J1 Phoenix MSTBA 2,5/3-G-5,08 (THT hand-solder) | — | — |
| Qwiic expansion | J9 genuine JST SH SM04B-SRSS-TB (4-pin horiz SMD) | LCSC C160404 | I²C |
| SEN66 socket | J3 genuine JST GH SM06B-GHS-TB (6-pin horiz SMD) | LCSC C133065 | I²C via cable |
| Flashing | Either of DevKitM-1's two onboard USB-C ports (USB-UART bridge or native USB-Serial-JTAG) | — | USB 2.0 |

ESP32-C6-DevKitM-1-N4 is the Espressif official devkit (ESP32-C6-MINI-1 SoM + two USB-C ports + buttons + onboard RGB NeoPixel + power LED). Form factor 48.26 × 25.4 mm. Chosen over generic "SuperMini" clones for deterministic pinout, full Espressif documentation, and verified Polish-distributor availability.

### ESP32-C6-DevKitM-1-N4 pinout (final)

> Authoritative pin assignment lives in `hardware/kicad/generate.py::GPIO_ASSIGNMENTS` and `GPIO_RESERVED`. The table below is a quick-reference summary. `pipeline/oas/06_check_boot.py` cross-checks the schematic against the dict on every regenerate.

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
    │   ├── generate.py             # SINGLE SOURCE OF TRUTH — project metadata, geometry,
    │   │                           #   footprints, schematic, plus ASSEMBLY_INSTRUCTIONS /
    │   │                           #   CASE_VERIFICATION_CHECKLIST / LOCALLY_SOURCED_PARTS
    │   ├── regenerate.py           # thin orchestrator — runs every pipeline/<subdir>/NN_*.py
    │   ├── oas_routes.py           # derived — routing snapshot replayed by generate.py
    │   ├── lcsc_mapping.py         # SOT for SMD LCSC SKUs — Python dict (Value, Footprint) -> entry
    │   ├── oas.kicad_pro / .kicad_sch / .kicad_pcb / sub-sheets  # generated artefacts
    │   ├── libraries/              # generated project libraries (OAS.kicad_sym + oas.pretty/)
    │   ├── pipeline/               # one stage per file (NN_<name>.py); each standalone-runnable
    │   │   ├── _common.py          # PROJECT-AGNOSTIC helpers (Stage, find_kicad_cli, run, sha256)
    │   │   ├── _project.py         # OAS config consumed by generic stages
    │   │   ├── generic/            # REUSABLE across KiCad projects (zero OAS references)
    │   │   │   ├── 01_generate.py        # invoke generate.py
    │   │   │   ├── 02_determinism.py     # bit-identity self-check
    │   │   │   ├── 03_drc.py             # kicad-cli pcb drc strict
    │   │   │   ├── 04_erc.py             # kicad-cli sch erc strict
    │   │   │   ├── 10_render_2d.py       # PCB top/cutouts/bottom SVG
    │   │   │   ├── 11_render_sch.py      # schematic root + sub-sheets SVG
    │   │   │   ├── 12_render_png.py      # cairosvg batch SVG -> PNG
    │   │   │   ├── 13_render_3d.py       # 3D top + iso renders
    │   │   │   ├── 20_export_gerbers.py  # Protel gerbers + Excellon drill + drill_map PDF
    │   │   │   ├── 21_export_pos.py      # JLCPCB CPL format
    │   │   │   ├── 23_bundle_jlcpcb.py   # ZIP gerbers + drill into oas-jlcpcb.zip
    │   │   │   └── 24_preflight_gerbers.py  # pygerber integrity + drill stats + composite render
    │   │   └── oas/                # OAS-only verification (hardcoded to this circuit)
    │   │       ├── 05_check_dc.py        # DC voltage propagation analytical model
    │   │       ├── 06_check_boot.py      # ESP32-C6 strap + signal pin audit
    │   │       ├── 07_check_ampacity.py  # IPC-2221 trace width verifier
    │   │       ├── 08_check_switching.py # ngspice LM2596 soft-start (hard FAIL if cache empty)
    │   │       └── 22_export_bom_jlcpcb.py  # BOM + LCSC lookup + range expansion + THT detection
    │   └── tools/                  # MANUAL-trigger scripts (extract_routes, jlcdfm_upload)
    ├── renders/                    # generated previews (PNG + SVG, sibling of kicad/)
    │   ├── pcb/                    # 2D / 3D / pygerber preflight
    │   └── sch/                    # schematic root + 4 sub-sheets
    └── output/                     # production deliverables (regenerable from generate.py)
        ├── oas-jlcpcb.zip          # COMMITTED snapshot for current revision
        ├── oas-bom.csv             # COMMITTED — JLCPCB happy-path 8-column format
        ├── oas-top-pos.csv         # COMMITTED — JLCPCB CPL header
        ├── oas-bottom-pos.csv      # COMMITTED
        └── oas-*.{gtl,gbl,...}     # gitignored — individual gerbers / drill / drill_map / gbrjob
```

`.gitignore` highlights:
```
# secrets
**/secrets.yaml

# build artifacts + caches
**/build/  **/.cache/  **/__pycache__/  *.bak  *-backups/

# auto-downloaded external tools (ngspice + LM2596 PSpice model, etc.)
/.tmp/

# production output — individual gerbers gitignored; ZIP + BOM + pos.csv committed
hardware/output/*.gtl
hardware/output/*.gbl
hardware/output/*.gts
hardware/output/*.gbs
hardware/output/*.gto
hardware/output/*.gbo
hardware/output/*.gtp
hardware/output/*.gbp
hardware/output/*.gm1
hardware/output/*.gbrjob
hardware/output/*.drl
hardware/output/*-drl_map.pdf

# freerouting (manual download by user; not redistributable)
hardware/kicad/freerouting.jar
hardware/kicad/freerouting.json
hardware/kicad/freerouting.log
```

---

## PCB design workflow

The KiCad project in `hardware/kicad/` is **script-driven**. The source of truth is the Python in `generate.py` plus the canonical SKU mapping in `hardware/kicad/lcsc_mapping.py` and the routing snapshot in `oas_routes.py`. The `oas.kicad_pcb` / `oas.kicad_sch` / `oas.kicad_pro` / `libraries/*` files are **derived artefacts** — regenerated bit-identically from the Python.

### How we work

1. The user describes a desired change (geometry tweak, new component, routing fix, etc.).
2. The assistant edits the appropriate constant / function in `generate.py` (or `oas_routes.py` / `lcsc_mapping.py` if applicable).
3. The assistant runs `python regenerate.py`. That command is a thin orchestrator that dispatches each `pipeline/NN_<name>.py` script in numeric order. The stages are:
   - `01_generate` — calls `generate.py` to rebuild every KiCad source file (which internally runs the Z-clearance guardrail on 76 footprints).
   - `02_determinism` — runs `generate.py` a SECOND time and checks 17 source files are bit-identical.
   - `03_drc` — `kicad-cli pcb drc` strict (`--severity-error --severity-warning --refill-zones`).
   - `04_erc` — `kicad-cli sch erc` strict (`--severity-error --severity-warning --exit-code-violations`).
   - `05_check_dc` / `06_check_boot` / `07_check_ampacity` / `08_check_switching` — DC voltage propagation, boot-strap audit, trace ampacity, ngspice transient (soft-skips with [WARN] if ngspice + LM2596 PSpice model not in `.cache/spice/`).
   - `10_render_2d` / `11_render_sch` / `12_render_png` / `13_render_3d` — re-renders SVG + PNG + 3D into `renders/`.
   - `20_export_gerbers` / `21_export_pos` / `22_export_bom_jlcpcb` / `23_bundle_jlcpcb` — production deliverables in JLCPCB happy-path format (CPL header `Designator, Mid X, Mid Y, Layer, Rotation`; BOM with LCSC mapping + range expansion + THT detection; ZIP bundle).
   - `24_preflight_gerbers` — pygerber integrity + drill statistics + composite renders (smoke test before fab upload).
   Numbers `08`–`09` and `14`–`19` are intentionally reserved for future verification checks; the gap stays visible in `ls`. **Aborts on any violation or determinism drift** (fail-fast — later stages don't run). Each `pipeline/<subdir>/NN_*.py` is also independently runnable for debug (`python pipeline/generic/03_drc.py`).
4. The assistant commits the resulting diff (sources + KiCad files + renders + gerbers together).
5. JLCPCB upload: `hardware/output/oas-jlcpcb.zip` (bare board) + `oas-top-pos.csv` + `oas-bom.csv` (SMT assembly). Drill review: `oas-PTH-drl_map.pdf` / `oas-NPTH-drl_map.pdf`. All files produced by stages 20-24 on every `regenerate.py` run.

### Rules

- **Never edit `.kicad_pcb`, `.kicad_sch`, `.kicad_pro`, or `*.kicad_mod` directly.** The next `regenerate.py` will overwrite the edit. If you find yourself wanting to hand-edit one of those, add a new constant / function to `generate.py` instead.
- **All UUIDs are deterministic v5** (namespaced under the OAS project). Two consecutive runs with no source changes produce a bit-identical PCB → empty `git diff`.
- **`renders/` is committed** as a visual changelog. Reviewers can see geometry changes in PRs without launching KiCad.
- **External services run MANUALLY only.** `tools/jlcdfm_upload.py` and any future TI-WEBENCH / LCSC-stock-check / OSHPark-upload tool must be invoked by explicit user request — never from `regenerate.py` or any CI loop. JLCPCB's `/checkIp` endpoint tracks upload volume per IP; running on every regenerate would risk rate-limiting.

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

- **v0.40-audit-16** (2026-05-17): Full canonical-name + ERC-clean sweep. Audit-16 caught four classes of canonical-name defects the audit-15 swarm had missed (focusing on pad geometry, not on the `(footprint "Lib:Name"` header itself): U1 / U2 non-canonical headers, J2 missing lib prefix, ZT1..ZT4 missing `oas:` prefix. Q1's `lib_footprint_mismatch` workaround (`rule_severities: {"...": "ignore"}` + `pin_name_map` G/S/D remap) eliminated by creating project-local `OAS:Q_PMOS_GDS` schematic symbol with numeric pin numbers 1/2/3 + letter pin NAMES. Final state: DRC 0, ERC 0 / 0 errors / 0 warnings, `rule_severities` empty `{}`, determinism PASS, Z-clearance PASS, every footprint header uses canonical `<lib>:<name>` or `oas:<name>`.

- **v0.40-post-order footprint sweep** (2026-05): 78-agent paranoid audit found ~24 SMD passive footprints sharing the same custom-stub deviation root cause as the v0.40 JLCPCB U1 / U2 rejection. Refactored 9 generators (`gen_capacitor_0402/0603/0805`, `gen_resistor_0603`, `gen_diode_sma/smb/sod323`, `gen_inductor_smd_5x5`, `gen_polyfuse_smd`) + Q1 SOT-23 + radial THT to verbatim stock-library parsing via `_emit_stock_lib_footprint`. L1 / L2 footprint name corrected from `L_APV_ANR5040` to `L_Cenker_CKCS5040` (matching actual LCSC parts).

- **v0.40-post-order**: Production firmware skeleton added (5-package ESPHome config + web_server dashboard) so the user can flash on day 1 of hardware delivery. JLCPCB rejected the original v0.40 SMT order (5 prototypes, ~712 PLN) due to U1 LM2596S TO-263-5 + U2 TPS62933 SOT-583 footprints emitting non-stock pad geometry; immediate surgical refactor of `gen_to263_5_pcb_footprint` and `gen_sot583_pcb_footprint` to verbatim stock parsing, followed by the wider audit-15 / audit-16 sweep.
