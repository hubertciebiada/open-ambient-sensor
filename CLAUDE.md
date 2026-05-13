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
- **Zip-tie hole X-positions** (SEN66-local frame, X along 55.2 mm axis pointing toward connector): available "safe" corridors where the zip-tie band passes over the top face without crossing an opening: **X ∈ [18.22, 32.03]** (14 mm wide, between inlet zone at X ≤ 18.22 and outlet at X ≥ 32.03), and X ∈ [52.77, 55.2] (marginal, 2.4 mm wide). Recommended: Pair 1 at X ≈ 25 (mid-safe corridor); Pair 2 at X ≈ 50 (post-outlet, minor outlet rim shading <10% acceptable). Exact positions in chunk #5a.
- **Open: SEN66 airflow sealing**. Sensirion mechanical guidelines require inlet and outlet in **separate sealed channels** to prevent parasitic recirculation (outflow back into inlets through host case interior). With face-up mount in AK-N-94, both inlets and outlet share the cover air-space → potential recirculation. Mitigation options TBD: (a) foam shroud separating inlet zone from outlet zone, (b) baffle on cover interior, (c) accept residual recirculation as design compromise. Decision after physical AK-N-94 sample arrives.
- **Sensor zone below electronics** (PCB flat on bottom edge). Reason: natural convection lifts heat from MCU / power section upward, away from the SEN66 air intake.
- **Connector strip along bottom flat**: 24V terminal, JST GH to SEN66, LD2410 connector, Qwiic, optional unpopulated SWD/UART recovery header. **No external USB-C** (use DevKitM-1's onboard USB before enclosure is sealed). Pre-defined positions exist in the manufacturer DXF; the case has matching cutouts / access.
- **Thermal isolation slots** (1.5 mm milled gaps in FR4) separate Power, MCU, and peripheral zones.
- **Shared I²C bus**: SEN66 (0x6B), NT3H1101 (0x55, on MIKROE-2462 NFC Tag 2 Click), plus Qwiic expansion. Pull-ups **10 kΩ on MCU side** (per SEN66 datasheet §3.1 spec; v0.6 changed from 4.7 kΩ → 10 kΩ). Bus length kept well inside the Sensirion <100 mm hard limit. Realized bus length on the v0.15 PCB is **~60 mm** (the v0.6 changelog assumption of "<40 mm total" turned out to be optimistic once the MCU, NFC, and SEN66 socket placements settled). Still comfortably within Sensirion's spec and far shorter than the previous off-PCB 80 mm via JST-GH cable.
- **Bluetooth proxy** = software-only; no extra hardware.

### ESP32-C6-DevKitM-1-N4 pinout (v0.4 final)

| Pin | Function | Notes |
|---|---|---|
| GPIO 6 | I²C SDA | shared bus: SEN66 (0x6B), NT3H1101 (0x55, on MIKROE-2462), Qwiic expansion |
| GPIO 7 | I²C SCL | shared bus, 10 kΩ pull-ups on MCU side (per SEN66 datasheet §3.1, v0.6) |
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
