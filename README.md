# OAS — Open Ambient Sensor

**DIY multi-sensor environmental monitor for indoor spaces.** Measures air quality and presence; mounts on a standard wall-recessed electrical box; runs ESPHome and integrates natively with Home Assistant.

[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg?style=flat-square)](./GPLv3-LICENSE.md)
[![Status: v0.51 prototypes ordered](https://img.shields.io/badge/Status-v0.51%20prototypes%20ordered-orange?style=flat-square)](#status)
[![MCU: ESP32-C6](https://img.shields.io/badge/MCU-ESP32--C6-green?style=flat-square)](#hardware-overview)
[![Framework: ESPHome](https://img.shields.io/badge/Framework-ESPHome-orange?style=flat-square)](https://esphome.io)

---

## Status

**v0.53 design complete and fully routed; first prototypes bench-tested.** The v0.51 prototype batch (5 units, JLCPCB SMT) was delivered and brought up on the bench: the firmware (5-package ESPHome config + web_server dashboard) runs on real hardware, the SEN66 delivers live CO₂/PM/VOC/NOx/T/RH readings (after an SDA/SCL cable-mirror fix now baked into the v0.53 board — see CLAUDE.md Lesson 21), the LED ring and Wi-Fi/OTA/Home Assistant integration work. The v0.53 revision folds in the bring-up findings: the SEN66 now recesses through a PCB cutout so the enclosure lid closes, a cable pass-through slot feeds its lead, the DevKit moved clear of the bulk capacitors, and the board was fully re-routed from scratch (DRC 0 violations / 0 unconnected; JLCPCB DFM 0 Danger). The board has since been re-routed again, after the presence connector was reworked for the HLK-LD2410C and the radar's UART was moved off the ESP32's console pins (which the DevKit shares with its USB-UART bridge): DRC 0 violations / 0 unconnected. Verification pipeline: 35 stages, `build.py` 35/35 PASS. A fresh JLCPCB DFM pass is still owed on these gerbers before ordering. See [`CLAUDE.md`](./CLAUDE.md) for the design rationale, hard constraints, and lessons learned.

---

## Can I build one today?

**Short answer: you *can*, but you probably want to wait for the v1 validation milestone.**

- **The design is complete and routed, but not yet DFM-checked at this revision.** The committed production files under [`hardware/output/jlcpcb/`](./hardware/output/jlcpcb/) describe the fully-routed board and are regenerated and verified by the 35-stage pipeline on every build — but the manual JLCPCB DFM pass has not been re-run since the presence-connector rework, so wait for that before ordering from them.
- **It is a partially validated prototype.** The v0.51 batch was powered, flashed, and bench-tested: power chain, SEN66 air-quality readings, LED ring, Wi-Fi/OTA and Home Assistant integration all work. Still open: the presence radar (two HLK-LD2410B samples from different sellers both had a mute UART with a working presence pin, which is why the design moved to the LD2410C) and the v0.53 mechanical changes (SEN66 recess depth, cable-slot ergonomics) which exist only in CAD until the next batch is manufactured. The Bluetooth proxy, disabled during bring-up after a boot crash-loop, is enabled again (the bug was in the config's own BLE kill-switch, GitHub issue #4). Early adopters should wait for the v1 validation milestone before ordering.
- **Cost positioning.** OAS deliberately sits above bargain-DIY BOM cost: a calibrated Sensirion SEN66 combo sensor, an mmWave radar with stillness detection, and a commercial-grade injection-moulded enclosure are all premium choices made on purpose — see [Design philosophy](#design-philosophy). If lowest possible cost is your priority, other open-source projects optimise for that instead.

When hardware validation lands, this section will be replaced by a build guide (ordering, enclosure sourcing, flashing, Home Assistant onboarding). Flashing and Home Assistant integration are already documented in [`firmware/README.md`](./firmware/README.md); open work is tracked in the [TODO list](./CLAUDE.md#open-work--todo) in `CLAUDE.md`.

---

## What it measures

- **Air quality** — CO₂, PM1 / PM2.5 / PM4 / PM10, VOC index, NOx index, temperature, relative humidity (Sensirion SEN66)
- **Occupancy / presence** — mmWave radar with stillness detection (HiLink HLK-LD2410C)

## Additional features

- 7× SK6812-SIDE RGB AQI ring with breathing effect (7 LEDs on an 8-slot ring; D13 vacated for the J1 24 V terminal); colour reflects an aggregated air-quality index
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
| Presence | HiLink HLK-LD2410C | UART @ 256000 baud |
| Visual indicator | 7× SK6812-SIDE side-emit ring (Ø26 mm base pitch, 8 slots with D13 vacated for J1) | 1-wire WS281x on GPIO 8 |
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
│   │   ├── packages/               # core / leds / air-quality / presence / bt-proxy
│   │   └── examples/               # anonymized per-device override examples
│   └── secrets.yaml.example
└── hardware/
    ├── kicad/
    │   ├── build.py                # THE single entrypoint — emits sources + runs the 35-stage pipeline
    │   ├── boardgen/               # source of truth — generators for every .kicad_* file
    │   ├── pipeline/               # 35 verification/export stages (generic / oas / jlcpcb)
    │   ├── tests/                  # unit-test suite (pytest; run by stage 16 of build.py)
    │   ├── tools/                  # manual-trigger scripts (route extract, DFM upload, jlcparts cache)
    │   ├── oas_routes.py           # routing snapshot (replayed onto the generated PCB)
    │   ├── lcsc_mapping.py         # SMD BOM — LCSC SKU source of truth
    │   └── oas.kicad_*             # generated KiCad project files (derived artefacts — never hand-edit)
    ├── renders/                    # generated previews (PNG + SVG, visual changelog)
    └── output/                     # production deliverables (ibom + jlcpcb/ ZIP + BOM + 2× CPL)
```

---

## Rebuilding the design from source

The KiCad project is **fully script-generated**. The `.kicad_pcb` / `.kicad_sch` / `.kicad_pro` / library files are derived artefacts — **never hand-edit them**; the next build overwrites every edit. The source of truth lives in [`hardware/kicad/boardgen/`](./hardware/kicad/boardgen/) (Python generators), [`lcsc_mapping.py`](./hardware/kicad/lcsc_mapping.py) (SMD BOM), and [`oas_routes.py`](./hardware/kicad/oas_routes.py) (routing snapshot).

```sh
cd hardware/kicad
python build.py
```

`build.py` is the only top-level entrypoint. It regenerates every KiCad source file bit-identically (deterministic v5 UUIDs — an unchanged tree produces an empty `git diff`) and then runs the full 35-stage verification pipeline: DRC, ERC, determinism self-check, analytical DC / ampacity / boot-strap / thermal / I²C-rise-time checks, ngspice SPICE simulations (buck soft-start, IEC 61000-4-5 surge, reverse polarity), unit tests, renders, and the vendor export stages that produce the JLCPCB deliverables. Any stage failure aborts the build.

**Requirements:**

- Python 3.11+
- KiCad 10 with `kicad-cli` on `PATH`
- `pip install mypy pytest cairosvg pygerber`
- `git submodule update --init` (kicad-skip, InteractiveHtmlBom, jlcparts, and other tools under `hardware/kicad/third_party/`)
- One-time jlcparts offline cache for the LCSC part-verification stage: `python hardware/kicad/tools/setup_jlcparts_cache.py` (~2 GiB download, expands to a local SQLite cache)

ngspice and the vendor SPICE models are downloaded automatically into a gitignored `.tmp/` directory on first run. Individual pipeline stages are independently runnable for debugging (e.g. `python pipeline/generic/03_drc.py`), but a committable state always comes from a full `build.py` pass.

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
- ESPHome documentation: <https://esphome.io>
- JLCPCB component library: <https://jlcpcb.com/parts>
