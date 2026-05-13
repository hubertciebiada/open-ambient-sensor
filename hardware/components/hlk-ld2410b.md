# HLK-LD2410B

Verified specifications for the HiLink Electronics **HLK-LD2410B** 24 GHz mmWave
human presence radar module, used as the OAS presence sensor. Cross-checked
against the official HiLink datasheet (V1.04, 2022-06-29, FCC-filed PDF),
the base **HLK-LD2410** manual (V1.03, 2022-06-29), the **HLK-LD2410C**
datasheet, the ESPHome `ld2410` component documentation, the
`ncmreynolds/ld2410` Arduino library, and several DIY references.

Verification date: 2026-05-13.

---

## Identifiers

- **MPN (base, no pins)**: `HLK-LD2410B`
- **MPN (pins pre-soldered + 20 cm Dupont cable kit)**: `HLK-LD2410B-P`
- **Manufacturer**: Shenzhen Hi-Link Electronic Co., Ltd. ("HiLink").
- **Manufacturer URL (product page)**: <https://www.hlktech.net/index.php?id=1094>
- **Manufacturer URL (test-kit variant)**: <https://www.hlktech.net/index.php?id=1183>
- **FCC ID**: `2AD56HLK-LD2410B-P` (24010-24245 MHz, FMCW, Class B)
- **Datasheet (FCC-filed, V1.04, 2022-06-29)**: <https://fcc.report/FCC-ID/2AD56HLK-LD2410B-P/6620025.pdf>
- **Serial protocol document**: "HLK-LD2410B Serial Communication Protocol V1.05.pdf" (referenced in the datasheet; available from HiLink Google Drive)
- **LCSC part**: `C5183132` (HLK-LD2410B-P, the with-pins variant) — <https://www.lcsc.com/product-detail/C5183132.html>
- **JLCPCB part**: same `C5183132` (Extended Library)
- **EAN/GTIN**: **NOT verified** — Botland (Poland) does not currently list this module under EAN search; project will need to source via AliExpress, LCSC, Amazon, TinyTronics, or a regional distributor. The CLAUDE.md project rule for Module Identification is satisfied by the **MPN + FCC ID + LCSC part number** triple even without an EAN.
- **Suppliers verified May 2026**:
  - TinyTronics (NL): `HLK-LD2410B-P` (1.27 mm pinheaders) listed — <https://www.tinytronics.nl/en/home-automation/sensors/motion-and-presence/hi-link-hlk-ld2410b-24ghz-radar-sensor-module-with-bluetooth-1.27mm-pinheaders>
  - LCSC: 530+ in stock at ~$2.92/ea
  - AliExpress / Amazon: multiple resellers (no canonical EAN)

---

## Variant — B vs C vs S vs base

| Variant | Pin pitch | Dimensions | Bluetooth | Notes |
|---|---|---|---|---|
| **HLK-LD2410** (base) | 1.27 mm | 7 × 35 mm | No | Original 2022 release. Same pin order as B. No BLE. |
| **HLK-LD2410B** ★ | **1.27 mm** | **7 × 35 mm** | **Yes (BLE for HLKRadarTools app)** | What OAS uses. Adds BLE config support over base. Same dimensions, same pin order. |
| **HLK-LD2410B-P** | 1.27 mm | 7 × 35 mm | Yes | Same as B but ships with pins pre-soldered + 20 cm 1.27→2.54 mm Dupont cable. **Recommended SKU for OAS** if we want the 1.27 mm pins pre-mounted; otherwise we hand-solder our own. |
| **HLK-LD2410C** | **2.54 mm** | **16 × 22 mm** | Yes | Bigger PCB but standard 2.54 mm pin pitch. Same firmware/protocol as B. **Pin order DIFFERS** (see below). |
| **HLK-LD2410S** | 1.27 mm | smaller | No | Stripped-down variant, no BLE. Different protocol. |

**Decision for OAS: HLK-LD2410B is the right choice.**
Reasons:
- 1.27 mm pitch is more compact than 2.54 mm — better for the OAS PCB area budget (the LD2410 sits in the left-side group at PCB X=-44.45..-29.21 along with the ESP32-C6 DevKitM-1).
- BLE is useful during initial configuration of each unit (HLKRadarTools mobile app) without needing the UART connected to a host PC.
- Same code base and same ESPHome `ld2410` component as the C variant; no firmware difference visible to the OAS application.
- Form factor 7 × 35 mm matches the soldered-daughterboard pattern we use (vertical orientation, antenna face pointing toward the front of the AK-N-94 cover).
- LD2410C's 2.54 mm pitch would force a wider J4 footprint (12.7 mm vs 5.08 mm row span) and would push the SEN66 / NFC daughterboards' placements; no compensating benefit.

**Important caveat — pin order is NOT the same on C as on B.**
The LD2410B datasheet (Table 1, page 7) and the base LD2410 manual (Table 1, page 7) both list:
- Pin 1 = OUT, Pin 2 = UART_Tx, Pin 3 = UART_Rx, Pin 4 = GND, Pin 5 = VCC.

The LD2410C datasheet (Table 1, page 8) lists:
- Pin 1 = UART_Tx, Pin 2 = UART_Rx, Pin 3 = OUT, Pin 4 = GND, Pin 5 = VCC.

A pinout drawn for one variant will short the supply if you swap to the other. Document the variant clearly on F.SilkScreen next to J4 ("HLK-LD2410B 1.27mm"); if a contributor later substitutes the C variant they must also re-route J4.

---

## Mechanical

All values from HLK-LD2410B datasheet V1.04 (FCC-filed PDF, page 7 §4.1
"Dimensions" and page 16 §7 "Performance and electrical parameters").

| Dimension | Value | Notes |
|---|---|---|
| Module length (long axis) | **35 mm** | Datasheet §4.1: "Module size: 7mm × 35mm". The 35 mm runs from the antenna patches at one short edge to the pin row at the opposite short edge. |
| Module width (short axis) | **7 mm** | The short axis. The board is a tall narrow rectangle — antennas at one short edge, pin row at the other. |
| Module thickness (PCB only) | ~1.0–1.2 mm | Not stated in the datasheet; observed across community photos. Standard 4-layer PCB. |
| Total height **above OAS PCB** when soldered into 1.27 mm vertical THT pin header | ~**5–7 mm** | Pin-header standoff ~2.5 mm (1.27 mm vertical header plastic body height) + module PCB ~1.0 mm + on-board components (24 GHz front-end SoC, BLE chip, antenna patches are flush on top side; tallest non-edge SMD ~1.5 mm). Conservative budget: **7 mm**. OAS `generate.py` uses `LD2410_BODY_Z = 7.0` which is consistent. |
| Pin hole diameter (LD2410 PCB) | **0.6 mm** | Datasheet §4.1. Mating pins are 0.5 mm square / 0.5 mm round. The OAS-side J4 is a stock KiCad `PinHeader_1x05_P1.27mm_Vertical` — verify drill ≥ 0.6 mm if hand-soldering the LD2410 *into* the OAS-side header (the OAS pads carry the male pins; the LD2410 module's own 0.6 mm holes are the receiving side). |
| Mounting holes on the LD2410 PCB | **None** | The LD2410 has no screw holes. Retention on the OAS PCB is via the 5 soldered pins only. The module is a vertical daughterboard. |
| Antenna location | One short edge (the 7 mm edge **opposite** the pin row) | 1T2R microstrip patches printed directly on the top face of the LD2410 PCB. Beam radiates **perpendicular to the LD2410 PCB top face** (i.e., upward through the top side, with the back-lobe weaker but present — datasheet §5.5: "metal shield or metal backplane can be used to shield the radar back lobe"). |

OAS-specific placement (`generate.py`, constants):
- `LD2410_BODY_W = 35.56` mm (long axis, 1.27 mm grid-aligned multiple — slightly oversized vs the 35 mm datasheet value to provide silkscreen clearance)
- `LD2410_BODY_H = 15.24` mm (short axis) — **DISCREPANCY**: datasheet says the short axis is **7 mm**, but `generate.py` carries 15.24 mm. The 15.24 mm value matches the **LD2410C** (16 × 22 mm) or one of the development-kit carrier boards — **not** the bare HLK-LD2410B (7 × 35 mm). See "Discrepancies" section below.
- `LD2410_BODY_Z = 7.0` mm — consistent with measured community values.
- `LD2410_ROTATION = 270` — long axis along PCB Y; antenna short edge faces NORTH (PCB −Y, toward 12:00); pin row at the chord-facing short edge (PCB +Y). Matches the design intent (antenna beam radiates upward through the cover).

---

## Pin header

- **Location**: One short edge (the **7 mm** edge) of the LD2410 PCB. The five pin holes are arranged in a single row parallel to the short axis, in the centre of that edge.
- **Pin count**: **5**.
- **Pitch**: **1.27 mm** (datasheet §4.1).
- **Pin hole diameter**: **0.6 mm** (datasheet §4.1).
- **Pin row physical orientation**: Single 1×5 row on the short edge. With the LD2410 mounted as a vertical daughterboard, the row is perpendicular to the OAS PCB surface and the LD2410 stands upright above the OAS PCB.
- **Default population from factory**: For the bare **HLK-LD2410B** SKU, pin holes are **not populated** — the user solders pins or wires. The **HLK-LD2410B-P** SKU ships with pins **pre-soldered** in 1.27 mm pitch plus a 20 cm 1.27→2.54 mm Dupont conversion cable.

---

## Pin assignment

**Authoritative source**: HLK-LD2410B Datasheet V1.04 (2022-06-29) **Table 1, page 7**.
Same pin order is shown in the base **HLK-LD2410** manual V1.03 Table 1, page 7.
**Different** pin order is shown in **HLK-LD2410C** Table 1, page 8 (see variant table above — do not cross-substitute).

| Pin # | Symbol | Name | Function | Direction (from LD2410) | OAS net |
|---|---|---|---|---|---|
| **1** | **OUT** | Target status output | Digital 3.3 V level: HIGH = presence detected; LOW = no presence | output (LD2410 → MCU) | `LD2410_OUT` → ESP32-C6 GPIO 2 |
| **2** | **UART_Tx** | Serial Tx | UART transmit, 256000 baud 8N1 | output (LD2410 → MCU) | `UART_RX` (on MCU side) ← ESP32-C6 GPIO 17 |
| **3** | **UART_Rx** | Serial Rx | UART receive, 256000 baud 8N1 | input (MCU → LD2410) | `UART_TX` (on MCU side) → ESP32-C6 GPIO 16 |
| **4** | **GND** | Power ground | Ground reference | — | `GND` |
| **5** | **VCC** | Power input | DC supply, **5 V** (5–12 V range, ≥200 mA capability) | input | `+5V` (from LM2596S-5.0 buck output) |

Notes from the datasheet electrical section (§5.1, §7):
- Module **supply voltage = 5 V** (range 5–12 V), supply capacity must be **>200 mA**.
- Average operating current **79 mA** at 5 V (datasheet Table 2). Peak / startup may exceed this briefly — datasheet shows measured current Figure 11.
- Module **IO logic level = 3.3 V** on UART_Tx, UART_Rx, OUT. Safe to wire directly to an ESP32-C6 3.3 V GPIO. **No level shifter required** in either direction (the 3.3 V LD2410 outputs are well above the C6's V_IH; the 3.3 V from the C6 is at the LD2410's input V_IH).

---

## Electrical / RF

| Parameter | Value | Source |
|---|---|---|
| Operating frequency | 24010 – 24245 MHz | Datasheet §7 |
| Modulation | FMCW (frequency-modulated continuous wave) | Datasheet §7 |
| Sweep bandwidth | 250 MHz | Datasheet §7 |
| Operating voltage | DC 5 V (range 5–12 V), supply ≥ 200 mA | Datasheet §5.1, §7 |
| Average operating current | 79 mA @ 5 V | Datasheet Table 2 |
| Peak current (startup / transient) | not explicitly stated; >100 mA observed in Figure 11 of datasheet | Datasheet §7 Figure 11 |
| IO logic level | 3.3 V (UART_Tx, UART_Rx, OUT) | Datasheet §5.1 |
| UART baud rate (default) | **256000** | Datasheet §5.1 |
| UART format | **1 stop bit, no parity** (8N1) | Datasheet §5.1 |
| Detection distance | 0.75 – 6 m, configurable in 0.75 m gates 1..8 | Datasheet §5.2, §7 |
| Detection angle | ±60° | Datasheet §7 |
| Distance resolution | 0.75 m | Datasheet §7 |
| Antenna gain | 5.1 dBi @ 24-24.25 GHz (PCB patch); 2.72 dBi @ 2.4-2.5 GHz (BLE chip antenna) | FCC ID §2.7 |
| Ambient operating temperature | −40 to +85 °C | Datasheet §7 |
| Bluetooth | BLE for configuration via HLKRadarTools mobile app; broadcast name `HLK-LD2410B_xxxx`; default password `HiLink`; can be disabled via UART command | Datasheet §6 |

---

## OAS pinout verification

For each OAS J4 pin assignment (`generate.py` lines 11846–11910), confirm against
the HLK-LD2410B datasheet Pin Definition Table:

| OAS J4 pin (current generate.py) | OAS assignment in generate.py | Datasheet pin name for that pin number | Match? |
|---|---|---|---|
| J4 pin 1 (Y = 140.97 mm) | **VCC** (+5 V supply) | **OUT** (target status output) | **NO — MISMATCH** |
| J4 pin 2 (Y = 143.51 mm) | GND | UART_Tx (serial out) | **NO — MISMATCH** |
| J4 pin 3 (Y = 146.05 mm) | TX (LD2410 → MCU; wired to MCU UART_RX label) | UART_Rx (serial in) | **NO — MISMATCH** (LD2410 pin 3 is the MCU-to-LD2410 direction, not the other way) |
| J4 pin 4 (Y = 148.59 mm) | RX (MCU → LD2410; wired to MCU UART_TX label) | GND | **NO — MISMATCH** (UART_TX wired to GND would short the MCU's UART driver into the 5 V buck's return) |
| J4 pin 5 (Y = 151.13 mm) | OUT (presence interrupt) | VCC (5 V power input) | **NO — MISMATCH** (powering 5 V into a 3.3 V MCU GPIO 2 would damage the C6) |

**Result: the OAS J4 pin order is reversed end-for-end from the datasheet, and is electrically unsafe as currently drawn.**

If this footprint is built and the LD2410 module is soldered in:
1. Module Pin 5 (VCC, 5 V input) lands on OAS J4 Pin 1, which is wired to the +5 V rail. **Coincidentally correct** for power — only because the wiring at both ends of the reversed pair happen to be supply pins.
2. Module Pin 4 (GND) lands on OAS J4 Pin 2 (also wired to GND). **Coincidentally correct.**
3. Module Pin 3 (UART_Rx, input on the LD2410) lands on OAS J4 Pin 3 (driven by the MCU's UART_RX label = ESP32 GPIO 17, which is an MCU **input**). **Two inputs driving each other — neither side hears anything.**
4. Module Pin 2 (UART_Tx, output from LD2410) lands on OAS J4 Pin 4 (driven by the MCU's UART_TX label = ESP32 GPIO 16, which is an MCU **output**). **Two outputs driving each other — bus contention.**
5. Module Pin 1 (OUT, **3.3 V** output) lands on OAS J4 Pin 5, which is wired to the `LD2410_OUT` label → MCU GPIO 2 input. **Functionally correct direction**, but the **net name is wrong** at this position.

In short: power and ground happen to land on the right pins by accident, but the UART direction is swapped (TX/RX crossed in the wrong way for this orientation) **and** the OUT signal is at the wrong end of the row.

**Required fix**: re-map `J4_PIN_Y` in `generate.py` (lines 11849-11855) so that **pin 1 = OUT, pin 2 = TX, pin 3 = RX, pin 4 = GND, pin 5 = VCC**. The OUT/UART_TX/UART_RX/GND/VCC wires on the schematic side stay attached to the same hierarchical labels; only the **mapping from those labels to the physical J4 pin numbers** changes. After the swap, re-verify in 2d-top.svg that the LD2410's antenna short edge still points "NORTH" toward 12:00 (it should — `LD2410_ROTATION=270` is unrelated to pin numbering).

Also update the LD2410-side body short-axis dimension `LD2410_BODY_H` from 15.24 mm to **~7 mm** (datasheet value) — see "Discrepancies" below.

---

## OAS-specific notes

- **5 V rail**: J4 pin 5 must be tied to the OAS +5 V net (output of U1 = LM2596S-5.0 buck). The LD2410 datasheet's `5–12 V` range means feeding it from the **24 V input** (via a smaller series resistor or directly) would technically be allowed, but adds heat in the LD2410's internal LDO and the average current ×24 V = ~1.9 W of dissipation in the module. **Keep on +5 V**.
- **C11 decoupling**: 100 nF ceramic close to J4 pin 5 (VCC) ↔ pin 4 (GND). After the J4 pin-order fix, C11 placement may need to shift to match the new VCC/GND end of the row.
- **OUT pin usage**: GPIO 2 is configured in ESPHome as a `binary_sensor.gpio` with `pulldown` mode (LD2410 OUT is `active high`, idle low). The OUT path is redundant with the UART data stream — both report presence — but OUT has lower latency (no UART parse needed) and is useful as a wake-from-light-sleep interrupt source.
- **UART**: ESPHome `ld2410:` component, `uart:` config with `baud_rate: 256000`, `data_bits: 8`, `parity: NONE`, `stop_bits: 1`. The C6's UART hardware supports 256000 baud cleanly — no software UART needed.
- **Antenna keep-out**: the LD2410's PCB antenna patches sit at the short edge opposite the pin row. The OAS layout must keep that edge clear of nearby copper, ground planes on the OAS PCB **directly below the antenna patches**, large metal objects, and (critically) clear of the AK-N-94 cover's internal metal screw bosses if any. The white perforated ABS of AK-N-94 is RF-transparent at 24 GHz (datasheet §8 calls out ABS as compatible) — no separate radome needed.
- **Back-lobe**: the LD2410 also radiates rearward (toward the OAS PCB) at reduced gain. Datasheet §5.5 recommends a metal backplane to suppress the back lobe. OAS does not currently include one; the back lobe will see the SEN66 body and the rear-side PCB copper — acceptable for a small enclosure but a possible source of false detections from objects directly behind the OAS unit (i.e., inside the electrical wall box on the other side of the mounting wall). Re-evaluate after first-prototype field testing.

---

## Discrepancies vs current generate.py / CLAUDE.md

| # | Item | Current OAS value | Datasheet value | Severity | Action |
|---|---|---|---|---|---|
| 1 | **J4 pin order** | Pin 1=VCC, 2=GND, 3=TX, 4=RX, 5=OUT | Pin 1=**OUT**, 2=**Tx**, 3=**Rx**, 4=**GND**, 5=**VCC** | **CRITICAL — UART direction is swapped and OUT signal is at the wrong end** | Swap the `J4_PIN_Y` mapping in `gen_sensors_sch()` (lines 11849-11855) end-for-end. Re-verify schematic + PCB renders. |
| 2 | **`LD2410_BODY_H` (short axis on PCB)** | 15.24 mm | **7 mm** (datasheet §4.1) | Medium — over-allocates PCB shadow area; may also affect F.SilkScreen body outline and zip-tie/clearance calculations near the LD2410 | Reduce `LD2410_BODY_H` to ~7.62 mm (1.27 mm grid-aligned multiple slightly above the 7 mm datasheet value, for silkscreen breathing room) **after** confirming with the physical sample dimensions on arrival. Keep `LD2410_BODY_W` at 35.56 mm (matches 35 mm datasheet + 0.56 mm margin). |
| 3 | **`LD2410_BODY_Z` (height above OAS PCB)** | 7.0 mm | ~5–7 mm (community-measured, datasheet does not state) | Low — current value is the conservative upper bound | Keep at 7.0 mm. Mark as TBD-pending-physical-measurement in `generate.py` comment. |
| 4 | Module identification in CLAUDE.md hardware table | "HiLink LD2410B/C" (ambiguous) | The B and C variants have **different pin orders and dimensions** | Low — but violates the Module Identification rule (no generic name) | Pin CLAUDE.md to **HLK-LD2410B** specifically. The C variant is **not** a drop-in substitute (different pin order). |
| 5 | EAN/GTIN | Not listed | Not assigned for HLK-LD2410B at Botland (May 2026) | Low — MPN + FCC ID + LCSC C5183132 satisfy Module Identification | Document that the OAS uses MPN + FCC ID for identification rather than EAN. |

---

## Sources

1. **HiLink HLK-LD2410B Radar Module User Manual V1.04 (2022-06-29)** — FCC-filed PDF, fetched directly. <https://fcc.report/FCC-ID/2AD56HLK-LD2410B-P/6620025.pdf> — pin definition Table 1 page 7, dimensions §4.1 page 6 ("7mm × 35mm, 1.27 mm pitch, 0.6 mm hole"), electrical Table 2 page 16 (5–12 V, 79 mA avg, 256000 8N1, 3.3 V IO, FCC ID 2AD56HLK-LD2410B-P).
2. **HiLink HLK-LD2410 Manual V1.03 (2022-06-29)** — base variant manual. <https://seengreat.com/upload/file/86/HLK+LD2410+Life+Presence+Sensor+Module+Manual+V1.03(220629).pdf> — pin definition Table 1 page 7 (identical pin order to LD2410B: Pin 1 = OUT, Pin 2 = UART_Tx, Pin 3 = UART_Rx, Pin 4 = GND, Pin 5 = VCC).
3. **HiLink HLK-LD2410C Datasheet** — <https://tehno32.ru/sites/default/files/download/hlk_ld2410/hlkld2410c.pdf> — pin definition Table 1 page 8 (**DIFFERENT** pin order: Pin 1 = UART_Tx, Pin 2 = UART_Rx, Pin 3 = OUT, Pin 4 = GND, Pin 5 = VCC), dimensions 16 × 22 mm, pitch 2.54 mm.
4. **HiLink official product page (LD2410B)** — <https://www.hlktech.net/index.php?id=1094> — confirms 7 × 35 mm, 1.27 mm pitch, 0.6 mm hole, 5-12 V supply.
5. **HiLink official product page (LD2410C)** — <https://www.hlktech.net/index.php?id=1095>.
6. **ESPHome `ld2410` component** — <https://esphome.io/components/sensor/ld2410.html> — confirms 256000 baud / 8N1 default, OUT pin can be wired to any GPIO as a `binary_sensor.gpio`.
7. **`ncmreynolds/ld2410` Arduino library README** — <https://github.com/ncmreynolds/ld2410> — confirms 5 V supply, 3.3 V IO, 256000 baud default, 1.27 mm pin pitch.
8. **studiopieters.nl complete guide to the HLK-LD2410** — <https://www.studiopieters.nl/the-complete-guide-to-the-hlk-ld2410-24ghz-human-presence-radar-module/> — confirms Pin 1 = OUT, Pin 5 = VCC ordering.
9. **OpenELAB LD2410B vs LD2410C comparison** — <https://openelab.io/blogs/learn/difference-between-hlk-ld2410b-and-hlk-ld2410c> — confirms B is 7 × 35 mm 1.27 mm, C is 16 × 22 mm 2.54 mm.
10. **LCSC HLK-LD2410B-P product page (C5183132)** — <https://www.lcsc.com/product-detail/C5183132.html> — pin-pre-soldered variant in stock 530 ea ~$2.92.
11. **TinyTronics (NL) HLK-LD2410B-P** — <https://www.tinytronics.nl/en/home-automation/sensors/motion-and-presence/hi-link-hlk-ld2410b-24ghz-radar-sensor-module-with-bluetooth-1.27mm-pinheaders> — confirms 1.27 mm pitch on the with-pins variant.
12. **Home Assistant community "LD2410C vs 2410B vs LD2410S vs 2411 vs HLK-LD2420 vs LD2450"** — <https://community.home-assistant.io/t/ld2410c-vs-2410b-vs-ld2410s-vs-2411-vs-hlk-ld2420-vs-ld2450/652599> — cross-checks that B and C share the same firmware/protocol but differ in pin order, pitch, and dimensions.
