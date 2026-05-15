# Architecture

**Status:** preliminary draft. Subject to change.

## Module list

| Function | Component | Interface | Notes |
|---|---|---|---|
| MCU | **ESP32-C6-DevKitM-1-N4** (EAN 5904422385651) | 2× USB-C on module | see pinout table below |
| Air quality combo | Sensirion SEN66 | I²C (JST GH cable) | Mounts on the enclosure cover, not on the PCB |
| Presence | HiLink LD2410B/C | UART @ 256000 baud | Plus presence-interrupt GPIO |
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
| NXP NT3H2211 | 0x55 |

Pull-ups: **10 kΩ on the MCU side** (per SEN66 datasheet §3.1; v0.6).

## ESP32-C6-DevKitM-1-N4 pinout (v0.4, post chip-pinout validation)

**Module**: ESP32-C6-DevKitM-1-N4 (Espressif official), EAN 5904422385651 (Botland), Espressif SKU `ESP32-C6-DevKitM-1-N4`. Uses the ESP32-C6-MINI-1 SoM (ESP32-C6FH4 chip with 4 MB internal SiP flash).

**Critical fact**: ESP32-C6 with internal SiP flash bonds out 22 of the chip's nominal 30 GPIOs. **GPIO 10 and GPIO 11 are NOT available** — those pins serve the internal flash bus. Available GPIOs: **0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23**.

| Pin | Function | Notes |
|---|---|---|
| GPIO 6 | I²C SDA | shared bus: SEN66 (0x6B), NT3H2211 (0x55) |
| GPIO 7 | I²C SCL | shared bus, 4.7 kΩ pullups on MCU side |
| GPIO 16 | UART1 TX → LD2410 RX | 256000 baud |
| GPIO 17 | UART1 RX ← LD2410 TX | 256000 baud |
| **GPIO 2** | LD2410 OUT (presence interrupt) | safe non-strap input. Earlier drafts wrongly assigned GPIO 4 (MTMS strap) then GPIO 10 (does not exist on SiP flash variants) |
| **GPIO 3** | NT3H2211 FD (NFC field-detect interrupt) | safe non-strap input. Earlier drafts wrongly assigned GPIO 5 (MTDI strap) then GPIO 11 (does not exist on SiP flash variants) |
| GPIO 8 | WS2812 DIN | uses the **onboard addressable RGB NeoPixel** on DevKitM-1; no external WS2812 needed |
| USB D+/D− | GPIO 12 / GPIO 13 — wired to **one of the two** DevKitM-1's USB-C connectors (native USB-Serial-JTAG). The other USB-C goes to the onboard USB-to-UART bridge IC | no external USB-C on the case wall — flash via either of the module's USBs before sealing, OTA after |

**Strap pins on ESP32-C6 (avoid for general I/O)**: GPIO 4 (MTMS), 5 (MTDI), 8 (strap, but OK for WS2812 in idle-low state), 9 (must float or pull-up at boot — used as the BOOT button on DevKitM-1), 15 (boot-mode select).

**USB-reserved pins**: GPIO 12, 13 (internally routed to USB-C on the DevKitM-1).

**Safe non-strap GPIOs (free for general I/O on DevKitM-1)**: 0, 1, 2, 3, 14, 18, 19, 20, 21, 22, 23.

**Firmware framework**: ESPHome on `esp-idf` (not `arduino`) — required for adequate memory headroom with BLE-proxy + WiFi + sensor stack combined.

**Antenna orientation**: ESP32-C6-MINI-1's PCB antenna sits on the top edge of the module (the short edge with no pin headers). Place the DevKitM-1 so its antenna edge points radially outward toward the case wall, and keep the bucks well away from the antenna to reduce RF noise pickup.

**Form factor**: 48.26 × 25.4 mm. PCB layout must avoid placing tall components directly under the module body to maintain the 17 mm front-side height limit including the module's headers + standoff (~6-8 mm total module stack).

**Onboard hardware to be aware of**:
- Power LED (always-on indicator, ~10 mA on 3.3V = ~30 mW — could be desoldered post-bringup if SEN66 measurements show a temperature bias)
- Addressable RGB NeoPixel on GPIO 8 (= our status LED, software-controlled)
- Reset and Boot pushbuttons (useful during development; closed enclosure makes them inaccessible — that's fine, OTA handles updates)
- 5V→3.3V LDO on the module — bypassed in our design by feeding 3.3V directly into the 3V3 pin from our TPS62933 buck (no LDO loss, no LDO heat)
- **Two USB-C connectors**: one goes through the onboard USB-to-UART bridge IC (classic flashing path), the other is wired directly to the ESP32-C6's native USB-Serial-JTAG (GPIO 12/13). With no USB cable plugged in after deployment, the bridge IC enters suspend mode and contributes negligible heat (~10 µW). Both connectors share the +5V power input net, so plugging into either one powers the module.

## PCB layout — functional grouping (soft guideline)

The schematic is split into four hierarchical sub-sheets by **function**, not by geography: `power.kicad_sch`, `mcu.kicad_sch`, `sensors.kicad_sch`, `io.kicad_sch`. Layout follows function loosely, not strictly.

As a starting heuristic, the PCB roughly behaves like a clock face — power on the upper-left, MCU on the upper-right, sensors filling the bottom half — with 24 V entering through the central cable hole and power flowing roughly clockwise (centre → power → MCU → sensors). This keeps rails and signal paths short and the antenna far from the bucks. **It is a hint, not a hard constraint** — components (notably the SEN66, which is large) may cross any imagined boundary if the layout needs it. No separator lines or sector labels are drawn on the PCB.

## Thermal / layout strategy

- **PCB outline:** Ø120 mm D-shape, flat chord 82.65 mm on the bottom edge (arc R=60 mm; full precision 82.6545 mm from manufacturer DXF)
- **Mounting:** 3× M3 holes (Ø3.8 mm, NPTH) on pitch circle Ø110 mm, trójkąt równoboczny, one hole opposite the chord. NPTH because the screws go into plastic bosses
- **Cable entry:** Ø12 mm circular cut-out at PCB centre for 24 V power (3× 1.5 mm² conductors). Wires enter from the rear of the enclosure (behind the unit, from an electrical wall box) and reach a terminal block mounted on the front side of the PCB. The bare conductors stay enclosed within the case
- **Front-side component-height limit:** 17 mm (per manufacturer DXF)
- **Back-side limit:** **5 mm effective** (DXF baseline 3 mm + 2 mm gained by washers under the M3 mounting screws) — fits standard through-hole pin-header bottoms without aggressive trimming; SMD components still discouraged on back side
- **Orientation:** flat chord on the bottom; sensor zone (SEN66 inlet path) is below the electronics, so natural convection lifts heat upward and away from the air intake
- **Thermal isolation:** 1.5 mm milled FR4 slots separate the Power, MCU and peripheral zones
- **Connector strip along the bottom flat:** 24 V terminal, USB-C, SWD header, Qwiic, JST GH to SEN66 — positions match the manufacturer enclosure cutouts (5 keepout zones C1…C5 in `oas.kicad_pcb` block the corresponding rectangles on F.Cu/B.Cu; see [`../hardware/case/README.md`](../hardware/case/README.md#connector-cutouts-in-the-case-wall-along-the-flat-chord) for dimensions)

## Why SEN66 mounts on the cover

The SEN66 module is 21.5 mm tall, which exceeds the 17 mm front-side component limit on the PCB. Mounting it on the enclosure cover via a short JST GH 6-pin cable (~50 mm) keeps it within the available headroom and also places the air inlet near the perforated cover area.

A 3D-printed bracket is required to retain the SEN66 against the cover (see [`hardware/case/sen66-bracket.stl`](../hardware/case/sen66-bracket.stl) — TODO).

## Open architectural questions

- NFC antenna geometry — PCB spiral dimensions and the matching capacitor value (driven by NXP AN11203)
- Buck converter IC selection — final choice depends on efficiency at the expected load profile and JLCPCB Basic Library availability

---

## Firmware architecture

The OAS firmware runs on **ESPHome** (esp-idf framework) on the ESP32-C6-MINI-1 SoM. Source lives at [`../firmware/esphome/`](../firmware/esphome/). For the developer-facing per-package responsibility map and workflow notes, see [`../firmware/esphome/README.md`](../firmware/esphome/README.md). For the user-facing flashing workflow, see [`./FLASHING.md`](./FLASHING.md).

### What runs where

| Subsystem | Runs on | Notes |
|---|---|---|
| WiFi 6 stack, BLE proxy, mDNS, OTA, API | ESP32-C6 | esp-idf chosen over arduino framework for IRAM headroom |
| Sensor sampling + STAR-Engine I²C upload | ESP32-C6 | STAR-Engine params re-uploaded on every boot (volatile) |
| LED ring effects + AQI colour mapping | ESP32-C6 (RMT peripheral) | 11 SK6812-SIDE LEDs driven via 1-wire WS281x protocol |
| Air quality measurement (CO₂ NDIR, PM laser scatter, MOX VOC/NOx, integrated SHT) | SEN66 internal | Sensor reports compensated values over I²C |
| Radar presence detection + per-gate sensitivity | LD2410 internal MCU | Firmware on the LD2410 module handles raw FMCW processing; OAS only receives parsed protocol frames over UART |
| NFC EEPROM dynamic content | NT3H1101 on MIKROE-2462 | OAS firmware writes NDEF URL record every 60 s; tag itself handles ISO 14443A field detection |

### I²C bus topology

```
ESP32-C6 ─── SDA (GPIO 6) ──┬─── SEN66           (0x6B)
                            ├─── NT3H1101 / NFC  (0x55)
                            └─── Qwiic / expansion port (J9)

ESP32-C6 ─── SCL (GPIO 7) ──┴─── (same chain)
```

- Pull-ups: **4.7 kΩ on the MCU side** (R5/R6, v0.22+). Lowered from 10 kΩ after measuring realised bus length of ~140 mm PCB MST + ~80 mm SEN66 JST-GH cable = ~220 mm total. At 10 kΩ the I²C rise time exceeded standard-mode spec (t_r > 1 µs at 100 kHz); 4.7 kΩ brings τ comfortably back under spec. See CLAUDE.md "Shared I²C bus" entry.
- Bus speed: 100 kHz (standard mode). The SEN66 datasheet allows up to 400 kHz but we're well inside the conservative envelope at 100 kHz with margin for the long cable.
- An ESD protection diode on the Qwiic line is TBD — added when the bus is taken outside the case.

### UART topology

```
ESP32-C6 ─── TX (GPIO 16) ────► LD2410 RX
ESP32-C6 ◄── RX (GPIO 17) ───── LD2410 TX
```

- Baud: **256000** (LD2410 default; non-standard but ESP32-C6 UART supports it natively).
- Protocol: HiLink's custom binary protocol (header `FD FC FB FA`, footer `04 03 02 01`). ESPHome's `ld2410` component handles parsing.
- Logger UART is disabled (`baud_rate: 0` in `core.yaml`) — UART0 default pins overlap with our LD2410 wiring on some board variants and we don't want log spam stomping on radar protocol frames. Logs flow via USB-Serial-JTAG / web_server / API instead.

### Interrupt lines

| GPIO | Source | Direction | Purpose |
|---|---|---|---|
| GPIO 2 | LD2410 OUT pin | input | Hardware-level presence flag. Fastest path — fires before the UART protocol frame arrives. Used for snappy presence binary sensor. |
| GPIO 3 | NT3H1101 FD pin | input (open-drain, pulled up) | NFC field-detect — asserts when a phone is in the antenna's near field. Lets firmware bump the NDEF refresh rate while a tap is in progress. |

### LED chain

```
ESP32-C6 ─── GPIO 8 (RMT TX) ──► D11 DIN ──► D12 DIN ──► … ──► D22 DIN
                                                                  │
                                                               D22 DOUT (open)
```

- 11 LEDs total. Index 3 (D14) is **vacant** — its slot was reclaimed in v0.18 for the J1 24 V terminal block on the south side of the cable hole. The daisy-chain skips from D13.DOUT to D15.DIN.
- Each LED is an SK6812-SIDE (side-emit 4020 package) with an integrated WS281x-compatible controller.
- GPIO 8 is technically a strap pin (boot-mode select on some ESP32 variants) but on the C6 it's safe in idle-low state. R7 = 10 kΩ pull-up to +3V3 (added in v0.22) guarantees a deterministic HIGH at boot regardless of LED chain state.
- Power: SK6812-SIDE ring is fed from the LM2596S-5.0 +5 V rail (not the +3V3 MCU rail). Peak draw 600 mA worst-case at full white; typical breathing-animation average ~80 mA.

### Boot-strap pin notes

| GPIO | Role | OAS treatment |
|---|---|---|
| GPIO 4 (MTMS) | strap | Not used for signals (reserved JTAG) |
| GPIO 5 (MTDI) | strap | Not used for signals (reserved JTAG) |
| GPIO 8 | strap (boot-mode), LED data | R7 = 10 kΩ external pull-up to +3V3 ensures HIGH at boot (DevKitM-1's onboard pull-up is on V5V which floats in OAS) |
| GPIO 9 | BOOT button on DevKitM-1 | Inaccessible after enclosure is closed — recovery via J10 if ever needed |
| GPIO 12, 13 | USB-Serial-JTAG D-/D+ | Reserved by hardware; J10 recovery header exposes them as the back-door flash path |
| GPIO 15 | boot-mode select | Not used for signals |
