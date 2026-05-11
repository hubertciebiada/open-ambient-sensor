# Enclosure — SZOMK AK-N-94

The OAS reference enclosure is the **SZOMK AK-N-94** — a Ø128 mm perforated white ABS housing with a smoke-detector form factor.

## What is in this directory

This directory contains **own work** only:

- `sen66-bracket.stl` — 3D bracket for mounting the Sensirion SEN66 on the inside of the enclosure cover (TODO — see open work in `CLAUDE.md`)
- Any other derived dimension drawings or own 3D models

## What is NOT in this directory

Manufacturer-supplied files are **not redistributable through this public repository** (see Rule 6 in [`CLAUDE.md`](../../CLAUDE.md#rule-6--third-party-intellectual-property)). The following files are deliberately excluded and gitignored:

- Manufacturer DXF dimension drawings (`*.dxf`)
- Manufacturer datasheets (`*-datasheet.pdf`)
- Manufacturer STEP files (`manufacturer-*.step`)

## How to obtain the manufacturer files

The DXF and datasheet are available directly from SZOMK:

1. Visit <https://www.chinaenclosure.com>
2. Search for **AK-N-94** in the enclosure catalogue
3. Request the dimension DXF and the product datasheet from the supplier
4. Place the files locally in this directory — the patterns above are already in `.gitignore`

## Derived dimensions (used in KiCad)

Measured from the manufacturer DXF and copied into our own KiCad board outline (own work, committable):

- **PCB outline:** Ø120 mm D-shape (arc R=60 mm)
- **Flat chord:** 82.65 mm along the bottom edge (full precision 82.6545 mm from DXF line measurement; chord Y from centre = 43.498 mm)
- **Mounting holes:** 3× M3 (Ø3.8 mm, **NPTH**) on **pitch circle Ø110 mm** (R=55 mm), trójkąt równoboczny with one hole opposite the chord. NPTH because the screws thread into plastic bosses in the AK-N-94 — no metal chassis to bond to, so a copper pad would just be floating copper.
- **Cable pass-through:** Ø12 mm hole in the geometric centre of the PCB (origin). 24 V power (and optional PE) wires enter the case from the rear (electrical box behind the unit), pass through this hole, and terminate at a terminal block mounted on the front side of the PCB. Sized for 3× 1.5 mm² conductors (e.g. YDY 3×1.5, outer Ø ≈ 8–9 mm) with margin. Keeping the wire entry inside the PCB outline shields the bare conductors — they are inaccessible from outside the enclosure.
- Hole positions (origin = centre of the PCB outline):
  - H1: (+47.631, +27.500) — bottom-right (near chord)
  - H2: (−47.631, +27.500) — bottom-left (near chord)
  - H3: (0, −55.000) — top (opposite the chord)
- **Front-side component-height limit:** 17 mm (per manufacturer DXF annotation 正面限高 17mm)
- **Back-side component-height limit:** 3 mm (per manufacturer DXF annotation 背面焊脚限高 3mm — "back-side solder-pin height limit")

These are encoded in `../kicad/oas.kicad_pcb` and the regeneration script `../kicad/generate.py`.

## Connector cutouts in the case wall (along the flat chord)

The AK-N-94 has **5 rectangular cutouts** in the case wall at the chord position. Connectors mounted on the PCB extend through these cutouts. The cutouts are encoded as **keepout zones** in `oas.kicad_pcb` so that no traces, vias, pads or footprints can accidentally be placed in the area where a connector body must sit, and as **rectangles on `Dwgs.User`** for visual reference in pcbnew.

Coordinates are PCB-local (origin = centre of the PCB outline; +Y is toward the chord = visually downward in pcbnew):

| # | X range (mm) | Y range (mm) | Size (W × H) | Position vs. chord |
|---|---|---|---|---|
| C1 | −33.8 → −21.8 | +31.5 → +42.5 | 12.0 × 11.0 | fully inside PCB |
| C2 | −16.8 → −1.1  | +27.2 → +43.5 | 15.7 × 16.3 | clipped at chord (would extend 3 mm beyond) |
| C3 | +4.9  → +13.9 | +29.0 → +43.5 | 9.0 × 14.5  | clipped at chord (would extend 1 mm beyond) |
| C4 | +18.9 → +22.9 | +35.0 → +43.5 | 4.0 × 8.5   | clipped at chord (has language tab Ø3 mm in case wall above) |
| C5 | +27.9 → +35.4 | +36.5 → +42.5 | 7.5 × 6.0   | fully inside PCB |

Names (C1…C5) are placeholders — the final connector assignment (USB-C, terminal 24 V, JST GH to SEN66, SWD header, Qwiic) will be decided during schematic + layout.

The C4 language tab (Ø3 mm semicircle in the case wall, above the chord) is not drawn in the KiCad file — it sits outside the PCB outline and has no implication for PCB design.
