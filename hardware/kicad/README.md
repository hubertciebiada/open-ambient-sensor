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

- **Board outline on `Edge.Cuts`:** Ø120 mm circular arc (R=60 mm) + flat chord 82.65 mm (precise: 82.6545 mm from the DXF). Origin (0, 0) is the centre of the circle. The flat chord sits at Y≈+43.50 — in KiCad's coordinate convention (Y grows downward on screen), that's the visual **bottom** of the board.
- **3× M3 mounting holes (NPTH)**: Ø3.8 mm drill, no copper pad, on a pitch circle Ø110 mm. Positions:
  - H1: (+47.631, +27.500) — bottom-right
  - H2: (−47.631, +27.500) — bottom-left
  - H3: (0, −55.000) — top (opposite the chord)
- **Cable pass-through hole**: Ø12 mm circular cut-out on `Edge.Cuts` at the PCB centre (origin) — 24 V power wires enter from the rear of the case, pass through to a terminal block on the front side. Sized for 3× 1.5 mm² conductors with margin.
- **5× connector cutout keepout zones** on F.Cu + B.Cu blocking tracks, vias, pads, copperpour and footprints — one per case-wall cutout. See [`../case/README.md`](../case/README.md#connector-cutouts-in-the-case-wall-along-the-flat-chord) for the exact dimensions.
- **5× rectangle markers on `Dwgs.User`** labelled `C1…C5` with their size — visual reference for connector placement in pcbnew (this layer is not plotted).
- **Clock-face sector markers on `Dwgs.User`**: 3 dashed radial lines (12:00, 03:00, 09:00 azimuths) + 3 labels (`POWER`, `MCU`, `SENSORS`). Sectors map onto the hierarchical schematic sheets and define where each subsystem's components belong on the PCB. See [`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md#pcb-sector-layout) for the rationale.
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

## How to regenerate everything

The single entry point for any change is **`regenerate.py`**:

```bash
python regenerate.py
```

That script:
1. runs `generate.py` to rebuild every KiCad source file from the Python geometry constants;
2. runs `kicad-cli pcb drc` and `kicad-cli sch erc` (aborts on any error / warning);
3. re-renders every preview into `renders/`:
   - `2d-top.{svg,png}` — production-style top view (F.Cu + masks + silks + Edge.Cuts)
   - `2d-cutouts.{svg,png}` — Edge.Cuts + Dwgs.User cutout markers + F.Cu (no-go zones)
   - `2d-bottom.{svg,png}` — mirrored bottom view
   - `3d-top.png` — raytraced 3D render (~15 s)
   - `_drc.rpt` / `_erc.rpt` — text reports of DRC / ERC results

Typical run time: ~30 s (dominated by the 3D render).

**UUIDs are deterministic** (v5 namespaced under the OAS project), so re-running with no source changes produces a **bit-identical** `oas.kicad_pcb` — `git diff` is empty unless geometry actually changed.

### When to use `generate.py` directly

Almost never. `regenerate.py` is the canonical entry point. The one case where `generate.py` alone makes sense is if you want a quick smoke test of a `generate.py` change without paying for the 3D render.

### Changing geometry

Edit the constants at the top of `generate.py`:

- `R_OUTLINE`, `CHORD`, `HALF_CHORD` — PCB outline
- `HOLE_DIAMETER`, `PAD_DIAMETER`, `R_PITCH` — mounting holes
- `CUTOUTS` — list of `(name, x_min, x_max, y_min, y_max)` for the case-wall cutouts
- `PAGE_CENTRE_X`, `PAGE_CENTRE_Y` — page-space offset (you almost never want to change this)

For structural / material changes (layer count, stackup, design rules, footprint definitions), edit the relevant generator function further down in `generate.py`.

After editing, run `python regenerate.py` and commit the resulting diff (sources + KiCad files + renders together — they are one logical change).

The geometry constants currently match the SZOMK AK-N-94 manufacturer DXF (see [`../case/README.md`](../case/README.md)).

## Layout strategy

The PCB orientation in KiCad matches the physical wall-mount orientation:

- **Bottom edge** (flat chord, Y=+43.5) — connector strip: 24 V terminal, JST GH (to SEN66 on cover), SWD header (unpopulated), Qwiic (no external USB-C — DevKitM-1's onboard USB-C accessible before sealing)
- **Top half** — sensor zone: VEML7700, LD2410 mmWave radar
- **Middle** — MCU (ESP32-C6-DevKitM-1-N4, antenna toward 12:00) and status LED (onboard NeoPixel on GPIO 8)
- **Adjacent to the 24 V terminal** — power section (TVS, PTC, buck converters)

Thermal-isolation slots (1.5 mm milled gaps in FR4) will separate the Power, MCU and peripheral zones — to be drawn on `Edge.Cuts` once the floorplan is finalised.

See [`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) for the full pinout and thermal/layout rationale.

## What you'll do next (TODO)

Roughly in order:

1. **Schematic** (`oas.kicad_sch`) — place the ESP32-C6-DevKitM-1-N4 (EAN 5904422385651), SEN66 connector, LD2410 connector, VEML7700, NT3H2211, buck converters, TVS, PTC, 24 V terminal block, SWD/UART recovery header (unpopulated), Qwiic connector. No external USB-C and no external WS2812 — both are on the DevKitM-1 module. Net them up.
2. **Footprints** — assign footprints in the schematic (most parts are stock in `Connector_*`, `Sensor_*`, `Package_DFN_QFN`, `Package_SO`). The mounting holes already use the custom `oas:MountingHole_3.8mm_M3`.
3. **PCB layout** — update PCB from schematic, then place parts respecting:
   - 17 mm front-side height limit (5 mm back-side with washer-lifted PCB)
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
