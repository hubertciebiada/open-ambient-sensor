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

Once measured from the manufacturer DXF and copied into our own KiCad board outline (own work, committable):

- **PCB outline:** Ø120 mm D-shape
- **Flat chord:** 82.6 mm along the bottom edge
- **Mounting holes:** 3× M3 (Ø3.8 mm) at the positions defined in the DXF
- **Front-side component-height limit:** 17 mm
- **Back-side component-height limit:** 3 mm (solder fillets only — no components)
