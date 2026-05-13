# SK6812 SIDE-A — addressable side-emit RGB LED

Status-LED ring element for OAS. Twelve of these arranged on a Ø22 mm pitch
circle around the central cable hole form the AQI status indicator (see
`_research-led-diffuse-ring.md` for the design decision). Side-emitting LEDs
eliminate the "dot through perforation" problem that plagues top-emit LEDs
mounted under the AK-N-94 white perforated cover.

## Identifiers

| Field                    | Value                                                                                                                                          |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| MPN                      | `SK6812 SIDE-A`                                                                                                                                |
| Variant naming           | `SK6812SIDE-A` (no space) and `SK6812 SIDE-A-001` (Opsco / OPSCO Optoelectronics revision) appear in retail listings — all refer to the same 4020 side-emit package. |
| Manufacturer (primary)   | Shenzhen Normand Electronic Co., Ltd. (SK6812 SIDE-A datasheet Rev. 01, 2018-07-07)                                                            |
| Manufacturer (alt batch) | Dongguan Occidental Optoelectronics Technology (OPSCO) — same chip, "SK6812 SIDE-A-001" revision, Rev. A/1, 2021-01-10                          |
| Package                  | 4020 SMD (top-SMD with side light emission), MSL: 5a                                                                                            |
| Datasheet (Normand)      | <http://www.normandled.com/upload/201810/SK6812%20SIDE-A%20LED%20Datasheet.pdf> — verified 2026-05-13                                          |
| Datasheet (Opsco/Lighting Hut) | <https://www.ledlightinghut.com/files/SK6812SIDE-A-001.pdf> — verified 2026-05-13                                                         |
| LCSC search              | <https://www.lcsc.com/search?q=SK6812SIDE> — Normand/OPSCO variants typically C2761795-class or similar; stock fluctuates                       |

Per CLAUDE.md "Module Identification" rule, source the LEDs by MPN at order
time and verify the datasheet attachment on the LCSC product page matches
the pinout below. Multiple Asian manufacturers ship parts under the
"SK6812SIDE" name; the *pinout* below has been cross-checked against two
independent datasheets (Normand 2018 and Opsco 2021) and is identical
between them.

## Mechanical

### Package outline (Normand datasheet §4, Opsco §4)

| Axis | Value (mm)    | Notes                                                                                                  |
| ---- | ------------- | ------------------------------------------------------------------------------------------------------ |
| Length (long axis, pad row) | **4.00 ± 0.10** | Four SMD pads (DIN, VDD, DOUT, GND) sit along this edge.                            |
| Width (short axis, emission axis) | **2.00 ± 0.05** | Light emerges perpendicular to this axis through one of the long side faces.  |
| Height            | **1.60 ± 0.10** | Slab profile; lays flat on the PCB.                                                                  |

The package is sometimes labelled "4020 LED chip" by Sensirion / Opsco
nomenclature (4.0 × 2.0 mm footprint, 1.6 mm tall). Inside the package, the
RGB die and the integrated WS281x-protocol controller IC sit under a silicone
encapsulant; emission exits the long-side face opposite the pad row, not
through the top.

### Emission direction

Light radiates **parallel to the PCB**, perpendicular to the pad row, through
one of the 4.0 × 1.6 mm long side faces. Looking down at the LED on the PCB:

```
        emission face (4.0 × 1.6 mm)
              ↑
   +---------------------+
   |                     |   ← package top (no light)
   |       silicone      |
   |     encapsulant     |
   |                     |
   +---+-+-+-+-+-+-+-+---+   ← pad-row face (bottom)
       1 2 3 4
       pads ↓
       (to PCB)
```

For OAS the LEDs sit with their **emission face pointing radially outward**
from the central cable hole, so light radiates outward into the AK-N-94
perforated cover and bounces off the inside of the white ABS as a diffuse
halo — never seen by the user as a sharp dot through any single perforation.

### Pin layout (Normand datasheet §5 / Opsco §5)

| Pin | Symbol | Function                       |
| --- | ------ | ------------------------------ |
| **1** | **DIN**  | Control data signal input (cascade from previous LED's DOUT or from MCU) |
| **2** | **VDD**  | Power supply (3.7 V – 5.5 V; 5 V typical)                              |
| **3** | **DOUT** | Control data signal output (feeds next LED's DIN)                       |
| **4** | **GND**  | Ground                                                                  |

The four pads run in a row along the 4.0 mm long edge, separated by ~0.55 mm
gaps. Pad-row centerline sits offset from the package geometric centerline
toward one long edge; the opposite long edge is the emission face.

> Pin numbering differs from the **stock KiCad `SK6812` symbol** (which is
> the 5050 PLCC4 footprint with 1=VSS, 2=DIN, 3=VDD, 4=DOUT). Do NOT use
> the stock symbol — the SK6812 SIDE-A uses the numbering above. The
> OAS project ships its own `OAS:SK6812-SIDE` symbol with the correct
> 1=DIN, 2=VDD, 3=DOUT, 4=GND mapping.

### Recommended PCB land pattern (datasheet §6)

Four rectangular pads, ~0.95 mm pitch, sized to match the SMD terminations
(approximately 1.0 × 0.5 mm each). OAS uses pads at body-local coordinates:

| Pin | Body-local X (mm) | Body-local Y (mm) | Pad size (mm) |
| --- | ----------------- | ----------------- | ------------- |
| 1   | -1.425            | +0.85             | 0.6 × 1.0     |
| 2   | -0.475            | +0.85             | 0.6 × 1.0     |
| 3   | +0.475            | +0.85             | 0.6 × 1.0     |
| 4   | +1.425            | +0.85             | 0.6 × 1.0     |

Body local frame: origin at LED package centre, +X along the 4.0 mm long
axis (pad-row direction), +Y along the 2.0 mm short axis pointing *toward
the pad-row face* (i.e. the emission face is at body-local -Y).

## Electrical

### Absolute maximum ratings (Normand §8, Opsco §8)

| Parameter                | Symbol  | Range            | Unit |
| ------------------------ | ------- | ---------------- | ---- |
| Power supply voltage     | VDD     | +3.5 to +5.5     | V    |
| Logic input voltage      | VIN     | -0.5 to VDD+0.5  | V    |
| Operating temperature    | Topt    | -40 to +85       | °C   |
| Storage temperature      | Tstg    | -50 to +150      | °C   |
| ESD pressure (HBM)       | VESD    | 4 kV (Normand) / 2 kV (Opsco) | V    |

### Operating characteristics (Normand §9-10, Opsco §9-10)

| Parameter                       | Symbol | Min   | Typ.  | Max   | Unit | Notes |
| ------------------------------- | ------ | ----- | ----- | ----- | ---- | ----- |
| Operating supply voltage        | VDD    | 3.7   | 5.0   | 5.5   | V    | datasheet §8 |
| Static (idle) current per LED   | IDD    | —     | 1     | —     | mA   |       |
| Forward current per channel (R) | IF,R   | —     | 12    | —     | mA   | SK6812 = 12 mA series |
| Forward current per channel (G) | IF,G   | —     | 12    | —     | mA   |       |
| Forward current per channel (B) | IF,B   | —     | 12    | —     | mA   |       |
| Peak full-white current         | —      | —     | ~50   | —     | mA   | 3 × 12 mA + controller idle (≈ 50 mA observed across NeoPixel libraries) |
| Logic high threshold            | VIH    | 0.7 × VDD | —   | —   | V    |       |
| Logic low threshold             | VIL    | —     | —     | 0.3 × VDD | V |       |
| PWM frequency                   | FPWM   | —     | 1.2   | —     | kHz  |       |
| Data rate                       | fDIN   | —     | 800   | —     | kbps |       |

### Data protocol

Unipolar RZ (return-to-zero) communication, 24-bit data frame per pixel,
800 kbps typical. Compatible with the WS281x / NeoPixel protocol family —
ESPHome `light.neopixelbus` (or `light.esp32_rmt_led_strip` on ESP32-C6,
which uses the chip's hardware RMT peripheral) drives the chain natively
with `chipset: SK6812` selection.

## Dominant wavelength and luminance (Opsco §9, SK6812 12 mA)

| Colour | Dominant wavelength (nm) | Luminance (mcd) | Luminous flux (lm) |
| ------ | ------------------------ | --------------- | ------------------ |
| Red    | 620 – 630                | 240 – 450       | (combined ~3-5 lm) |
| Green  | 515 – 530                | 580 – 1050      |                    |
| Blue   | 460 – 475                | 160 – 320       |                    |

## OAS application

- **Count**: 12 LEDs on a Ø22 mm pitch circle around the central cable hole.
- **Orientation**: emission face radially outward; long axis (pads) tangential
  to the ring. Each LED's KiCad rotation angle = `(270 - θ) mod 360`, where
  `θ` is the position-angle in PCB-local frame (0° = +X, increasing clockwise
  with KiCad's +Y-down screen convention).
- **Supply rail**: +5 V (LM2596S-5.0 output, shared with LD2410). Peak draw
  at 12 LEDs × ~50 mA = 600 mA full-white (worst case); average AQI breathing
  animation ~80 mA. LM2596S-5.0 rated 3 A — comfortable margin.
- **Decoupling**: one 100 nF 0402 X7R per LED, placed adjacent to the VDD
  pad. Twelve caps total (C20 – C31 in the schematic).
- **Daisy chain**: DIN of D11 driven from ESP32-C6 GPIO 8 (the same pin
  that drove the now-unusable onboard NeoPixel — see CLAUDE.md "OPEN ISSUE
  #2" resolution in the v0.16 changelog). DOUT of D11 → DIN of D12 → ... →
  DOUT of D22 (terminated unconnected).
- **ESPHome config** (preliminary):
  ```yaml
  light:
    - platform: esp32_rmt_led_strip
      name: "OAS AQI ring"
      pin: GPIO8
      num_leds: 12
      chipset: SK6812
      rgb_order: GRB    # default for SK6812 RGB; verify against actual batch
      effects:
        - addressable_color_wipe:
            name: "Breathing"
            colors: ...
  ```

## Sources

- Shenzhen Normand Electronic — *SK6812 SIDE-A LED Datasheet* (Document
  No. SPC/SK6812 SIDE-A, Rev. 01, 2018-07-07).
  <http://www.normandled.com/upload/201810/SK6812%20SIDE-A%20LED%20Datasheet.pdf>
- Opsco / Dongguan Occidental Optoelectronics — *SK6812 SIDE-A-001
  Specification* (Document No. OSK-SPC-SK6812SIDE-A-001, Rev. A/1,
  2021-01-10). <https://www.ledlightinghut.com/files/SK6812SIDE-A-001.pdf>
- KiCad 10 stock symbol library `LED.kicad_sym` contains a generic
  `SK6812` symbol (PLCC4 5050 footprint) with a different pin numbering;
  do NOT use it for the SIDE variant. The OAS project ships its own
  `OAS:SK6812-SIDE` symbol matching this datasheet's pinout.
- ESPHome `light.esp32_rmt_led_strip` docs (driving SK6812 chains on
  ESP32-C6 via hardware RMT): <https://esphome.io/components/light/esp32_rmt_led_strip>

## Revision history

- **2026-05-13** — Initial entry. Pinout cross-verified between Normand
  2018 rev 01 and Opsco 2021 rev A/1 datasheets — both agree on the
  1/2/3/4 = DIN/VDD/DOUT/GND mapping. Package 4.0 × 2.0 × 1.6 mm
  confirmed by both. Used as the OAS v0.16 AQI status-ring element.
