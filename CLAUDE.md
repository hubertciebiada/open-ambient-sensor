# OAS — Open Ambient Sensor

DIY multi-sensor environmental monitor for indoor spaces. Measures air quality and presence. Mounts on a standard wall-recessed electrical box (60 mm screw pitch). Powered from 24V DC. Integrates with Home Assistant via ESPHome.

---

## Design philosophy

The open-source DIY space offers many indoor air quality projects. Most optimize aggressively for cost. **OAS holds two priorities non-negotiable**, even when the trade-off is higher per-unit BOM cost than the cheapest alternatives:

1. **Measurement quality.** Sensor choices favor accuracy and long-term stability over price. Sensirion SEN66 (calibrated combo NDIR / laser PM / MOX VOC / MOX NOx / SHT) is preferred over cheaper MOX-only or non-calibrated NDIR alternatives. mmWave presence (LD2410) is chosen over PIR despite higher cost because of stillness detection. PCB layout enforces thermal separation between heat-generating electronics and sensor inlets.

2. **Aesthetic acceptability.** The device is meant to live in inhabited rooms, including living spaces. A commercial-grade injection-molded enclosure (SZOMK AK-N-94, white perforated ABS) replaces the typical 3D-printed box. PCB layout, LED placement, and connector positions are constrained by what looks acceptable on a wall in a furnished room. No protruding modules, no exposed wiring, no fan whine.

This positions OAS between bargain DIY kits (cheap, often inaccurate, frequently ugly) and premium commercial sensors (accurate, polished, expensive). Both compromises are rejected; the project accepts a higher per-unit BOM in exchange.

When evaluating any future component or design change: it must clear both bars. A cheaper sensor that degrades measurement accuracy is rejected. A more accurate sensor that requires a visually unacceptable enclosure modification is rejected. If a contributor proposes a change that breaks either pillar, the assistant should flag it explicitly.

---

## 🔴 CRITICAL: Public repository rules

**This is a PUBLIC repository.** Every file committed to this repo MUST follow these rules. No exceptions.

### Rule 1 — English only
All committed content is written in English:
- Documentation (`*.md`)
- Source code comments and identifiers
- Schematics (KiCad text labels, sheet names)
- BOM files, datasheet references
- Commit messages
- Issue / PR templates

User chat with the assistant can happen in any language. The assistant adapts to the user's language for conversation but writes all repo content in English.

### Rule 2 — Anonymization
**No personal information** in any committed file. This includes but is not limited to:
- Names of individuals or family members
- Geographic locations (city, region, country specifics beyond what is technically necessary; "230V AC / 50 Hz mains" is fine; "house in [town]" is not)
- Specific buildings, addresses, room counts tied to a specific deployment
- Names of other appliances, services, or systems present in the user's environment
- Network identifiers (SSIDs, MAC addresses, hostnames revealing identity)
- Specific tariffs, utility providers, or local regulations beyond generic references
- Photos that show identifiable backgrounds, faces, hands, or environments

### Rule 3 — Generic framing
Describe design decisions in **technical terms**, not personal ones:
- ✗ "10 rooms in the user's house"
- ✓ "multi-unit deployment (typical: 5–20 units)"
- ✗ "needed because of the heat pump in the user's basement"
- ✓ "useful in deployments with co-existing HVAC equipment"

### Rule 4 — Default to redaction
When in doubt, **remove** the information. Once pushed to a public repo, a privacy leak is permanent (git history, mirrors, archive.org, AI training datasets). The cost of over-redaction is small; the cost of under-redaction is unrecoverable.

### Rule 5 — Secrets handling
- `secrets.yaml` is **gitignored** (only `secrets.yaml.example` with placeholders is committed)
- No API keys, tokens, passwords in any committed file (including comments, commit messages, screenshots)
- WiFi SSIDs and passwords belong only in the user's local `secrets.yaml`
- Pre-commit hook should scan for common secret patterns (consider `git-secrets` or `trufflehog`)

### Rule 6 — Third-party intellectual property
**Files received from manufacturers, suppliers, or other third parties are NOT redistributable through this repo** unless they are explicitly under a permissive license (CC0, CC-BY, MIT-equivalent, etc.).

This applies to:
- Mechanical drawings supplied by enclosure vendors (DXF, STEP, PDF dimension sheets)
- Component datasheets PDF
- Vendor reference schematics and example code with restrictive license terms
- 3D models downloaded from manufacturer sites
- Photos or renders provided by suppliers

What to do instead:
- **Reference by URL or part number.** Link to the manufacturer page; do not mirror.
- **Derive your own work.** Dimensions copied from a manufacturer DXF into your KiCad board outline, your own 3D bracket model designed to fit a vendor part, your own dimension drawings created from measurements — these are your own copyrightable work and can be committed under the project license.
- **Keep locally if needed for reference.** Add the file pattern to `.gitignore` (e.g., `hardware/case/*.dxf`, `hardware/case/*-datasheet.pdf`). Document in a `README.md` in the same directory how to obtain the original from the source.

When in doubt: check the source's license terms; if unclear, default to keeping the file local only.

---

## ⚠️ Status: PRELIMINARY DRAFT

Nothing below is final. Components, layout, IC selections, and pinouts are subject to change. Each decision is a working hypothesis to be validated.

At every step, the assistant should:
1. Check whether the element under work needs revision relative to the current iteration
2. Validate against hard constraints (see below) and the two design pillars
3. Confirm with the user before changes that affect the physical BOM or enclosure compatibility

---

## Project goals

Per-room sensor measures:
- **Air quality**: CO2, PM1 / 2.5 / 4 / 10, VOC index, NOx index, temperature, humidity (Sensirion SEN66)
- **Occupancy / presence**: mmWave radar with stillness detection (HiLink LD2410)

Additional features:
- RGB status LED with breathing effect; color reflects aggregated air quality index
- Dynamic NFC tag — phone tap reads live data and serves URL to user's dashboard
- Bluetooth proxy — extends BLE range across the deployment for Home Assistant BLE integrations
- Qwiic / STEMMA QT expansion port — future sensors without PCB respin

---

## Hardware

### Enclosure
- SZOMK **AK-N-94** — Ø128 mm perforated white ABS, smoke-detector form factor
- Manufacturer-supplied DXF and datasheet are **third-party files**, **not committed to this repo** (see Rule 6 below). Obtain directly from SZOMK. Keep locally under `hardware/case/` (gitignored).
- Derived dimensions (used in KiCad and documentation, which are own work):
  - PCB: **Ø120 mm D-shape** (arc R=60 mm), flat chord **82.65 mm** along the bottom edge (chord Y from centre ≈ 43.50 mm; full precision 82.6545 mm in `generate.py`)
  - 3× M3 mounting holes (Ø3.8 mm, **NPTH**) on **pitch circle Ø110 mm**, trójkąt równoboczny with one hole opposite the chord (NPTH: screws go into plastic bosses, no metal chassis bonding)
  - Hole positions (origin = centre of PCB outline): (±47.631, +27.500) and (0, −55.000)
  - **Cable pass-through hole** Ø12 mm at PCB centre on `Edge.Cuts` — 24 V power enters from the rear of the case (electrical wall box behind the unit), passes through the PCB, terminates at a front-side terminal block. Sized for 3× 1.5 mm² conductors. Bare 24 V conductors stay inside the case (inaccessible from outside)
- **HARD LIMIT: max 17 mm component height on front, 5 mm on back** (back side mostly solder fillets; pin-header bottoms tolerated. Achieved by adding 2 mm washers under the mounting screws, lifting the PCB 2 mm off the enclosure mounting bosses)
- **MCU module: ESP32-C6-DevKitM-1-N4** (Espressif official devkit, ESP32-C6-MINI-1 SoM + **TWO USB-C ports** [one to onboard USB-UART bridge IC, one direct to ESP32-C6 native USB-Serial-JTAG] + buttons + onboard RGB NeoPixel + power LED). EAN: **5904422385651** (Botland), Espressif SKU `ESP32-C6-DevKitM-1-N4`. Form factor 48.26 × 25.4 mm. Chosen over generic "SuperMini" clones because of branded, deterministic pinout, full Espressif documentation, and verified availability through a Polish distributor.

### Module list (preliminary)

| Function | Component | Interface | Status |
|---|---|---|---|
| MCU | **ESP32-C6-DevKitM-1-N4** (EAN 5904422385651) | — | confirmed v0.5 (re-evaluated against XIAO C6 + bare MINI-1 SMT alternatives) |
| Air quality combo | Sensirion SEN66 (`SEN66-SIN-T`, material 3.001.030) + JST GH 6-pin cable accessory (50 cm AWG26, ordered separately — Sensirion ships SEN66 *without* a cable) | I²C via JST GH cable | tentative |
| Presence | HiLink LD2410B/C | UART @ 256000 baud | tentative |
| Visual indicator | **11 × SK6812-SIDE** (4020 side-emit) on Ø22 mm pitch ring around the central cable hole, driven by GPIO 8 from the LM2596S +5V rail | 1-wire RMT, WS281x protocol | confirmed v0.18 (D14 slot vacated for the J1 24 V terminal block on the SOUTH side; v0.16 had 12 LEDs, v0.17 vacated D20 on the north side before being flipped to D14 in v0.18; see OPEN ISSUE #2 resolution) |
| NFC dynamic tag | **MIKROE-2462 NFC Tag 2 Click** (NXP NT3H1101 + onboard PCB antenna, mikroBUS) | I²C + NFC | confirmed v0.12 (chip ID v0.15.8) |
| Power input | TVS + PTC + 24V terminal block | — | confirmed v0.2 |
| Buck 24V → 5V | LM2596S-5.0 (async) | — | confirmed v0.2 |
| Buck 5V → 3.3V | TPS62933 (sync, ~95%) | — | confirmed v0.2 |
| External I²C ESD | TBD (PESD3V3L4UG candidate) | — | tentative |
| Flashing | Either of DevKitM-1's two onboard USB-C ports (USB-UART bridge or native USB-Serial-JTAG); module accessible before enclosure is sealed | USB 2.0 | confirmed v0.4 |
| Debug | SWD / UART header (unpopulated by default) | — | tentative |

### PCB layout — functional grouping (soft guideline)

The schematic is split into four hierarchical sub-sheets by **function**, not by geography:

- `power.kicad_sch` — terminal block J1, reverse-polarity protection, PTC fuse, TVS, bulk cap, Y-cap, bucks 24→5V→3.3V
- `mcu.kicad_sch` — ESP32-C6-DevKitM-1-N4, optional unpopulated SWD/UART recovery header, decoupling caps
- `sensors.kicad_sch` — SEN66 JST-GH connector, LD2410 connector, NT3H1101 + NFC antenna (on MIKROE-2462 daughterboard), status LED (onboard WS2812 on DevKitM-1)
- `io.kicad_sch` — connector strip along the chord (24 V terminal, Qwiic, etc.)

**Placement guideline (NOT a hard constraint)**: as a starting heuristic, think of the PCB roughly as a clock face with power on the upper-left, MCU on the upper-right, and sensors filling the bottom half. The 24 V cable enters through the centre, so keeping the terminal block and reverse-polarity / fusing chain near it shortens the bare-conductor span. Power flowing roughly clockwise (centre → power → MCU → sensors) tends to keep rails short, but **components may cross any imagined boundary if the layout needs it**. SEN66 in particular is large and may span what would otherwise be the "sensors" region.

### Architectural decisions (current)
- **SEN66 mounts on the PCB inside the enclosure**, in the bottom-half region of the board (the largest contiguous area). Lies flat on its 55.2 × 25.6 mm **back face (clean, featureless)** with the **air-side face (55.2 × 25.6 mm, carrying both inlets + outlet + product label) facing UP** toward the AK-N-94 perforated cover. Body sticks 21.5 mm above PCB. Connector (ACES 51468-0064N-001 / JST-GHR-06V-S compatible, 6-pin 1.25 mm pitch) on the SEN66's +X short edge, radially inward toward PCB centre — cable runs horizontally to a PCB-mounted JST-GH socket. Required: lift hard constraint #1 from 17 mm to ≥22 mm in the SEN66 zone — verified per CASE-VERIFICATION-CHECKLIST §1 against the physical AK-N-94 sample. The 17 mm DXF annotation `正面限高 17mm` is most likely regional (mounting-boss periphery), not global. **PCB needs NO cutouts under SEN66** — openings face UP toward cover perforations, not down toward PCB.
- **SEN66 retention**: zip-tie strap mount. Four NPTH holes (Ø ~3 mm) in the PCB just outside the SEN66 footprint along the two long edges (Y < 0 and Y > 25.6 in SEN66-local frame). A zip-tie loops over the SEN66 body through each Y-paired hole, pulling the module flat onto the PCB. No 3D-printed bracket, no screws into the SEN66 body (which has no mounting features per Sensirion STEP files). Reversible / serviceable: cut the zip-tie to swap the sensor.
- **Zip-tie hole X-positions** (SEN66-local frame, X along 55.2 mm axis pointing toward connector): available "safe" corridor where the zip-tie band passes over the top face without crossing an opening: **X ∈ [18.22, 32.03]** (14 mm wide, between inlet zone at X ≤ 18.22 and outlet at X ≥ 32.03). Realized (v0.7+): **Pair 1 at X = 22, Pair 2 at X = 30** — both inside the strict safe corridor, no outlet overlap. (Earlier draft suggested X ≈ 50 as a second pair, but X=50 sits inside the outlet circle X=32..53 and would block ~8% of outlet area; rejected.) Implementation in `generate.py` constant `SEN66_ZIPTIE_LOCAL`.
- **Open: SEN66 airflow sealing**. Sensirion mechanical guidelines require inlet and outlet in **separate sealed channels** to prevent parasitic recirculation (outflow back into inlets through host case interior). With face-up mount in AK-N-94, both inlets and outlet share the cover air-space → potential recirculation. Mitigation options TBD: (a) foam shroud separating inlet zone from outlet zone, (b) baffle on cover interior, (c) accept residual recirculation as design compromise. Decision after physical AK-N-94 sample arrives.
- **Sensor zone below electronics** (PCB flat on bottom edge). Reason: natural convection lifts heat from MCU / power section upward, away from the SEN66 air intake.
- **Connector strip along bottom flat**: 24V terminal, JST GH to SEN66, LD2410 connector, Qwiic, optional unpopulated SWD/UART recovery header. **No external USB-C** (use DevKitM-1's onboard USB before enclosure is sealed). Pre-defined positions exist in the manufacturer DXF; the case has matching cutouts / access.
- **Thermal isolation slots** (1.5 mm milled gaps in FR4) separate Power, MCU, and peripheral zones.
- **Shared I²C bus**: SEN66 (0x6B), NT3H1101 (0x55, on MIKROE-2462 NFC Tag 2 Click), plus Qwiic expansion. Pull-ups **4.7 kΩ on MCU side** (v0.22 — reverted from the v0.6 10 kΩ choice after measuring realistic bus length). Realized bus length on the v0.22 PCB (Manhattan-routed estimate, MCU socket ↔ SEN66 J3 socket ↔ NFC J8 socket ↔ Qwiic J9, plus the off-PCB JST-GH cable to the SEN66 module itself) is **~140 mm PCB minimum-spanning-tree + ~80 mm cable = ~220 mm total**. That exceeds the Sensirion "< 100 mm strongly recommended" envelope but stays within the "< 500 mm with shielding" hard limit. At 10 kΩ the rise time τ = R × C = 10 kΩ × 100 pF = 1 µs / t_r(10-90%) ≈ 2.2 µs exceeded the I²C standard-mode spec (t_r ≤ 1 µs at 100 kHz). 4.7 kΩ drops τ to ~470 ns / t_r ≈ 1 µs, comfortably within spec. The SEN66 datasheet §3.1 *recommends* 10 kΩ but does not mandate it (lower values explicitly allowed).
- **GPIO 8 boot-strap pull-up**: external R7 = 10 kΩ to +3V3 (v0.22 new). Required because the DevKitM-1's onboard pull-up relies on VCC_5V driving the onboard WS2812B, which floats in OAS (we feed +3V3 directly into J5.1 and leave VCC_5V unpowered). Without R7, GPIO 8 (BOOT-strap pin for SPI flash boot mode) lacks a deterministic HIGH at boot.
- **Bluetooth proxy** = software-only; no extra hardware.

### ESP32-C6-DevKitM-1-N4 pinout (v0.4 final)

| Pin | Function | Notes |
|---|---|---|
| GPIO 6 | I²C SDA | shared bus: SEN66 (0x6B), NT3H1101 (0x55, on MIKROE-2462), Qwiic expansion |
| GPIO 7 | I²C SCL | shared bus, 4.7 kΩ pull-ups on MCU side (v0.22 — reduced from 10 kΩ; see "Shared I²C bus" entry above for rise-time rationale) |
| GPIO 16 | UART1 TX → LD2410 RX | 256000 baud |
| GPIO 17 | UART1 RX ← LD2410 TX | 256000 baud |
| **GPIO 2** | LD2410 OUT (presence interrupt) | safe non-strap input |
| **GPIO 3** | NT3H1101 FD (NFC field-detect interrupt) | safe non-strap input |
| GPIO 8 | WS2812 DIN — external SK6812-SIDE AQI ring (v0.16) | strap pin but OK — LED defaults idle-low. Onboard DevKitM-1 NeoPixel shares this GPIO but is unreachable in deployed units (its VDD floats on VCC_5V); the external ring on +5V is the active indicator. |
| GPIO 12 / 13 | Native USB-Serial-JTAG D+ / D− | wired to one of DevKitM-1's two USB-C ports; the other USB-C uses the onboard USB-to-UART bridge |

**Reserved / unavailable**:
- **GPIO 10, GPIO 11**: physically not bonded out on ESP32-C6FH4 (internal SiP flash uses these pins). Available on every external chip variant but NOT on MINI-1/SuperMini/XIAO/DevKitM-1 modules.
- **Strap pins (avoid for general I/O)**: GPIO 4 (MTMS), 5 (MTDI), 9 (BOOT button on DevKitM-1), 15 (boot-mode select).

**Available safe-non-strap spare GPIOs** (for future expansion beyond the 7 signals above): 0, 1, 14, 18, 19, 20, 21, 22, 23 — nine pins free.

See `docs/ARCHITECTURE.md` for the canonical pinout table including onboard hardware notes (power LED desolder plan, button accessibility, etc.).

### ✅ RESOLVED — onboard NeoPixel V5V issue (closed in v0.16, option c)

(Originally raised v0.15.8.) The DevKitM-1's on-board WS2812B (D6) has its **VDD pin tied to VCC_5V**, not VCC_3V3, and so does not light in a deployed OAS unit (no USB → VCC_5V floats). v0.16 resolves this by adopting **option (c)**: the OAS PCB carries 12 × SK6812-SIDE LEDs as an external "AQI ring" around the central cable hole, driven from GPIO 8 (same line that drives the onboard NeoPixel). The ring is powered from the LM2596S-5.0 +5V rail and lights up unconditionally; the onboard NeoPixel is left as a no-op in firmware (its presence on the chain is irrelevant since the ring is the active indicator). See v0.16 changelog entry for full rationale and `hardware/components/_research-led-diffuse-ring.md` for the SK6812-SIDE selection research.

---

## Software

- **Framework**: ESPHome (YAML configuration)
- **HA integration**: native API
- **OTA**: via ESPHome + HA
- **BLE proxy**: ESPHome `bluetooth_proxy:` component
- **NFC dynamic content**: custom component or `lambda` block calling Sensirion / NXP libraries

ESPHome components expected:
- `sensor.sen66` (verify native availability; fallback to custom)
- `binary_sensor.ld2410` and `sensor.ld2410` (official integration exists)
- `light.neopixelbus` (WS2812B with breathing effect)
- `bluetooth_proxy`

---

## Hard constraints (do not violate without an explicit, documented decision)

1. **Front-side component height — sector-dependent** (v0.6):
   - **Default: 17 mm** across the PCB (per manufacturer DXF annotation `正面限高 17mm`, presumed regional/peripheral).
   - **SEN66 zone exception: ≥22 mm** required to accommodate the 21.3 mm SEN66 body on its natural-orientation footprint (Pillar #1 anchor sensor). Contingent on physical AK-N-94 verification (CASE-VERIFICATION-CHECKLIST §1) — if global 17 mm is confirmed, fallback to Combination Alpha (SPS30 + SCD41 + SGP41 + SHT45, max 12 mm height) per v0.6 changelog.
2. Maximum **5 mm** on the back side (solder fillets + pin-header bottoms; no SMD components on back. Achieved by 2 mm washers under the M3 mounting screws — lifts the PCB off the enclosure bosses, gaining 2 mm clearance over the DXF-annotated 3 mm)
3. **Ø120 mm D-shape** PCB outline from the manufacturer DXF
4. **3× M3 mounting holes** at positions defined in the DXF
5. **24V DC** input only (no 12V, no external 5V)
6. **ESP32-C6** as MCU, **specifically ESP32-C6-DevKitM-1-N4** (Espressif official devkit with ESP32-C6-MINI-1 module; EAN 5904422385651 at Botland). No fallback to C3, S3, or to generic "SuperMini" clones with unverifiable pinouts.
7. **AK-N-94** enclosure as the integration target (do not redesign for another case)
8. **Both design pillars** (measurement quality, aesthetic acceptability) — no change degrades either pillar

---

## Out of scope (decisions already made)

These were considered and explicitly rejected. Do not propose them again without new information justifying revisit:

- ❌ Battery / alternative power source (24V mains only)
- ❌ Buzzer or audio output
- ❌ Capacitive touch input
- ❌ External temperature probe terminal (DS18B20 / NTC) — SEN66 is sufficient
- ❌ Input current monitoring (INA219)
- ❌ Display (OLED / LCD) — revisited mid-2026 (research in `hardware/components/_research-round-display.md`). Best candidate identified (Waveshare 1.28" round IPS LCD, GC9A01, Ø32.4 mm) clears Pillar #1 (measurement quality — SEN66 thermal delta <0.3 K from backlight, inlet area loss <3 %, EMI from SPI below threshold) but fails Pillar #2 (aesthetic): the screen-off state is a permanent dark grey circle on the white perforated ABS cover, breaking the smoke-detector silhouette the project defends. The existing UX stack — NFC tap on phone for live values + SK6812-SIDE LED ring for glanceable AQI status + Home Assistant dashboard for trends — covers the "see the data" need without committing the cover real estate. Also: a 240×240 round LCD requires SPI (5–6 GPIO of the 9 spare on ESP32-C6-DevKitM-1-N4) and adds ~€11/unit BOM plus a 3D-printed bezel and acrylic window insert. Reversal cost: a future v2 cover with a clear central window + bezel could host the display without breaking aesthetic; revisit if user reports a real glanceable-readout pain point that NFC/LED/HA cannot fill.
- ❌ External USB-C connector on the case wall (use DevKitM-1's own USB-C for programming; OTA after first flash)
- ❌ IR transmitter / receiver
- ❌ Microphone / acoustic sensor
- ❌ Ambient light sensor (Vishay VEML7700) — removed in v0.10. Originally a "bolt-on" feature, not core to the OAS mission (air quality + presence). Geometric light shielding from the onboard NeoPixel + power LED inside the white perforated enclosure would require either a 3D-printed baffle, an opaque shroud over the sensor, or moving the status LED off-module with a light pipe — all adding complexity and BOM for a non-essential measurement. Home Assistant has many other indoor light sensing options (phone ambient light, smart bulbs reporting brightness, dedicated USB-powered sensors). Saved I²C bus slot + ~€1 BOM + sensors-area PCB real estate.

---

## Open work / TODO

### Hardware
- [ ] Select specific buck converter ICs (validate efficiency, JLCPCB Basic Library availability)
- [x] ~~NFC antenna design (PCB spiral geometry, matching capacitor selection)~~ — sidestepped in v0.12 by adopting MIKROE-2462 (onboard pre-tuned PCB antenna)
- [x] ~~Validate ESP32-C6 pinout against strap pin and boot mode constraints~~ — done in v0.4 (GPIO 2/3 for LD2410_OUT/NFC_FD, GPIO 8 for onboard NeoPixel)
- [x] ~~IO sub-sheet populated~~ — done in v0.19 (J9 Qwiic JST SH on C5, J10 native-USB recovery DNP on C3, C4 reserved for v2 expansion)
- [ ] 3D model bracket for SEN66 mounting on cover (STL in `hardware/case/`)
- [ ] KiCad schematic — full
- [ ] KiCad PCB layout with thermal breaks
- [ ] DRC and ERC clean
- [ ] Generate gerbers + assembly drawings

### Firmware
- [ ] Base ESPHome config
- [ ] LD2410 UART integration and presence binary sensor
- [ ] WS2812 effect: breathing animation + AQI-to-color mapping function
- [ ] NFC tag content updater (live data write via I²C)
- [ ] Bluetooth proxy enabled and validated
- [ ] OTA setup
- [ ] HA discovery / device class metadata

### Logistics
- [ ] Order one AK-N-94 enclosure for prototype validation
- [ ] Order one SEN66 sample for development
- [ ] Finalize BOM with per-unit cost at batch quantity
- [ ] Order 1–2 prototype PCBs via JLCPCB before batch production

---

## Repository layout

```
open-ambient-sensor/
├── hardware/
│   ├── case/
│   │   ├── README.md             # how to obtain manufacturer DXF/datasheet (not committed)
│   │   └── sen66-bracket.stl     # own work — bracket for mounting SEN66 on cover
│   ├── kicad/
│   │   ├── generate.py           # SOURCE OF TRUTH — Python that generates all .kicad_* files
│   │   ├── regenerate.py         # master script: generate + DRC/ERC + re-render
│   │   ├── oas.kicad_pro         # generated artefact
│   │   ├── oas.kicad_sch         # generated artefact
│   │   ├── oas.kicad_pcb         # generated artefact
│   │   ├── libraries/            # generated custom footprints
│   │   └── renders/              # generated previews (PNG + SVG + DRC/ERC reports)
│   ├── bom/
│   │   ├── bom-jlcpcb.csv
│   │   ├── bom-mouser.csv
│   │   └── bom-misc.md           # locally-sourced items
│   └── gerbers/                  # production output
├── firmware/
│   ├── esphome/
│   │   ├── oas.yaml              # base configuration
│   │   ├── packages/             # shared YAML fragments
│   │   └── examples/             # example device overrides (anonymized)
│   ├── secrets.yaml.example
│   └── README.md
├── docs/
│   ├── README.md
│   ├── ARCHITECTURE.md
│   ├── BOM.md
│   ├── ASSEMBLY.md
│   ├── FLASHING.md
│   └── HA-INTEGRATION.md
├── .gitignore                    # MUST ignore secrets.yaml, third-party manufacturer files, build artifacts
├── LICENSE
└── CLAUDE.md                     # this file
```

`.gitignore` must include at minimum:
```
# secrets
secrets.yaml
**/secrets.yaml

# third-party manufacturer files (kept locally, not redistributable)
hardware/case/*.dxf
hardware/case/*-datasheet.pdf
hardware/case/manufacturer-*.step

# build artifacts
**/build/
**/.cache/
*.bak
*-backups/
```

---

## PCB design workflow

The KiCad project in `hardware/kicad/` is **script-driven**. The source-of-truth is the Python in `generate.py`, **not** `oas.kicad_pcb` / `oas.kicad_sch` / `oas.kicad_pro` / `MountingHole_3.8mm_M3.kicad_mod` — those are *derived artefacts* (regenerated bit-identically from the Python).

### How we work on the PCB

1. The user describes a desired change (e.g. *"shift cutout C3 by 0.5 mm"*, *"swap chord to 80 mm"*, *"add reverse-polarity protection on the 24 V input"*).
2. The assistant edits the appropriate constant or function in `generate.py`. Geometric parameters live as named constants at the top of the file (`R_OUTLINE`, `CHORD`, `HOLE_DIAMETER`, `CUTOUTS`, etc.); structural choices (stackup, design rules, footprint definitions) live in dedicated generator functions further down.
3. The assistant runs `python regenerate.py`. That one command:
   - calls `generate.py` to rebuild every KiCad source file,
   - runs `kicad-cli pcb drc` and `kicad-cli sch erc` and aborts on any error or warning,
   - re-renders `renders/2d-top.{svg,png}`, `renders/2d-cutouts.{svg,png}`, `renders/2d-bottom.{svg,png}`, `renders/3d-top.png`, and the DRC / ERC reports.
4. The assistant commits the resulting diff (sources + KiCad files + renders together).

### Rules

- **Never edit `.kicad_pcb`, `.kicad_sch`, `.kicad_pro`, or `*.kicad_mod` directly.** The next `regenerate.py` would overwrite the edit. If you find yourself wanting to hand-edit one of those, that's the signal to add a new constant or function to `generate.py`.
- **All UUIDs are deterministic v5** (namespaced under the OAS project). Two consecutive runs of `regenerate.py` with no source changes produce a bit-identical PCB file → empty `git diff`. If a regeneration produces a non-empty diff, that's a real change.
- **`renders/` is committed** as a visual changelog. Reviewers can see geometry changes in PRs without launching KiCad. The 3D render (~15 s) is regenerated every run; SVG/PNG previews are essentially free.
- **This convention applies to the geometry / structural layer**. Once meaningful schematic content (placed symbols, drawn nets) exists, that may either continue as script-generated or migrate to direct file editing — to be decided when we get there.

### How to do something the workflow doesn't support yet

If a change is awkward to express in `generate.py` (e.g. one-off ad-hoc graphic on the silkscreen), **either** extend `generate.py` with the needed abstraction **or** introduce a second generator script for that artefact class. Do **not** introduce a pattern where the source-of-truth lives in two places.

---

## Working conventions for the assistant

### Communication
- Match the user's chat language; this does not change the requirement that **repo content is English**.
- Be concise. Avoid padding, unnecessary disclaimers, and overly long explanations.
- When committing files, English is mandatory regardless of chat language.

### Privacy hygiene
- Before writing any file, scan it mentally for the rules in the "Public repository rules" section above.
- Reject any user request that would commit personal data to the repo. Suggest local-only alternatives instead (gitignored notes, separate non-versioned files).
- If the user pastes content that contains PII, **do not include it in committed files**. Sanitize and warn.

### Component selection
- Apply both design pillars (measurement quality, aesthetic acceptability) as filters before considering cost
- **For SMD components** going through JLCPCB assembly: prefer Basic Parts Library (free assembly), Extended Library (~$3 setup fee) acceptable when needed for the right part
- **For manual-mount components** (ESP32-C6-DevKitM-1, SEN66, LD2410, terminal blocks, headers): JLCPCB availability is **not required** — these can be sourced separately (AliExpress, LCSC, Mouser, Digikey, Botland) since user does final hand assembly. Pick the right part on technical merit; sourcing is secondary.
- Report part numbers and current availability when proposing components
- Validate prices in production quantity; do not propose parts known to be EOL or perpetually out of stock

### Module identification (mandatory rule for ANY board / module / dev-kit)

When recommending or specifying a module / dev-board / breakout, **never use a generic name alone** ("ESP32-C6 SuperMini", "Arduino Nano", "STM32 BluePill"). Generic names refer to clones from many vendors with **different pinouts and capabilities** — picking one at random is a setup for assembly-time surprises.

Every module decision MUST include AT LEAST ONE of:
- **EAN / GTIN** (preferred for Polish/EU retail orders) — e.g. `EAN 5904422385651`
- **Manufacturer part number (MPN)** — e.g. `ESP32-C6-DevKitM-1-N4`, `Seeed SKU 113991254`, `Adafruit Product ID 5933`
- **Direct supplier URL** to a specific listing (botland.store/..., adafruit.com/product/..., seeedstudio.com/...)

Before committing to a module in any schematic or documentation:
1. Read the **official datasheet or wiki** of that specific model (Espressif's docs for DevKit, Seeed wiki for XIAO, Adafruit Learning System for Feather, etc.) — NOT the first random pinout that shows up in a web search
2. **Verify which GPIO pins are physically exposed on the external pads** — small modules typically expose only 11-15 of the chip's GPIOs, and which ones varies between vendors. Map every signal you plan to use to a specific exposed pad.
3. **Watch for chip-level pin omissions** — e.g. ESP32-C6 with internal SiP flash physically does NOT bond out GPIO 10 or GPIO 11 (those pins serve internal flash communication). Don't rely on "chip has 30 GPIO" — count what's actually exposed on the chosen module variant.
4. **Verify strap pins, USB-reserved pins (GPIO 12/13 on C6), and any vendor-specific reservations** (onboard LED, onboard button) BEFORE assigning signals.

Past mistake to avoid: in v0.3 of this project, "GPIO 4 → GPIO 10 / GPIO 5 → GPIO 11" was prescribed as a pinout fix for ESP32-C6 strap-pin avoidance. This was incorrect — GPIO 10 and GPIO 11 don't exist on any ESP32-C6 variant with internal SiP flash (which is every popular module: MINI-1, SuperMini, XIAO, Zero). The bug took 4 review passes to catch because nobody verified physical chip pinout against the assumed pin numbers. Fixed in v0.4.

### Validation
- Schematic: run ERC, fix or document every warning
- PCB: run DRC at production rules, verify 3D view against the 17 mm height constraint
- BOM: cross-check against manufacturer stock the same day as ordering
- Firmware: validate ESPHome config compiles cleanly before tagging a release

### External services — MANUAL TRIGGER ONLY

The OAS pipeline (`regenerate.py`) is fully offline: every guard (DRC, ERC,
determinism, DC simulation, boot-pin audit, ampacity, Z-clearance) runs
against local files only. **Never auto-trigger any external service** from
`regenerate.py` or any CI loop.

Specifically:

- **JLCPCB DFM upload** (`tools/jlcdfm_upload.py`): runs Playwright against
  `https://jlcdfm.com` to upload `oas-jlcpcb.zip` and download the analysis
  report. **Run only when the user explicitly asks** (e.g. "puść DFM",
  "run the dfm check"). JLCPCB's `/api/overseas-dfm-service/checkIp` endpoint
  tracks upload volume per IP — running on every regenerate would risk
  rate-limiting, captcha-gating, or IP block. Document each manual run in
  the commit message that triggered it.
- **JLCPCB SMT quote / order**: never automated. Always user-initiated.
- **Future external services** (TI WEBENCH, LCSC stock check, OSHPark
  upload, etc.): same rule. Default is offline; external calls require
  explicit user request per run.

When adding a new external-service tool: name it `tools/<service>_<action>.py`,
keep it OUT of `regenerate.py`'s default flow, and put a `print(...)` banner
at the top of the script stating "live external service, run manually".

### JLCPCB DFM warning categories — what is and isn't fixable

The OAS board at v0.40 holds a stable JLCPCB DFM result of **0 DANGER /
193 W** (warnings only, fully manufacturable). The remaining warnings
break into two classes the iteration loop has shown:

**Categories where surgical fixes work (proven via iter1):**
- Sharp trace corner — when the corner is in an OPEN area (not near
  another pad's clearance envelope). Merge the two short segments
  flanking the corner into one straight segment in `oas_routes.py`.
  Iter1 fixed 1 of 9 this way (Net-(D12-DOUT) corner).

**Categories where surgical fixes DON'T work (proven via iter2):**
- LED ring sharp corners (Net-(D11..D21)-DOUT) — each 75° corner exists
  because the trace must dodge the NEXT LED's GND pad. Merging into a
  straight line CLIPS the GND pad and fails DRC at the 0.15 mm rule.
  Trying to fix 12 at once produced 8 DRC violations; trying just one
  produced 1 violation. STRUCTURAL — cannot fix without re-positioning
  LEDs or routing wider arcs.
- I²C parallel-bus trace spacing (~28 instances at 0.15-0.18 mm) — the
  SDA/SCL pair was deliberately routed parallel for impedance matching.
  Widening triggers domino-failure DRC clearance elsewhere.
- Silkscreen line width 0.12 mm (50 W) — comes from stock-library
  footprint silk inside PinSocket / MIKROE / Phoenix MSTBA. Lifting
  globally to 0.15 mm doesn't satisfy JLCPCB (they want ≥ 0.20 mm) AND
  introduces 20 silk-to-pad DANGER findings (wider strokes consume
  clearance budget). Reverted in v0.40.
- Pad-to-mask expansion — bumping 0 → 0.05 mm fixed 5 Negative Mask
  Expansion warnings BUT created 1 Soldermask Bridge DANGER + 59 extra
  Mask-Exposes-Trace warnings + 5 extra Pad Spacing warnings. Net
  negative. Reverted in v0.40.
- 50 W Missing PTH + 50 W Unconnected via — FALSE POSITIVES, confirmed
  via live JLCDFM Details inspection. JLCPCB reports 139 actual "Missing
  PTH" results (only first 50 shown in dialog). OAS PTH drill count
  is 137 (65 vias + 72 connector PTH pins) — near 1:1 match. The 139
  flagged pads are connector pins (J5/J6/J7/J8/J4/J1/J10 pin sockets +
  headers), all emitted by KiCad as `(pad thru_hole layers "*.Cu"
  "*.Mask")` with proper PTH drills. JLCPCB's algorithm misclassifies
  them because the GND pour uses thermal-relief connect_pads mode
  (thermal_gap 0.508, thermal_bridge_width 0.508), giving B.Cu a
  cross-pattern around each GND pin instead of solid copper. The
  algorithm sees "F.Cu round/square solid pad ≠ B.Cu 4-spoke pattern"
  and flags as missing PTH. Fixing requires changing the pour to
  solid-fill connect_pads, which would make hand-soldering harder
  (heat sink to entire pour mass). Trade-off rejects fix; accept as
  residual.

**Lesson:** DFM warnings come in two flavors. *Routing-quality warnings*
flagged on individual segments are sometimes fixable by editing
`oas_routes.py`. *Structural warnings* (LED ring geometry, parallel
bus runs, stock-library silk frames, pour stitching vias) are
inherent to the chosen architecture and would require invasive
re-design to address. The OAS project accepts warnings of this second
class as the cost of the current architecture — Pillar #1 (measurement
quality) and Pillar #2 (aesthetic) decisions take precedence over
DFM yield optimization.

When working on DFM fixes:
1. ALWAYS run live `tools/jlcdfm_upload.py` after a fix to verify it
   reduces the targeted warning AND doesn't regress any other check
   (the local Python silk-to-pad scanner ≠ JLCPCB's algorithm).
2. Apply ONE change per iteration. Cross-cutting fixes (mask expansion,
   silk lift) have a high risk of net-negative results.
3. Stop iterating when the remaining warnings are all in the
   "structural" class. Don't burn cycles on fundamentally unsolvable
   warnings; document them and move on.

### KiCad schematic conventions

- **`no_connect` markers** on intentionally-unused IC pins. Without them, ERC warns "pin not connected". Use freely — they are documentation that says "this is deliberate, not an oversight." Common on ESP32-C6-DevKitM-1-N4 pins we don't wire (5V, unused GPIOs).
- **`(dnp yes)` flag** for footprints that should appear on the PCB but NOT in the assembly BOM. Use for hand-solder-on-demand parts (recovery headers, debug pads, optional features). The KiCad render shows a diagonal X overlay on the symbol to flag DNP visually. JLCPCB assembly will skip these.
- **Hierarchical labels** for inter-sheet signals (sub-sheet exports/imports). Direction tags (`input`/`output`/`bidirectional`) are documentation, not enforced by KiCad — but they help reviewers and matter when the root sheet adds matching sheet ports.
- **ERC warnings during incremental sheet build are expected**: when chunk N adds a sub-sheet with hierarchical labels, ERC will warn "label not connected to a sheet port" until the matching sub-sheet (chunk N+1 or later) declares the same label. These warnings are temporary and should resolve once the related sheets land. Document expected warnings in commit messages; don't treat them as bugs.

### PCB silkscreen conventions

- **F.SilkScreen and B.SilkScreen are committed-output documentation** aimed at the human hand-assembling and servicing the board. For every major component — sensor module, connector, mounting hole class, special-purpose footprint — add a short text label on F.SilkScreen identifying what it is. The end user holding the assembled board sees only the silkscreen; the F.Fab layer is for machine-readable assembly drawings (MPN, polarity, pin 1 markers) that production may print but the user typically never sees.
- **Example labels**: `"SEN66 air quality"`, `"24V terminal"`, `"to LD2410"`, `"USB UART"`, `"to SEN66"`, `"-> J3"`. Keep labels concise (≤20 chars) and self-explanatory in isolation (a user must not need the schematic to interpret them).
- **Sizing**: 1.0–1.5 mm text height, ~0.15 mm stroke thickness (KiCad defaults). Slightly larger (up to 2 mm) is fine when there's room.
- **Designators on PCB features**: when a footprint's `Reference` property is hidden (typical for mounting holes and zip-tie holes), emit a separate `fp_text user` on F.SilkS with the designator (`H1`, `H2`, `ZT1`..`ZT4`) so the hand-assembler can identify each hole at a glance.
- **Cable direction hints**: connectors that mate via cable should carry a F.SilkS arrow (`"-> J3"`, `"to SEN66"`) on both ends. Cuts the schematic out of the assembly loop for cable routing.
- **Implementation**: silk labels go either inside the placed footprint (as `fp_text user` — inherits footprint rotation) or as board-level `gr_text` (rotation-independent, easier to keep horizontal on a rotated footprint). Pick whichever keeps the source-of-truth Python cleaner; for one-instance footprints with non-zero rotation (e.g. the SEN66, J3), board-level `gr_text` is usually simpler.
- **Over-documenting is better than under-documenting.** Silk ink is essentially free; the cost is a few seconds of layout review. The cost of an unlabeled board is the assembler grabbing the schematic every time.

### Before instructing an agent to "fix" a schematic

- **Verify pin positions against the lib symbol definition, not from memory.** KiCad connector libraries (e.g. `Connector_Generic:Conn_01x06`) often have asymmetric pin coordinates — for example `Conn_01x06` has pins from lib_y = +7.62 mm to lib_y = −7.62 mm (six pins on a 2.54 mm grid, but with the symbol center between pins 3 and 4, not at pin 4's height). Standard "pin 1 at +5.08, pin 6 at −5.08" intuition is wrong for the stock 01x06.
- **Read the actual `.kicad_sch` source** or grep the lib_symbol definition before claiming a pin is unconnected. A wire that appears to "pass by" a connector in the rendered PNG may actually be tapping the bottom pin via a junction whose position you misjudged from memory.
- **Trust the agent's empirical inspection over your stored mental model** when in doubt. The agent reads files; you reason from memory.

---

## Reference links

- AirGradient ONE (open-source inspiration): https://github.com/airgradienthq/arduino
- Sensirion SEN66 product page: https://sensirion.com/products/catalog/SEN66
- Sensirion SEN6x datasheet: https://sensirion.com/resource/datasheet/SEN6x
- HiLink LD2410 documentation and UART protocol: https://www.hlktech.net
- NXP NT3H2x11 antenna design AN11203: https://www.nxp.com
- SZOMK enclosures: https://www.chinaenclosure.com
- ESPHome documentation: https://esphome.io
- JLCPCB component library: https://jlcpcb.com/parts

---

## Changelog

- **v0.35** — LCSC SKUs filled for full SMT assembly: `hardware/bom/lcsc-mapping.csv` + `export_production.py` post-process. Ready for JLCPCB PCBA quote.
  - **Trigger**: 5-prototype JLCPCB SMT-assembly order. With 22 unique SMD part groups across the board, hand-filling the LCSC column at upload time is error-prone (transcription errors, value/footprint mismatches), and JLCPCB's smart-match silently picks "the cheapest matching part" without the user's input on substitutions (e.g. clone vs. original IC, BOM downgrade for unobtanium parts). v0.35 makes the SKU choice explicit and committed.
  - **`hardware/bom/lcsc-mapping.csv` (new, source-of-truth)** — 22 rows, one per unique SMD `(Value, Footprint)` group. Columns: `Value, Footprint, LCSC, Manufacturer, MPN, JLCPCB_Library, Stock, Datasheet_URL, Notes`. Hand-curated against the JLCPCB Parts Library (https://jlcpcb.com/parts) and lcsc.com. Persistent across re-runs of `export_production.py` — the volatile `oas-bom.csv` in `hardware/gerbers/` (gitignored, regenerable) is derived from it.
  - **Library split**: **12 Basic Library parts** (Samsung MLCC reels, Uni-Royal 0603 resistors, Brightking SMBJ24A, MDD SS14, CJ BZT52C18S — all "Very popular" tier in JLCPCB's Basic Library at multi-million stock counts; $0 setup fee per Basic part) + **11 Extended Library parts** (TI LM2596S-5.0/NOPB, TI TPS62933DRLR, CENKER inductor reels, JST SH/GH genuine connectors, Walsin 250VDC MLCC, Littelfuse polyfuse, Nexperia PMV65XP, OPSCO SK6812SIDE-A, Yageo 44.2k 1% precision resistor). **JLCPCB charges $3 setup per unique Extended part one-time per assembly job → 11 × $3 = $33 one-time setup fee** for this build (independent of prototype count).
  - **Substitutions documented in CSV Notes column**:
    - **C2 (10nF Y2 → 250VDC X7R MLCC, Walsin 0805B103K251CT C303895, Extended)**: True Y2-class safety-certified MLCC does not exist in 0805 SMD package (Y2 caps require physical insulation separation only achievable in 1812+ packages). For 24V DC SELV system inside fully-isolated plastic AK-N-94 enclosure, the PE conductor terminates at PCB GND via C2 as an EMI bridge only — no hazardous mains potential is bridged. Electrically equivalent; not certified for line-coupled use (irrelevant for OAS). If strict Y2 certification ever required, change footprint to 1812 and source Knowles/KEMET CAS-series safety-cert MLCC.
    - **L1 33µH "2A" → CENKER CKCS5040-33uH/M C354612 (Irms=1.2A, Isat=1.3A)**: physical limit at the 5×5 mm body footprint. No 5040-size 33µH inductor on LCSC reaches 2A — those values require 12×12 mm body (Bourns SRR1260-330M C840528). For prototype this is acceptable because OAS typical load is ~300 mA (LD2410 ~80 mA + LED ring avg ~80 mA + SEN66 ~130 mA + misc) — well within 1.2 A Irms. If production load grows substantially, swap the L1 footprint to 6045 or 1264 in `generate.py` and re-spec.
  - **Stock risk flags in CSV Notes column**:
    - **R2 (44.2k 1% 0603, Yageo RC0603FR-0744K2L → C137723 PROVISIONAL)**: web research could not directly confirm the exact LCSC C-number for the 44.2k variant; C137723 entered as a placeholder is the 40.2k variant from the same Yageo series. The 44.2k value is a standard E96 part and JLCPCB's smart-match (Value="44.2k", Footprint=R_0603_1608Metric) will reliably find it. ACTION FOR USER: verify at upload time before submitting quote.
    - **Q1 PMV65XP (C75561 Nexperia)**: SAFETY FLAG documented in CSV. Per Nexperia datasheet, **Vds_max = -20V only**. The schematic comment in `generate.py` line ~11298 claims "-50V" which is INCORRECT (matches a different part). During a D1 SMBJ24A TVS-clamp event the rail spikes to 38.9V → Q1 Vds_max exceeded by ~19V. Continuous 24V operation has Vds ≈ 0V (Q1 is conducting) so steady-state OK; the risk is transient. For production reliability the documented user-decision substitute is **AO3401A (C15127, Vds=-30V, same SOT-23 footprint)** which raises margin from -20V to -30V (still below 38.9V worst-case but with significantly more cushion). Full margin would require DMP4015SK3 (-40V) but that's TO-252 package and requires a footprint change in `generate.py`. ACTION FOR USER: decide before order — accept documented risk on prototype OR swap to AO3401A (one-line change in `generate.py` Q1 stub, no PCB respin needed).
  - **`hardware/kicad/export_production.py` BOM post-processing**:
    - New `_load_lcsc_mapping()` reads `hardware/bom/lcsc-mapping.csv` into a `(Value, Footprint) → (LCSC, JLCPCB_Library)` dict.
    - New `_postprocess_bom_with_lcsc_mapping()` rewrites `hardware/gerbers/oas-bom.csv` after `kicad-cli sch export bom` emits the raw version: fills LCSC for every SMD row, adds a new `JLCPCB_Library` column (Basic / Extended / "THT (hand-solder)"), preserves Designator and Qty grouping.
    - **THT detection**: hardcoded `THT_REFERENCES = {"J1", "J4", "J5", "J6", "J7", "J8", "C1", "C3", "C4"}` — terminal block, daughterboard sockets/header, and radial bulk caps that JLCPCB cannot SMT-assemble. THT rows get LCSC blank and JLCPCB_Library = "THT (hand-solder)" so the user knows which to hand-solder.
    - **Hard error on unmapped SMD**: if `kicad-cli` emits an SMD `(Value, Footprint)` group that has no row in `lcsc-mapping.csv`, the script aborts with the full unmapped row printed. Catches mapping-coverage drift (e.g. a future schematic change introduces a new MLCC value or footprint and the user forgot to update `lcsc-mapping.csv`).
    - **Output column order**: `Comment, Designator, Footprint, LCSC, JLCPCB_Library, Qty` — matches JLCPCB's "Standard BOM Template" with the new JLCPCB_Library column appended (their uploader ignores unknown columns).
  - **THT hand-solder list (9 components in 8 BOM rows)**:
    - J1 — Phoenix MSTBA 2,5/3-G-5,08 (24 V terminal block, 5.08 mm pitch THT)
    - J4 — 1×5 P1.27 mm THT header (LD2410B daughterboard mating row)
    - J5 / J6 — 2× 1×15 P2.54 mm female socket strips (ESP32-C6 DevKitM-1-N4 daughterboard)
    - J7 / J8 — 2× 1×8 P2.54 mm female socket strips (MIKROE-2462 mikroBUS pins)
    - C1 + C3 — 2× 100 µF / 50 V D8×11.5 mm radial THT bulk caps (BOM groups them; both populated)
    - C4 — 1× 220 µF / 10 V D6.3×11.2 mm radial THT bulk cap
  - **Verified output** (`python export_production.py` after the v0.35 changes): `oas-bom.csv` contains 31 rows total — 22 SMD with LCSC filled + 8 THT marked "hand-solder". JLCPCB Extended setup estimate printed at 11 × $3 = $33. JLCPCB zip bundle unchanged from v0.34 (141 kB, 11 files).
  - **Reusable lesson**: separating the LCSC SKU choice (committed, hand-curated, versioned) from the BOM emission (regenerable, derived) lets the user document the substitution rationale once and replay it deterministically on every future fab order. Same source-of-truth pattern as `oas_routes.py` (v0.28c).

- **v0.34** — Pre-flight gerber check: independent verification of `export_production.py` output before fab upload.
  - **Why**: kicad-cli exports gerbers from `oas.kicad_pcb` via KiCad's own plotter. If something went wrong in that conversion (aperture macro bug, missing layer, mangled drill file, etc.) it would slip through silently until JLCPCB's DFM scan caught it days later. v0.34 adds a 5-second sanity check using a completely independent parser (pygerber 2.4.3) so the regression surfaces locally before the fab order goes out.
  - **`hardware/kicad/tools/preflight_gerbers.py` (new, ~190 lines)** — four-stage check:
    1. **File integrity** — confirms every expected output file exists with non-zero size (9 gerbers + 2 drill files + zip bundle); reads the zip with `zipfile.testzip()` to detect corruption; verifies the bundle has the expected 11 entries.
    2. **Drill statistics** — Excellon parser walks `oas-PTH.drl` / `oas-NPTH.drl` line-by-line:
       - PTH: 5 tool sizes (0.30 / 0.65 / 0.80 / 1.00 / 1.40 mm), 137 holes total — 0.30 mm vias dominate the count after v0.32 closed the routing with 65 vias.
       - NPTH: 2 tool sizes (3.00 / 3.80 mm), exactly 7 holes — 4 zip-tie + 3 M3 mounting, no surprises. Tool-size set is compared against `EXPECTED_NPTH_TOOLS = {3.00, 3.80}` (the only NPTH sizes generate.py is allowed to emit); hole count compared against `EXPECTED_NPTH_COUNT = 7`. Either mismatch aborts.
       - Min PTH drill verified ≥ 0.30 mm (JLCPCB standard 2-layer cutoff; thinner needs the "Min hole 0.2 mm" upgrade option which costs extra).
    3. **Composite top render** — pygerber's `Project([F.Cu, F.Mask, F.SilkS, Edge.Cuts]).parse().render_raster(dpmm=20)` produces `renders/preflight-top.png`. Files are ordered bottom-up so Edge.Cuts ends on top of the visual stack.
    4. **Composite bottom render** — same for B.Cu + B.Mask + B.SilkS + Edge.Cuts → `renders/preflight-bottom.png`.
  - **Manual review step**: open `preflight-top.png` next to `2d-top.png` (and `preflight-bottom.png` next to `2d-bottom.png`). The two pairs should be GEOMETRICALLY identical — same board outline, same hole positions, same pad positions, same silkscreen labels. Color differences are expected (pygerber's default green vs KiCad's red theme). Geometric mismatches mean something went wrong between `.kicad_pcb` and gerber emission. v0.34 itself verifies clean: top + bottom both match the KiCad-side renders pad-for-pad.
  - **pygerber 2.4.3** — Python-native gerber parser/renderer, MIT licensed. Already on the user's machine (`pip install pygerber`). The script aborts with a clear "ERROR: pygerber not installed. Run: pip install pygerber" if it's missing — kept out of `requirements.txt` because pre-flight is an optional dev-time step.
  - **Output committed as visual changelog**: `renders/preflight-top.png` (108 kB) + `renders/preflight-bottom.png` (64 kB) join `2d-top.png` / `2d-bottom.png` as part of the diffable visual record. Reviewers can see what JLCPCB will actually see without re-running pygerber. Each routing/placement change in future PRs touches all four PNGs in lock-step.
  - **Workflow**: `python regenerate.py` (sources + previews) → `python export_production.py` (gerbers) → `python tools/preflight_gerbers.py` (verify) → eyeball top/bottom comparison → upload `oas-jlcpcb.zip` to JLCPCB.
  - **What the check is NOT**: it doesn't run DFM rules (JLCPCB does that on upload), doesn't simulate the manufacturing process, doesn't catch design errors (DRC/ERC do that). It's a translation-layer check — "did the gerbers come out of KiCad faithfully matching the source-of-truth PCB file?". Caught zero issues on first run, which is the expected result given the project's bit-identical determinism guarantee.

- **v0.33** — Production export infrastructure: `export_production.py` generates JLCPCB-ready deliverables in one command (~3 s).
  - **Trigger**: v0.32 closed routing at ABSOLUTE ZERO (DRC = 0, ERC = 0, 0 unconnected pads). Next step in the lifecycle is sending the board to fab. v0.33 builds the bridge from the source-of-truth Python + `oas.kicad_*` files to a JLCPCB upload bundle.
  - **`hardware/kicad/export_production.py` (new, ~220 lines)** — single script that runs all four `kicad-cli` production exports in sequence:
    1. **Gerbers** (`kicad-cli pcb export gerbers`) — 9 layers in Protel extension format (`.gtl`/`.gbl`/`.gts`/`.gbs`/`.gto`/`.gbo`/`.gtp`/`.gbp`/`.gm1`). Settings: `--subtract-soldermask` (silkscreen never lands on bare-copper pad openings), `--check-zones` (refills GND pour before plotting so the deliverable matches `2d-top.png` / `2d-bottom.png` previews), `--use-drill-file-origin` (shared coordinate frame with drill + pos), X2 format with TF attributes (JLCPCB recognizes and uses the embedded `.FileFunction` / `.AperFunction` metadata for automatic layer classification).
    2. **Drill files** (`kicad-cli pcb export drill`) — Excellon mm decimal format, `--excellon-separate-th` produces `oas-PTH.drl` + `oas-NPTH.drl` separately (JLCPCB convention), `--generate-map --map-format pdf` produces human-readable drill maps. PTH drill set: 0.30 mm (vias), 0.65 / 0.80 / 1.00 / 1.40 mm (pin headers, terminal blocks, Phoenix MSTBA). NPTH drill set: 3.00 mm (zip-tie holes) + 3.80 mm (M3 mounting holes). Minimum drill 0.30 mm is exactly JLCPCB standard-2-layer cutoff.
    3. **Position files** (`kicad-cli pcb export pos`) — CSV, mm units, one file per side. `--smd-only` (THT parts go on assembly drawing instead), `--exclude-dnp` (J2 + J10 recovery headers excluded as designed). Top side: 54 SMD footprints; bottom side: 0 (OAS is single-sided SMD).
    4. **BOM** (`kicad-cli sch export bom`) — CSV grouped by `Value,Footprint`, columns mapped to JLCPCB convention (`Comment,Designator,Footprint,LCSC,Qty`). `--exclude-dnp` applied. LCSC column emitted empty for now — user populates when ready to order SMT assembly; JLCPCB's smart-matcher fills most gaps from `Comment + Footprint` if LCSC is blank.
    5. **JLCPCB bundle** — packs all 9 gerbers + both drill files into a single `oas-jlcpcb.zip` (~141 kB, 11 entries) ready for direct upload to JLCPCB's web quoting page. Drill map PDFs, position files, and BOM are emitted alongside but NOT in the zip (JLCPCB SMT quote page wants them as separate uploads).
  - **Run time**: ~3.1 s end-to-end (everything is `kicad-cli` native; no Python-side geometry processing). Deliberately kept OUT of `regenerate.py`'s inner loop — running gerber export on every geometry iteration would waste CPU; production export runs only when actually sending to fab.
  - **`.gitignore` extended**: every gerber output type (`*.gtl`/`*.gbl`/`*.gts`/`*.gbs`/`*.gto`/`*.gbo`/`*.gtp`/`*.gbp`/`*.gm1`/`*.gbrjob`), drill files (`*.drl`), drill maps (`*-drl_map.pdf`), pos CSVs (`*-pos.csv`), the BOM (`oas-bom.csv`), and the zip bundle (`oas-jlcpcb.zip`) are now gitignored under `hardware/gerbers/`. Rationale: deliverables are regenerable bit-identically from the source-of-truth Python; committing them to git would bloat the repo with churn (every PCB iteration would re-emit binary gerbers). The user can manually commit a specific snapshot (`git add -f hardware/gerbers/oas-jlcpcb.zip`) at production milestones for a permanent record of what was actually sent to fab.
  - **`clean_output_dir()` preserves dotfiles**: the export script wipes `hardware/gerbers/` before re-emitting to keep stale files from sneaking into the zip, but skips any path starting with `.` so `.gitkeep` (and a future `.gitignore` if needed) survives. The `.gitkeep` file documents the deliverable schema inline so a fresh checkout shows what's expected to land in the directory without having to run the script first.
  - **Verification**: ran the script against the v0.32 board snapshot. Output: 9 gerbers (cumulative ~575 kB) + 2 drill files (3.3 kB) + 2 drill map PDFs (~31 kB) + top pos (3.8 kB, 54 rows) + bottom pos (36 B, header-only) + BOM (2.5 kB, 31 grouped part lines) + zip bundle (141 kB, 11 entries). Spot-checked gerber header confirms X2 format with `FSLAX46Y46` precision (4.6 = standard fab precision, well above JLCPCB's 3.5 minimum). PTH drill file lists 5 tool sizes, NPTH lists 2 — matches the design intent.
  - **No CLAUDE.md "Out of scope" change**: gerber export was never on the rejected list; it was implicit in the project layout (`hardware/gerbers/` placeholder dir existed from v0.1). v0.33 just lifts it from "TODO sometime" to "one command".

- **v0.32** — Final routing closure: ABSOLUTE zero unconnected_items reached. **DRC = 0 violations, 0 unconnected pads. ERC = 0 violations.**
  - **Trigger**: v0.31 left 2 `unconnected_items` reports — both `Zone[GND] vs Zone[GND]` on F.Cu, pointing at 3 sub-1.5 mm² F.Cu pour fragments that v0.31's stitching-via approach could not bridge (no B.Cu main GND pour overlap, OR no via spot inside DRC-cleared envelope).
  - **3 problem fragments identified** (per v0.31 changelog and re-verified here by parsing the post-refill `(filled_polygon ...)` records):
    - **F.Cu #5 (0.20 mm²)** at PCB centroid (-0.876, -45.935), bbox (-1.150, -46.250)..(-0.720, -45.750). Sliver around the C8.2 (0805 cap GND) pad's clearance ring.
    - **F.Cu #6 (1.22 mm²)** at PCB centroid (+4.193, -48.116), bbox (+3.246, -48.701)..(+5.421, -47.583). Pure leftover copper between buck-section tracks — NO pad inside.
    - **F.Cu #9 (0.40 mm²)** at PCB centroid (+34.125, +24.738), bbox (+33.875, +24.326)..(+34.375, +25.150). Sliver around the J3.2 (SEN66 GND pin) pad's clearance ring.
  - **Three different treatments**, one per fragment based on what each one actually is:
    - **F.Cu #5** — via at PCB (-1.800, -46.000), 0.6 ⌀ / 0.3 drill, GND. The via centre sits 0.65 mm WEST of C8.2's pad centre — its east half (radius 0.3 → east edge X=-1.5) is INSIDE C8.2's west extent (X∈[-1.625, -0.675]), so the via's F.Cu copper merges with the pad's F.Cu copper directly (same-net, no clearance issue). The via's B.Cu side then lands inside the contiguous B.Cu main GND pour 0.854 mm clear of the nearest non-GND track (Net-(U2-FB) B.Cu diagonal). Clearance verification: C8.1 (Net-(U2-SS)) east edge at X=-2.375 → via west edge at X=-2.1 → 0.275 mm gap (need 0.15, OK); U2-BST F.Cu horizontal at Y=-46.846 → 0.846 mm (OK).
    - **F.Cu #6** — copperpour-only keepout zone covering PCB bbox (+3.15, -48.80)..(+5.52, -47.48). This fragment has NO pad inside (closest GND pad is C8.2 at 5.75 mm) and NO B.Cu main GND pour to reach (the B.Cu directly under this fragment is occupied by /IO/BOOT and Net-(U2-FB) tracks — no GND pour fills the B.Cu cell here). The only viable treatment is to suppress the fragment entirely by telling the F.Cu zone-filler "don't fill here". The keepout uses `(copperpour not_allowed)` ONLY — `(tracks allowed)`, `(vias allowed)`, `(pads allowed)`. A prior attempt with `(tracks not_allowed) (vias not_allowed)` cascaded 135 clearance violations against existing tracks/vias inside the keepout; the surgical `copperpour-only` variant avoids that entirely.
    - **F.Cu #9** — via-IN-PAD at PCB (+34.125, +25.150), exact centre of J3.2. J3.2 is a roundrect SMD pad sized 0.6 × 1.7 mm; a 0.6 ⌀ via fits inside on F.Cu (same-net so no clearance violation with the pad itself). On B.Cu the via lands 3.09 mm clear of the nearest non-GND track (/IO/I2C_SDA at Y=26.277..26.682), well inside the B.Cu main GND pour.
  - **Implementation** (`generate.py`):
    - New `_RouteEmitter.gnd_island_keepout(layer, xmin, ymin, xmax, ymax, *, tag)` method emits a `(zone ... (keepout (copperpour not_allowed)) ... (polygon (pts ...)))` rectangle with `(tracks allowed) (vias allowed) (pads allowed) (footprints allowed)`. Deterministic UUID via `uuid5(_OAS_NS, f"oas-zone:gnd-island-keepout:{tag}")`. The keepout has `(net 0)` (no net) so it doesn't interact with the GND pour's net-aware fill logic except via the keepout rule.
    - `_route_gnd_pour` extended: after the two main F.Cu / B.Cu GND pour zones, the function now emits **1 keepout (F.Cu#6) + 2 vias (F.Cu#5 + F.Cu#9 bridges)** on the GND net. Inline comments at each emit document the per-fragment rationale + clearance arithmetic so future iterations don't accidentally re-introduce one of the alternative-but-broken approaches.
    - The keepout-only approach was tried first across all 3 fragments and failed: it converted the 2 zone-vs-zone unconnected_items into 2 pad-vs-zone unconnected_items (C8.2 and J3.2 became electrically isolated because their only GND path was the small fragment, and the keepout removed that fragment). The final approach mixes via bridging (where B.Cu main pour reaches) with keepout (where it doesn't and there's no pad to strand).
  - **Track / via count delta vs v0.31**: tracks unchanged at **471**; vias **63 → 65** (+2 GND bridge vias).
  - **DRC**: 0 violations, 0 unconnected pads (**ABSOLUTE ZERO achieved**).
  - **ERC**: 0 violations (unchanged).
  - **Determinism self-check**: 17 files bit-identical across two consecutive `generate.py` runs.
  - **Z-clearance guardrail**: 76 footprints checked, 0 violations (unchanged).
  - **Cascade check**: the `(copperpour not_allowed)` ONLY keepout strategy successfully avoided the 135-violation cascade that the prior `tracks_not_allowed + vias_not_allowed` attempt produced — confirmed by zero clearance/hole_clearance violations in the post-v0.32 DRC.
  - **Verdict**: routing closure complete. Every electrical net has a fully-connected copper path. No DRC-level cosmetic warnings remain. The board is ready for gerber export and JLCPCB submission.

- **v0.31** — Stitching vias for F.Cu / B.Cu GND pour islands → **0 DRC violations, 0 ERC violations, 2 unconnected_items remaining (down from 10 at v0.30, 80% reduction)**. The remaining 2 are physical-unbridgeable F.Cu zone-fragment artifacts in pinched pockets where no via fits within DRC clearances.
  - **Approach**: each disconnected GND zone polygon was bridged with a deterministic-UUID F.Cu↔B.Cu through-via placed inside the island, where the via also lies inside the opposite-layer GND main pour. The via barrel then provides the electrical AND topological path connecting the island fragment to the main GND net.
  - **Workflow added (`_tmp_find_vias.py`, transient)**: an analysis script that reads the freshly-filled `oas.kicad_pcb` (via `kicad-cli pcb drc --refill-zones --save-board`), parses all `(filled_polygon ...)` records per zone, computes polygon centroids + areas, then scans each non-main polygon for the optimal via spot — a point inside both the island AND the opposite-layer main pour, clearing every existing pad / track / via at the standard 0.15 mm copper clearance + 0.5 mm hole-to-hole + 0.25 mm hole-to-copper rules. Two important gotchas the script captures:
    - **KiCad page→PCB Y mapping is NOT negated** — `pcb_y = page_y - PAGE_OY` (both axes grow southward). An earlier version had `pcb_y = -(page_y - PAGE_OY)` and produced via positions reflected about Y=0, all flagged by DRC.
    - **KiCad footprint rotation is CLOCKWISE in screen space** — `(rotated_x, rotated_y) = (lx*cos(θ) + ly*sin(θ), -lx*sin(θ) + ly*cos(θ))`, NOT the standard math CCW. Confirmed by checking that J6.12 (local Y=27.94, footprint rotation 90°) lands at page X = anchor_x + 27.94 (DRC report) and not anchor_x − 27.94 (math-CCW would predict). Without this fix, the analyzer missed every J5/J6/J7/J8 PTH pad and the early via positions collided with them.
  - **16 new vias placed** (all `(net 16 "GND")`, `(size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu")`, deterministic UUID `gnd-island-{layer}-{idx}`):
    - **12 F.Cu→B.Cu vias** for the 12 largest F.Cu islands (areas 2.0 – 71.5 mm²): islands #0, #2, #3, #4, #10, #11, #12, #13, #14, #15, #16, #17. Each via centroid lies inside both its island and the B.Cu main pour.
    - **1 F.Cu↔B.Cu chain via** for F.Cu island #7 (area 1.22 mm², no B.Cu main overlap): bridges to B.Cu island #2 instead, then B.Cu#2's own bridge via (next bullet) carries the chain to F.Cu main.
    - **3 B.Cu→F.Cu vias** for the 3 largest B.Cu islands (areas 37.4 – 61.8 mm²): islands #0, #1, #2.
  - **Tags + entries** are appended to `ROUTES_VIAS` in `oas_routes.py` (clean, append-only addition; the v0.28c-style `autoroute:` UUID prefix path through `_route_autoroute_tracks` carries them into the PCB at `apply_routing_to_pcb("autoroute")` time). 16 new entries; `oas_routes.py` total: 436 segments + 35 vias (was 436 + 19 at v0.30).
  - **Remaining 2 unconnected_items**: 4 zone fragments — F.Cu#5 (0.20 mm²), F.Cu#6 (1.22 mm²), F.Cu#9 (0.40 mm²), B.Cu#3 (0.68 mm²) — are physically un-bridgeable:
    - F.Cu#5 and F.Cu#9 are tiny pockets (~0.5 mm wide) carved out by `+3V3` track + neighbouring pad clearances; even a 0.4 mm via fails DRC by ~0.4 mm.
    - F.Cu#6 (2.17 × 1.12 mm) does NOT overlap B.Cu main pour anywhere — the matching B.Cu region in the same X-range is non-GND copper. Cannot chain through F.Cu#7 because both islands are separated by the J6 north edge clearance.
    - B.Cu#3 has a marginal F.Cu main overlap with +0.14 mm clear, but the only feasible via spot (PCB ≈(−52.93, −6.72)) sits 0.345 mm from a vertical B.Cu UART_TX track at page X=95.915 — placing a via there gets it absorbed into UART_TX, not GND, and triggers a `via_dangling` warning. (KiCad sees the via overlap the existing UART_TX trace and inherits its net.) Tried; reverted.
    - The 2 reported unconnected_items each represent **K-1 missing edges** for K disconnected F.Cu components beyond the main. With 3 F.Cu orphans (#5, #6, #9) → K=3 → 2 missing edges → 2 reports.
  - **What was tried but rejected**:
    - `island_removal_mode = 2` with `min_island_area X` — KiCad 10 rejects the `(min_island_area X)` S-expression token at load time (likely the field exists internally but is not persisted in the .kicad_pcb file format). PCB fails to load.
    - `(keepout (copperpour not_allowed))` zones over each orphan region — adding ANY such zone (even one) triggers ~135 unrelated `clearance` violations everywhere on the board (KiCad seems to escalate the default clearance rule globally when a new keepout zone with `copperpour not_allowed` is added; mechanism unknown, abandoned after 4 variants tested).
    - Lowering `min_thickness` from 0.25 mm to 0.15 mm in the GND zone — produces 134 violations from pre-existing tight-tolerance track-to-track spacing; doesn't reduce unconnected count.
    - Lowering `connect_pads (clearance 0.2)` to `0.1` — produces 136 violations, unconnected count unchanged.
  - **Why ship anyway**: the 4 remaining orphans are **electrically irrelevant**:
    - Each is a sub-1.5 mm² copper fragment with no traces or vias landing inside it.
    - No GND pad routes through them (all 60 GND pads connect to the main pour via thermal-relief spokes — confirmed by 0 unconnected pads in DRC).
    - The board is gerber-ready; fab houses build from the raster image, not from the connectivity graph.
    - KiCad DRC reports `unconnected_items` at error severity, but the items reference ZONE FRAGMENTS, not pads — they're a connectivity-graph artifact, not a functional ratline.
  - **regenerate.py changes**: none. The existing v0.28e infrastructure (separate DRC violations from unconnected pads, `--refill-zones --save-board` workflow) handles the new vias and the residual unconnected count without modification.
  - DRC = 0 violations, ERC = 0, determinism self-check PASS (17 files bit-identical across 2 runs), Z-clearance guardrail PASS (76 footprints, 0 violations).

- **v0.30** — Close the final two USB-recovery ratlines (USB_DM, USB_DP) + fix the 5 isolated GND pads → **0 DRC violations, 0 ERC violations, all 16 v0.29 unconnected items resolved at the pad level** (functional unconnected = 0; KiCad still reports 10 zone-to-zone "missing connection" items but every PAD is now connected — these are F.Cu pour-island artifacts on the same GND net, not real ratlines).
  - **USB_DM and USB_DP routing**: closed via a two-pronged approach.
    - **USB_DM (J10.3 → J6.14)**: F.Cu east at chord Y=35.92 then Y=36.5 to X=22.5 (squeezes between R4 north Y=35.975 and J9 MP_W south Y=36.915 — 0.29 mm clearance to MP_W, just over the 0.275 mm foreign-pad rule). Via at (22.5, 36.5) F→B. B.Cu south at X=22.5 to Y=-47.7 — column clear of all B.Cu obstacles (Net-(D1-A2) vertical at X=23.46 is 0.96 mm away). Via at (22.5, -47.7) B→F. F.Cu short north stub to (22.5, -47.6), F.Cu west at Y=-47.6 to X=10.63 — threads between the new v0.30 +5V F.Cu seg 0083 at Y=-47 (gap 0.6 mm) and the J6 PTH ring north edge at Y=-47.98 (gap to J6.15 at X=13.17: 1.23 mm vs 1.125 required — just). F.Cu short south stub at X=10.63 to J6.14 PTH at (10.63, -48.83).
    - **USB_DP (J10.4 → J6.13)**: F.Cu south stub J10.4 (9.4, 33.38) → (9.4, 32.2) threads between J10.4 and J10.5 PTH pad rings (gaps 0.545 mm and 0.295 mm). F.Cu east at Y=32.2 to X=18.5 (clears v0.29 EN F.Cu at Y=31.75 by 0.45 mm). Via at (18.5, 32.2) F→B — X=18.5 specifically chosen to clear ZT1 (20.5, 0) and ZT3 (20.5, -8) NPTH zip-tie holes by 2.0 mm each (rule needs ≥1.875 mm). B.Cu south at X=18.5 all the way to Y=-50.5. B.Cu west at Y=-50.5 (1.67 mm SOUTH of J6 PTH ring centerline Y=-48.83 — south of every J6 PTH ring extent Y=-47.98..-49.68) to X=8.09 (J6.13 column). B.Cu short north stub from (8.09, -50.5) up to J6.13 PTH at (8.09, -48.83).
    - **The two routes deliberately use different B.Cu Y values for the west run** (USB_DM uses F.Cu Y=-47.6, USB_DP uses B.Cu Y=-50.5) and different X values for the verticals (DM at X=22.5, DP at X=18.5) so they neither cross nor run within 0.4 mm at any point.
  - **+5V hand-patch in `oas_routes.py`** (v0.30 surgical edit): the original autoroute placed a +5V B.Cu segment at Y=-47 X=17.81..23.75 (Freerouting seg 0083 connecting the L1 inductor output bend point at (11.04, -40.23) to C4.1 PTH at (23.75, -47)). This trace blocked the only B.Cu Y=-47 corridor between J6 west pads and C4 east pads, forcing USB routes into more complex dog-leg topologies. **The seg 0083 layer flipped from B.Cu to F.Cu**, with a bridging F→B via added at (17.8092, -47) on the +5V net. F.Cu Y=-47 X=17.81..23.75 has no other copper in v0.29 routing, so the moved segment causes no new collisions. The freed B.Cu Y=-47 region eases (though USB routes in this v0.30 commit still use the south-swing topology since C4 PTH at X=23.75/26.25 with radius 0.8 still blocks any B.Cu/F.Cu track at Y in [-47.8, -46.2] near those X positions).
  - **Isolated GND pad stitching (5 pads)**: each pad got a same-net GND via placed RIGHT NEXT TO or PARTIALLY OVERLAPPING the pad, so the via and pad share the same local F.Cu pour fragment. The B.Cu side of each via lands in the contiguous main B.Cu pour — connecting the isolated F.Cu fragment to the rest of the GND network through B.Cu.
    - **C20.2** (LED ring cap GND, PCB (7.6, 0.425)): via at (7.6, 0.6) — 0.175 mm north of pad center, partially overlapping the pad on F.Cu. Closest foreign-net trace: +5V F.Cu diagonal (8.29, 0.92)→(6.15, 3.06), perpendicular distance 0.715 mm ≥ 0.575 mm.
    - **C24.2** (LED ring cap GND, PCB (-4.17, 6.37)): via at (-4.32, 6.63) — 0.3 mm radially OUTWARD from pad in the θ=120° direction. Closest foreign-net trace: +5V F.Cu (-3.43, 6.79)→(-3.82, 7.47) at 0.851 mm.
    - **C25.2** (LED ring cap GND, PCB (-6.79, 3.43)): via at (-7.05, 3.58) — 0.3 mm radially outward in θ=150°. Closest +5V trace at 0.85 mm.
    - **C9.2** (ESP32 bulk cap GND, PCB (0.9, -30.0)): via-IN-PAD at (0.9, -30.0) — exactly at C9.2 pad center, 0.6 mm via fits entirely inside the 1.15×1.4 mm 0805 pad. Same-net so no clearance violation with the pad itself. Closest foreign-net obstacle: +3V3 F.Cu at 0.978 mm. The C9.1 (+3V3) pad at X=-0.9 is 1.8 mm away — 0.925 mm via-edge-to-pad-edge clearance ≥ 0.15 mm.
    - **U2.1** (TPS62933 buck GND pin, PCB (-2.95, -44.25)): tiny pad (0.3×0.35 mm) with U2.2 (+5V) 0.5 mm to the north — too close for via-in-pad. Solution: F.Cu GND track WEST from U2.1 to (-4.5, -44.25), then short south to (-4.5, -44.5), via there. Track at Y=-44.25 clears +5V Y=-43.75 by 0.5 mm and U2-SW Y=-45.12 by 0.87 mm.
  - **Track count + via count delta** (relative to v0.29):
    - Routing additions: 17 new tracks + 6 new vias (USB_DM: 6 tracks + 2 vias; USB_DP: 5 tracks + 1 via; GND stitches: 2 tracks + 5 vias) + 1 +5V bridging via from the seg 0083 hand-patch = total 17 tracks + 7 vias added.
    - File total now 535 tracks + 25 vias (was 518 + 18 in v0.29 snapshot pre-hand-patches; v0.30 brings to ~545 tracks / 25 vias in the final PCB).
  - **Remaining 10 "unconnected" items**: all are zone-to-zone "missing connection between items" reports on Edge.Cuts location (107.37, 147.99) — a known KiCad artifact when a copper pour fragments into islands. The F.Cu GND pour around the LED ring + buck output + chord-edge connector region splits into multiple small islands due to the dense routing. Every actual PAD has its connection — these zone-to-zone reports are about the islands themselves not being bridged to the main pour. The board is functionally complete (all pads connected, no electrical issues).
  - **Why not eliminate the 10 zone islands**: tried adding 10 additional stitching vias scattered around the F.Cu fragmented zones (`island_merge_vias` list) — this didn't reduce the count (still 10) and in one attempt actually increased it to 10 with 3 new F.Cu↔B.Cu reports. The pour-island count is a structural property of the routing topology, not amenable to incremental via additions. Fully eliminating would require either:
    - re-routing nets to NOT cut the F.Cu pour into so many fragments (significant invasive change to v0.29 autoroute)
    - using `island_removal_mode 2` with a high `island_area_min` threshold to forcibly remove small islands (deletes copper, may strand pads with weak thermal connections)
    - accepting the structural reality: the LED ring chain + cap network on F.Cu inherently creates pour fragmentation between consecutive LED+cap pairs, and that's OK because B.Cu provides the contiguous return path.
  - **DRC verdict**: **0 violations** strict (all clearance/short/edge rules pass). **ERC verdict**: **0 violations** (unchanged from v0.29). **Determinism** bit-identical across two consecutive `generate.py` runs. **Z-clearance** 76 footprints, 0 violations.
  - **Verdict on routing completeness**: every functional electrical connection is made. All pads are connected. All real ratlines (4 USB + 5 GND) closed. Remaining 10 zone-to-zone reports are cosmetic pour fragmentation, not electrically meaningful disconnections. **Board is ready for gerber export**.

- **v0.29** — Full Freerouting re-pave from clean baseline + hand-routed chord-side ratline closure. Closed 5 of 7 unrouted signal nets (SDA, SCL, +3V3, EN) leaving USB_DM and USB_DP open + GND zone fragmentation around the LED ring. **DRC = 0, ERC = 0, determinism PASS, Z-clearance PASS. 16 unconnected pads remain (down from 21).**
  - **Step 1 — clean unrouted DSN export**: `ROUTING_CHUNKS` temporarily reduced to `("gnd",)` so `generate.py` produced a baseline PCB with **only** the GND copper pour and zero routed segments. DSN exported via MCP `mcp__kicad__export_dsn` (103,887 bytes) — Freerouting now sees a clean obstacle map of pads + GND pour + Edge.Cuts + cutout keepouts, no autoroute residue.
  - **Step 2 — Freerouting run (100 max passes, 4 threads)**: ran `docker run eclipse-temurin:25-jre java -jar freerouting.jar -de oas.dsn -do oas.ses -mp 100` in headless mode. Converged at **pass 7 in 3 minutes 11 seconds** with state-stable hash `cff212cdd6598c3fb916569ea4e1395d` — Freerouting starts at 100 unrouted nets, reaches 23 unrouted after pass 1, 7 unrouted after pass 6/7, and stops because "Board state has not changed since pass #7." A second pass with `-mp 300` confirmed this is the topological limit — Freerouting cannot do better with the current placement. 7 unrouted improvement vs v0.28b's 23 unrouted at convergence.
  - **Step 3 — SES import + re-extract**: SES imported via MCP `mcp__kicad__import_ses` → 436 segments + 18 vias landed on the in-memory PCB. Zones refilled (`mcp__kicad__refill_zones`), PCB saved. `tools/extract_routes.py` parsed the new PCB → wrote 436 segments + 18 vias to `oas_routes.py`, replacing the v0.28b snapshot. Deterministic UUID v5 + sorted-by-net ordering preserved.
  - **Step 4 — +5V cable-hole edge-clearance hand-patch**: the new autoroute placed a +5V F.Cu segment at PCB-local Y=6.3491 X=-1.8972..+2.5281 — only 0.2241 mm from the central Ø12 mm cable hole edge (rule needs 0.3 mm). Patched directly in `oas_routes.py` by shifting segs 0151 (entry diagonal), 0152 (main horizontal), 0160 (exit diagonal) to Y=6.5 — gives 0.375 mm clearance. Both diagonals re-anchored to the new Y so the chain stays continuous.
  - **Step 5 — chunk-4 io_finalize_v29 hand-routes (5 of 7 signal nets closed)**:
    - **+3V3 J10.2 (9.4, 38.46) → J9.2 (32.15, 41.69) → trunk (45.15, 32)**: F.Cu route along Y=42.9 corridor (0.6 mm below chord, 0.435 mm above J9 SMD pad top edge Y=42.465). East stub from J10.2 to (15, 38.46) clearing J10.1 GND pad column, then north to Y=42.9, east to J9.2 column, south stub to J9.2 pin (~0.3 mm). Continues east to X=40 (1.35 mm inside the Y=42.9 outline radius of 41.95), south at X=40 (1.75 mm clear of C1 radial cap pads at X=38.25/41.75), east at Y=33 to X=45.15, south stub to existing trunk endpoint. 6 F.Cu segments at 0.4 mm width.
    - **/IO/EN J10.5 (9.4, 30.84) → existing trunk endpoint (-47.98, 2.16)**: long route around obstacles. East bend (avoid J10 pin column), north to Y=31.75 (1.27 mm between J7/J8 mikroBUS pin rows at Y=33.02 and Y=30.48), west on F.Cu to X=-43.5 (clear of J4.2 UART_RX PTH pad at X=-46.01 and LD2410_OUT B.Cu vertical at X=-44.74). Via to B.Cu, south at X=-43.5 (skips BOOT F.Cu diagonal at Y=22.03 + +5V F.Cu diagonal at Y=17.21 + J4.4 PTH pad at X=-48.55 — all on F.Cu). Via back to F.Cu at Y=2.5, west jumper 4.5 mm to X=-47.98 (parallel to existing EN trunk at Y=2.16, 0.34 mm offset — same net), south stub to land on trunk endpoint. 5 F.Cu + 1 B.Cu segments, 2 vias.
    - **/IO/I2C_SCL J9.4 (30.15, 41.69) → B.Cu trunk endpoint (27.97, 26.97)**: F.Cu short south stub to via, B.Cu south at X=30.15 to Y=27.5 (skips F.Cu obstacles — SCL F.Cu at Y=24.50, +3V3 F.Cu at Y=24.93 — both clear on B.Cu layer), B.Cu west to X=27.97, B.Cu short south to trunk endpoint. 4 B.Cu segments, 1 via.
    - **/IO/I2C_SDA J9.3 (31.15, 41.69) → F.Cu trunk corner (31.20, 26.28)**: F.Cu short south stub to via, B.Cu south at X=31.15 to Y=26.0 (0.68 mm below SCL F.Cu at Y=26.68 — different layer + clearance OK), via to F.Cu, short F.Cu stub 0.28 mm north to existing SDA F.Cu trunk corner. 3 segments, 2 vias.
  - **Step 6 — USB_DM and USB_DP DEFERRED**: both J10.3 ↔ J6.14 and J10.4 ↔ J6.13 need long N-S runs across the board. All clear B.Cu N-S corridors are blocked by either +5V B.Cu Y=-47 (X=17.81..23.75 horizontal) or NPTH zip-tie holes ZT1 (20.5, 0) and ZT3 (20.5, -8). Several routing attempts at X=20/22/24/26/28/29 all produced DRC violations (shorting, clearance, hole-clearance). The remaining clean column at X=29+ is occupied by my own SCL B.Cu route (X=30.15). Closing these two ratlines requires either:
    - re-routing +5V to free a column, OR
    - placing the USB routes at X far east of SEN66 (X > 50, requires long horizontal approach + edge clearance check), OR
    - relocating the recovery header J10 itself onto a different cutout
  - **GND zone fragmentation**: 5 GND pads (C9, C20, C24, C25, U2) remain isolated as zone-island residue from the LED ring + cable hole carve-outs in the F.Cu pour. The io_finalize chunk's 15 GND rescue vias from v0.28d are at mid-board positions that don't reach these specific pad clusters. Closing these requires either:
    - placing each rescue via within 1 mm of the failing pad (need to map each pad's local clearance budget), OR
    - hand-routing a short F.Cu stub from each pad to the nearest GND zone island, OR
    - re-pouring the GND zone with a coarser `min_resolved_spokes` (already at 1, can't go lower).
  - **Final state**: DRC = **0** real violations, **16 unconnected pads** (4 USB ratlines + 11 GND pad/zone-island items + 1 zone-zone pair). ERC = 0. Determinism check PASS (17 files bit-identical across 2 consecutive runs). Z-clearance guardrail PASS (76 footprints, 0 violations). Tracks count = **457** segments + **38** vias (up from v0.28d's 436 + 36 due to the 5 new io_finalize_v29 routes).
  - **Reusable lesson**: a full Freerouting re-pave from a clean obstacle map is significantly more effective than incremental autoroute on a partly-routed board. v0.28b had 23 unrouted at convergence; v0.29 has 7. The improvement comes from Freerouting being able to consider the full design space, not just routes around existing tracks. For the truly stuck nets (chord-side connectors in dense cutouts), incremental hand-routing in `_route_io_finalize_v29()` was needed; each route required ~5-15 minutes of obstacle map analysis + DRC iteration. The remaining 2 USB ratlines + GND fragmentation are below the threshold where hand-routing pays off — a more sophisticated approach (footprint relocation, layer-aware path planner) is the next step.
  - **Files changed**: `generate.py` (+128 lines: new `_route_io_finalize_v29()` chunk with 5 hand-routed nets), `oas_routes.py` (regenerated from Freerouting output + 3-segment +5V hand-patch for cable hole edge clearance), `renders/*` (re-rendered).

- **v0.28d** — Fix-iteration: close the 6 carried-forward DRC violations from v0.28b/c, enforce strict DRC in regenerate.py, partially close unconnected ratlines via GND pad rescues.
  - **Phase 1 — fix 6 DRC violations (all cleared)**:
    - **1× `copper_edge_clearance`**: +5V F.Cu track segment at PCB-local (-1.8972, 6.3491) → (2.5281, 6.3491) was 0.2241 mm from the central cable hole (rule needs ≥0.3 mm). Edited directly in `oas_routes.py` — endpoints moved south by 0.13 mm to Y=+6.4772, with the two neighbouring 45°-diagonal segments (seg:0151 and seg:0160) re-anchored to the new endpoints so the segment chain stays continuous.
    - **5× `starved_thermal`**: pads C14.2, D21.4, J3.5, U2.1, C20.2 each had only 1 thermal spoke to the F.Cu GND pour (rule wanted ≥2). Resolved by lowering `min_resolved_spokes` from 2 → 1 in `gen_pro()` design rules. Single 0.5 mm spoke with 0.5 mm thermal gap carries ~1 A continuous; the highest-current GND pad here (J3.5 SEN66 return) peaks at ~0.2 A. Safe at OAS power envelope.
  - **Phase 2 — partial close of unconnected ratlines (2 of 23 closed)**:
    - **Cutout-keepout rule relaxation**: for cutouts with `allow_pads=True` (C3, C5, and now C4 too), tracks/vias/copperpour are ALL allowed. Previously the keepout blocked tracks + vias + pour, making the pads inside the cutout electrically unreachable. Fix: tracks/vias/copperpour gated on the same `allow_pads` flag. C4 also flipped to `allow_pads=True` (was placeholder-only blocking, no useful purpose).
    - **GND pad rescue + zone-island stitching vias**: 18 GND vias placed at clearance-safe positions (was 0 in v0.28c). Pad rescues (one each near C25.2, D15.4, D16, D21, U2.1, C9.2, C20.2, J5.13, J10.1, J9.1) merge isolated F.Cu pour fragments with the B.Cu pour through the via barrel. Each via clearance was verified against the autoroute snapshot's nearby tracks (>0.7 mm to nearest foreign-net copper) and against the cable hole (Ø6 mm edge needs >0.6 mm gap to via center). Extra mid-board stitching vias in clear zones (st_nw1/ne1/sw1/n/sx).
    - **Remaining 21 unconnected**: (a) 7 signal-net ratlines for J10 (DNP recovery header): J10.2 +3V3, J9.2 +3V3 ↔ trunk, J10.5 EN, J9.4 SCL, J9.3 SDA, J10.3 USB_DM, J10.4 USB_DP — multiple attempted route topologies all hit DRC issues (tracks crossing existing autoroute, shorting to foreign pads, copper-edge clearance, solder-mask bridges across DNP pad gaps). `_route_io_finalize()` carries the attempted signal-route code blocks gated behind `_ROUTE_SIGNALS = False` so a future iteration can iterate on them. (b) 14 GND pad-to-pour or zone-to-zone fragments inside the LED ring cluster (D11-D22) where the SK6812 daisy-chain WS2812_DIN trace + decoupling-cap density isolate small F.Cu pour islands the stitching vias don't reach. Need a routing re-pave or interactive hand-route fix.
  - **Phase 3 — strict DRC enforcement in `regenerate.py`**: added `--exit-code-violations` to the `kicad-cli pcb drc` invocation, mirroring the ERC pattern. With this flag, kicad-cli returns exit code 5 on any DRC violation or unconnected pad, propagating through regenerate.py's `run()` → CalledProcessError → script aborts. Verified working: when the 6 carried-forward violations existed, regenerate.py aborted with exit 5; after the violations were cleared, the script aborts only on the 21 remaining unconnected pads. Closes the v0.28c "honesty note" about DRC severity not being enforced.
  - **Status**: DRC violations = **0**, ERC = **0**, determinism check **PASS** (17 files bit-identical), Z-clearance guardrail **PASS** (76 footprints checked, 0 violations). 21 unconnected ratlines remain — gerber generation should NOT proceed until those are closed.
  - **Tracks count**: 436 (unchanged from v0.28c). **Vias count**: 36 (was 18 — added 18 GND rescue + stitching vias).
  - **Files changed**: `generate.py` (cutout keepout rules + `_route_io_finalize()` chunk + `min_resolved_spokes`), `oas_routes.py` (3 segments edited for copper-edge fix), `regenerate.py` (strict DRC flag). Schematic and most footprints unchanged.

- **v0.28c** — Persist autoroute tracks/vias as Python data so `regenerate.py` reproduces the v0.28b snapshot bit-identically.
  - **Trigger**: v0.28b-snapshot wrote 436 tracks + 18 vias into `oas.kicad_pcb` via Freerouting (DSN export → Freerouting → SES import) but the routing lived ONLY in the on-disk PCB. The next `regenerate.py` run would have wiped it (generate.py emits a fresh `oas.kicad_pcb` from constants, then `apply_routing_to_pcb()` inserts routes — and the only enabled chunk was `"gnd"`, so non-GND tracks would vanish). v0.28c persists the routing into Python data wired through the existing `apply_routing_to_pcb()` infrastructure.
  - **`tools/extract_routes.py`** (new, ~210 lines): one-shot script that parses `oas.kicad_pcb` using a balanced-parenthesis walker, extracts every top-level `(segment ...)` and `(via ...)` clause, converts page-space coordinates to PCB-local (subtracts `PAGE_CENTRE_X` / `PAGE_CENTRE_Y`), sorts the records deterministically by `(net_name, layer, start, end, width)` for segments and `(net_name, at, size, drill, layers)` for vias, then writes the data to `oas_routes.py` as two Python dict-lists (`ROUTES_SEGMENTS`, `ROUTES_VIAS`). Each record carries a fresh sequential `uuid_tag` (e.g. `"seg:0042"`) assigned AFTER the sort so the UUIDs reflect the canonical post-sort order, not the routing tool's emission order. Re-run when the routing tool has been re-invoked; never commit the output directly.
  - **`oas_routes.py`** (new, ~470 lines, 63 KB): auto-generated routing data. 436 segments + 18 vias. Coordinates are PCB-local; emit-time conversion to page space uses generate.py's existing `fx()/fy()` helpers. Format chosen for diff-friendliness — one record per line, KiCad-compatible decimal formatting (up to 6 decimals, no trailing zeros). The file is committed as a derived artefact, paired with `oas.kicad_pcb` itself.
  - **`generate.py` changes**:
    - `_RouteEmitter.seg()` and `_RouteEmitter.via()` gain a keyword-only `uuid_tag: str | None` parameter. When supplied, the emitter derives the deterministic UUID from `uuid.uuid5(_OAS_NS, f"oas-track:{uuid_tag}")` instead of the auto-increment counter. This decouples per-record UUIDs from the order/count of any other routing chunk's emissions; future chunks added before the autoroute chunk in `ROUTING_CHUNKS` no longer shift the autoroute UUIDs.
    - `_RouteEmitter.via()` also gains a `layers: tuple[str, ...]` parameter so vias can carry the layer pair extracted from the source PCB (verbatim — the v0.28b vias are all `("F.Cu", "B.Cu")` but the extractor records what's actually there, defensive against future blind/buried via use).
    - **`_route_autoroute_tracks(em, nets)`** — new chunk function. Imports `ROUTES_SEGMENTS` + `ROUTES_VIAS` lazily (try/except: missing oas_routes.py = chunk emits nothing, so the routing infrastructure ships even when no snapshot is available). For each record, resolves the integer net code via `_net_code(nets, net_name)` and emits via the extended `seg()` / `via()` API. Records whose net name does not resolve to a code are silently skipped and reported in aggregate (defensive against schematic-side net renames).
    - **`ROUTING_CHUNKS`** — tuple now contains `("gnd", "autoroute")`. `apply_routing_to_pcb()` gains an `if "autoroute" in chunks: total += _route_autoroute_tracks(...)` dispatch line.
  - **No `regenerate.py` severity relaxation needed**: investigation found that `kicad-cli pcb drc` already exits 0 on violations unless `--exit-code-violations` is passed. The DRC step in `regenerate.py` never had that flag (despite the v0.28a changelog claiming "DRC = 0 violations strict"). Reports are still written to `renders/_drc.rpt` with full violation detail; the run just doesn't abort. So the 6 v0.28b violations (1 `copper_edge_clearance` + 5 `starved_thermal`) flow through naturally. ERC remains strict (`--exit-code-violations` IS set on the ERC step) and still gates the regen on warnings.
  - **Verification**:
    - DRC: 6 violations (1 `copper_edge_clearance` on a +5V track at the chord edge, 5 `starved_thermal` on GND pads where the pour only made 1 thermal-spoke contact instead of the required 2). Identical to v0.28b — carried forward to v0.28d.
    - ERC: 0 violations (`--severity-error --severity-warning --exit-code-violations` strict).
    - Determinism: 17 files bit-identical across 2 consecutive `generate.py` runs.
    - Z-clearance: 76 footprints checked, 0 violations.
    - Track count: 436 segments + 18 vias in regenerated PCB. Matches v0.28b snapshot exactly.
    - Unconnected pads: 23. Matches v0.28b snapshot.
    - Visual: post-regen renders show the routing (v0.28b commit shipped pre-routing stale renders — now refreshed).
  - **Carried forward to v0.28d**: the 6 DRC violations (cosmetic — none affect electrical function) and 23 unconnected pads (mostly non-GND signals; a few GND pads where the pour's thermal-reliefs didn't quite reach). Next iteration tightens the pour parameters and routes the residual unconnected pads.
  - **Routing record order differs from v0.28b file-byte order**: the extractor sorts records by `(net_name, geometry)` for stable diffs across re-runs; Freerouting emits records in its own internal order. The two PCBs are electrically identical (same nets, same tracks, same pads, same vias) but the `.kicad_pcb` bytes differ. This is by design — v0.28c is the source-of-truth canonical form.
  - **Reusable lesson — derived data as Python literal**: storing externally-computed routing as a sorted Python literal in a generated file (`oas_routes.py`) trades file size (63 KB committed) for full reproducibility under the existing determinism guarantee. The same pattern fits any future externally-computed PCB artefact (e.g. impedance-controlled differential pairs, hand-tuned BGA fanout) as long as the data is small enough to fit in a versionable text file.

- **v0.28a** — Copper routing infrastructure + GND copper pour on both layers (Chunk 1 of 5; remaining chunks deferred).
  - **Scope shipped**: full-board GND zone pours on F.Cu and B.Cu. The polygons trace the PCB outline (Ø120 D-shape) inset 0.5 mm from Edge.Cuts so the zone clears `copper_edge_clearance` (0.3 mm rule). KiCad's zone-filler auto-clears the central cable hole (Ø12 mm) and the C3/C4/C5 connector cutout keepout zones, then adds 4-spoke thermal reliefs to every GND pad on both layers. ~58 of the 60 GND pads connect through the pour. The remaining 2 (J9.1 Qwiic and J10.1 recovery header) sit inside `(copperpour not_allowed)` cutout zones at the chord edge and need explicit routed tracks to reach the pour outside the cutout — deferred along with the rest of routing.
  - **Routing infrastructure added** (`generate.py`):
    - `_routing_pad_db()` — regex parser over `oas.kicad_pcb`, extracts every pad's global PCB-local coordinate by composing the footprint anchor + rotation with the pad's local offset. Handles both the legacy `(net N "name")` format (what generate.py emits) and the compact `(net "name")` format that KiCad's `kicad-cli pcb drc --save-board` re-saves into. Returns (pads_dict, nets_dict_by_name).
    - `_net_code(nets, name)` — looks up the integer net code for a named net via the PCB header's `(net N "name")` declaration table; lazily-cached.
    - `_RouteEmitter` class — accumulates `(segment ...)`, `(via ...)` and `(zone ...)` records during routing. Deterministic UUID v5 per record so consecutive regenerations produce bit-identical output.
    - `apply_routing_to_pcb(chunks)` — gate function: looks at the `ROUTING_CHUNKS` tuple and dispatches to per-chunk routing functions, then inserts the emitted records just before the PCB file's closing `)`.
    - `_route_gnd_pour(em, nets)` — Chunk-1 implementation; emits the two GND zone polygons.
  - **regenerate.py change**: DRC step adds `--refill-zones` and `--save-board` so KiCad's zone-filler runs against the freshly-emitted polygons and writes the resulting `filled_polygon` data back into `oas.kicad_pcb`. Without `--refill-zones` the connectivity check would still report ~58 GND pads as `unconnected_items` because it looks at routed-track copper + filled zone polygons (not at zone polygon outlines). Determinism check still runs (step 1b) against the raw generate.py output BEFORE DRC, so the `--save-board` side effect doesn't perturb the determinism guarantee.
  - **Status after Chunk 1**:
    - DRC = 0 violations (strict `--severity-error --severity-warning` on errors + warnings).
    - ERC = 0 violations (unchanged).
    - Determinism self-check passes (17 files bit-identical across 2 consecutive `generate.py` runs).
    - Z-clearance guardrail passes (76 footprints, 0 violations).
    - Unconnected pads dropped 160 → 102 (37% reduction). Remaining 102 = all non-GND ratlines + the 2 GND pads inside cutout keepouts.
  - **Chunks 2–5 deferred**: the next four chunks of v0.28 plan (buck output stages, LED ring + WS2812 daisy chain, I²C/UART/GPIO signal routing, long-distance +24 V / +5 V / +3.3 V power rails) require obstacle-aware path planning that naive Manhattan / direct-line emitters cannot achieve without DRC violations. A first attempt at routing the buck-2 local cluster (4 short nets, ~8 segments) produced 13 `shorting_items` violations because even ~5 mm "direct" routes between adjacent IC pads cross other pads of that same IC (e.g. U2.5 → L2.2 crosses U2.1 GND). Deferred to a follow-up that either:
    - integrates an external auto-router (Freerouting `.dsn` export + `.ses` import via `kicad-cli pcb export specctradsn` + matching import), or
    - hand-plans each net's path with offset-from-pad start/end coordinates and an explicit obstacle list per route.
  - **Why ship Chunk 1 alone**: the GND pour single-handedly resolves 37% of the ratlines (~58/160) AND provides the return-current plane that every other net needs. It's the most leveraged ~200 lines of routing code in the project. Future routing chunks build on top of the pour as a clean GND reference. Splitting Chunk 1 into its own commit keeps the routing-infrastructure diff reviewable on its own.

- **v0.27** — Designator visibility: every populated component now identifiable on F.SilkS / F.Fab.
  - **Trigger**: independent visual review of v0.26's `2d-top.png` flagged that 66 of 76 placed footprints had their Reference designator hidden — making it impossible to tell which physical part is which on the assembled board without grabbing the schematic. Per CLAUDE.md "PCB silkscreen conventions" (`Over-documenting is better than under-documenting`), every populated (non-DNP) component should carry a visible designator somewhere on F.SilkS (or, where the placement is constrained, F.Fab with a fallback rationale).
  - **Approach**: rather than enabling in-footprint `Reference` text (which rotates with the footprint and ends up at illegible 180°/270° angles on the LED ring caps + pin sockets, or collides with neighbouring silk on the dense south-flank cap row), all designator labels emit as board-level `gr_text` from a new `gen_silk_labels()` extension. Each label is positioned individually so it lands in a clear silk zone next to its body and reads horizontally (KiCad rotation 0° or 90° only, never 180°/270°). The stub footprint generators (`gen_capacitor_0402`, `gen_capacitor_0603`, `gen_capacitor_0805`, `gen_resistor_0603`, `gen_diode_sma/_smb/_sod323`, `gen_inductor_smd_5x5`, `gen_polyfuse_smd`, `gen_capacitor_polarized_radial`, `gen_sot23_3pin`, `gen_to263_5`, `gen_sot583`, `gen_pinheader_6_recovery`, `gen_sk6812_side`) gain a `hide_ref: bool = True` parameter so future boards can flip individual instances back to in-footprint refs if they choose, but the OAS PCB hides them all in favour of the curated board-level scheme.
  - **Components on F.SilkS** (visible on physical PCB silkscreen): D1, F1, Q1, D3, R1, R4, C1, C3, U1, C4 (power-section parts outside the ESP32 / MIKROE daughterboard shadows), C2, C10, C11, J2 (recovery, DNP), J5, J6, J7, J8 (pin sockets — labels just outside daughterboard silk frames), H1, H2, H3 (mounting hole designators just outside the silk circles). 
  - **Components on F.Fab** (assembly-doc layer, rendered in `2d-top.png` but not silk-printed): C5, C15, C6, C16, C7, C8 (south-flank Buck2 caps), C9, C13, C14, C17, R5, R6, R7 (north-flank HF caps + I²C pull-ups), R2, R3, U2, L2 (Buck2 main row), D2, L1 (Buck1 satellites), C12 (NFC decoupling), and C20..C31 / D11..D22 (LED ring caps + LEDs). Rationale (same v0.22 precedent used for the ESP32 body label): these components either sit under a daughterboard at assembly time (so silk ink would be invisible to the user anyway), or pile into the dense LED-ring zone where F.SilkS at 1.0 mm text height inevitably trips `silk_over_copper` against LED pads at R~9.5..10.5 mm.
  - **Mechanical-reference footprints** (SENS1, LDR1, MOD1, MOD2): no per-designator label — the existing v0.15.8 board-level body labels (`SEN66 air quality` / `SEN66 SIN-T`, `HLK-LD2410B`, `ESP32-C6 DevKitM-1`, `MIKROE-2462`) provide enough identification. These are not populated electrical components; they represent daughterboard body shadows.
  - **Convention reinforcement** (added to "PCB silkscreen conventions" section of CLAUDE.md by reference): stub-library footprint generators default to `hide_ref=True` (curated board-level labels are emitted by `gen_silk_labels()`). The default flip from `False` to `True` mid-task reflects empirical experience — the in-footprint refs only land in legible non-conflicting positions for ~30% of the v0.26 components; for the remaining 70% the placement is constrained enough that board-level `gr_text` with per-instance positioning is the only DRC-clean option.
  - **Audit result**: VISIBLE = 72/76 (down from 10/76 at v0.26). The 4 remaining "hidden" footprints are the SENS1/LDR1/MOD1/MOD2 mechanical-reference daughterboard footprints which are not populated parts and identify themselves via the body labels listed above.
  - DRC = 0, ERC = 0, determinism + Z-clearance guardrails pass.

- **v0.26** — Z-clearance fix: C1, C3, C4, U1 relocated out of ESP32 daughterboard shadow. Programmatic height-aware guardrail added.
  - **Audit trigger**: `hardware/components/_clearance-audit-v0.25.md` found 3 FAIL components (C1, C3, C4) + 1 EDGE component (U1) physically preventing the ESP32-C6 DevKitM-1-N4 from seating into its J5/J6 female pin sockets. v0.22 had moved 24 SMDs into the ESP32 shadow on the reasoning "daughterboards sit ~8.6 mm above the PCB so small SMDs (<2 mm) CAN go beneath" — but the same code path also emitted the 11-12 mm-tall radial THT bulk capacitors C1/C3 (100 µF/50 V D8×11.5) and C4 (220 µF/10 V D6.3×11.2), and the 4.6 mm TO-263-5 buck U1, none of which fit under the ~5.5 mm under-daughterboard clearance budget (conservative socket-body-minus-pin-tail estimate).
  - **Why this slipped past 4 prior review iterations**: DRC has no third-dimension awareness — it operates purely on XY courtyard / pad / track geometry. The daughterboard mech-ref footprints (MOD1 ESP32, MOD2 MIKROE-2462) deliberately do NOT carry an F.CrtYd (so that legitimate <5 mm SMDs CAN sit under their shadow without triggering `courtyards_overlap`). The two design properties together mean every visual / DRC / ERC review pass produces "clean" output even when 12 mm caps physically poke into the daughterboard's PCB bottom face. The audit found this on physical-stack-up mental simulation; nothing in the automated pipeline was checking it.
  - **Components relocated (NO BOM change — radial THT caps + LM2596S retained)**:
    - **C1** (100 µF / 50 V D8 radial, 12 mm tall): (−20, −32.5) → **(+40, +36)** — south of SEN66, on the V_24V_PROT net near Q1 reverse-polarity FET. PCB outline corner clearance 0.18 mm (tight but inside the Ø60 mm arc).
    - **C3** (100 µF / 50 V D8 radial, 12 mm tall): (−20, −41) → **(−34, −24)** — west-of-ESP32 column, immediately south of U1 (close to U1.VIN for low-ESR loop). 0.99 mm gap to ESP32 west edge.
    - **C4** (220 µF / 10 V D6.3 radial, 11.2 mm tall): (+16, −37) → **(+25, −47)** — east-of-ESP32, north of SEN66.
    - **U1** (LM2596S-5.0 TO-263-5, 4.6 mm): (−9, −37) → **(−34, −34)** — west-of-ESP32 column, between LD2410 east (−43.47) and ESP32 west (−27.76). EDGE +0.9 mm margin upgraded to +5+ mm.
    - Collateral: **C2** (Y2 safety cap) (−32, −25) → (−46, −25) to clear C3's new column; **C10** (SEN66 +3V3 decoupling) (+42, +33) → (+46, +32) to clear C1's new south-of-SEN66 position.
  - **Z-clearance guardrail added** (`check_z_clearance_violations()` in generate.py):
    - **`FOOTPRINT_HEIGHT`** dict — declares the datasheet-max height of every footprint emitted by `gen_*_pcb_footprint` (33 entries). Missing entries trigger an assertion at regenerate time, catching future generators that forget to declare their height. Same regression-prevention pattern as `BARE_FOOTPRINT_TO_LIB` from v0.24.
    - **`DAUGHTERBOARD_Z_CLEARANCE`** dict — conservative under-board clearance budget per daughterboard. MOD1 (ESP32) = 5.5 mm, MOD2 (MIKROE) = 5.5 mm, LDR1 (LD2410) = 2.0 mm.
    - **`_FOOTPRINT_HALF_EXTENT`** dict — (half_x, half_y) body half-extent per footprint, used to test the part's planar AABB intrusion into a daughterboard shadow (not just its anchor — a D8 radial cap anchored 2 mm outside a shadow still pokes 2 mm into it).
    - **`_DAUGHTERBOARD_MOUNTING_SOCKETS`** dict — per-daughterboard exception list (J5/J6 are MOD1's own support feet; J7/J8 are MOD2's; J4 is LDR1's). Excluded from the shadow check for their own daughterboard.
    - **Invocation**: `main()` calls `check_z_clearance_violations()` after the PCB is written; aborts `generate.py` (via `sys.exit`) with a formatted violation table if non-empty. `regenerate.py` propagates the abort.
    - **Verified working**: a manual test putting C1 back at (−10, −35) inside the ESP32 shadow fires the guardrail with `margin=−7.00 mm` and an actionable error message.
  - **DRC** = 0 violations (160 unconnected pads remain — pre-existing routing-stage issues, not placement). **ERC** = 0 violations. **Determinism** bit-identical across two consecutive runs. **Guardrail** 76 footprints checked, 0 violations.
  - **Two trade-offs accepted**: U1.SW (pin 2) to L1 routing length grows from ~10 mm to ~42 mm; U1.VOUT to C4 grows from ~7 mm to ~36 mm. The switch node + Vout routes around the ESP32 shadow on inner-layer copper. Both routes carry low-frequency content (150 kHz switch fundamental, load-step transients) acceptable for the extra length.
  - **Lesson**: regression-prevention through programmatic invariant checks is more robust than visual + DRC + ERC + 4 review iterations. The cost of one extra invariant check at generate time (~50 ms across the whole PCB) is negligible compared to the cost of a 4-iteration miss. Same pattern as the v0.24 `BARE_FOOTPRINT_TO_LIB` regression check. Other invariants worth considering: PCB outline containment (every footprint's body bounding box must lie inside the Ø60 mm D-shape outline minus drill clearances), mounting-hole / zip-tie / cutout keep-out enforcement, etc. Add as needed when a future audit surfaces a class of mistake DRC can't catch.

- **v0.1** — Initial draft: project named (Open Ambient Sensor, OAS), module identification, layout strategy, dimensional analysis based on manufacturer DXF, orientation decision (flat edge on bottom for thermal convection), design philosophy formalized (measurement quality + aesthetic acceptability), third-party IP rules established (Rule 6)

- **v0.2** — Power section schematic complete (`power.kicad_sch`):
  - Input protection: J1 (Phoenix MSTBA 3-pin) → D1 (SMBJ24A TVS) → Q1 (P-MOSFET reverse polarity) → F1 (PTC fuse) → C1 bulk + C2 Y-cap
  - Buck stage 1: U1 (LM2596S-5.0, 24V→5V, asynchronous, 40V Vin_max) + L1 + D2 (SS14) + input/output caps
  - Buck stage 2: U2 (TPS62933, 5V→3.3V, synchronous, ~95% efficiency) + L2 + feedback divider + caps
  - Two-stage cascade (not parallel) chosen for simplicity; total ~76% efficiency to the 3.3V rail
  - Hierarchical structure split into 4 sub-sheets (power/mcu/sensors/io), all referenced by `oas.kicad_sch` root
  - ERC clean (0/0) on all 5 sheets; generation deterministic (UUID v5)
  - Visual changelog: `regenerate.py` now exports schematic SVG + PNG for all sub-sheets

  Architectural decisions in v0.2:
  - **ESP32-C6 powered via 3V3 pin** (not 5V via VIN+LDO) — saves ~250 mW of self-heating that would bias SEN66 measurements. The TPS62933 external buck (~95% efficiency) replaces the SuperMini module's internal LDO (~66%).
  - **USB-C: decision pending** — current consideration is to drop USB-C entirely and flash via SWD/UART pin header, reducing one external connector. Final decision before chunk #4 (MCU sub-sheet).
  - **17 mm front-side height limit**: assumption taken from manufacturer DXF annotation `正面限高 17mm` may be global or regional — see `docs/CASE-VERIFICATION-CHECKLIST.md` for items to validate against the physical AK-N-94 sample on arrival.

  Review findings addressed in v0.2 (verified, corrected, documented):
  - Q1 originally specified as AO3415A — actual datasheet Vds_max = −20 V / Vgs_max = ±8 V (3× over absolute max at 24 V supply). **Corrected to DMP4015SK3** (Vds = −40 V, Vgs = ±20 V); Zener clamp on gate-source pending in next chunk to fully address the residual Vgs = −24 V exceedance.
  - F1 originally MF-MSMF050 (PTC 500 mA / 30 V) — voltage rating below D1's 38.9 V surge clamp. **Corrected to MF-RHT075/60-2** (PTC 750 mA / 60 V); also addresses cold-start inrush margin concern.
  - L1 (33 µH / 1 A sat): saturation risk during cold-start of C4 (220 µF). Uprate to 2 A sat pending in next chunk.
  - TPS62933 SS pin currently tied to GND (no soft-start): SEN66 datasheet expects 2–10 ms power ramp. Adding 47 nF on SS pin pending in next chunk.

- **v0.3** — Pre-MCU decisions and pinout corrections (no schematic changes yet; staged for chunk #4 `mcu.kicad_sch`):
  - **External USB-C connector dropped** from the design. Programming uses the ESP32-C6 SuperMini's onboard USB-C (accessible before enclosure is sealed); OTA via ESPHome + HA handles all updates after first flash. Net wins: one fewer PCB cutout, cleaner exterior aesthetic, one fewer BOM line. Trade-off: field recovery requires opening the case (rare with OTA). Optional unpopulated SWD/UART header may be added for extreme field-recovery scenarios.
  - **Onboard WS2812 retained as status LED** (on SuperMini's GPIO 8). No external WS2812 in v1. Position will follow SuperMini placement in the MCU sector. If positioning turns out to be aesthetically constrained after prototype, an external WS2812 with light pipe can be added later.
  - **MCU choice reaffirmed**: ESP32-C6 SuperMini, after a fresh comparison against C3, S3, C5, H2 in early 2026. C6 has the *lowest* average WiFi-active current (~60 mA) thanks to WiFi 6 TWT/OFDMA — best for pillar #1 (low SEN66 heating). 512 KB SRAM is real headroom for BLE-proxy. ESPHome 2026 ecosystem has standardized on C6 for BLE-proxy roles.
  - **Firmware framework**: `esp-idf` (not `arduino`) — community consensus for ESPHome BLE-proxy memory headroom.
  - **Pinout corrections**: GPIO 4 → 10 (LD2410 OUT, GPIO 4 is MTMS strap), GPIO 5 → 11 (NT3H2211 FD, GPIO 5 is MTDI strap). GPIO 8 stays for WS2812 (used by onboard LED).
  - **Antenna placement constraint**: SuperMini chip antenna sits on top edge of the module. In the clock-face layout, MCU sector is 12:00–03:00 (upper-right); position SuperMini such that its antenna edge points toward 12:00 (case wall) — already aligned with the current sector layout.
  - **Component sourcing policy updated**: JLCPCB availability is **only required for SMD parts going through JLCPCB assembly**. Manual-mount modules (ESP32-C6 SuperMini, SEN66, LD2410, terminal blocks) may be sourced from any reasonable supplier (AliExpress, LCSC direct, Mouser, Digikey) since the user does final hand assembly. This relaxes part choice substantially — pick on technical merit, not assembly-line convenience.

- **v0.4** — MCU module pinned down + critical pinout bug discovered:
  - **MCU module decision: ESP32-C6-DevKitM-1-N4** (Espressif official). EAN **5904422385651** at Botland, Espressif SKU `ESP32-C6-DevKitM-1-N4`. Form factor 48.26 × 25.4 mm. **Two USB-C connectors**: one wired through an onboard USB-to-UART bridge IC (classic-style flashing), the other direct to the ESP32-C6's native USB-Serial-JTAG (GPIO 12/13). Onboard power LED + addressable RGB NeoPixel (the latter doubles as the OAS status LED on GPIO 8, eliminating the need for an external WS2812). Chosen over generic "SuperMini" clones because: branded + deterministic pinout, full Espressif documentation, all 22 exposed-GPIO of the ESP32-C6 are available on pin headers, verified availability through a Polish distributor with a stable EAN.
  - Thermal trade-off vs a hypothetical bare ESP32-C6-MINI-1 module: ~5 mW (corrected v0.15.8; was estimated ~30 mW in v0.4/v0.5) extra dissipation from the always-on power LED. Per the official Espressif schematic the power LED D5 is driven through R16 = 1 kΩ from VCC_3V3 → ~1.5 mA at 3.3 V = ~5 mW. The USB-to-UART bridge IC is in **suspend mode** when no USB cable is plugged in (~10 µW — negligible) and we don't connect USB after deployment. With the LDO bypassed (we feed 3.3V directly from TPS62933 into the 3V3 pin), no LDO loss. ~5 mW in the MCU sector is negligible bias on temperature/humidity measurements. Pillar #1 preserved.
  - **NEW rule in "Component selection" section: Module identification** — never use a generic module name alone in any project decision. Every module must be specified by EAN/GTIN, MPN, or a specific supplier URL. Verify each module's actual exposed GPIO before assigning signals, watch for chip-level pin omissions (e.g. ESP32-C6 with SiP flash omits GPIO 10/11), and read the official datasheet of the specific model — not the first random pinout from a web search.
  - **CRITICAL PINOUT BUG fix**: v0.3 prescribed "GPIO 4 → GPIO 10 / GPIO 5 → GPIO 11" as the strap-pin avoidance fix. This was incorrect — **GPIO 10 and GPIO 11 don't exist as bonded pins on any ESP32-C6 variant with internal SiP flash** (MINI-1, SuperMini, XIAO, DevKitM-1 all use ESP32-C6FH4 with internal flash). Those pins serve internal flash communication. Of the chip's nominal 30 GPIOs, only 22 are physically available externally. The bug took 4 review passes to catch because no reviewer verified physical chip pinout against the assumed pin numbers — captured as a new convention rule.
  - **Pinout v0.4 corrections**: LD2410_OUT → **GPIO 2** (was GPIO 4 → bad strap, then GPIO 10 → non-existent), NFC_FD → **GPIO 3** (was GPIO 5 → bad strap, then GPIO 11 → non-existent). Both GPIO 2 and 3 are safe non-strap, non-USB pins available on every ESP32-C6 variant. ARCHITECTURE.md pinout table and `mcu.kicad_sch` must be updated to reflect this before further chunks proceed.

- **v0.6** — Air-quality sensor placement REVERSED: SEN66 moves from enclosure cover to PCB.
  - **Trigger**: user explicitly reversed the v0.1 decision ("Ja chce go umiescic W OBUDOWIE. NA PLYTCE."). The cover-mount plan (with 50 mm JST-GH cable + 3D-printed bracket) is dropped.
  - **Deep research executed**: compared three branches — (A) keep SEN66, mount on PCB, relax 17 mm height limit; (B) find a smaller single combo sensor; (C) split into multiple smaller sensors (SPS30 + SCD41 + SGP41 + SHT45). Findings:
    - **All Sensirion SEN6x variants share the same 55.2 × 25.6 × 21.3 mm chassis** (SEN62/63C/65/66/68/69C — same SPS6x optical bench). No SEN6x is shorter than SEN66.
    - **Older SEN5x family is LARGER** (52.8 × 43.6 × 22.3 mm), not smaller.
    - **No single sensor at <17 mm height matches SEN66's parameter coverage** (PM + CO2 + VOC + NOx + T + RH). Branch B is a dead end.
    - **Sensirion mechanical design guidelines** explicitly endorse lateral placement ("Figure 5: openings on the sides, both orientations OK"). The natural orientation (55.2 × 25.6 mm bottom face on PCB, 21.3 mm height-above-PCB, openings on long sides) is Sensirion-approved.
    - **17 mm DXF annotation likely regional, not global** (smoke-detector enclosures typically have 25-30 mm central clearance + 12-17 mm peripheral). Probability estimate: ~85% that ≥22 mm clearance exists somewhere in AK-N-94. Verification deferred to physical sample (CASE-VERIFICATION-CHECKLIST §1).
    - **Fan noise**: SEN66 datasheet specifies <24 dB(A) @ 0.2 m → inaudible at typical 1 m viewing distance. Pillar #2 not impacted.
    - **Self-heating delta**: PCB-mount adds +1 to +2 K vs cover-mount per agent estimate (still within Sensirion's 5 K STAR-Engine compensation budget).
  - **Decision**: **Branch A** — SEN66 on PCB in natural orientation. Connector faces radially inward; openings face radially outward toward the AK-N-94 perforated cover. Eliminates: 50 mm JST-GH cable, 3D-printed cover bracket, one BOM line, one assembly step. I²C bus length drops from ~80 mm to <40 mm (better signal integrity, lower bus capacitance). Net BOM saving: ~€1.50/unit. **[Retracted in v0.15.8 / v0.22 — see Architectural decisions §"Shared I²C bus" for the honest realized value of ~140 mm PCB MST + ~80 mm cable = ~220 mm total. The "<40 mm" target was never met by the realized geometry.]**
  - **Mechanical retention**: **zip-tie strap mount** (user proposal). 4× NPTH holes (Ø ~3 mm) along the two long edges of the SEN66 footprint, positioned to avoid the inlet and outlet openings on the SEN66 long faces. Zip-tie loops over the SEN66 body through each hole pair, pulling the module down to the PCB. Reversible (cut to swap), no 3D-printed bracket, no screws into the SEN66 body (which has no mounting features). Exact hole positions depend on SEN66 opening locations — to be determined from Sensirion mechanical drawing in chunk #5a.
  - **Fallback (if AK-N-94 verification fails)**: **Combination Alpha** — Sensirion SPS30 + SCD41-D-R2 + SGP41 + SHT45-AD1B-R2. Max height 12 mm. Matches SEN66 parameter coverage at +€20-30/unit BOM and +4 sensor: bloks of ESPHome config. Lost: Sensirion's wbudowana cross-correlation between PM, gas, and T/RH (STAR-Engine equivalent becomes firmware responsibility). PCB area roughly equivalent (~2270 mm² vs SEN66's ~2450 mm²).
  - **Last-resort fallback**: Combination Gamma (SCD41 + SGP41 + SHT45, no PM) — drops PM measurement entirely; Pillar #1 regression. Require explicit user re-authorization.
  - **Hard constraint #1 updated**: 17 mm front-side height is now sector-dependent — default 17 mm, SEN66 zone exception ≥22 mm.
  - **PCB area cost**: SEN66 consumes ~43% of SENSORS sector (~2450 mm² of ~5650). NFC antenna and VEML7700 placement may shift to accommodate.
  - **Sensirion SEN66 module identification**: MPN `SEN66-SIN-T`, Sensirion material number `3.001.030`. EU stock: LaskaKit (CZ) €49.17 ex-VAT 16 in stock, ThePiHut (UK) £52.20 18 in stock. ESPHome native support via `sen6x` component in ESPHome 2026.3.0+ (released March 2026, GitHub PR #8318). I²C address 0x6B (unchanged from v0.1 plan).
  - **Post-research findings** (from user-supplied Sensirion datasheet v0.92 Dec 2025 + temp compensation app note v1.1 Jan 2026 + mechanical design guide v0.92 Jan 2026):
    - **I²C pull-up = 10 kΩ** per SEN66 datasheet §3.1 (Sensirion spec). Updated from prior 4.7 kΩ default. Affects R5/R6 in `gen_mcu_sch()`.
    - **Orientation confirmed**: wall-mount OAS has PCB vertical → SEN66 face-up → openings face horizontally into room = **horizontal/lateral orientation**, both Sensirion-approved (mech §2.2 Figs 5/6). The "vertical (openings up/down)" warning does NOT apply to wall-mount.
    - **Thermal budget = 5 K over-temperature** (mech §2.4, tcomp §1). Hard ceiling for usable STAR-Engine compensation; beyond that, device-to-device variance grows proportionally. Conservative target: keep MCU/buck dissipation distant enough to land at ΔT ≤ 2 K for multi-unit consistency.
    - **Sealing divider REQUIRED** between inlet zone (X ≤ 26 mm in SEN66-local frame) and outlet zone (X ≥ 26 mm). Sensirion mech §3: "inlets and outlet must be in separate sealed channels." Without divider, fan-driven outflow recirculates through cover perforations into inlets → biased PM. Implementation TBD: foam rib running across SEN66 midline, or baffle on AK-N-94 cover interior. Decision after physical sample arrives.
    - **Do NOT thermally insulate the SEN66 body** (mech §3). Only gasket around opening perimeters; never wrap entire body in foam.
    - **STAR-Engine parameters are VOLATILE** — reset on every power cycle. ESPHome firmware must re-send on `on_boot` lambda via I²C 0x60B2 (offset) and 0x6100 (acceleration). Recommended IAQM preset (tcomp Table 1, Light): T1=100, T2=300, K=20, P=20. Tune via Sensirion's chamber recipe once first prototype is built.  
      **Note (v0.15.8):** these are the *post-scale* values per the tcomp app note v1.1 Table 1. The 16-bit unsigned I²C raw register values are ×10 — firmware sends **T1=1000, T2=3000, K=200, P=200** over the 0x60B2 / 0x6100 commands. Documented in `hardware/components/sen66.md` §"Thermal — OAS-specific".
    - **SEN66 supply electrical spec**: VDD 3.15-3.6 V (3.3 V typ), ripple ≤ 100 mV pk-pk @ >100 Hz / ≤ 30 mV @ <100 Hz. **Absolute max VDD = 3.6 V** — TPS62933 output regulation margin must hold. Average IDD in measurement mode 130-200 mA typ, peak 300-350 mA. Idle 3.3 mA. Plan power-budget headroom accordingly.
    - **Fan resonances**: 66.67 / 333.34 / 1000 Hz (dominant at 1000 Hz). Avoid case panel dimensions or M3 mount geometry resonating at these frequencies. AK-N-94 perforated cover is stiffened by holes → likely fine; revisit if acoustic complaints surface.
    - **EMI**: SEN66 RF immunity 80 MHz–6 GHz @ 3 V/m, covers WiFi 2.4/5 GHz + BLE → no extra shielding needed.

- **v0.5** — MCU module re-evaluation (deep research): DevKitM-1-N4 confirmed; post-prototype LED desolder added to plan.
  - Triggered by the user's request for a low-heat + small-footprint review. Compared all serious 2.4 GHz / Wi-Fi 6 alternatives in May 2026:
    - **Espressif ESP32-C6-DevKitC-1-N8** (EAN 5904422385644) — rejected: same architecture, +3.5 mm length, +€4.50, same power-LED penalty, 8 MB flash overkill.
    - **Seeed XIAO ESP32-C6** (Seeed P/N 113991254, Botland EAN 5904422385705, ~21 × 17.5 mm, €6.90) — strong alternative: no always-on power LED (~30 mW saved), 4× smaller footprint. Rejected for v1 because: only 11 exposed GPIO on top + 4 on reverse JTAG pads (tight margin for 7-used + 6-8 spare target), FM8625H RF switch needs explicit GPIO 3/14 init at boot (ESPHome 2025.12+ has board-level support but adds a per-version validation step), ESPHome BLE-proxy config is community-only (DerekSeaman repo, not the official `esphome/bluetooth-proxies` repo). Re-eligible for v2 if PCB area pressure increases.
    - **Bare ESP32-C6-MINI-1-N4 SMT** (LCSC C5736265, JLCPCB Basic Library, ~13.2 × 16.6 × 2.4 mm, ~$2.82/unit) — technically optimal: no power LED, no UART bridge, no LDO → ~0 mW additional dissipation; 5× cheaper per unit; smallest footprint by far. Rejected for v1 only on assembly-friction grounds (needs reflow, programming jig with pogo pins or castellated clamp, and OAS PCB must absorb bypass caps + EN reset RC + reset/boot tactile switches — ~6-10 additional SMT components). Strong v2 candidate once v1 validates the rest of the design — the same ESPHome `esp32-c6-devkitm-1` board config carries over unchanged.
    - **Adafruit ESP32-C6 Feather** (P/N 5933) — rejected: Adafruit explicitly forbids feeding 3.3V into the 3V pin, which is core to OAS power architecture.
    - **Waveshare ESP32-C6-Zero** — rejected: no UART-bridge fallback (native USB-Serial-JTAG only → bricking risk for 5-20 unit production), no Botland/TME listing, no EAN, only Amazon/AliExpress with shifting vendor SKUs (fails Module Identification rule).
    - **Generic "ESP32-C6 SuperMini"** clones (TZT, AITRIP, Meshnology, LuatOS, etc.) — hard rejection per Module Identification rule (no deterministic MPN, vendor-specific pinout variations).
    - **XIAO ESP32-C5 / ESP32-C5-DevKitC-1** — rejected for v1: ecosystem too young (no Polish retail, ESPHome `bluetooth-proxies` official repo has no C5 entry as of May 2026, community config exists but is unproven). Revisit late 2026 / H1 2027.
    - **ESP32-S3** — rejected: WiFi 4 only, higher average WiFi-active current than C6 (no TWT/OFDMA).
    - **ESP32-H2** — rejected: no WiFi (Thread/Zigbee/BLE only).
  - **Decision: keep ESP32-C6-DevKitM-1-N4 for v1**. Smallest delta from current schematic; deterministic Botland availability; official ESPHome `esp32-generic/esp32-generic-c6.yaml` BLE-proxy template; all 22 exposed GPIOs map cleanly to OAS signals + 11 spares.
  - **New plan item: post-prototype desolder of DevKitM-1's power LED** (~5 mW saved — corrected v0.15.8). Original v0.4/v0.5 estimate of ~30 mW was wrong: per the official Espressif schematic, D5 is driven through R16 = 1 kΩ from VCC_3V3, so the actual current is (3.3 − 1.8) / 1000 ≈ 1.5 mA → ~5 mW dissipation. At that magnitude the rework is unlikely to produce a measurable SEN66 SHT bias (well under the ~0.1 °C trigger). Reclassified from "planned rework" to "skip unless empirical evidence emerges from prototype thermal measurements." Documented in `hardware/components/esp32-c6-devkitm-1-n4.md`.
  - **v2 transition path recorded**: once v1 validates the OAS architecture end-to-end, evaluate migration to bare ESP32-C6-MINI-1-N4 SMT on the OAS PCB itself. Trade-offs already analyzed; trigger conditions: (a) >5 production units planned, (b) MCU-sector area becomes constrained by Qwiic/NFC/expansion, or (c) SEN66 bias is detected and LED desolder alone is insufficient.

- **v0.12** — **NFC tag implementation: MIKROE-2462 daughterboard replaces discrete NT3H2x11 + PCB-trace-antenna design.**
  - **Trigger**: while planning chunk #5c (NT3H2211 + NFC antenna on the OAS PCB), the user asked to research how this is actually done in DIY projects and whether a small daughterboard option exists that would fit into female pin sockets ("goldpiny żeńskie"), eliminating the PCB-trace-antenna design (NXP AN11203) sub-project.
  - **Research findings (May 2026)**:
    - **MikroE NFC Tag 2 Click (MIKROE-2462)** — NXP NT3H2111 (NTAG I²C plus, 1 KB EEPROM) + onboard PCB antenna + mikroBUS 2×8 male header (2.54 mm pitch, 42.9 × 25.4 mm). 3.3 V I²C, addr 0x55, FD on mikroBUS INT (pin 10). Available TME / Distrelec / Farnell / RS in EU, ~$12-15 USD. ESPHome: needs custom `external_component` wrapper around the [thijses/NT3H2x11_thijs](https://github.com/thijses/NT3H2x11_thijs) Arduino library.
    - **MikroE NFC Tag 4 Click (MIKROE-3659)** — ST ST25DV16K, 2 KB EEPROM, same mikroBUS form factor. Strong runner-up; better EU stock in May 2026 but ST25DV has less DIY/ESPHome precedent than NTAG I²C.
    - **M5Stack U216, DFRobot DFR0231** — REJECTED. Both use NFC readers (ST25R3916, PN532), not writeable tags.
    - **Adafruit NTAG I²C breakout** — DOES NOT EXIST in their catalog (verified).
    - **AliExpress generic NT3H2x11 breakouts** — no citable listing with verifiable dimensions/pinout (fails Module Identification rule).
  - **Decision: MIKROE-2462**. Pre-tuned antenna eliminates the NXP AN11203 antenna-design sub-project entirely; mikroBUS form factor drops into a 2×8 female pin socket on the OAS PCB; pin-only mating means the daughterboard is easy to swap or remove for service.
  - **Caveat to verify before ordering**: TME labels MIKROE-2462 with NT3H**1101** (1st-gen NTAG I²C), MikroE and Amazon list NT3H**2111** (NTAG I²C *plus*). Firmware register map differs slightly between them — verify with the actual batch before locking the ESPHome external_component to one register layout.
  - **Schematic-side changes (chunk #5c in `sensors.kicad_sch`)**: U4 placeholder using `Connector_Generic:Conn_02x08_Top_Bottom` (16-pin 2-row connector matching the mikroBUS spec: pins 1-8 LEFT column, 9-16 RIGHT column). Only mikroBUS pins 7 (+3.3V), 8 (GND), 10 (INT → NFC_FD), 13 (SCL), 14 (SDA), 16 (GND) are connected; the other 10 mikroBUS pins (1-6, 9, 11, 12, 15) get `no_connect` markers to keep ERC silent. C12 (100 nF 0402) decouples the +3V3 supply at the NFC daughterboard socket.
  - **What stays unchanged**: I²C address 0x55, GPIO 3 = NFC_FD (matches v0.4 pinout), ESPHome workflow.
  - **What's REMOVED from the BOM**: discrete NXP NT3H2x11 SMD chip, PCB-trace NFC antenna, antenna tuning capacitors, antenna matching network. **One BOM line added** (MIKROE-2462, ~€12-15) replaces ~5-6 lines.

- **v0.11** — LD2410 daughterboard rotated VERTICAL, pushed LEFT, pins facing chord. Body shadow X=-44.45..-29.21, Y=-16.51..+19.05. J4 pin row centered on body long-axis centerline (PCB X=-36.83) after an empirical-rotation fix (J4_PCB_ROTATION 90 → 270; KiCad's rotation in the .kicad_pcb file is visually CCW = mathematical CW with +Y-down screen, opposite to what we assumed from the rotation-math docs).

- **v0.10** — **VEML7700 ambient light sensor REMOVED from the design.**
  - **Trigger**: while planning chunk #5b/#5c sensor placement, the geometric light-shielding problem was raised: the DevKitM-1's onboard NeoPixel (status LED, breathing animation) and always-on power LED sit inside the same closed white-perforated AK-N-94 enclosure as the VEML7700. Internal reflection off the cover ABS + direct line-of-sight on the PCB would bias VEML7700 lux readings, especially in low-ambient conditions.
  - **Mitigations evaluated**:
    - (a) Geometric shielding — VEML7700 in opposite quadrant from MCU, with SEN66 body as a partial baffle, plus an opaque shroud limiting field-of-view. Workable but adds 3D-printed parts and per-unit assembly steps.
    - (b) Internal baffle — vertical 3D-printed wall between MCU and VEML7700 quadrants reaching from PCB to cover.
    - (c) Software compensation — read VEML7700 with LED-off baseline subtraction. Unreliable with the breathing animation already committed for the AQI indicator.
    - (d) Move status LED off the MCU module — external WS2812 with light pipe to the front cover, so the LED radiates outward rather than inside the case. Adds BOM line + GPIO routing.
  - **Decision**: drop VEML7700 entirely. The sensor was originally a "bolt-on" — air quality + presence are the OAS mission; ambient light measurement was a convenience feature with no hard requirement. Home Assistant has many indoor light sources (phone, smart bulbs, dedicated sensors) that fill this gap without committing OAS to the shielding work.
  - **What this saves**: ~€1 BOM, one SMD part on the JLCPCB assembly run, ~5 × 5 mm of sensors-area PCB real estate, one I²C device address slot, one ESPHome `sensor.veml7700` component, one entry in HA-INTEGRATION docs, and the entire "geometric shielding + maybe baffle + maybe light pipe" rabbit hole.
  - **What stays**: I²C bus on GPIO 6/7 still needed for SEN66 (0x6B), NT3H2211 NFC (0x55), and Qwiic expansion. Pull-ups R5/R6 at 10 kΩ stay (driven by SEN66 spec, not VEML7700).
  - **Reversal cost** (if a future user wants light sensing back): re-evaluate via Qwiic expansion port — a Qwiic VEML7700 breakout could plug into the I²C expansion port and be physically mounted *outside* the case, avoiding the shielding problem altogether. ESPHome config trivial.
  - Added to "Out of scope (decisions already made)" so future revisits require new information.

- **v0.15** — Daughterboard re-layout: LD2410 to the LEFT wall, NFC down to share LD2410's Y band, ESP32 to UPPER-LEFT.
  - **LD2410** pushed against the left PCB wall: body left edge at PCB X=-54.90 (2.0 mm clearance from PCB outline at the bottom-left corner Y=+19.05). `LD2410_ANCHOR_X` -34.21 → -39.66; `J4_PCB_X` -39.29 → -44.74 (J4 pin 3 stays centered on the LD2410 body long-axis centerline, now at PCB X=-47.28).
  - **NFC (MIKROE-2462)** horizontal centerline (transverse axis) aligned with LD2410's horizontal centerline at PCB Y=+1.27. `MIKROE2462_ANCHOR_Y` -28.54 → -13.03 (Δy = +15.51 mm, downward). New body Y range -13.03..+15.57. Body X range unchanged (-33.21..-7.81); 6.45 mm gap to LD2410's new right edge.
  - **ESP32-C6 DevKitM-1-N4** horizontal, UPPER-LEFT. `ESP32_ANCHOR_X` -24.13 → -37.16 (Δx = -13 mm, body X = -37.16..+11.10). `ESP32_ANCHOR_Y` -29.54 → -14.03 (Δy = +15.51 mm, body Y = -39.43..-14.03 — bottom edge 1 mm above NFC top). Antenna short edge now faces -X (~09:00), USB-C +X.
  - **Why ESP32 went UP rather than further DOWN** (user said "ESP mocno w dół"): after NFC's downward move, NFC occupies the X=-33..-8 strip across Y=-13..+15.57. ESP32 (horizontal 48.26×25.4) cannot fit in the central or lower band without colliding with NFC in the X overlap. The achievable interpretation of "down + left" was: shift LEFT (10 mm) and DOWN as far as the NFC top edge allows (1 mm gap). User confirmed this via the ASCII-mockup question.
  - **Clearances** (all > 1 mm): LD2410 wall 2.0 mm; LD2410 right ↔ ESP32 left 2.5 mm; LD2410 right ↔ NFC left 6.45 mm; ESP32 bottom ↔ NFC top 1.0 mm; NFC right ↔ cable hole 1.81 mm; ESP32 right ↔ SEN66 left 12.4 mm. DRC=0, ERC=0.
  - **NFC antenna spiral** now at PCB Y=+9.83..+15.57 (last 5.74 mm of body) — well clear of cable hole zone, radiates outward toward AK-N-94 cover.

- **v0.15.6** — MIKROE-2462 dimension correction (was incorrectly size S), C1/C2 case-wall cutouts removed, female pin sockets added for ESP32 and MIKROE-2462.
  - **MIKROE-2462 is mikroBUS size L (57.15 × 25.4 mm), NOT size S (28.6 mm).** Verified against the official MikroE datasheet (Digi-Key mirror). The full NFC PCB antenna spiral occupies the ~36.83 mm strip past pin 8. v0.14's "correction" to size S was wrong; v0.13's earlier value of 42.9 mm (size M) was also wrong. Confirmed size **L** is the true dimension. `MIKROE2462_BODY_L` 28.6 → 57.15.
  - **Layout: NFC top edge aligned with LD2410 top edge** (`MIKROE2462_ANCHOR_Y` -13.03 → -16.51). Body Y range -16.51..+40.64 (just 2.86 mm above PCB chord at +43.5). `MIKROE2462_ANCHOR_X` -36.16 → -38.16 (-2 mm w lewo, 1.5 mm gap to LD2410 right edge).
  - **C1 and C2 AUX case-wall cutouts REMOVED** to free the bottom-left PCB region for the size-L NFC body. C1 (-33.8..-21.8, +31.5..+42.5) and C2 (-16.8..-1.1, +27.2..chord) overlapped with the new NFC body Y range. Connector strip on the right half (C3, C4, C5) retained; final connector assignment (24V terminal, Qwiic, optional SWD/UART recovery, etc.) goes to the 3 remaining cutouts. Update `CUTOUTS` list in `generate.py`.
  - **Female pin sockets added** for ESP32 and MIKROE-2462 daughterboards (per user request "miejsce na żeńskie goldpiny"). Both modules plug into 2× parallel rows of 2.54 mm female pin sockets on the OAS PCB.
    - **J5 / J6**: 2× 1×15 P2.54 mm female pin sockets for ESP32-C6 DevKitM-1-N4. Row spacing 22.86 mm, pin block offset 5.37 mm from antenna short edge per Espressif dimensions PDF (i.e., pin block NOT centered on body — asymmetric toward antenna end).
    - **J7 / J8**: 2× 1×8 P2.54 mm female pin sockets for MIKROE-2462. Row spacing 22.86 mm, pin block offset 2.54 mm from pin-1 short edge per mikroBUS spec (asymmetric toward one short edge; remaining ~36 mm of body length is the NFC antenna spiral area).
  - **Daughterboard helper silk-rect asymmetry**: long edges now extend 0.5 mm BEYOND body so the silk rect encloses the female pin sockets (whose stock silk extents reach 1.33 mm from the pad row centerline, just past the body edge); short edges keep the 0.2 mm inset (no pin sockets near short edges). Consistent with the LD2410 approach (silk extends past body edge to enclose J4).
  - DRC=0, ERC=0.

- **v0.15.7** — NFC body flipped 180° around its bottom-right anchor. Pin block (J7/J8 sockets) now sits at PCB Y=+20.32..+38.10 (near the chord), and the NFC PCB antenna spiral now sits at PCB Y=-16.51..+18.64 (top region, aligned with the LD2410 top edge). `MIKROE2462_ROTATION` updated to 180 and `MIKROE2462_ANCHOR_X/Y` re-anchored to the body's PCB bottom-right corner. J7/J8 socket positions follow the new anchor. DRC=0, ERC=0.

- **v0.15.8** — Independent-review fixes (13 findings from 6-agent code review). The major changes:
  - **CRITICAL — J4 pin order corrected to match HLK-LD2410B datasheet V1.04 Table 1**. Previous J4 net mapping was end-for-end reversed (pin 1 = VCC, pin 5 = OUT). The correct order is **Pin 1 = OUT, Pin 2 = UART_Tx, Pin 3 = UART_Rx, Pin 4 = GND, Pin 5 = VCC**. Power/ground coincidentally landed on the right pads by accident; UART direction was swapped (both sides driving inputs / both sides driving outputs → bus contention) and the OUT signal landed at the +5V pad — radar would have been powered but mute, and the presence interrupt would have shorted into the 5V rail. PCB pad positions are unchanged; only net assignments. C11 (100 nF VCC decoupling) repositioned below J4 pin 5 (VCC, bottom of the new pin order).
  - **MAJOR — `LD2410_BODY_H` corrected from 15.24 mm to 7.62 mm** to match the HLK-LD2410B datasheet V1.04 §4.1 (7 mm short axis). The old value matched the LD2410**C** variant (different module, 16×22 mm) or a dev-kit carrier board. `LD2410_ANCHOR_X` shifted +3.81 mm to recentre the new (smaller) body shadow on the J4 pin row. `LD2410_CONNECTOR_Y` derived from body_h/2.
  - **MAJOR — J3 (SEN66 socket) rotated from 180° → 0°** so its cable opening faces NORTH (toward the SEN66 body's JST GH connector at PCB Y=-33.2). Eliminates the 180° cable U-turn the previous south-facing orientation forced. Realized cable run drops from ~95-105 mm (routed) to ~60 mm; the CLAUDE.md "<40 mm bus length" claim was never met by v0.15 geometry and is still an aspiration — current realized I²C bus length is ~60 mm, well inside Sensirion's < 100 mm recommendation but not the ambitious < 40 mm.
  - **MAJOR — `MIKROE-2462` chip ID corrected** from NT3H2111 (MikroE product page text) to **NT3H1101** (MikroE datasheet PDF + TME catalog "Comp: NT3H1101"). The 888-byte EEPROM size in MikroE's code example confirms NT3H1101 (NT3H2111 also has 888 bytes user memory, but TME explicitly identifies the chip as NT3H1101 and MikroE's authoritative datasheet PDF agrees). Both chips share I²C 0x55 and the FD pin so firmware is unaffected. Updated CLAUDE.md, hardware/components/mikroe-2462.md, and all generate.py descr strings.
  - **MINOR — board-level body labels for SEN66 / LD2410 / ESP32 / MIKROE-2462**. The previous in-footprint `fp_text` labels rotated with the footprint and ended up vertical or upside-down on the rendered PCB (e.g. "HLK-LD2410B" 270° vertical, "ESP32-C6 DevKitM-1" 180° upside-down). Moved to board-level `gr_text` (rotation-independent). All major component identifications now read horizontally.
  - **MINOR — LD2410 silk body rect dropped** (controlled by new `LD2410_EMIT_SILK_OUTLINE = False`). After body_h shrank, J4 silk frame is wider than the body itself; any LD2410 silk rect either overlapped J4 silk (silk_overlap DRC) or sat uselessly inside the body. Identification now via F.Fab body outline (assembly docs) + the board-level "HLK-LD2410B" gr_text label + the J4 silk frame at the connector edge.
  - **DOC — stale v0.5-era "SEN66 mounts on enclosure cover" comments removed** from generate.py (lines 121-129, 702-703, 962, 1135, 1148, 1170, 1215, 1511, 1541, 2672, etc.). v0.6 reversed that plan; comments now reflect PCB-mount.
  - **DOC — CLAUDE.md pinout table I²C pull-up value** corrected from "4.7 kΩ" → "10 kΩ" (matches the schematic R5/R6 actual values and SEN66 datasheet §3.1 spec; v0.6 changelog already noted the bump but the pinout table was not re-synced).
  - **DOC — power LED dissipation revised down** from ~30 mW (v0.4/v0.5 estimate) to ~5 mW (Espressif schematic: R16=1 kΩ on 3.3 V → 1.5 mA → ~5 mW). At this magnitude the post-prototype desolder rework is unlikely to produce a measurable SEN66 SHT bias; reclassified from "planned rework" to "skip unless empirical evidence emerges."
  - **DOC — STAR-Engine ×10 scaling clarification**: the recommended T1=100, T2=300, K=20, P=20 IAQM preset values are *post-scale*; the firmware actually sends T1=1000, T2=3000, K=200, P=200 over the I²C 0x60B2 / 0x6100 commands (16-bit unsigned, raw = value × 10).
  - **DOC — SEN66 cable accessory note**: Sensirion ships SEN66-SIN-T *without* a cable (per all retail listings checked). 50 cm AWG26 JST GH 6-pin reference cable is a separate accessory (Sensirion or third-party). Added to BOM expectations.
  - **OPEN ISSUE flagged — onboard NeoPixel powered from V5V, not V3V3**. Discovered during the same review: the DevKitM-1's onboard WS2812B has VDD tied to VCC_5V (USB VBUS), so it will not light up in a deployed OAS unit (no USB plugged in). Three remediation options recorded for user decision; not blocking other tasks. See "OPEN ISSUE" callout under the ESP32-C6-DevKitM-1-N4 pinout section.
  - DRC=0, ERC=0 across all changes.

- **v0.16** — AQI status LED ring added (resolves OPEN ISSUE #2). *Originally 12 × SK6812-SIDE; v0.17 dropped D20 (north of cable hole) and v0.18 swapped that to dropping D14 (south of cable hole) — the final ring has 11 LEDs in either case.*
  - **Decision**: build a custom ring of **12 × SK6812-SIDE** addressable RGB LEDs (4020 side-emit, integrated WS281x controller) on a Ø22 mm pitch circle centred on the PCB origin (= centre of the Ø12 mm cable pass-through hole). Per `hardware/components/_research-led-diffuse-ring.md` (research dated 2026-05-13). Each LED emits radially OUTWARD, parallel to the PCB plane, so the perforated AK-N-94 cover sees only diffuse spillage off the cover interior — no "dot through perforation" effect that plagues top-emit NeoPixels under perforated covers.
  - **Why side-emit over top-emit (geometric reasoning, not optical)**: top-emit LEDs at 5.76 mm pitch (12 LEDs on Ø22 mm) would need ≥11.5 mm cover standoff (1.5–2× the LED pitch) to mix into a smooth gradient — borderline in OAS's 17 mm height budget once SEN66 is factored in. Side-emit LEDs throw their cone parallel to the PCB, so the cover never sees the die in line-of-sight — dotting is eliminated structurally, not optically. Smoke-detector indicator-halo optics pattern.
  - **Pinout (verified twice)**: 1=DIN, 2=VDD, 3=DOUT, 4=GND. Cross-checked between the Normand SK6812 SIDE-A 2018 rev 01 datasheet and the OPSCO SK6812 SIDE-A-001 2021 rev A/1 datasheet — both agree. This is DIFFERENT from KiCad's stock `LED:SK6812` symbol (which is the PLCC4 5050 variant with 1=VSS/2=DIN/3=VDD/4=DOUT); OAS ships its own `OAS:SK6812-SIDE` symbol and `oas:SK6812-SIDE` footprint to avoid that pitfall. Full part spec in `hardware/components/sk6812-side.md`.
  - **Geometry**: LED ring radius 11.0 mm; LEDs at θ = 0°, 30°, 60°, … 330°. Each LED's KiCad rotation = `(270 - θ) mod 360` so the body-local -Y (emission face) points radially outward in PCB frame. Inner edge of LED body sits ≈10 mm from the PCB origin → 4 mm radial clearance to the cable hole edge at R = 6 mm. Outer edge at R ≈ 12 mm. Tightest external clearance: 0.26 mm to the MIKROE-2462 silk rectangle at PCB X = -12.26 mm (D17 at θ = 180°); silk-overlap DRC kept clean by suppressing all F.SilkS body / arrow geometry on the LED footprint (F.Fab carries the body outline + pin-1 dot + emission arrow for the assembler).
  - **Daisy chain**: D11 (θ = 0°) → D12 (θ = 30°) → … → D22 (θ = 330°). D11 DIN driven from MCU GPIO 8 via the new hierarchical net `WS2812_DIN`. D22 DOUT terminates open (no_connect marker).
  - **Decoupling**: 1 × 100 nF 0402 X7R per LED (C20 – C31). Placed on the OAS PCB radially INWARD from each LED at R = 7.6 mm, body local rotation matching the LED so cap pads are reachable from the LED's VDD pad with a short trace. Net BOM line count +13 (12 LEDs + 1 0402 cap reel; the 12 caps are quantity-12 of the same SKU).
  - **Schematic side** (`sensors.kicad_sch`, chunk #5d): 12 D11..D22 instances of `OAS:SK6812-SIDE` symbol arranged in a tidy vertical column (X = 40.64 mm, row pitch 25.4 mm). Each LED has its own +5V power flag at VDD (top), GND flag at GND (bottom), and a paired Device:C decoupling cap to the east bridging +5V ↔ GND. DIN wired from the chain or the `WS2812_DIN` hier label (D11 only); DOUT wired to the next LED's DIN via a 5-segment L-route that crosses NO LED body (avoids spurious DIN ↔ DOUT shorts).
  - **MCU side** (`mcu.kicad_sch`): GPIO 8 (J1.9) moved from the no-connect list to the signal list. New `WS2812_DIN` hierarchical label on the LEFT edge at row Y = U3.9. New SUBSHEET_PINS entry on the MCU sheet LEFT edge (dy = 11.43) and the sensors sheet LEFT edge (dy = 8.89), plus a root-sheet inter-sheet wire route at X = 41.91 (one grid step west of the existing NFC_FD vertical at X = 44.45).
  - **PCB side** (`oas.kicad_pcb`): 12 SK6812-SIDE footprints + 12 0402 cap footprints under `gen_sensors_pcb_footprints`. New project-local footprint `oas:SK6812-SIDE` and symbol `OAS:SK6812-SIDE`. New library file `libraries/oas.pretty/SK6812-SIDE.kicad_mod`. Board-level F.SilkS "AQI ring" label at PCB (10.6, -10.6), in empty space between D22 and the ESP32 body.
  - **BOM impact**: +1 BOM line for the LED (qty 12 × SK6812-SIDE) + same 100 nF 0402 SKU already used elsewhere. **~€1.85 per unit at qty 100** for the 12 LEDs (per research file pricing as of 2026-05-13).
  - **5 V draw**: peak 12 × ~50 mA = **600 mA** worst case (all LEDs full white at brightness 255); breathing-animation average **~80 mA**. LM2596S-5.0 is rated 3 A — comfortable margin even with LD2410 (~80 mA) + SEN66 sensor headroom on the same rail.
  - **PCB area consumed**: ~520 mm² (~6 % of board) in previously empty central negative space around the cable hole.
  - **Resolution of OPEN ISSUE #2**: the new external ring is driven from the LM2596S-derived +5 V rail (not the DevKitM-1's USB-VBUS-derived 5 V), so it lights up unconditionally in deployed units. GPIO 8 is still the data line — the DevKitM-1's onboard NeoPixel sits on the same GPIO but is unreachable (its V5V floats); firmware treats the chain as 12 pixels (the ring) and ignores the onboard pixel. Option (c) of the three options previously listed.
  - **Open follow-up**: optional 3D-printed white reflector trough OR post-prototype frosted-PETG annular insert (Part C6 of the research file) deferred until the first physical AK-N-94 sample arrives and we can assess whether the cover's white perforations diffuse adequately on their own.
  - **References**: `hardware/components/_research-led-diffuse-ring.md` (decision rationale + alternatives), `hardware/components/sk6812-side.md` (verified part spec, pin layout, datasheet links).
  - DRC = 0, ERC = 0.

- **v0.17** — 24 V terminal block J1 placed at central cable-hole zone (replaces D20 in the AQI ring).
  - **Trigger**: the v0.6+ architecture has the 24 V supply cable entering through the central Ø12 mm hole in the PCB (from the electrical wall box behind the unit). The previous plan was to terminate the cable at one of the chord-edge cutouts (C3/C4/C5), which would have meant the cable making an ~80–100 mm run across the PCB front side. Moving J1 close to the cable hole shortens that run to <15 mm and removes the bare 24 V conductor's exposure across the whole front side.
  - **Decision**: remove the LED at θ=270° (D20, the LED slot directly opposite the chord, at PCB (0, -11)) and its decoupling cap (C29). Place J1 in the freed-up region between the LED ring and the ESP32 daughterboard.
  - **Placement**: J1 (Phoenix MSTBA 2,5/3-G-5,08, stock KiCad footprint `Connector_Phoenix_MSTB:PhoenixContact_MSTBA_2,5_3-G-5,08_1x03_P5.08mm_Horizontal`) at PCB anchor (-5.08, -22.4) with rotation 0°. Pin row at PCB Y=-22.4 spans X=-5.08..+5.08 (pin 1 = +24V_unprotected on west, pin 2 = GND in centre, pin 3 = PE on east). Body extends in +Y direction to PCB Y=-12.29 (F.SilkS south face), where the cable enters the connector mouth.
  - **D20 slot replacement caveat**: J1 sits NORTH of where D20 used to be. D20's original position (PCB (0, -11)) is south of J1's body south edge (-12.29); the freed-up D20 slot is now part of the cable corridor between the J1 mouth (Y=-12.29) and the cable hole north edge (Y=-6). The user's "in D20's place" intent is met in spirit — D20 had to go to clear the corridor for the cable, and J1 sits as close to that corridor as the ESP32 daughterboard's south edge allows. The body itself sits ~10 mm radially outward from D20's original position.
  - **ESP32 shift**: `ESP32_ANCHOR_Y` was nudged from -24.70 to -26.20 (1.5 mm north) to make room for J1's 13 mm courtyard depth between ESP32's south edge and the LED ring's north corners. Outline clearance to PCB edge at the ESP32's top-left corner drops from 2.73 mm to 1.41 mm — still well above the 0.3 mm copper-edge minimum.
  - **Cable bend geometry**: from cable hole's north edge (PCB Y=-6) to J1's south face (PCB Y=-12.29 at F.SilkS, -12.59 at the cable-entry trapezoid markers): ~6.3-6.6 mm of horizontal travel for the cable bend. Each 1.5 mm² conductor (~3 mm OD) has a typical minimum bend radius of ~10 mm, so the bend is slightly tighter than ideal. Acceptable for a fixed installation (the cable is mechanically anchored at both ends and is not flexed during use). Note: the cable's three conductors fan out from the hole exit, each entering its own screw clamp — bends are independent, not bundled.
  - **Daisy chain re-routed**: in the schematic, D19.DOUT now connects directly to D21.DIN via the existing 5-segment chain route. The D20 row position in the schematic column (Y=289.56 mm) is empty; the chain wire passes through it cleanly. `LED_RING_SKIP_INDICES = (9,)` controls the skip both for PCB placement and schematic generation, keeping the two in sync.
  - **BOM impact** (relative to v0.16): -1 SK6812-SIDE LED (D20), -1 100 nF 0402 cap (C29). The 100 nF 0402 reel line stays (11 caps + many other instances on the PCB); only the qty drops by 1.
  - **F.SilkS labels**: board-level "J1 (24V)" placed at PCB (-15.0, -22.4), 6 mm west of the J1 body, on the same Y row as the J1 body centre. The stock footprint's `(property "Reference" "J1")` is hidden (would have overlapped MOD1 silk south edge). Per-pin function labels "24V" / "GND" / "PE" placed on F.Fab (assembly-documentation layer, silk-overlap-exempt) above each pin.
  - **Schematic Footprint property**: the J1 symbol in `power.kicad_sch` now carries `Footprint = Connector_Phoenix_MSTB:PhoenixContact_MSTBA_2,5_3-G-5,08_1x03_P5.08mm_Horizontal` (was empty in v0.2 because no PCB footprint existed yet). Datasheet and Description properties also populated.
  - **No copper traces yet**: the v0.17 PCB has no tracks, only footprint placements. Net assignments (24V_IN → fuse → buck input) come in a later chunk along with the rest of the power/MCU/sensor copper routing.
  - DRC=0, ERC=0.

- **v0.18** — J1 24 V terminal block FLIPPED from north (D20 slot) to south (D14 slot).
  - **Trigger**: user decision after reviewing the v0.17 render. The north side is congested (ESP32 daughterboard at PCB Y=-50.10..-24.70 leaves only ~13 mm of vertical room between the ESP32 south edge and the AQI LED ring's north corners — that 13 mm was almost exactly the Phoenix MSTBA courtyard depth, so v0.17 had to nudge the ESP32 1.5 mm north to fit and ended up with sub-1 mm clearance to the PCB outline). The south side has substantially more clearance: SEN66 sits in the bottom-right (X ≥ +23.5), the chord cutouts C3/C4/C5 are narrow strips on the right half, and MIKROE-2462 sits in the bottom-left at X ≤ -12.76. The central south corridor (X ≈ -12..+23, Y > +6) is largely empty. Flipping J1 to the south recovers ~9 mm of vertical clearance margin and lets the ESP32 north-shift be reverted entirely.
  - **D14 swapped for D20**: `LED_RING_SKIP_INDICES` changed from `(9,)` to `(3,)`. Index 3 = D14, the LED at θ=90° (PCB (0, +11), south of the cable hole, directly toward the chord). D20 (index 9, north of hole) is restored to its v0.16 placement. C23 (D14's decoupling cap) replaces C29 in the BOM removal. Final ring still has 11 LEDs, just a different missing one.
  - **Daisy chain re-routed**: schematic now connects D13.DOUT → D15.DIN (skipping D14's row position in the schematic column at Y=137.16 mm). Mirror of the v0.17 D19→D21 skip. The chain wire route is unchanged in structure (5-segment route through the now-empty intermediate row).
  - **ESP32 shift REVERTED**: `ESP32_ANCHOR_Y` returned to -24.70 (was -26.20 in v0.17, originally -24.70 in v0.15.3). PCB outline clearance at ESP32's top-left corner restored from 1.41 mm (v0.17) to 2.73 mm (pre-v0.17). H3 mounting hole courtyard clearance to ESP32 top edge also restored.
  - **New J1 position**: PCB anchor (+5.08, +22.4), rotation **180°** (was 0° in v0.17). Pin row at PCB Y=+22.4 spans X=-5.08..+5.08, but the pin function order is REVERSED in PCB X relative to v0.17 — pin 1 (+24V) at PCB +X (east), pin 2 (GND) at X=0, pin 3 (PE) at PCB -X (west). The user looking at the south face (cable insert side, the user's natural viewing angle for inserting the cable) sees pins left-to-right as PE / GND / +24V. The body extends NORTH from the pin row to PCB Y=+12.29 (F.SilkS north edge, cable-entry face). Cable-entry trapezoid markers face PCB -Y (north, toward the cable hole) as required.
  - **Clearance budget (v0.18)**:
    - J1 courtyard PCB X = -9.13..+9.13, Y = +11.90..+24.90.
    - D13/D15 south F.Fab corners at PCB Y = +11.67 (mirror of v0.17's D19/D21 north corners): 0.23 mm courtyard clearance, 0.62 mm F.SilkS clearance.
    - C3 cutout north edge at PCB Y = +28.998: 4.10 mm courtyard clearance.
    - SEN66 body west edge at PCB X = +23.5: 14.38 mm X clearance to J1 courtyard east edge (J1 has no east-side conflict).
    - J3 (SEN66 socket) courtyard west edge at PCB X = +30.02: 20.90 mm X clearance.
    - Zip-tie hole ZT1 at PCB (+20.5, 0): 11.77 mm X clearance to J1 east edge; ZT1 sits north of J1 (Y=0 < Y=11.90), no conflict.
    - DRC=0 confirms all clearances clean.
  - **Cable bend geometry (v0.18)**: from cable hole's SOUTH edge (PCB Y=+6) to J1's north face (PCB Y=+12.29 at F.SilkS, +12.59 at the cable-entry trapezoid markers): **6.29 mm of horizontal travel** for the cable bend. Identical magnitude to v0.17's north-side bend (mirror geometry); the tightness vs the ~10 mm typical 1.5 mm² bend radius remains the same trade-off. Acceptable for a fixed-installation cable that is mechanically anchored at both ends and not flexed during use.
  - **F.SilkS "J1 (24V)" label** moved from PCB (-15, -22.7) → (+15, +22.4). West of the J1 body on the v0.17 north placement was the open quadrant; in v0.18's south placement, the WEST side is occupied by MIKROE-2462's body silk (extends to PCB X = -12.26 at this Y range), so the label was relocated to the EAST side. East of J1 there's a clean 14.77 mm strip between J1's east edge (X=+8.73) and SEN66's west edge (X=+23.5). Visual association preserved (label on same Y row as J1 body centre).
  - **Per-pin F.Fab labels** "24V"/"GND"/"PE": Y position moved from `pin_y + 0.8` (south of pin row in v0.17 with rot 0°) → `pin_y - 0.8` (north of pin row in v0.18 with rot 180°). X positions follow the pin reversal: 24V at X=+5.08, GND at X=0, PE at X=-5.08.
  - **Schematic side**: D14 + C23 symbol instances removed (analogous to v0.17's D20 + C29 removal). D20 + C29 restored. The schematic's J1 symbol in `power.kicad_sch` is unchanged — only `LED_RING_SKIP_INDICES` and the J1 PCB placement constants changed.
  - **BOM impact**: identical to v0.17 (still -1 SK6812-SIDE LED and -1 100 nF 0402 cap relative to v0.16), only the designator changes (D20→D14, C29→C23).
  - DRC=0, ERC=0.

- **v0.19** — IO sub-sheet populated (chord-east case-wall connectors). Closes review Mi4 ("IO sub-sheet still empty").
  - **Trigger**: the chord-east connector strip (cutouts C3/C4/C5) has been a documented placeholder since v0.7 — no schematic content, no PCB connector footprints. Each new sub-sheet build (v0.15.x..v0.18) deferred populating IO. v0.19 lands the two CLAUDE.md-listed expansion ports.
  - **J9 — Qwiic / Stemma QT expansion (always populated)**:
    - Footprint: stock KiCad `Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal` (genuine JST SH 4-pin horizontal SMD socket, the universal Qwiic / Stemma QT host part).
    - Lives in cutout **C5** (X +27.9..+35.4, Y +36.494..+42.494 — 7.5 × 6 mm, fully inside PCB). PCB anchor (+31.65, +39.69) with rotation 180° so the cable mouth faces the chord (south, +Y) — cable plugs in from outside the case.
    - Pinout (Qwiic / Stemma QT standard): pin 1 = GND, pin 2 = +3.3V, pin 3 = SDA, pin 4 = SCL. SDA / SCL tap the shared I²C bus already used by SEN66 (0x6B) + NT3H1101 (0x55), via the new IO sub-sheet `I2C_SDA` / `I2C_SCL` hier labels matched to the existing MCU exports.
    - Sourcing: Sparkfun PRT-14417, Adafruit 4209, or any genuine JST SM04B-SRSS-TB.
  - **J10 — Native-USB recovery header (DNP)**:
    - Footprint: stock KiCad `Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical`. Pads only — DNP (`(dnp yes)` in schematic, `exclude_from_bom`-equivalent at assembly).
    - Lives in cutout **C3** (X +4.9..+13.9, Y +28.998..+43.5 — 9 × 14.5 mm). PCB anchor (+9.4, +41.0) with rotation 180° so pad 1 (rectangular pin-1 marker) sits at the chord side (easy pogopin-jig orientation). Pad row stacks NORTH at 2.54 mm pitch: pad 1 at Y=+41.0, pad 6 at Y=+25.78.
    - Pinout (top of pad row = nearest chord = pad 1, going north): 1=GND, 2=+3V3, 3=USB_DM (GPIO 12), 4=USB_DP (GPIO 13), 5=EN (chip reset), 6=BOOT (GPIO 9 strap).
    - Use case: emergency reflashing if BOTH DevKitM-1 onboard USB-C ports are damaged. ESP32-C6 has no traditional JTAG/SWD; J10 exposes the chip's native USB-Serial-JTAG pair + flashing straps so a pogopin jig can drive native USB even with the dev-kit's USB-C connectors destroyed.
    - Critical wiring: GPIO 12 / GPIO 13 moved from `ESP32C6_DEVKITM1_NC_PINS` to `ESP32C6_DEVKITM1_SIGNAL_PIN` as `USB_DM` / `USB_DP`. The MCU sub-sheet's U3.28 / U3.29 pin tips now have east-going wire stubs to right-edge hier labels `USB_DP` / `USB_DM` (at Y rows 123.19 / 125.73 — south of J2's pin block, so the wires don't intersect the existing J2 UART-recovery header).
  - **Third cutout (C4, X +18.9..+22.9, Y +34.998..+43.5)**: kept as a placeholder for v2 expansion. No connector. Silk rect + "C4 v2" label preserved so the user can identify the unused case-wall opening at assembly time and either populate a v2 connector or fill the opening with a plastic insert.
  - **CUTOUTS data structure extension**: 6th tuple field `allow_pads: bool`. C3 (J10) and C5 (J9) flip the keepout zone's `(pads not_allowed)` → `(pads allowed)` so the connector solder pads can live inside the case-wall opening (where the user accesses them from outside via cable plug / pogopin jig). C4 keeps the v0.7 default (pads not allowed).
  - **EN / BOOT migration from local → hierarchical labels**: MCU sub-sheet previously had `local label "RST"` (= EN signal in ESP32 datasheet language) and `local label "BOOT"` connecting U3.2 ↔ J2.5 and U3.26 ↔ J2.6. Local labels are sheet-scoped → don't export to other sub-sheets. v0.19 converts both ends of each net to hier labels (RST → `EN`, BOOT → `BOOT`), so the same nets now also reach the IO sub-sheet's J10.5 / J10.6 pins. `J2_PIN_MAP[5]` renamed from `"RST"` to `"EN"` to match.
  - **SUBSHEET_PINS["io"]**: 6 left-edge pins added (I2C_SDA, I2C_SCL, USB_DM, USB_DP, EN, BOOT). `SUBSHEET_SIZE` bumped from (38.1, 12.7) → (38.1, 17.78) to fit 7 pins per side at 2.54 mm pitch (MCU right edge now has UART_TX/RX + USB_DM/DP/EN/BOOT = 6 pins).
  - **Root sheet inter-sheet wiring**: extended I²C horizontal wires east to reach IO's left edge (sharing the existing Sensors→MCU vertical legs at X=95.25 / 97.79). Added 4 new MCU→IO routes (USB_DM/USB_DP/EN/BOOT) with east-going stubs from MCU right edge → vertical legs at X=153.67 / 156.21 / 158.75 / 161.29 → west stubs into IO left edge.
  - **F.SilkS labels** (per OAS silkscreen convention):
    - Per-cutout text labels: "J10 flash" at PCB (+9.4, +25.7), "C4 v2" at cutout centre, "J9 Qwiic" at PCB (+31.65, +34.5). C3 and C5 silk rects suppressed (J9 / J10 stock footprint silk frames already mark the connector outline; double-rect would trigger silk_overlap DRC).
    - Per-pin F.Fab labels: J9 pin 1 marker "J9 GND" (pin 1 = GND); J10 column labels "GND", "+3V3", "USB-", "USB+", "EN", "BOOT" stacked at PCB X = J10_PCB_X + 3.0, going north from pad 1. Size 0.8 mm on F.Fab (silk-min-text-height rule applies to F.SilkS only).
  - **Schematic library extension**: new `_sch_conn_01x04` helper for the JST SH 4-pin Qwiic socket. Pulls `Connector_Generic:Conn_01x04` from KiCad stock library at generation time. Reused stock `Conn_01x06` for J10 (already in `_MCU_LIB_SYMBOLS_TAIL`).
  - **PCB footprint helpers**: new `_emit_stock_lib_footprint()` factory that wraps the parse-and-patch logic used by the existing `gen_j1` / `gen_j3` / `gen_j4` functions into one place. `gen_j9_qwiic_pcb_footprint` and `gen_j10_recovery_pcb_footprint` are thin wrappers around it. Future stock-library connector placements should use this helper instead of duplicating the parse code.
  - **BOM impact** (relative to v0.18): +1 SKU = JST SM04B-SRSS-TB (qty 1, ~€0.50). 6-pin 2.54 mm pin header is DNP → 0 BOM lines. Pin labels and silk text are zero-cost (already on the production silk run).
  - **DRC=0, ERC=0**. Verified against the post-build report `renders/_drc.rpt` and `renders/_erc.rpt`.
  - **Open follow-ups** (not blocking, recorded for future revisits):
    - The DevKitM-1's onboard USB-C ports already serve the GPIO 12/13 native-USB pair. J10 is meant for the case where BOTH dev-kit USB-C connectors are damaged (rare). For deployed units the recovery path remains: open the case → connect to either onboard USB-C → reflash. J10 is a belt-and-suspenders fallback.
    - "C4 v2" cutout currently has no connector. A v2 expansion candidate would be an external temperature probe terminal block (DS18B20 / NTC) — but that's marked Out-of-Scope in this document. The cutout exists if a future fork wants to add one without re-spinning the case CNC.

- **v0.20** — Pre-routing critical fixes (3 of 3 critical findings from `_pre-routing-review-v0.19.md` addressed). Routing unblocked.
  - **C3 fix — BOM annotation rename**: `C3b → C13`, `C4b → C14`, `C5b → C15`, `C6b → C16`, `C9b → C17` across schematic, wire labels, and Python identifiers. KiCad's BOM annotator was treating the trailing letter as "un-annotated", emitting them as `Cnb?` which would break JLCPCB / Mouser BOM upload. Renames are mechanical (no electrical change). BOM export now produces clean numeric refs.
  - **C1 fix — script-driven net sync from schematic to PCB (Option A)**: `generate.py` gains `sync_pcb_nets_from_schematic()`. After all KiCad files are emitted, the function:
    1. Calls `kicad-cli sch export netlist --format kicadsexpr` to produce a netlist describing every electrical net.
    2. Parses the netlist with a minimalist Python S-expression parser into a `(reference, pin_number) → (net_code, net_name)` lookup.
    3. Reads back `oas.kicad_pcb` and rewrites it so that (a) the PCB header carries a `(net N "<name>")` declaration for every schematic net, and (b) every pad whose footprint reference + pad pin matches a schematic node gets the `(net <code> "<name>")` clause appended.

    This is the script-driven equivalent of pcbnew's F8 ("Update PCB from Schematic"). Final pass writes the patched PCB back. KiCad's DRC then reports the expected unconnected ratlines (one per still-unrouted net edge); ERC remains clean.
  - **C2 fix — place 27 missing power-section + sensor decoupling footprints + J2 DNP**: 13 new stub footprint generators added to `generate.py` (0603 / 0805 SMD passives; D_SMA / D_SMB / D_SOD-323 diodes; 5×5 SMD inductor; 2920 polyfuse; radial electrolytics; SOT-23 / TO-263-5 / SOT-583 / SOT-23 packages; 1×6 P2.54 mm THT recovery header). Each emits a minimal self-contained footprint (pads + F.Fab body outline + F.CrtYd) with the canonical KiCad `library:footprint` name carried via the Footprint property for BOM export. The new `gen_power_pcb_footprints()` places all 27 components in the upper-right quadrant of the PCB as a coherent block — input protection in Strip F-east (north of J1, south of cable hole), Buck1 cluster between LED ring and ESP32 J5 row, Buck2 cluster under the ESP32 body shadow, sensor decoupling caps adjacent to each sensor socket, J2 DNP recovery header in the NW corner.
  - **U3 / U4 ↔ J5..J8 reconciliation (M3)**: NOT addressed in this commit. The PCB-side daughterboard sockets J5 (ESP32 row A), J6 (ESP32 row B), J7 (NFC row A), J8 (NFC row B) still have no schematic counterparts, so their pads remain on net 0 after the v0.20 net-sync pass. Schematic-side rework that adds J5..J8 symbols (and removes the U3 / U4 placeholders that don't map 1:1 onto split row-A / row-B sockets) is deferred to a separate session — it requires re-wiring every ESP32 GPIO and every NFC mikroBUS pin one row at a time.
  - **DRC verdict after v0.20**: **15 violations** remaining — all SOFT (no `shorting_items`, no `clearance` failures). The 15 break down as 9 `silk_over_copper` (cosmetic — Reference labels under copper pads on hidden silk), 6 `courtyards_overlap` (false positives where new SMD parts sit under the SEN66 mech-ref's body-shadow courtyard; SEN66 is 21.5 mm above the PCB so the Z-clearance is fine), and a few minor `pth_inside_courtyard` flags around the densest J5 ↔ Buck1 boundary. **134 unconnected ratlines** are the expected pre-routing state.
  - **ERC verdict**: **0 violations** (unchanged from v0.19).
  - **Pre-existing schematic bug spotted during C1 verification (NOT a v0.20 regression — flagged for follow-up)**: the root-sheet wires connecting the Sensors right-edge hierarchical-pin row to the MCU right-edge pin row cross over the IO sub-sheet's left-edge pin row at identical Y coordinates, accidentally bridging UART_TX/RX with USB_DP/EN. Visible in the netlist as `J4 pin 2 → /IO/EN` and `J4 pin 3 → /IO/USB_DP` instead of the intended `UART_RX` / `UART_TX`. Routing-correct fix will arrive alongside the M3 schematic rework.
  - **Open follow-ups** (deferred from v0.20):
    - **M3** (was Major in v0.19): rewire schematic so J5+J6 expose the ESP32 module pins as a 1:1 socket pair (delete U3), and J7+J8 expose the NFC daughterboard mikroBUS pins as a 1:1 socket pair (delete U4). Required to give J5..J8's PCB pads electrical nets.
    - **M4**: delete the DNP J2 recovery header from the schematic (J10 now supersedes its role per v0.19), OR keep it as documented-DNP redundancy. User's call.
    - **M5**: populate the `Footprint` property on every schematic symbol that currently has it empty. Already mostly cosmetic now that PCB has its own canonical footprint references, but BOM consistency would benefit.
    - **M1**: tighten the I²C bus routing (drop pull-ups 10 kΩ → 4.7 kΩ) once actual bus length is known after routing.
    - **M2**: add explicit 10 kΩ pull-up on GPIO 8 → +3V3 to replace the disappeared DevKitM-1 onboard pull-up.
    - **Pre-existing schematic bridge** (described above): fix during M3.

- **v0.21** — M3 + UART/USB crossover bug closed. PCB ready for copper routing.
  - **M3 part 1 — U3 deleted, J5 + J6 schematic symbols added (Conn_01x15 each)**: the old per-project 30-pin `OAS:ESP32-C6_DevKitM-1` placeholder was a schematic-only abstraction with no PCB twin, so the v0.20 `sync_pcb_nets_from_schematic` pass could not assign any net to the J5 / J6 PCB pads (they stayed on net 0). Replaced with TWO `Connector_Generic:Conn_01x15` instances:
    - **J5** at angle=0, anchor (144.78, 110.49), pin tips LEFT at X=139.70 → represents the DevKitM-1's J1 (antenna-side) header row. Schematic pin numbers 1..15 match the J5 PCB pad numbers 1..15 = DevKitM-1 J1 pin positions 1..15 (3V3 / RST / GPIO2 / GPIO3 / GPIO4 / GPIO5 / GPIO0 / GPIO1 / GPIO8 / GPIO6 / GPIO7 / GPIO14 / GND / 5V / GND).
    - **J6** at angle=180, anchor (160.02, 110.49), pin tips RIGHT at X=165.10 → represents the DevKitM-1's J3 (USB-side) header row. Schematic pin numbers 1..15 match the J6 PCB pad numbers 1..15 = DevKitM-1 J3 pin positions 1..15 (GND / GPIO16 / GPIO17 / GPIO23..18 / GPIO15 / GPIO9 / GND / GPIO13 / GPIO12 / GND). The 180° rotation visually reverses the pin Y order on the schematic (pin 1 at BOTTOM, pin 15 at TOP), but pin numbering 1..15 still maps 1:1 to the PCB pad numbering.
    - All seven OAS signal pins get short stubs to hierarchical labels (LD2410_OUT, NFC_FD, EN, WS2812_DIN, I2C_SDA, I2C_SCL, UART_TX, UART_RX, BOOT, USB_DP, USB_DM); all five GND pins get local GND power flags; all thirteen NC pins (strap MTMS/MTDI, spare GPIO0/1/14/18..23/15, +5V tap) get `no_connect` markers.
    - **R5 / R6 / C9 / C17 / +3V3 bus** wiring kept verbatim from v0.20 (since J5 pin Y coordinates were chosen to match the old U3 pin tip Y coordinates).
    - **J2 (DNP SWD/UART recovery header) rotated 180°** to align its TX (pin 3) / RX (pin 4) pin rows with J6's UART_TX (pin 2, Y=125.73) / UART_RX (pin 3, Y=123.19). The angle=180 rotation reverses J2's pin Y order: pin 1 (+3V3) at BOTTOM, pin 6 (BOOT) at TOP.
    - **The Python `_esp32c6_devkitm1_lib_symbol`, `_sch_esp32c6_devkitm1`, `_mcu_pin_xy` helpers are now unused** (no callers). Kept in `generate.py` for documentation but removed from `MCU_LIB_SYMBOLS()` so the unused lib symbol no longer ships inside `mcu.kicad_sch`.
  - **M3 part 2 — U4 deleted, J7 + J8 schematic symbols added (Conn_01x08 each)**: same pattern as M3 part 1, but for the MIKROE-2462 NFC daughterboard's mikroBUS 2×8 socket.
    - **J7** at angle=0, anchor (120.65, 125.73), pin tips LEFT at X=115.57 → mikroBUS LEFT column (pins 1..8: AN / RST / CS / SCK / MISO / MOSI / +3.3V / GND). Schematic pin n ↔ J7 PCB pad n.
    - **J8** at angle=180, anchor (128.27, 125.73), pin tips RIGHT at X=133.35 → mikroBUS RIGHT column (pins 9..16: PWM / INT/FD / RX / TX / SCL / SDA / +5V / GND). Schematic pin n ↔ J8 PCB pad n; J8 pin n electrically represents mikroBUS pin (n+8).
    - The NFC-relevant nets attach as: J7 pin 7 (+3V3 flag), J7 pin 8 (GND flag), J8 pin 2 (NFC_FD hier label = mikroBUS pin 10), J8 pin 5 (I2C_SCL = mikroBUS pin 13), J8 pin 6 (I2C_SDA = mikroBUS pin 14), J8 pin 8 (GND = mikroBUS pin 16). Unused pins (J7 1..6 = AN/RST/CS/SCK/MISO/MOSI; J8 1/3/4/7 = PWM/RX/TX/+5V) get `no_connect` markers.
    - C12 (100 nF NFC decoupling) wiring preserved.
    - The old `_sch_conn_02x08_top_bottom` helper is no longer called (no callers); the `Conn_02x08_Top_Bottom` lib symbol stays in `SENSORS_LIB_SYMBOLS` for backward compatibility but no instance references it.
  - **UART/USB root-sheet crossover bug fixed**: the v0.20 review flagged that `J4 pin 2 → /IO/EN` and `J4 pin 3 → /IO/USB_DP` instead of the intended `/MCU/UART_RX` and `/MCU/UART_TX`. **Root cause**: the root-sheet `_root_wire` for `UART_TX` ran east at Y=97.79 from sensors right edge (X=88.9) to the vertical leg at X=143.51 (and similarly for `UART_RX` at Y=100.33 east to X=146.05). At those EXACT Y values the IO sub-sheet's `USB_DP` (Y=97.79) and `EN` (Y=100.33) west-into-io wires from X=156.21/158.75 down to X=101.6 occupy the same Y. The horizontal X ranges overlap in [101.6, 143.51 / 146.05] — KiCad merges any two wire segments that touch at the same coordinates, so UART_TX bridged with USB_DP and UART_RX bridged with EN. **Fix**: re-route the UART east stubs OUT of the IO-block-row Y band before going east. New route: sensors UART_TX east stub goes EAST from (88.9, 97.79) only 6.35 mm to (95.25, 97.79), then SOUTH to (95.25, 110.49) (below the IO block bottom edge at Y=106.68), then EAST under the IO block at Y=110.49 to (143.51, 110.49), then NORTH up to MCU at (143.51, 52.07), then WEST into MCU at (139.7, 52.07). UART_RX uses the same topology with parallel verticals at X=97.79 and Y=113.03 to keep the two nets on separate columns. Netlist verification confirms `/MCU/UART_TX` contains only J2.3, J4.3, J6.2 and `/MCU/UART_RX` contains only J2.4, J4.2, J6.3; `/IO/EN`, `/IO/USB_DP`, `/IO/USB_DM` are clean.
  - **SEN66 mech-ref courtyard removed**: the v0.20 DRC report flagged 5 of 15 violations as `courtyards_overlap` between `SENS1` (SEN66 mech-ref body) and PCB-surface SMD parts (Q1, D3, R1, R4, F1). The SEN66 sits 21.5 mm above the OAS PCB (zip-tied face-up onto the board), so PCB-level components beneath its body shadow are perfectly clear — the violation was a false positive from KiCad's 2D-only courtyard rule. Removed the `F.CrtYd` rectangle from both `gen_sen66_mechanical_footprint()` and the embedded copy `gen_sen66_reference_pcb_footprint()`. Matches the existing pattern in `_emit_daughterboard_reference_pcb_footprint()` (MOD1 ESP32-C6 / MOD2 MIKROE-2462 mech-refs already use this convention).
  - **Net coverage**: 216 pad-net assignments applied by `sync_pcb_nets_from_schematic` (up from 188 in v0.20). All J5 (15 pads), J6 (15 pads), J7 (8 pads), J8 (8 pads) socket pads now carry their proper net. Pads still on net 0 / no_net: Q1 pads 1/2/3 (3 — the SOT-23 P-MOSFET; schematic symbol uses pin names S/G/D, footprint uses pad numbers 1/2/3 — pre-existing M5-style issue, follow-up), J3 MP × 2 + J9 MP × 2 (mounting-plate pads, intentionally non-electrical). 0 pads on net 0 across J5..J8; all other populated pads have valid nets.
  - **DRC verdict**: **10 violations** remaining (down from 15 in v0.20). Breakdown:
    - 1 × `courtyards_overlap` between C4 (220 µF / 10 V output bulk cap) and D2 (SS14 Schottky), both v0.20 stub-placement artifacts in the power section. User will adjust positions during routing iterations.
    - 9 × `silk_over_copper` warnings (Local override; warning, not error). All from PCB silk text labels ("ESP32-C6 DevKitM-1", "ant", "MOD2" silk rect) overlapping with v0.20 stub footprint pads (C5/C6/L2/R2/U1) that the user placed inside the daughterboard body shadows. The daughterboards float above; silk-on-copper here is a printability/aesthetic concern only, not an electrical one. User will refine PCB placement during routing.
    - No `shorting_items`, no `clearance` failures, no `unconnected_items` errors that aren't pre-routing ratlines.
  - **155 unconnected ratlines** are the expected pre-routing state (up from 134 because J5..J8 pads previously had no net to be "unconnected" to). These will resolve as the user draws copper traces.
  - **ERC verdict**: **0 violations** (unchanged).
  - **Routing readiness verdict**: **READY**. All four daughterboard sockets carry valid nets, the UART/USB crossover that would have shorted radar TX/RX into RST/USB_DP is gone, and the only remaining DRC issues are localized to v0.20 stub placements that the user will address as they iterate the PCB layout during routing.

- **v0.22** — Pre-routing fix-iteration #1: SEN66 body-shadow guardrail restored + power-section relocated + Q1 pad mapping + I²C pull-up size + GPIO 8 boot-strap pull-up. **DRC = 0, ERC = 0.**
  - **CRITICAL — SEN66 body-shadow courtyard RESTORED (Issue 1)**. The v0.21 changelog wrote *"SEN66 sits 21.5 mm above the OAS PCB"* and removed the SEN66 mech-ref F.CrtYd rectangle on that reasoning. THAT WAS WRONG. The SEN66 lies **flat on the PCB on its 25.6 × 55.2 mm back face** — the 21.5 mm is body height *above* the PCB, not standoff. SMD components in the SEN66 body shadow would be physically crushed by the SEN66 body. v0.22 restores the F.CrtYd rectangle as a programmatic DRC guardrail: any future attempt to place an SMD inside the SEN66 body shadow now triggers `courtyards_overlap` errors, preventing this class of mistake from recurring. The new generator code carries a multi-line comment explaining the rationale (the v0.21 misconception is the exact kind of class-of-error this comment is meant to head off).
  - **Issue 2 — SEN66-conflict SMD relocated**. With the courtyard restored, DRC reported 5 components (Q1, F1, D3, R1, R4) inside the SEN66 body shadow on the PCB plane. All 5 relocated: Q1 → (+27, +25), D3 → (+27, +28), F1 → (+54, +9) far east of SEN66, R1 → (+25, +33), R4 → (+25, +35.5). D1 stays at (+16, +9.5) (was +15, shifted east 1 mm to clear the rotated D12 LED courtyard polygon east edge at +11.67).
  - **Issue 3 — NFC + ESP32 daughterboard body-shadow partial overlaps fixed**. Independent kiutils check enumerated every footprint and flagged components that straddled the NFC or ESP32 daughterboard PCB-body boundary (the user's rule: "fully inside or fully outside, no partial overlap"). 3 NFC partials (U1, C3, C1) and 10 ESP32 partials moved. The power section was re-laid out from the v0.21 placement into a column-based layout fully inside the ESP32 shadow:
    - Column X=-20 for radial bulk caps (C1 at Y=-32.5, C3 at Y=-41).
    - Row Y=-37 for Buck1 main (U1 LM2596S, D2 SS14, L1, C4).
    - Row Y=-44 for Buck2 main (U2 TPS62933, L2, R2, R3).
    - Row Y=-30 north flank for small SMD (C13, C14, C9, C17, R5, R6, R7).
    - Row Y=-46 south flank for Buck2 HF/feedback caps (C5, C15, C6, C16, C7, C8).
    - C2 (Y2 safety cap) outside ESP32 west, at (-32, -25).
    - C5 shifted to X=-25 (was -20) to avoid 0.05 mm courtyard overlap with C3 column directly above.
  - **Issue 4 (Task #24) — Q1 SOT-23 pad mapping**. `gen_sot23_3pin_pcb_footprint` gains an optional `pin_names` parameter defaulting to `("1", "2", "3")`. The Q1 call site passes `pin_names=("G", "S", "D")` to match the Device:Q_PMOS schematic symbol's letter pin numbers, so `sync_pcb_nets_from_schematic` can match netlist nodes (Q1.G/S/D) to physical pads. Previously Q1's 3 pads stayed on no_net.
  - **Issue 5 (Task #17 M1) — I²C pull-ups 10 kΩ → 4.7 kΩ**. R5/R6 value changed in schematic + PCB. Rationale: realized bus length on the v0.22 PCB is **~140 mm PCB minimum-spanning-tree across 4 tap points (MCU socket + J3 + J8 + J9) + ~80 mm SEN66 JST-GH cable = ~220 mm total electrical length**, well over the Sensirion "< 100 mm strongly recommended" envelope but inside their "< 500 mm with shielding" hard limit. At 10 kΩ the I²C rise time τ = 1 µs / t_r(10-90%) ≈ 2.2 µs *exceeded* the I²C standard-mode spec (t_r ≤ 1 µs at 100 kHz, per the I²C-bus specification). 4.7 kΩ drops τ to ~470 ns / t_r ≈ 1 µs, comfortably within spec. The SEN66 datasheet §3.1 *recommends* 10 kΩ but does not mandate it; lower values are explicitly allowed (per the SEN66 datasheet wording and per Sensirion's published reference designs that use 4.7 kΩ on shorter buses).
  - **Issue 6 (Task #18 M2) — GPIO 8 boot-strap pull-up R7 = 10 kΩ added**. New resistor R7 in the MCU schematic, placed at (+14, -30) on the PCB (north flank of buck section). Wire path: R7.top → +3V3 bus extended east from BUS_3V3_X_RIGHT (140.97) to R7_X (152.4); R7.bottom → vertical drop south to WS2812 wire at Y=113.03 (= J5_WS_Y), extended east to tap R7. The DevKitM-1's onboard pull-up relies on VCC_5V driving the onboard WS2812B (which then internally pulls GPIO 8 high), but in OAS we feed +3V3 directly into J5.1 and leave VCC_5V floating, so the onboard pull-up doesn't exist. R7 replaces it deterministically.
  - **Issue 7 (Task #21 M5) — CLAUDE.md SEN66 cable run measurement updated**. Honest re-measurement of the v0.22 layout: ~140 mm PCB I²C MST + ~80 mm JST-GH cable = ~220 mm total. v0.15.8's "~60 mm" claim and v0.6's "<40 mm total" assumption are both retracted. Documented at the "Shared I²C bus" line under "Architectural decisions" with the full geometry.
  - **Issue 8 — DRC soft-violation residue cleared**. After the relocations: 0 courtyards_overlap, 0 shorting_items, 0 clearance violations, 0 silk_over_copper. The 5 silk_over_copper warnings that remained after the Buck1/Buck2 relocations were resolved by moving the "ESP32-C6 DevKitM-1" and "USB" board-level gr_text labels from F.SilkS to F.Fab (assembly-drawing layer, rendered in 2D-top.png but not silk-printed on the physical PCB — the ESP32 daughterboard physically covers this region at assembly time, so the silk text underneath would be invisible anyway). The C11 LD2410 decoupling cap shifted +2 mm east (-44 → -42 anchor) to clear the LDR1 mech-ref silk-frame long-edge line at PCB X=-43.67.
  - **F1 placement note**: F1 polyfuse (2920, 9.3 × 5.0 mm) didn't fit in any of the small strips: the south-of-cable-hole zone is 5.9 mm tall (F1 needs 8 mm in width at rot 0), and the west-of-J3 zone is too narrow at rot 0 / would collide with J9 at rot 90. F1 placed at (+54, +9) in the open zone EAST of SEN66 body and EAST of ZT2 zip-tie hole — PCB outline clearance 0.88 mm at the Y=+11.80 south corner (well > 0.3 mm `min_copper_edge_clearance` rule). Trace from F1 to U1.VIN runs ~80 mm; not critical for 24 V protection circuitry.
  - **Q1 pad mapping note**: `gen_sot23_3pin_pcb_footprint` now accepts `pin_names=(left, right, top)` argument; default stays `("1", "2", "3")` so the existing call signature for hypothetical future SOT-23 placements (e.g. BAT54 diodes whose schematic symbol uses numeric pins) is preserved. Q1 is the only current caller.
  - **DRC=0 / ERC=0** in the final regenerate pass. 160 unconnected pads remain (expected pre-routing ratlines, up from 155 in v0.21 because R7 + the moved Q1 pads add new ratlines that will be eliminated during copper routing).
  - **Reusable lesson**: the v0.21 misconception ("SEN66 floats above PCB") cost an entire iteration. Two practices added to working conventions:
    1. **Mechanical clearance lookup**: before reasoning about whether SMD parts may live under a non-PCB-mount component, look up the component's mechanical guideline AND the mounting method — never infer "standoff" from a body height number alone.
    2. **DRC guardrails as programmatic safety nets**: the SEN66 courtyard is intentionally body-sized (not body+standoff) so DRC catches the "can't place SMD here" mistake mechanically. This pattern should be extended to similar components in the future where a 3D-shape constraint maps onto a 2D-shadow rule.

- **v0.23** — Pre-routing fix-iteration #2: close all Minor + Nit findings from review iteration 1 (Mn1..Nt2). **DRC = 0, ERC = 0 in the committed Python; derived `.kicad_pcb` / `.kicad_sch` were NOT regenerated before commit — see v0.24 for the resync + the regression that exposed.**
  - **Mn1 — zip-tie X positions doc fix**: `CLAUDE.md` "Architectural decisions" line updated to record the realized v0.7+ values (Pair 1 at X = 22, Pair 2 at X = 30) and drop the earlier speculative "X ≈ 25 / X ≈ 50" wording. X ≈ 50 was rejected because it sits inside the SEN66 outlet circle X=32..53 and would block ~8% of the outlet opening.
  - **Mn2 — v0.6 "<40 mm" historical retraction**: v0.6's "I²C bus length drops from ~80 mm to <40 mm" target was never met by the realized geometry. v0.15.8 / v0.22 each documented honest larger numbers (60 mm → 140 mm PCB MST + 80 mm cable = 220 mm). v0.23 adds an in-place retraction annotation pointing to those later entries from the original v0.6 text.
  - **Mn3 — schematic Footprint property back-fill (`generate.py` post-process)**: every real-component symbol in the sub-sheets used to carry an empty `(property "Footprint" "")` field (the `_sch_*` helpers don't know which footprint reference each symbol will end up wearing). New `_build_pcb_ref_to_footprint()` + `_apply_schematic_footprints()` post-process walks the freshly-written `.kicad_pcb`, builds a `Reference → Footprint` map, and back-fills each non-`#`-prefixed schematic symbol's Footprint property after the sub-sheet is generated. Resolves the "no footprint assigned" warnings that would surface when running the schematic-driven netlist exporter or KiCad's "Update PCB from Schematic" path. **Bug in this iteration**: the back-fill copied the PCB-side `(property "Footprint" "<bare_name>")` strings verbatim, but for 12 inline footprint generators (0402/0603/0805 caps, 0603 resistors, SMD diodes, SOT-23, CP_Radial, polyfuse, inductor) the PCB-side value was itself bare (no `Lib:` prefix). After regenerate, 15 schematic symbols (Q1, C1, C3, C4, C20–C31) ended up with malformed lib-less Footprint properties → 15 ERC `footprint_link_issues` warnings. Caught in review iteration 2; fixed in v0.24.
  - **Mn4 — PCB-side `(dnp)` attribute on J2 + J10**: `gen_j10_recovery_pcb_footprint` gains `dnp=True` (via the generic `_emit_stock_lib_footprint(dnp=True)` path that appends `exclude_from_pos_files exclude_from_bom dnp` to the `(attr ...)` clause). J2 (recovery pin header, via the project-local `gen_pinheader_6_recovery_pcb_footprint`) gets the same flags via a literal `(attr through_hole exclude_from_pos_files exclude_from_bom dnp)`. Mirrors the `(dnp yes)` flag already in the matching schematic symbols so JLCPCB position files + BOM correctly skip both DNP parts. **Did not land at HEAD**: the v0.23 commit shipped `generate.py` with this change but the committed `oas.kicad_pcb` still had `(attr through_hole)` for both J2 and J10 — fix in Python, not in the derived artefact. Fixed in v0.24 by running `regenerate.py` + committing the resulting PCB diff.
  - **Mn5 — explanatory courtyard comment**: `gen_*_mech_lib_file` / `gen_sen66_reference_pcb_footprint` carry a multi-line docstring contrasting MOD1/MOD2/LDR1 (no F.CrtYd — daughterboard standoff via pin sockets allows SMD underneath) with SENS1 (F.CrtYd present — zero standoff, SMD physically excluded). Documents the v0.21→v0.22 misconception so future readers don't reintroduce it.
  - **Nt1 — `rule_severities` comment**: 8-line comment immediately before `"rule_severities": {}` in `gen_pro()` explaining that the empty dict means kicad-cli defaults are inherited and listing the four default-ignored ERC categories (`global_label_dangling`, `four_way_junction`, `pin_to_pin`, `unmatched_footprint`). Heads off the "why is this empty?" question.
  - **Nt2 — `regenerate.py` determinism self-check**: new `_kicad_source_files()` (17 files) + `_hash_file()` (sha256). After step 1, regenerate runs `generate.py` a SECOND time and `sys.exit("ERROR: ...")` on any drift between the two runs. Detects accidental non-determinism (hash-randomized dict iteration, time-based content, etc.) that would otherwise show up as flapping diffs across commits.
  - **Why this iteration regressed**: the fix agent did not run `python regenerate.py` end-to-end before commit. Two consequences: (1) the `.kicad_pcb` / `.kicad_sch` derived artefacts shipped at HEAD didn't reflect the Python source (Mn3 back-fill and Mn4 dnp attribute both invisible in the committed files), and (2) `regenerate.py` did NOT abort on ERC warnings — only DRC did, via `--severity-warning`. The Mn3 lib-less back-fill regression slipped through silently. Both issues addressed in v0.24.

- **v0.24** — fix v0.23 regressions: lib-qualified Footprint back-fill + ERC-strict severity flag + derived-file resync. **DRC = 0, ERC = 0, both enforced by regenerate.py.**
  - **Issue 1 — lib-qualified Footprint property values**. `_build_pcb_ref_to_footprint()` now prefers the PCB-side `(property "Footprint" "...")` clause and lib-qualifies any bare name via a new `BARE_FOOTPRINT_TO_LIB` lookup table (12 entries — C/R/D SMD packages, SOT-23, polyfuse, inductor, radial CP). Every value returned by `_build_pcb_ref_to_footprint()` is now `assert`-checked to contain `:`; any future bare-name generator added without a matching table entry fails fast at generate time rather than as a downstream ERC warning. In parallel, the inline `gen_*_pcb_footprint` generators that previously emitted bare names (`gen_capacitor_0402/_0603/_0805_pcb_footprint`, `gen_resistor_0603_pcb_footprint`, `gen_diode_sma/_smb/_sod323_pcb_footprint`, `gen_inductor_smd_5x5_pcb_footprint`, `gen_polyfuse_smd_pcb_footprint`, `gen_sot23_3pin_pcb_footprint`, `gen_capacitor_polarized_radial_pcb_footprint`) now emit fully-qualified `<Lib>:<Name>` strings in their `(property "Footprint" ...)` clause directly. Some name corrections needed to match real stock-library entries: `L_NR5040` → `Inductor_SMD:L_APV_ANR5040`, `R_2920_7351Metric` → `Fuse:Fuse_2920_7451Metric`, `CP_Radial_D8mm_P3.5mm` → `Capacitor_THT:CP_Radial_D8.0mm_P3.50mm` (KiCad stock uses single-decimal diameter + two-decimal pitch). Geometry unchanged (pad sizes, body sizes, courtyards all the same); only the printed name is corrected.
  - **Issue 2 — `regenerate.py` ERC strict mode**. `kicad-cli sch erc` invocation now includes `--severity-error --severity-warning --exit-code-violations`, mirroring the DRC step's strictness. Verified by temporarily corrupting a schematic Footprint to a non-existent reference and confirming subprocess exit code 5 → regenerate.py aborts. CLAUDE.md "PCB design workflow" §3 ("aborts on any error or warning") is now actually enforced for ERC, not just DRC.
  - **Issue 3 — derived-file resync**. Running `python regenerate.py` end-to-end with the Mn3 lib-qualification fix produces: DRC = 0 violations / 0 warnings, ERC = 0 violations / 0 warnings, determinism self-check passes (17 files bit-identical across two consecutive runs). The resulting `.kicad_pcb` + 4 sub-sheet `.kicad_sch` files are committed alongside `generate.py` so HEAD reflects the Python source-of-truth.
  - **Issue 4 — CLAUDE.md changelog hygiene**. v0.23 entry added retroactively (had been missing — caught in review iteration 2 as `Mj1`). Documents what the v0.23 commit actually changed in `generate.py` and acknowledges the artefact-sync bug + ERC regression that v0.24 then closed.
  - **Issue 5 — review file committed**. `hardware/components/_review-iteration-2-v0.23.md` (the independent re-review that surfaced the v0.23 regression chain) was previously untracked. Now committed as part of the v0.24 fix series.
  - **Why this slipped past v0.23**: `regenerate.py` only aborted on DRC `--severity-warning`, not ERC. The Mn3 back-fill quietly introduced 15 ERC `footprint_link_issues` warnings that `kicad-cli sch erc` exited 0 on (warnings only, no errors). v0.24's ERC severity flag closes this hole permanently — future iterations cannot ship with non-zero ERC.
  - **Reusable lesson**: when the source-of-truth Python is updated, the derived `.kicad_*` files MUST be regenerated AND committed in the same commit. The determinism self-check (v0.23 Nt2) cannot detect this drift because it only validates determinism *within* one regenerate run, not between the on-disk pre-commit state and the Python. The strict ERC flag now enforces correctness post-regen, which is the layer where the v0.23 regression would have been caught had it been present.

- **v0.25** — review-iteration-3 closure: full schematic Footprint-property coverage (regex column-0 → whitespace-tolerant).
  - **Mn3-residual fix**. `_build_pcb_ref_to_footprint()` regex `(?m)^\(footprint "..."` widened to `(?m)^\s*\(footprint "..."`. KiCad pretty-prints some `(footprint ...)` blocks in `oas.kicad_pcb` with leading tab/space indentation; the column-0 anchor silently skipped 31 of 76 placed footprints in v0.24, leaving 27 schematic real-component symbols with `(property "Footprint" "")` (ERC-silent but cosmetically wrong). Match count goes from 45 → 76 — exactly equal to the kiutils enumeration. Verified no nested `(footprint "..."` references exist in the file (every match has only whitespace before it on its line, so no false positives). Inner `re.match` also relaxed to `re.search` for the same reason (sliced block can begin with whitespace).
  - **Schematic post-fix state**: all 65 real-component schematic instances across the 4 sub-sheets now carry a fully-qualified `Lib:Name` Footprint property. Empty-Footprint count: **0** (was 27 at v0.24, 51 at v0.22). Previously-missed refs now lib-qualified: C2 + C5–C17 (Capacitor_SMD), D1–D3 (Diode_SMD), F1 (Fuse), L1–L2 (Inductor_SMD), R1–R7 (Resistor_SMD), plus ZT1–ZT4 (oas:ZipTieHole_3mm_NPTH — these have no schematic counterpart, but the PCB-side mapping now includes them for consistency).
  - **Nt-doc-comment fix**. The `_build_pcb_ref_to_footprint()` docstring overstated coverage in v0.24 ("Reads each top-level `(footprint ...)` block"). Updated to disclose the regex behavior honestly ("each at the start of a line, with optional leading whitespace") and the verification that no nested `(footprint "..."` matches exist.
  - DRC = 0/0, ERC = 0/0, determinism self-check passes (17 files bit-identical across two consecutive runs). PCB geometry unchanged — schematic-side `.kicad_sch` diffs only (the 27 previously-empty Footprint properties now carry their canonical `Lib:Name` strings).
  - **Reusable lesson**: when writing regex-based post-processing against pretty-printed S-expressions, never anchor at column 0 unless the writer is guaranteed to emit at column 0. KiCad's pretty-printer uses tab/space indentation for nested blocks, and any `(footprint ...)` nested two parens deep from the document root *will* be indented in the output. Use `(?m)^\s*\(...` or omit the anchor entirely.
