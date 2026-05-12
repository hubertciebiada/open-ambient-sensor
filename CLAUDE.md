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
| Air quality combo | Sensirion SEN66 | I²C via JST GH cable | tentative |
| Presence | HiLink LD2410B/C | UART @ 256000 baud | tentative |
| Visual indicator | onboard RGB NeoPixel on DevKitM-1 (GPIO 8) | 1-wire RMT | confirmed v0.4 (no external WS2812 needed) |
| NFC dynamic tag | **MIKROE-2462 NFC Tag 2 Click** (NXP NT3H2111 + onboard PCB antenna, mikroBUS) | I²C + NFC | confirmed v0.12 |
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
- `sensors.kicad_sch` — SEN66 JST-GH connector, LD2410 connector, NT3H2211 + NFC antenna, status LED (onboard WS2812 on DevKitM-1)
- `io.kicad_sch` — connector strip along the chord (24 V terminal, Qwiic, etc.)

**Placement guideline (NOT a hard constraint)**: as a starting heuristic, think of the PCB roughly as a clock face with power on the upper-left, MCU on the upper-right, and sensors filling the bottom half. The 24 V cable enters through the centre, so keeping the terminal block and reverse-polarity / fusing chain near it shortens the bare-conductor span. Power flowing roughly clockwise (centre → power → MCU → sensors) tends to keep rails short, but **components may cross any imagined boundary if the layout needs it**. SEN66 in particular is large and may span what would otherwise be the "sensors" region.

### Architectural decisions (current)
- **SEN66 mounts on the PCB inside the enclosure**, in the bottom-half region of the board (the largest contiguous area). Lies flat on its 55.2 × 25.6 mm **back face (clean, featureless)** with the **air-side face (55.2 × 25.6 mm, carrying both inlets + outlet + product label) facing UP** toward the AK-N-94 perforated cover. Body sticks 21.5 mm above PCB. Connector (ACES 51468-0064N-001 / JST-GHR-06V-S compatible, 6-pin 1.25 mm pitch) on the SEN66's +X short edge, radially inward toward PCB centre — cable runs horizontally to a PCB-mounted JST-GH socket. Required: lift hard constraint #1 from 17 mm to ≥22 mm in the SEN66 zone — verified per CASE-VERIFICATION-CHECKLIST §1 against the physical AK-N-94 sample. The 17 mm DXF annotation `正面限高 17mm` is most likely regional (mounting-boss periphery), not global. **PCB needs NO cutouts under SEN66** — openings face UP toward cover perforations, not down toward PCB.
- **SEN66 retention**: zip-tie strap mount. Four NPTH holes (Ø ~3 mm) in the PCB just outside the SEN66 footprint along the two long edges (Y < 0 and Y > 25.6 in SEN66-local frame). A zip-tie loops over the SEN66 body through each Y-paired hole, pulling the module flat onto the PCB. No 3D-printed bracket, no screws into the SEN66 body (which has no mounting features per Sensirion STEP files). Reversible / serviceable: cut the zip-tie to swap the sensor.
- **Zip-tie hole X-positions** (SEN66-local frame, X along 55.2 mm axis pointing toward connector): available "safe" corridors where the zip-tie band passes over the top face without crossing an opening: **X ∈ [18.22, 32.03]** (14 mm wide, between inlet zone at X ≤ 18.22 and outlet at X ≥ 32.03), and X ∈ [52.77, 55.2] (marginal, 2.4 mm wide). Recommended: Pair 1 at X ≈ 25 (mid-safe corridor); Pair 2 at X ≈ 50 (post-outlet, minor outlet rim shading <10% acceptable). Exact positions in chunk #5a.
- **Open: SEN66 airflow sealing**. Sensirion mechanical guidelines require inlet and outlet in **separate sealed channels** to prevent parasitic recirculation (outflow back into inlets through host case interior). With face-up mount in AK-N-94, both inlets and outlet share the cover air-space → potential recirculation. Mitigation options TBD: (a) foam shroud separating inlet zone from outlet zone, (b) baffle on cover interior, (c) accept residual recirculation as design compromise. Decision after physical AK-N-94 sample arrives.
- **Sensor zone below electronics** (PCB flat on bottom edge). Reason: natural convection lifts heat from MCU / power section upward, away from the SEN66 air intake.
- **Connector strip along bottom flat**: 24V terminal, JST GH to SEN66, LD2410 connector, Qwiic, optional unpopulated SWD/UART recovery header. **No external USB-C** (use DevKitM-1's onboard USB before enclosure is sealed). Pre-defined positions exist in the manufacturer DXF; the case has matching cutouts / access.
- **Thermal isolation slots** (1.5 mm milled gaps in FR4) separate Power, MCU, and peripheral zones.
- **Shared I²C bus**: SEN66 (0x6B), NT3H2111 (0x55, on MIKROE-2462 NFC Tag 2 Click), plus Qwiic expansion. Pull-ups **10 kΩ on MCU side** (per SEN66 datasheet §3.1 spec; v0.6 changed from 4.7 kΩ → 10 kΩ). Bus length kept <10 cm per Sensirion guidance (face-up PCB-mount eliminates the previous 50 mm cable, achieving <40 mm total).
- **Bluetooth proxy** = software-only; no extra hardware.

### ESP32-C6-DevKitM-1-N4 pinout (v0.4 final)

| Pin | Function | Notes |
|---|---|---|
| GPIO 6 | I²C SDA | shared bus: SEN66 (0x6B), NT3H2111 (0x55, on MIKROE-2462), Qwiic expansion |
| GPIO 7 | I²C SCL | shared bus, 4.7 kΩ pull-ups on MCU side |
| GPIO 16 | UART1 TX → LD2410 RX | 256000 baud |
| GPIO 17 | UART1 RX ← LD2410 TX | 256000 baud |
| **GPIO 2** | LD2410 OUT (presence interrupt) | safe non-strap input |
| **GPIO 3** | NT3H2211 FD (NFC field-detect interrupt) | safe non-strap input |
| GPIO 8 | WS2812 DIN (onboard NeoPixel) | strap pin but OK — LED defaults idle-low |
| GPIO 12 / 13 | Native USB-Serial-JTAG D+ / D− | wired to one of DevKitM-1's two USB-C ports; the other USB-C uses the onboard USB-to-UART bridge |

**Reserved / unavailable**:
- **GPIO 10, GPIO 11**: physically not bonded out on ESP32-C6FH4 (internal SiP flash uses these pins). Available on every external chip variant but NOT on MINI-1/SuperMini/XIAO/DevKitM-1 modules.
- **Strap pins (avoid for general I/O)**: GPIO 4 (MTMS), 5 (MTDI), 9 (BOOT button on DevKitM-1), 15 (boot-mode select).

**Available safe-non-strap spare GPIOs** (for future expansion beyond the 7 signals above): 0, 1, 14, 18, 19, 20, 21, 22, 23 — nine pins free.

See `docs/ARCHITECTURE.md` for the canonical pinout table including onboard hardware notes (power LED desolder plan, button accessibility, etc.).

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
- ❌ Display (OLED / LCD)
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
  - **Decision**: **Branch A** — SEN66 on PCB in natural orientation. Connector faces radially inward; openings face radially outward toward the AK-N-94 perforated cover. Eliminates: 50 mm JST-GH cable, 3D-printed cover bracket, one BOM line, one assembly step. I²C bus length drops from ~80 mm to <40 mm (better signal integrity, lower bus capacitance). Net BOM saving: ~€1.50/unit.
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
  - **New plan item: post-prototype desolder of DevKitM-1's power LED** (~30 mW saved). Conditional rework — triggered if first-prototype SEN66 SHT measurements show >0.1 °C bias attributable to MCU-sector dissipation. The LED is on the top side of the DevKitM-1 board, easily accessible with a hot-air rework station before the OAS enclosure is sealed. Added to `docs/CASE-VERIFICATION-CHECKLIST.md` post-prototype rework list.
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
