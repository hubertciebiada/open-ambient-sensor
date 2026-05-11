# KiCad project — OAS

Base KiCad 10.x project for the Open Ambient Sensor PCB. **Preliminary draft** — board outline and mounting holes only; schematic and routing are TODO.

## How to open

1. Install **KiCad 10.0.2** or newer from <https://www.kicad.org/download/>.
2. Open `oas.kicad_pro` in KiCad.
3. The project will load:
   - `oas.kicad_sch` — empty schematic (placeholder)
   - `oas.kicad_pcb` — board outline + 3 mounting holes on `Edge.Cuts`
   - Local footprint library `oas` (just the custom `MountingHole_3.8mm_M3` for now)

When KiCad opens the PCB the first time it may ask you to migrate the project — accept; the file format is already at v10.

## What's already in `oas.kicad_pcb`

- **Board outline on `Edge.Cuts`:** Ø120 mm circular arc (R=60 mm) + flat chord 82.6 mm. Origin (0, 0) is the centre of the circle. The flat chord sits at Y=+43.524 — in KiCad's coordinate convention (Y grows downward on screen), that's the visual **bottom** of the board.
- **3× M3 mounting holes**: Ø3.8 mm drill, Ø6.5 mm annular pad on F.Cu/B.Cu, on a pitch circle Ø110 mm. Positions:
  - H1: (+47.631, +27.500) — bottom-right
  - H2: (−47.631, +27.500) — bottom-left
  - H3: (0, −55.000) — top (opposite the chord)
- **Stackup:** 2-layer, FR-4 1.6 mm, 1 oz (35 µm) copper, white solder mask, black silkscreen, HASL lead-free finish.
- **JLCPCB-compatible design rules:** min trace/space 0.15 mm, min via 0.5 mm Ø / 0.3 mm drill, min hole 0.3 mm, edge clearance 0.3 mm.

## Material and stackup decisions (and why)

You said you've never done a PCB — here's the rationale for every choice. Anything below can be changed in `oas.kicad_pro` (design rules) or in `oas.kicad_pcb`'s `(setup (stackup ...))` block.

| Choice | Value | Why |
|---|---|---|
| **Layer count** | 2 | Sufficient for ESP32-C6 + I²C + UART + WS2812. 4-layer is overkill for this design and costs ~1.5× more at JLCPCB. Can be bumped if noise becomes an issue in v2. |
| **Board thickness** | 1.6 mm | JLCPCB default, free; mechanically rigid for a Ø120 mm board. |
| **Material** | FR-4, Tg ≥ 130 °C | JLCPCB Standard FR-4 (Tg 135–150). Fine for 24 V DC, low currents, no thermal stress. |
| **Copper weight** | 1 oz (35 µm) | JLCPCB default, free. Adequate for ≤ 3 A peak on power traces. |
| **Solder mask colour** | **White** | **Aesthetic match with the white perforated ABS enclosure** (CLAUDE.md design pillar 2 — aesthetic acceptability). White mask at JLCPCB costs a small premium over green but is worth it here. |
| **Silkscreen colour** | Black | Standard, high contrast on white mask. |
| **Surface finish** | HASL lead-free | JLCPCB default, free. ENIG would look nicer but adds ~$15 to a small batch and the pads aren't visible in the enclosure anyway. |
| **Min trace / space** | 0.15 mm (6 mil) | JLCPCB Standard rules. Going finer (4 mil) costs more without benefit on this design. |
| **Min via** | 0.5 mm Ø / 0.3 mm drill | JLCPCB Standard rules. |
| **Min hole** | 0.3 mm | JLCPCB Standard rules. |
| **Edge clearance** | 0.3 mm | JLCPCB tolerance for the routed board edge. |

If you want a quote, upload the gerbers (once generated — TODO) to <https://jlcpcb.com>. With these defaults the board falls in JLCPCB's cheapest tier (~$2–5 per unit at quantity 5–10, plus shipping).

## How to regenerate the files

If you want to change geometry (e.g. different mounting-hole pitch, different chord length, different hole diameter), edit constants at the top of `generate.py` and run:

```bash
python generate.py
```

The script regenerates `oas.kicad_pcb`, `oas.kicad_sch`, `oas.kicad_pro`, the footprint library and the lib-tables. Generated UUIDs change every run — review the diff before committing.

The geometry constants currently match the SZOMK AK-N-94 manufacturer DXF (see [`../case/README.md`](../case/README.md)).

## Layout strategy

The PCB orientation in KiCad matches the physical wall-mount orientation:

- **Bottom edge** (flat chord, Y=+43.5) — connector strip: 24 V terminal, USB-C, JST GH (to SEN66 on cover), SWD header, Qwiic
- **Top half** — sensor zone: VEML7700, LD2410 mmWave radar
- **Middle** — MCU (ESP32-C6 SuperMini) and status LED (WS2812)
- **Adjacent to the 24 V terminal** — power section (TVS, PTC, buck converters)

Thermal-isolation slots (1.5 mm milled gaps in FR4) will separate the Power, MCU and peripheral zones — to be drawn on `Edge.Cuts` once the floorplan is finalised.

See [`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) for the full pinout and thermal/layout rationale.

## What you'll do next (TODO)

Roughly in order:

1. **Schematic** (`oas.kicad_sch`) — place the ESP32-C6 SuperMini, SEN66 connector, LD2410 connector, VEML7700, WS2812, NT3H2211, buck converters, TVS, PTC, 24 V terminal block, USB-C, SWD header, Qwiic connector. Net them up.
2. **Footprints** — assign footprints in the schematic (most parts are stock in `Connector_*`, `Sensor_*`, `Package_DFN_QFN`, `Package_SO`). The mounting holes already use the custom `oas:MountingHole_3.8mm_M3`.
3. **PCB layout** — update PCB from schematic, then place parts respecting:
   - 17 mm front-side height limit (3 mm back-side)
   - SEN66 is **not on the PCB** (mounted on cover, JST GH cable to a header)
   - Connector strip along the flat chord
   - Thermal-isolation slots between zones
4. **Run DRC** at JLCPCB rules; fix violations.
5. **3D view** — check no component exceeds 17 mm.
6. **Generate gerbers** (`File → Fabrication Outputs → Gerbers`) into `../gerbers/`.

## Files in this directory

```
hardware/kicad/
├── README.md                                    # this file
├── generate.py                                  # script that built the project
├── oas.kicad_pro                                # project (design rules, net classes)
├── oas.kicad_sch                                # empty schematic
├── oas.kicad_pcb                                # PCB with outline + mounting holes
├── fp-lib-table                                 # registers the "oas" footprint library
├── sym-lib-table                                # empty symbol library table
└── libraries/
    └── oas.pretty/
        └── MountingHole_3.8mm_M3.kicad_mod      # custom footprint matching the DXF
```
