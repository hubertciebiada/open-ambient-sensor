# Architecture

**Status:** preliminary draft. Subject to change.

## Module list

| Function | Component | Interface | Notes |
|---|---|---|---|
| MCU | ESP32-C6 SuperMini | native USB-C | Pinout must be validated against strap/boot constraints |
| Air quality combo | Sensirion SEN66 | I²C (JST GH cable) | Mounts on the enclosure cover, not on the PCB |
| Presence | HiLink LD2410B/C | UART @ 256000 baud | Plus presence-interrupt GPIO |
| Ambient light | Vishay VEML7700 | I²C | |
| Status LED | WS2812B (PLCC4) | 1-wire RMT | Single LED, breathing effect |
| NFC dynamic tag | NXP NT3H2211 + PCB trace antenna | I²C + NFC | Field-detect interrupt to MCU |
| Power input | 24 V DC + TVS + PTC | terminal block | Single 24 V rail across the deployment |
| Buck 24 V → 5 V | TBD (TPS62933 / MP2451 candidates) | — | JLCPCB Basic Library preferred |
| Buck 24 V → 3.3 V | TBD (TPS62840 / MP2315 candidates) | — | JLCPCB Basic Library preferred |
| External I²C ESD | TBD (PESD3V3L4UG candidate) | — | On the Qwiic/STEMMA QT port |

## I²C address map

| Device | Address |
|---|---|
| Sensirion SEN66 | 0x6B |
| Vishay VEML7700 | 0x10 |
| NXP NT3H2211 | 0x55 |

Pull-ups: **4.7 kΩ on the MCU side**.

## Tentative ESP32-C6 pinout

| Pin | Function |
|---|---|
| GPIO 6 | I²C SDA |
| GPIO 7 | I²C SCL |
| GPIO 16 | UART1 TX → LD2410 RX |
| GPIO 17 | UART1 RX ← LD2410 TX |
| GPIO 4 | LD2410 OUT (presence interrupt) |
| GPIO 8 | WS2812 DIN |
| GPIO 5 | NT3H2211 FD (NFC field-detect interrupt) |
| USB D+/D− | Native USB-C |

**TODO:** validate against ESP32-C6 SuperMini strap/boot pin constraints.

## Thermal / layout strategy

- **PCB outline:** Ø120 mm D-shape, flat chord 82.65 mm on the bottom edge (arc R=60 mm; full precision 82.6545 mm from manufacturer DXF)
- **Mounting:** 3× M3 holes (Ø3.8 mm) on pitch circle Ø110 mm, trójkąt równoboczny, one hole opposite the chord
- **Front-side component-height limit:** 17 mm (per manufacturer DXF)
- **Back-side limit:** 3 mm — solder fillets only, no components (per manufacturer DXF)
- **Orientation:** flat chord on the bottom; sensor zone (VEML7700, SEN66 inlet path) is below the electronics, so natural convection lifts heat upward and away from the air intake
- **Thermal isolation:** 1.5 mm milled FR4 slots separate the Power, MCU and peripheral zones
- **Connector strip along the bottom flat:** 24 V terminal, USB-C, SWD header, Qwiic, JST GH to SEN66 — positions match the manufacturer enclosure cutouts

## Why SEN66 mounts on the cover

The SEN66 module is 21.5 mm tall, which exceeds the 17 mm front-side component limit on the PCB. Mounting it on the enclosure cover via a short JST GH 6-pin cable (~50 mm) keeps it within the available headroom and also places the air inlet near the perforated cover area.

A 3D-printed bracket is required to retain the SEN66 against the cover (see [`hardware/case/sen66-bracket.stl`](../hardware/case/sen66-bracket.stl) — TODO).

## Open architectural questions

- VEML7700 placement — does it need its own thermal isolation slot to avoid bias from MCU/PSU heat?
- NFC antenna geometry — PCB spiral dimensions and the matching capacitor value (driven by NXP AN11203)
- Buck converter IC selection — final choice depends on efficiency at the expected load profile and JLCPCB Basic Library availability
