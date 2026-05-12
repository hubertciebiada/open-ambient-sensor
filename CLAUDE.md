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
  - PCB: **Ø120 mm D-shape** (arc R=60 mm), flat chord **82.65 mm** along the bottom edge (chord Y from centre ≈ 43.50 mm; full precision 82.6545 mm in `generate.py`)
  - 3× M3 mounting holes (Ø3.8 mm, **NPTH**) on **pitch circle Ø110 mm**, trójkąt równoboczny with one hole opposite the chord (NPTH: screws go into plastic bosses, no metal chassis bonding)
  - Hole positions (origin = centre of PCB outline): (±47.631, +27.500) and (0, −55.000)
  - **Cable pass-through hole** Ø12 mm at PCB centre on `Edge.Cuts` — 24 V power enters from the rear of the case (electrical wall box behind the unit), passes through the PCB, terminates at a front-side terminal block. Sized for 3× 1.5 mm² conductors. Bare 24 V conductors stay inside the case (inaccessible from outside)
- **HARD LIMIT: max 17 mm component height on front, 5 mm on back** (back side mostly solder fillets; pin-header bottoms tolerated. Achieved by adding 2 mm washers under the mounting screws, lifting the PCB 2 mm off the enclosure mounting bosses)
- **MCU module: ESP32-C6-DevKitM-1-N4** (Espressif official devkit, ESP32-C6-MINI-1 SoM + **TWO USB-C ports** [one to onboard USB-UART bridge IC, one direct to ESP32-C6 native USB-Serial-JTAG] + buttons + onboard RGB NeoPixel + power LED). EAN: **5904422385651** (Botland), Espressif SKU `ESP32-C6-DevKitM-1-N4`. Form factor 48.26 × 25.4 mm. Chosen over generic "SuperMini" clones because of branded, deterministic pinout, full Espressif documentation, and verified availability through a Polish distributor.

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
| Flashing | Native USB-C on ESP32-C6 SuperMini (onboard module only, no case-wall connector) | USB 2.0 | confirmed v0.3 |
| Debug | SWD / UART header (unpopulated by default) | — | tentative |

### PCB sector layout (clock-face convention)

The PCB is divided into three angular sectors viewed from the front:

| Sector | Clock hours | Quadrant in KiCad coords | Contents |
|---|---|---|---|
| **POWER** | 09:00 → 12:00 | upper-left (X < 0, Y < 0) | terminal block J1, reverse-polarity protection, PTC fuse, TVS, bulk cap, Y-cap, bucks 24→5V→3.3V |
| **MCU + logic** | 12:00 → 03:00 | upper-right (X > 0, Y < 0) | ESP32-C6 SuperMini (antenna edge → 12:00), optional unpopulated SWD/UART recovery header, decoupling caps |
| **SENSORS** | 03:00 → 09:00 | bottom half (Y > 0) | SEN66 JST-GH connector, LD2410 connector, VEML7700, WS2812, NT3H2211 + NFC antenna, status LED |

Power flow runs **clockwise** (24 V enters through the centre → POWER sector → MCU sector → SENSORS sector) so signal paths and power rails never need to cross sector boundaries.

The `power.kicad_sch`, `mcu.kicad_sch`, `sensors.kicad_sch`, and `io.kicad_sch` hierarchical sheets mirror this layout — each schematic sheet maps directly to one sector on the PCB.

Three radial separator lines (12:00, 03:00, 09:00 azimuths) plus sector labels are drawn on `Dwgs.User` as a visual aid in pcbnew (not plotted to gerbers). The cable pass-through hole at the centre is the natural "0:00 position" — 24 V enters here.

### Architectural decisions (current)
- **SEN66 mounts on the enclosure cover**, NOT on the PCB. Reason: SEN66 height (21.5 mm) exceeds front-side component limit (17 mm). Connected to PCB via short JST GH 6-pin cable (~50 mm).
- **Sensor zone below electronics** (PCB flat on bottom edge). Reason: natural convection lifts heat from MCU / power section upward, away from the SEN66 air intake.
- **Connector strip along bottom flat**: 24V terminal, JST GH to SEN66, LD2410 connector, Qwiic, optional unpopulated SWD/UART recovery header. **No external USB-C** (use SuperMini's onboard USB before enclosure is sealed). Pre-defined positions exist in the manufacturer DXF; the case has matching cutouts / access.
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

**v0.3 pinout corrections** (after strap-pin verification):
- GPIO 4 → **GPIO 10** (LD2410 OUT) — GPIO 4 is MTMS strap pin
- GPIO 5 → **GPIO 11** (NT3H2211 FD) — GPIO 5 is MTDI strap pin
- GPIO 8 stays for WS2812 — uses the **onboard WS2812** of the ESP32-C6 SuperMini module (no external WS2812 needed for v1; an external WS2812 footprint may be added later as DNP if positioning becomes a concern)
- USB-C **removed from external connector strip** — flashing uses the SuperMini's own USB-C accessible at programming time (before enclosure is sealed); an unpopulated SWD/UART recovery header may be added for field-recovery edge cases

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
- ❌ Display (OLED / LCD)
- ❌ External USB-C connector on the case wall (use SuperMini's own USB-C for programming; OTA after first flash)
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

### KiCad schematic conventions

- **`no_connect` markers** on intentionally-unused IC pins. Without them, ERC warns "pin not connected". Use freely — they are documentation that says "this is deliberate, not an oversight." Common on ESP32-C6 SuperMini pins we don't wire (5V, GPIO8 when onboard WS2812 is used, unused GPIOs).
- **`(dnp yes)` flag** for footprints that should appear on the PCB but NOT in the assembly BOM. Use for hand-solder-on-demand parts (recovery headers, debug pads, optional features). The KiCad render shows a diagonal X overlay on the symbol to flag DNP visually. JLCPCB assembly will skip these.
- **Hierarchical labels** for inter-sheet signals (sub-sheet exports/imports). Direction tags (`input`/`output`/`bidirectional`) are documentation, not enforced by KiCad — but they help reviewers and matter when the root sheet adds matching sheet ports.
- **ERC warnings during incremental sheet build are expected**: when chunk N adds a sub-sheet with hierarchical labels, ERC will warn "label not connected to a sheet port" until the matching sub-sheet (chunk N+1 or later) declares the same label. These warnings are temporary and should resolve once the related sheets land. Document expected warnings in commit messages; don't treat them as bugs.

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
- Vishay VEML7700 datasheet
- SZOMK enclosures: https://www.chinaenclosure.com
- ESPHome documentation: https://esphome.io
- JLCPCB component library: https://jlcpcb.com/parts

---

## Changelog

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
  - Thermal trade-off vs a hypothetical bare ESP32-C6-MINI-1 module: ~30 mW extra dissipation from the always-on power LED. The USB-to-UART bridge IC is in **suspend mode** when no USB cable is plugged in (~10 µW — negligible) and we don't connect USB after deployment. With the LDO bypassed (we feed 3.3V directly from TPS62933 into the 3V3 pin), no LDO loss. ~30 mW in the MCU sector (upper-right of the PCB) is far from the SEN66 inlet (mounted on the cover, ~15-20 mm above PCB) — negligible bias on temperature/humidity measurements. Pillar #1 preserved.
  - **NEW rule in "Component selection" section: Module identification** — never use a generic module name alone in any project decision. Every module must be specified by EAN/GTIN, MPN, or a specific supplier URL. Verify each module's actual exposed GPIO before assigning signals, watch for chip-level pin omissions (e.g. ESP32-C6 with SiP flash omits GPIO 10/11), and read the official datasheet of the specific model — not the first random pinout from a web search.
  - **CRITICAL PINOUT BUG fix**: v0.3 prescribed "GPIO 4 → GPIO 10 / GPIO 5 → GPIO 11" as the strap-pin avoidance fix. This was incorrect — **GPIO 10 and GPIO 11 don't exist as bonded pins on any ESP32-C6 variant with internal SiP flash** (MINI-1, SuperMini, XIAO, DevKitM-1 all use ESP32-C6FH4 with internal flash). Those pins serve internal flash communication. Of the chip's nominal 30 GPIOs, only 22 are physically available externally. The bug took 4 review passes to catch because no reviewer verified physical chip pinout against the assumed pin numbers — captured as a new convention rule.
  - **Pinout v0.4 corrections**: LD2410_OUT → **GPIO 2** (was GPIO 4 → bad strap, then GPIO 10 → non-existent), NFC_FD → **GPIO 3** (was GPIO 5 → bad strap, then GPIO 11 → non-existent). Both GPIO 2 and 3 are safe non-strap, non-USB pins available on every ESP32-C6 variant. ARCHITECTURE.md pinout table and `mcu.kicad_sch` must be updated to reflect this before further chunks proceed.
