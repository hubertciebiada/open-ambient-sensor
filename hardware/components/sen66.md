# Sensirion SEN66 — air quality sensor module

Primary air-quality sensor for OAS. Combo module: PM (1 / 2.5 / 4 / 10), CO2, VOC index,
NOx index, temperature, relative humidity. Fan-driven sampling with Sensirion's patented
sheath-flow optical bench. Datasheet-and-app-note verified against Sensirion source
documents (datasheet v0.92 Dec 2025, mechanical guide v0.92 Jan 2026, temperature
compensation app note v1.1 Jan 2026).

## Identifiers

| Field                    | Value                                                                                                                                          |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| MPN                      | `SEN66-SIN-T`                                                                                                                                  |
| Sensirion material no.   | `3.001.030`                                                                                                                                    |
| Engineering-sample MPN   | `SEN66-ENG` (Digi-Key P/N 1649-SEN66-ENG-ND)                                                                                                   |
| Manufacturer             | Sensirion AG (CH-8712 Stäfa, Switzerland)                                                                                                      |
| Product page             | <https://sensirion.com/products/catalog/SEN66>                                                                                                 |
| Datasheet (SEN6x family) | <https://sensirion.com/resource/datasheet/SEN6x> — v0.92, Dec 2025, 60 pages                                                                   |
| Mechanical app note      | <https://sensirion.com/resource/application_note/SEN6x_mechanical_design_assembly_guidelines> — v0.92, Jan 2026                                |
| Temperature comp. note   | <https://sensirion.com/resource/SEN6x-temp-compensation> — v1.1, Jan 2026                                                                      |
| ESPHome support          | `sen6x` component, native, released in **ESPHome 2026.3.0** (March 2026, PR #12553 / earlier groundwork PR #8318)                              |
| EAN / GTIN               | **not published** by Sensirion or by Digi-Key, ThePiHut, Future Electronics, SOS Electronic, or Octopart as of 2026-05-13. Manufacturer relies on the MPN + Sensirion material number as the canonical SKU. |

### Module variants (same chassis, different sensor stack)

The SEN6x family all share the same package outline, fan, and connector. Variants
differ only by the populated gas-sensor die set:

| MPN          | Material no. | PM | RH&T | VOC + NOx | CO2 | HCHO |
| ------------ | ------------ | -- | ---- | --------- | --- | ---- |
| SEN62-SIN-T  | 3.001.163    | yes | yes |           |     |      |
| SEN63C-SIN-T | 3.001.197    | yes | yes |           | yes |      |
| SEN65-SIN-T  | 3.001.203    | yes | yes | yes       |     |      |
| **SEN66-SIN-T** | **3.001.030** | **yes** | **yes** | **yes** | **yes** |  |
| SEN68-SIN-T  | 3.001.198    | yes | yes | yes       |     | yes  |
| SEN69C-SIN-T | 3.001.418    | yes | yes | yes       | yes | yes  |

## Mechanical

### Package outline (datasheet §5.1, Figure 11)

| Axis | Value (mm) | Notes                                                                                                  |
| ---- | ---------- | ------------------------------------------------------------------------------------------------------ |
| X    | **55.2**   | "long" edge of the air-side face; carries label and openings                                            |
| Y    | **25.6**   | "short" edge                                                                                            |
| Z    | **21.3**   | height above the mounting face (datasheet figure). ThePiHut lists 21.5 mm — likely a rounded value.    |

Weight: ~20 g ± 10 % (datasheet §1.1, Table 1).

> **Discrepancy noted**: ThePiHut publishes `55.5 × 25.6 × 21.5 mm`. The Sensirion datasheet
> v0.92 dimensional drawing (Figure 11, page 55) is the authority — `55.2 × 25.6 × 21.3 mm`.
> The OAS KiCad model uses `Z = 21.5 mm` (rounded up by 0.2 mm — safe for clearance budgeting).

### Airflow openings

- Two **inlets** (low-flow side) and one **outlet** (fan side, larger opening)
- All openings sit on the top face (the same 55.2 × 25.6 mm face that carries the product label)
- The communication-interface connector is located on the short edge **adjacent to the air outlet** (datasheet §3, "Figure 4. Pin layout")
- Required total opening areas for the host enclosure / cover (mechanical app note §2.1):
  - **Ain ≥ 56 mm²** (combined for both inlets)
  - **Aout ≥ 148 mm²**
  - Increase the area if a fine mesh is fitted in the channel.
- Channel length `d` should be kept as short as possible. Ideally inlets and outlet open
  directly into ambient with no channel.

### Sealing requirements (mechanical app note §2.1)

- Inlets and outlet **must** be insulated from each other by tight sealing.
- Inlets and outlet **must** also be sealed from the rest of the host-device internal
  volume, to prevent parasitic recirculation back through the body of the host.
- Goal: avoid under- or over-pressure between the ambient-coupled openings and the
  device's internal volume (`P_int = P_amb`).

### Mounting orientations (mechanical app note §2.2)

| Orientation                                | Allowed? | Notes                                                                                                                |
| ------------------------------------------ | -------- | -------------------------------------------------------------------------------------------------------------------- |
| Lateral (openings facing horizontally)     | YES — both directions | Sensirion-approved (Figure 5)                                                                            |
| Horizontal (openings facing horizontally, body flat) | YES — both directions | Sensirion-approved (Figure 6)                                                                  |
| Vertical (openings up or down)             | DISCOURAGED          | Risk of dust accumulation / accelerated aging if openings face up; falling dust if openings face down       |

OAS uses **lateral** placement (PCB vertical on the wall → SEN66 air-side face points
horizontally outward through the AK-N-94 perforated cover) — Sensirion-approved.

### Thermal guidelines (mechanical app note §2.4, tcomp app note §1)

- The SEN6x has an internal STAR-Engine temperature compensation algorithm — it
  compensates for the module's own self-heating.
- Additional heat induced from outside (MCU, Wi-Fi modules, displays, batteries) is **not**
  pre-compensated and introduces uncertainty.
- **Hard recommendation: keep over-temperature < 5 K**. Beyond 5 K, device-to-device
  variance grows proportionally with the over-temperature.
- Place the sensor **below** other heat sources where possible — convection rises and would
  otherwise warm the sensor.
- **Do not thermally insulate the SEN66 body.** Gaskets and foam are for sealing the
  air openings and damping vibration, not for thermally wrapping the body.

### Acoustic profile (datasheet §1.1, mech FAQ Q2)

- Long-term acoustic emission level: **< 24 dB(A) @ 0.2 m**
- Long-term drift: **+0.5 dB(A) / year** @ 0.2 m
- Fan speed: **4 000 RPM**, constant (not adjustable)
- Airflow: **0.8 – 0.9 l/min**
- Resonance frequencies to avoid in host structural design:
  - **66.67 Hz** — base (4 000 / 60)
  - ~200 Hz — brace-related (3 braces)
  - **333.34 Hz** — blade-pass (5 blades)
  - 666.67 Hz, **1 000 Hz** — harmonics
  - **Dominant: 1 000 Hz**

### Mounting interface

- The SEN66 body has **no screw mounting features**. Sensirion's reference design uses a
  snap-in plastic fixture (STEP file is offered on the SEN6x product page) — the
  disclaimer explicitly tags this example as "prototyping only".
- OAS retains the SEN66 via **4× zip-ties** routed through NPTH holes in the PCB,
  outside the body footprint, along the two long edges. Pulls the body flat against
  the PCB without forming a thermal trap.

### Light sensitivity

- Direct sunlight into the inlets or outlet biases PM measurements and accelerates aging
  (mech app note §2.5). Mitigated for OAS by the white perforated AK-N-94 cover (no direct
  sunlight onto the SEN66).

## Electrical

### Supply (datasheet §2.1, Table 11)

| Parameter                         | Min   | Typ.  | Max   | Unit | Notes                                                |
| --------------------------------- | ----- | ----- | ----- | ---- | ---------------------------------------------------- |
| Supply voltage VDD                | 3.15  | 3.3   | 3.6   | V    | min spec includes ripple                              |
| Ripple ≥ 100 Hz                   | —     | —     | 100   | mV pp |                                                     |
| Ripple < 100 Hz                   | —     | —     | 30    | mV pp |                                                     |
| Idle current — first 10 s         | —     | 4.6   | —     | mA   |                                                      |
| Idle current — steady (SEN66)     | —     | 3.3   | —     | mA   | after first 10 s                                     |
| Measurement-mode avg (SEN66)      | —     | 140   | 200   | mA   | "after first 60 s" — Sensirion's 5-second-averaged    |
| Peak current (2 ms pulse)         | —     | 300   | 350   | mA   | inrush during fan / laser startup transients          |

> **Absolute maximum VDD: 3.6 V** (Table 12). The TPS62933 5 V→3.3 V buck output regulation
> tolerance must leave headroom under this absolute max.

### I²C (datasheet §3.1, §4.4)

| Property        | Value                                                                  |
| --------------- | ---------------------------------------------------------------------- |
| I²C address     | **0x6B (7-bit)** — confirmed                                            |
| Max bus speed   | 100 kbit/s (standard mode)                                              |
| Pull-ups        | **10 kΩ** recommended on SDA and SCL (datasheet §3.1)                  |
| Clock stretching | Not used — sensor NACKs while busy                                     |
| Cable length    | < 10 cm strongly recommended (datasheet §3.1, mech FAQ Q1: max 0.5 m with shielding) |
| Logic           | TTL 5 V compatible per pin description, but ABS max on I/O pins is 5.5 V |

OAS bus length is < 40 mm thanks to PCB-mount SEN66 placement (well inside the < 10 cm
recommendation).

### ESD / EMC (datasheet §2.3)

- ESD: ±4 kV contact, ±4 kV air (IEC 61000-4-2)
- RF immunity: 80 MHz – 1 000 MHz and 1.4 GHz – 6 GHz @ 3 V/m → covers Wi-Fi 2.4 / 5 GHz
  and BLE without additional shielding
- Magnetic field immunity: 30 A/m, 50 / 60 Hz
- Emission: 40 dB(µV/m) QP @ 3 m (30 – 230 MHz), 47 dB(µV/m) QP @ 3 m (230 – 1000 MHz)

## Pin-out (JST GH 6-pin, datasheet §3, Table 16)

### Connector physical specification

| Side          | Part                                                                  |
| ------------- | --------------------------------------------------------------------- |
| Sensor side   | **ACES 51468-0064N-001** (1.25 mm pitch, 6-position)                  |
| Cable side    | **ACES 51452-006H0H0-001** or compatible, e.g. **JST GHR-06V-S**       |
| Wire gauge    | AWG 26 (0.128 mm²)                                                    |
| Standard length | **50 cm** (Sensirion's reference cable)                              |
| OAS PCB-side socket | **JST SM06B-GHS-TB** (or compatible Würth/Hirose JST-GH-equivalent), through-hole or SMD |

> **Cable supplied?** Looking at the major retail listings as of 2026-05-13:
>
> - **Digi-Key SEN66-SIN-T** — no cable mentioned in the listing; cable sold separately as
>   `SEN5X JUMPER 6-PIN JST GHR-06V-S CABLE SET` (Sensirion accessory).
> - **ThePiHut** — explicitly "1× Sensirion SEN66" only; cable offered as paid extra.
> - **Future Electronics** — listing title "SEN66-SIN-T in Box"; box contents not detailed.
> - **SEK-SEN66 evaluation kit** — includes 1× SEN66 + 1× adapter cable + 1× jumper set
>   + 1× Qwiic adapter.
>
> Plan to order the cable as a separate accessory or substitute a third-party JST-GH cable.

### Pin assignment

| Pin | Name     | Description                  | Notes                                  |
| --- | -------- | ---------------------------- | -------------------------------------- |
| 1   | **VDD**  | Supply voltage (3.15–3.6 V)  | **Pins 1 and 6 are internally connected** |
| 2   | **GND**  | Ground                       | **Pins 2 and 5 are internally connected** |
| 3   | **SDA**  | I²C serial data (open drain) | TTL 5 V compatible                     |
| 4   | **SCL**  | I²C serial clock (open drain) | TTL 5 V compatible                     |
| 5   | GND      | Ground (or leave NC)         | Optional — internally tied to pin 2    |
| 6   | VDD      | Supply (or leave NC)         | Optional — internally tied to pin 1    |

> **No dedicated SEL or INT pin.** The SEN66 has no hardware interrupt-out pin (presence
> events / data-ready are polled via I²C). The "INT" or "SEL" that some commenters list
> for SEN54/55 (the older SEN5x family) is **not present on the SEN66**.

### Mating cable colour codes

The supplied Sensirion 50 cm jumper cable carries the same six conductors. Third-party
JST-GH cables vary in colour assignment — verify continuity with a multimeter before
first power-up.

## Thermal — OAS-specific

- Target over-temperature **≤ 2 K** for multi-unit consistency, conservatively below the
  5 K budget Sensirion calls out as the usable limit for STAR-Engine compensation.
- Heat-source distancing on OAS: MCU and 5 V → 3.3 V buck sit on the opposite half of the
  PCB; SEN66 is the lowest sensor in the convection path (PCB mounts vertically on a wall
  box; SEN66 below MCU and bucks → cold air enters the sensor first, hot air rises away).
- STAR-Engine calibration must be done **on the final assembled OAS** (datasheet calls the
  recipe out in the temperature compensation app note v1.1) — the chamber procedure cannot
  be run on a bare SEN66 alone, the host enclosure changes the offset.
- ESPHome temperature offset / slope / time-constant must be re-sent on every boot
  (parameters are stored in **volatile** memory only — tcomp app note §3.1, §3.2).
  I²C commands:
  - `0x6100` — set acceleration (T1, T2, K, P)
  - `0x60B2` — set offset / slope / time-constant per slot (5 slots, 0..4)
- Recommended starting parameters (tcomp Table 1, **Light / IAQM** preset — matches OAS
  indoor air-quality mission profile):

  | Parameter | Value | Encoded I²C value |
  | --------- | ----- | ----------------- |
  | T1        | 100 s | 1000              |
  | T2        | 300 s | 3000              |
  | K         | 20    | 200               |
  | P         | 20    | 200               |

  (Scale factor 10 — all four are 16-bit unsigned, value = raw × 10.)

## ESPHome integration

- Component: `sen6x` (native, no external_component needed)
- Released in ESPHome 2026.3.0 (March 2026)
- Default I²C address: 0x6B (configurable)
- Exposes (SEN66 subset): `pm_1_0`, `pm_2_5`, `pm_4_0`, `pm_10_0`, `temperature`,
  `humidity`, `voc`, `nox`, `co2`
- Polling rate: 1 Hz default (matches the 1 s sample interval of the sensor)
- STAR-Engine temperature compensation: confirm whether the upstream ESPHome integration
  exposes `temperature_compensation:` / `temperature_acceleration:` blocks. If not,
  apply the offset and acceleration via an `on_boot:` lambda issuing raw I²C writes to
  `0x6100` and `0x60B2`.

Example YAML snippet (for the OAS base config):

```yaml
i2c:
  sda: GPIO6
  scl: GPIO7
  frequency: 100kHz   # SEN66 max

sensor:
  - platform: sen6x
    address: 0x6B
    update_interval: 1s
    pm_1_0:
      name: "PM 1.0"
    pm_2_5:
      name: "PM 2.5"
    pm_4_0:
      name: "PM 4.0"
    pm_10_0:
      name: "PM 10"
    temperature:
      name: "Temperature"
    humidity:
      name: "Humidity"
    voc:
      name: "VOC Index"
    nox:
      name: "NOx Index"
    co2:
      name: "CO2"
```

## Operating range (datasheet §1.7.2, Table 9)

| Parameter           | Recommended range  | Notes                                              |
| ------------------- | ------------------ | -------------------------------------------------- |
| Operating temp      | typ. −10 °C to +50 °C | per Digi-Key listing for SEN66-SIN-T              |
| Operating humidity  | 0 – 90 %RH non-condensing | datasheet §1.7.2                               |
| Lifetime            | > 10 years         | indoor 24 h/day mission profile (datasheet §1.1)   |
| HCHO lifetime       | (not applicable on SEN66) |                                              |
| Laser class         | Class 1            | IEC 60825-1:2014 / DIN EN 60825-1:2022 — eye-safe |

## Sources

- Sensirion product page: <https://sensirion.com/products/catalog/SEN66>
- Sensirion SEN6x datasheet v0.92 (Dec 2025): <https://sensirion.com/resource/datasheet/SEN6x>
- Sensirion SEN6x mechanical design and assembly guidelines v0.92 (Jan 2026):
  <https://sensirion.com/resource/application_note/SEN6x_mechanical_design_assembly_guidelines>
- Sensirion SEN6x temperature compensation and acceleration v1.1 (Jan 2026):
  <https://sensirion.com/resource/SEN6x-temp-compensation>
- Digi-Key SEN66-SIN-T (P/N 1649-SEN66-SIN-T-ND, 804 in stock @ $60.87/ea):
  <https://www.digikey.com/en/products/detail/sensirion-ag/SEN66-SIN-T/25700945>
- ThePiHut SEN66 (SKU 106524, £52.20 incl. VAT, 17 in stock):
  <https://thepihut.com/products/sensirion-sen66-environmental-sensor-node>
- Future Electronics SEN66-SIN-T ($49.54 @ 1 / $47.18 @ 50+):
  <https://www.futureelectronics.com/p/semiconductors--analog--sensors--air-quality/sen66-sin-t-sensirion-7191688>
- SOS Electronic SEN66-SIN-T (P/N 399091):
  <https://www.soselectronic.com/en/products/sensirion/sen66-399091>
- ESPHome sen6x component docs: <https://esphome.io/components/sensor/sen6x/>
- ESPHome 2026.3.0 changelog: <https://esphome.io/changelog/2026.3.0/>
- ESPHome PR #8318 (SEN66 initial support): <https://github.com/esphome/esphome/pull/8318>
- ESPHome PR #9254 (SEN6X family extension): <https://github.com/esphome/esphome/pull/9254>
- Sensirion arduino-i2c-sen66 reference library:
  <https://github.com/Sensirion/arduino-i2c-sen66>

## Revision history

- **2026-05-13** — Initial entry. Datasheet v0.92, mechanical app note v0.92, temperature
  compensation app note v1.1 all cross-checked. ESPHome `sen6x` confirmed released in
  2026.3.0. No EAN/GTIN published by Sensirion or any of 5 distributors checked.
