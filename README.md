# OAS — Open Ambient Sensor

**DIY multi-sensor environmental monitor for indoor spaces.** Measures air quality, presence and ambient light; mounts on a standard wall-recessed electrical box; runs ESPHome and integrates natively with Home Assistant.

[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg?style=flat-square)](./GPLv3-LICENSE.md)
[![Status: Draft](https://img.shields.io/badge/Status-Preliminary%20Draft-orange?style=flat-square)](#status)
[![MCU: ESP32-C6](https://img.shields.io/badge/MCU-ESP32--C6-green?style=flat-square)](#hardware)
[![Framework: ESPHome](https://img.shields.io/badge/Framework-ESPHome-orange?style=flat-square)](https://esphome.io)

---

## Status

**Preliminary draft.** Components, layout, IC selections and pinouts are subject to change. Each decision in this repository is a working hypothesis to be validated. See [`CLAUDE.md`](./CLAUDE.md) for the current design rationale and constraints.

---

## What it measures

- **Air quality** — CO₂, PM1 / PM2.5 / PM4 / PM10, VOC index, NOx index, temperature, relative humidity (Sensirion SEN66)
- **Occupancy / presence** — mmWave radar with stillness detection (HiLink LD2410)
- **Ambient light** — lux (Vishay VEML7700)

## Additional features

- RGB status LED with breathing effect; colour reflects an aggregated air-quality index
- Dynamic NFC tag — a phone tap reads live data and serves a dashboard URL
- **Bluetooth proxy** — extends BLE range across the deployment for Home Assistant BLE integrations
- Qwiic / STEMMA QT expansion port — future sensors without a PCB respin

---

## Design philosophy

The open-source DIY space offers many indoor-air-quality projects. Most optimise aggressively for cost. **OAS holds two priorities non-negotiable**, even when the trade-off is a higher per-unit BOM than the cheapest alternatives:

1. **Measurement quality.** Sensor choices favour accuracy and long-term stability over price.
2. **Aesthetic acceptability.** The device is meant to live in inhabited rooms; a commercial-grade injection-moulded enclosure replaces the typical 3D-printed box.

Both compromises (cheap-but-inaccurate, accurate-but-ugly) are rejected. See [`CLAUDE.md`](./CLAUDE.md) for the full rationale and the hard constraints any change must clear.

---

## Hardware overview

| Function | Component | Interface |
|---|---|---|
| MCU | ESP32-C6-DevKitM-1-N4 (EAN 5904422385651) | 2× USB-C on module |
| Air quality combo | Sensirion SEN66 | I²C (JST GH cable, mounts on cover) |
| Presence | HiLink LD2410B/C | UART @ 256000 baud |
| Ambient light | Vishay VEML7700 | I²C |
| Visual indicator | onboard RGB NeoPixel on DevKitM-1 (GPIO 8) | 1-wire RMT |
| NFC dynamic tag | NXP NT3H2211 + PCB trace antenna | I²C + NFC |
| Power input | 24 V DC terminal block + TVS + PTC | — |

**Enclosure:** SZOMK AK-N-94 (Ø128 mm perforated white ABS). PCB is a **Ø120 mm D-shape** with a flat chord along the bottom edge so the sensor zone sits below the electronics — natural convection lifts heat away from the SEN66 intake.

For the full module list, pinout and architectural decisions, see [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) and [`docs/BOM.md`](./docs/BOM.md).

---

## Repository layout

```
open-air-sensor/
├── hardware/
│   ├── case/                     # 3D bracket for SEN66 (own work); manufacturer DXF kept local
│   ├── kicad/                    # schematic, PCB, project libraries
│   ├── bom/                      # production BOMs (JLCPCB, Mouser, misc)
│   └── gerbers/                  # production output
├── firmware/
│   ├── esphome/                  # ESPHome YAML — base config, packages, examples
│   ├── secrets.yaml.example
│   └── README.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── BOM.md
│   ├── ASSEMBLY.md
│   ├── FLASHING.md
│   └── HA-INTEGRATION.md
├── CLAUDE.md                     # design rationale, hard constraints, working conventions
├── GPLv3-LICENSE.md
└── README.md
```

---

## Getting started

The project is in **preliminary draft** — no prototype has been built yet. Once hardware is validated, this section will document:

- Ordering the PCB (gerbers + JLCPCB assembly)
- Sourcing the SZOMK AK-N-94 enclosure
- Flashing the ESP32-C6 with ESPHome
- Adding the device to Home Assistant

In the meantime, follow the [open work / TODO](./CLAUDE.md#open-work--todo) list in `CLAUDE.md`.

---

## Contributing

Contributions are welcome once the design stabilises. Any change must clear both design pillars (measurement quality, aesthetic acceptability) and the hard constraints listed in [`CLAUDE.md`](./CLAUDE.md#hard-constraints-do-not-violate-without-an-explicit-documented-decision).

**This is a public repository** — see the [public-repository rules](./CLAUDE.md#-critical-public-repository-rules) for the anonymisation and third-party-IP requirements that apply to every committed file.

---

## License

GNU General Public License v3.0 — see [`GPLv3-LICENSE.md`](./GPLv3-LICENSE.md).

---

## References

- AirGradient ONE (open-source inspiration): <https://github.com/airgradienthq/arduino>
- Sensirion SEN66 product page: <https://sensirion.com/products/catalog/SEN66>
- HiLink LD2410 documentation: <https://www.hlktech.net>
- NXP NT3H2x11 antenna design AN11203: <https://www.nxp.com>
- ESPHome documentation: <https://esphome.io>
- JLCPCB component library: <https://jlcpcb.com/parts>
