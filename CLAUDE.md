# OAS — Open Ambient Sensor

DIY multi-sensor environmental monitor for indoor spaces. Measures air quality, presence, and ambient light. Mounts on a standard wall-recessed electrical box (60 mm screw pitch). Powered from 24V DC. Integrates with Home Assistant via ESPHome.

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
- **Ambient light**: lux (Vishay VEML7700)

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
  - PCB: **Ø120 mm D-shape** (arc R=60 mm), flat chord **82.6 mm** along the bottom edge (chord Y from centre ≈ 43.52 mm)
  - 3× M3 mounting holes (Ø3.8 mm) on **pitch circle Ø110 mm**, trójkąt równoboczny with one hole opposite the chord
  - Hole positions (origin = centre of PCB outline): (±47.631, +27.500) and (0, −55.000)
- **HARD LIMIT: max 17 mm component height on front, 3 mm on back** (back side is solder fillets only)

### Module list (preliminary)

| Function | Component | Interface | Status |
|---|---|---|---|
| MCU | ESP32-C6 SuperMini | — | tentative |
| Air quality combo | Sensirion SEN66 | I²C via JST GH cable | tentative |
| Presence | HiLink LD2410B/C | UART @ 256000 baud | tentative |
| Ambient light | Vishay VEML7700 | I²C | tentative |
| Visual indicator | WS2812B (PLCC4) | 1-wire RMT | tentative |
| NFC dynamic tag | NXP NT3H2211 + PCB trace antenna | I²C + NFC | tentative |
| Power input | TVS + PTC + 24V terminal block | — | tentative |
| Buck 24V → 5V | TBD (TPS62933 / MP2451 candidates) | — | tentative |
| Buck 24V → 3.3V | TBD (TPS62840 / MP2315 candidates) | — | tentative |
| External I²C ESD | TBD (PESD3V3L4UG candidate) | — | tentative |
| Flashing | Native USB-C on ESP32-C6 | USB 2.0 | tentative |
| Debug | SWD / UART header (unpopulated by default) | — | tentative |

### Architectural decisions (current)
- **SEN66 mounts on the enclosure cover**, NOT on the PCB. Reason: SEN66 height (21.5 mm) exceeds front-side component limit (17 mm). Connected to PCB via short JST GH 6-pin cable (~50 mm).
- **Sensor zone below electronics** (PCB flat on bottom edge). Reason: natural convection lifts heat from MCU / power section upward, away from the SEN66 air intake.
- **Connector strip along bottom flat**: 24V terminal, USB-C, SWD header, Qwiic, JST GH to SEN66. Pre-defined positions exist in the manufacturer DXF; the case has matching cutouts / access.
- **Thermal isolation slots** (1.5 mm milled gaps in FR4) separate Power, MCU, and peripheral zones.
- **Shared I²C bus**: SEN66 (0x6B), VEML7700 (0x10), NT3H2211 (0x55). Pull-ups 4.7 kΩ on MCU side.
- **Bluetooth proxy** = software-only; no extra hardware.

### Tentative ESP32-C6 pinout

| Pin | Function |
|---|---|
| GPIO 6 | I²C SDA |
| GPIO 7 | I²C SCL |
| GPIO 16 | UART1 TX → LD2410 RX |
| GPIO 17 | UART1 RX ← LD2410 TX |
| GPIO 4 | LD2410 OUT (presence interrupt) |
| GPIO 8 | WS2812 DIN |
| GPIO 5 | NT3H2211 FD (NFC field detect interrupt) |
| USB D+/D− | Native USB-C |

Pinout must be validated against ESP32-C6 SuperMini strap / boot pin constraints.

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
- `sensor.veml7700`
- `light.neopixelbus` (WS2812B with breathing effect)
- `bluetooth_proxy`

---

## Hard constraints (do not violate without an explicit, documented decision)

1. Maximum **17 mm** component height on the front side of the PCB
2. Maximum **3 mm** on the back side (solder fillets only — no components)
3. **Ø120 mm D-shape** PCB outline from the manufacturer DXF
4. **3× M3 mounting holes** at positions defined in the DXF
5. **24V DC** input only (no 12V, no external 5V)
6. **ESP32-C6** as MCU (no fallback to C3 / S3)
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
- ❌ Display (OLED / LCD)
- ❌ IR transmitter / receiver
- ❌ Microphone / acoustic sensor

---

## Open work / TODO

### Hardware
- [ ] Select specific buck converter ICs (validate efficiency, JLCPCB Basic Library availability)
- [ ] NFC antenna design (PCB spiral geometry, matching capacitor selection)
- [ ] Validate ESP32-C6 SuperMini pinout against strap pin and boot mode constraints
- [ ] Decide whether VEML7700 placement requires its own thermal isolation slot
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
│   │   ├── oas.kicad_pro
│   │   ├── oas.kicad_sch
│   │   ├── oas.kicad_pcb
│   │   └── libraries/            # custom symbols and footprints
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
- Prefer **JLCPCB Basic Library** parts (free assembly) and Extended Library (~$3 setup fee) where they pass the two pillars
- Report part numbers and current availability when proposing components
- Validate prices in production quantity; do not propose parts known to be EOL or perpetually out of stock

### Validation
- Schematic: run ERC, fix or document every warning
- PCB: run DRC at production rules, verify 3D view against the 17 mm height constraint
- BOM: cross-check against manufacturer stock the same day as ordering
- Firmware: validate ESPHome config compiles cleanly before tagging a release

---

## Reference links

- AirGradient ONE (open-source inspiration): https://github.com/airgradienthq/arduino
- Sensirion SEN66 product page: https://sensirion.com/products/catalog/SEN66
- Sensirion SEN6x datasheet: https://sensirion.com/resource/datasheet/SEN6x
- HiLink LD2410 documentation and UART protocol: https://www.hlktech.net
- NXP NT3H2x11 antenna design AN11203: https://www.nxp.com
- Vishay VEML7700 datasheet
- SZOMK enclosures: https://www.chinaenclosure.com
- ESPHome documentation: https://esphome.io
- JLCPCB component library: https://jlcpcb.com/parts

---

## Changelog

- **v0.1** — Initial draft: project named (Open Ambient Sensor, OAS), module identification, layout strategy, dimensional analysis based on manufacturer DXF, orientation decision (flat edge on bottom for thermal convection), design philosophy formalized (measurement quality + aesthetic acceptability), third-party IP rules established (Rule 6)
