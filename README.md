# OAS — Open Ambient Sensor

**DIY multi-sensor environmental monitor for indoor spaces.** Measures air quality and presence; mounts on a standard wall-recessed electrical box; runs ESPHome and integrates natively with Home Assistant.

[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg?style=flat-square)](./GPLv3-LICENSE.md)
[![Status: v0.40 prototype](https://img.shields.io/badge/Status-v0.40%20prototype-orange?style=flat-square)](#status)
[![MCU: ESP32-C6](https://img.shields.io/badge/MCU-ESP32--C6-green?style=flat-square)](#hardware-overview)
[![Framework: ESPHome](https://img.shields.io/badge/Framework-ESPHome-orange?style=flat-square)](https://esphome.io)

---

## Status

**v0.40 prototype.** First SMT-assembled boards (5 units) are in flight at JLCPCB. Firmware skeleton (5-package ESPHome config + web_server dashboard) is ready for first flash on delivery. See [`CLAUDE.md`](./CLAUDE.md) for the current design rationale, hard constraints, and the v0.40 saga (audit-15 → audit-16 → final order).

---

## What it measures

- **Air quality** — CO₂, PM1 / PM2.5 / PM4 / PM10, VOC index, NOx index, temperature, relative humidity (Sensirion SEN66)
- **Occupancy / presence** — mmWave radar with stillness detection (HiLink HLK-LD2410B)

## Additional features

- 11× SK6812-SIDE RGB AQI ring with breathing effect; colour reflects an aggregated air-quality index
- Dynamic NFC tag (NXP NT3H1101 on MIKROE-2462) — a phone tap reads live data and serves a dashboard URL
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
| Air quality combo | Sensirion SEN66-SIN-T | I²C (JST GH 6-pin cable) |
| Presence | HiLink HLK-LD2410B | UART @ 256000 baud |
| Visual indicator | 11× SK6812-SIDE side-emit ring (Ø22 mm pitch) | 1-wire WS281x on GPIO 8 |
| NFC dynamic tag | NXP NT3H1101 on MIKROE-2462 NFC Tag 2 Click | I²C 0x55 + NFC |
| Power input | 24 V DC terminal block + TVS + PTC + reverse-polarity P-FET | — |

**Enclosure:** SZOMK AK-N-94 (Ø128 mm perforated white ABS). PCB is a **Ø120 mm D-shape** with a flat chord along the bottom edge. Mounts on a standard wall-recessed electrical box (60 mm screw pitch).

Authoritative module metadata (EAN, MPN, datasheet URLs, derived dimensions) lives in [`hardware/kicad/boardgen/_project.py::EXTERNAL_MODULES`](./hardware/kicad/boardgen/_project.py). Pinout is in [`boardgen/_project.py::GPIO_ASSIGNMENTS`](./hardware/kicad/boardgen/_project.py). Full design rationale and hard constraints: [`CLAUDE.md`](./CLAUDE.md).

---

## Repository layout

```
open-ambient-sensor/
├── README.md                       # this file
├── CLAUDE.md                       # design rationale, hard constraints, working conventions
├── GPLv3-LICENSE.md
├── .gitignore
├── firmware/
│   ├── README.md                   # flashing + Home Assistant integration
│   ├── esphome/
│   │   ├── oas.yaml                # top-level ESPHome config
│   │   ├── packages/               # core / leds / air-quality / presence / nfc / bt-proxy
│   │   └── examples/               # anonymized per-device override examples
│   └── secrets.yaml.example
└── hardware/
    ├── kicad/                      # build.py + boardgen/ (SOT) + pipeline + generated KiCad sources
    ├── renders/                    # generated previews (PNG + SVG, visual changelog)
    └── output/                     # production deliverables (gerbers ZIP + BOM + pos CSV)
```

---

## Getting started

The board is at the v0.40 prototype stage. Once hardware lands and ESPHome flashes cleanly, this section will document:

- Ordering the PCB (gerbers in [`hardware/output/jlcpcb/oas-jlcpcb.zip`](./hardware/output/jlcpcb/), JLCPCB SMT assembly with [`hardware/output/jlcpcb/oas-BOM.csv`](./hardware/output/jlcpcb/) + [`oas-top-CPL.csv`](./hardware/output/jlcpcb/))
- Sourcing the SZOMK AK-N-94 enclosure
- Flashing the ESP32-C6 — see [`firmware/README.md`](./firmware/README.md)
- Adding the device to Home Assistant — see [`firmware/README.md`](./firmware/README.md)

In the meantime, follow the [open work / TODO](./CLAUDE.md#open-work--todo) list in `CLAUDE.md`.

---

## Contributing

Contributions are welcome once the design stabilises. Any change must clear both design pillars (measurement quality, aesthetic acceptability) and the hard constraints listed in [`CLAUDE.md`](./CLAUDE.md#hard-constraints-do-not-violate-without-an-explicit-documented-decision).

**This is a public repository** — see the [public-repository rules](./CLAUDE.md#-public-repository-rules) for the anonymisation and third-party-IP requirements that apply to every committed file.

---

## License

GNU General Public License v3.0 — see [`GPLv3-LICENSE.md`](./GPLv3-LICENSE.md).

---

## References

- AirGradient ONE (open-source inspiration): <https://github.com/airgradienthq/arduino>
- Sensirion SEN66 product page: <https://sensirion.com/products/catalog/SEN66>
- HiLink LD2410 documentation: <https://www.hlktech.net>
- NXP NT3H1101 datasheet: <https://www.nxp.com>
- ESPHome documentation: <https://esphome.io>
- JLCPCB component library: <https://jlcpcb.com/parts>
