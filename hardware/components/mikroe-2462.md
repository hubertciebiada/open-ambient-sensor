# MIKROE-2462 — NFC Tag 2 Click

Verified specifications for the MikroElektronika **NFC Tag 2 Click** (MIKROE-2462)
used as the OAS dynamic NFC daughterboard. Cross-checked against the official
MikroE product datasheet PDF (PID MIKROE-2462, mirrored on Digi-Key), TME catalog,
Mouser, DigiKey, RS Components, and the mikroBUS Standard Specification.

Verification date: 2026-05-13.

---

## Identifiers

- **MPN**: `MIKROE-2462` (MikroElektronika)
- **Marketing name**: NFC Tag 2 Click (also written "NFC Tag 2 click")
- **Manufacturer**: MikroElektronika d.o.o. (Belgrade, Serbia)
- **NFC chip on production boards**: **NT3H1101** (NXP NTAG I²C, 888 bytes EEPROM, 64 bytes SRAM) — see "Chip variant" note below.
- **EAN/GTIN**: **NOT found** in any consulted distributor listing as of 2026-05-13. None of Mouser, DigiKey, TME, RS Components, Bürklin, or Future Electronics expose a GTIN/EAN field for MIKROE-2462. Manufacturer code `MIKROE-2462` is the only universally-recognized identifier; use it (not an EAN) when ordering. Botland does not currently list this part (verified absent), so no Polish EAN exists.
- **Product page (manufacturer)**: <https://www.mikroe.com/nfc-tag-2-click>
- **Datasheet/manual PDF (Digi-Key mirror, authoritative)**: <https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/2165/MIKROE-2462_Web.pdf>
- **Schematic PDF**: <https://download.mikroe.com/documents/add-on-boards/click/nfc-tag-2/nfc-tag-2-click-schematic-v101-a.pdf>
- **Distributor — TME (EU)**: <https://www.tme.eu/en/details/mikroe-2462/add-on-boards/mikroe/nfc-tag-2-click/>
- **Distributor — Mouser (global)**: <https://www.mouser.com/ProductDetail/Mikroe/MIKROE-2462>
- **Distributor — DigiKey (global)**: <https://www.digikey.com/en/products/detail/mikroelektronika/MIKROE-2462/6691194> — ~$14 USD, 12+ units in stock at fetch time.
- **Distributor — RS Components (export)**: <https://export.rsdelivers.com/product/mikroelektronika/mikroe-2462/mikroelektronika-nfc-tag-2-click-arduino-board/1360855> — RS stock code `136-0855`.
- **Distributor — Bürklin (EU)**: <https://www.buerklin.com/en/nfc-tag-2-click/p/74s7590>

### Chip variant — NT3H1101 vs NT3H2111

The **MikroE product page text** (mikroe.com/nfc-tag-2-click, May 2026) and several
3rd-party listings (DigiKey, Amazon, MG Super Labs, Electromaker, Future Electronics)
mention **NT3H2111**.

The **authoritative MikroE datasheet PDF** (PID MIKROE-2462, dated 2017-02-24) and the
**TME catalog** ("Comp: NT3H1101") explicitly identify the on-board chip as **NT3H1101**.

Both chips are in NXP's NTAG I²C family and share most of the I²C register map, but the
EEPROM size differs:

| Variant | EEPROM (user memory) | SRAM | I²C address |
|---|---|---|---|
| **NT3H1101** | 888 bytes (1 KB total incl. config) | 64 bytes | 0x55 |
| NT3H2111 (NTAG I²C *plus* 1k) | 888 bytes | 64 bytes | 0x55 |
| NT3H2211 (NTAG I²C *plus* 2k) | 1904 bytes | 64 bytes | 0x55 |

The MikroE datasheet code example writes **888 bytes** of `user_memory` (`memset(...,0,888)`
and `nfctag2_memory_write(0, ..., 888)`), which matches the NT3H1101 user-memory size.

**Conclusion**: production boards as of 2017 onward carry **NT3H1101**. The MikroE
product page's "NT2H2111" mention is most likely an unmaintained marketing edit;
the firmware-relevant chip on the silicon is **NT3H1101** unless verified otherwise
on the physical board after order. **Verify with the actual batch** (the chip
silkscreen mark or test the I²C config register at boot) before locking firmware to
either chip's register layout.

For OAS: this distinction is **only** firmware-side. ESPHome external_component can
target either chip with the same I²C address (0x55) and the same INT/FD signal; the
NT3H1101 vs NT3H2111 difference is internal register-map detail handled by the
[`thijses/NT3H_thijs`](https://github.com/thijses/NT3H_thijs) Arduino library, which
supports **NT3H2111, NT3H2211, NT3H1101, NT3H1201**.

---

## Mechanical

| Dimension | Value | Source |
|---|---|---|
| **Click board size category** | **L** (long) | MikroE datasheet PDF, "Specification" table |
| **Board length** | **57.15 mm** | MikroE datasheet PDF |
| **Board width** | **25.40 mm** | MikroE datasheet PDF |
| **Board thickness** | ~1.6 mm | Standard MikroE PCB (not annotated) |
| Pin pitch (within a row) | 2.54 mm | mikroBUS standard |
| Row spacing (centerline-to-centerline) | 22.86 mm | mikroBUS standard (= 9 × 2.54 mm) |
| Pin headers | 2× 1×8 male, 2.54 mm pitch, vertical | mikroBUS standard |

OAS CLAUDE.md previously listed `L = 57.15 × 25.4 mm` — **confirmed correct** by the
official MikroE PDF (v0.15.6 correction validated).

### Antenna position on board

From the high-resolution product photo in the MikroE datasheet PDF (page 1) and the
silkscreen "NFC Tag 2 click" text near the pin block:

```
   short edge (NO pin header)
  ┌──────────────────────────┐
  │      ___________         │
  │     /   PCB    \         │
  │    / SPIRAL     \        │  ← antenna fills the upper ~35 mm
  │    \ ANTENNA    /        │     of the board length
  │     \_________/          │
  │   ──────────────         │
  │   U1  R1..R5  C1 C2  LD1 │  ← NT3H1101, matching network,
  │   GND/NC ◯  ◯  ◯ ◯ ◯ ◯ ◯ ◯  PWR/FD LEDs
  │   NC/NC  ◯  ◯  ◯ ◯ ◯ ◯ ◯ ◯  pin block (16 pins, 2×8)
  │   "NFC Tag 2 click"      │
  └──────────────────────────┘
   short edge WITH pin header (mikroBUS male pins protrude DOWN)
```

- **Antenna is OPPOSITE the pin block**, occupying roughly the upper ~36 mm of the
  57.15 mm board length.
- **The IC (U1, NT3H1101)**, its decoupling caps, matching components, and the two
  status LEDs (PWR, FD) sit between the antenna and the pin block.
- **Pin 1 of the mikroBUS header is at the antenna-distal end** of the board (the
  end with the pin block); the antenna is at the antenna-distal-of-pin-1 end.

This matches the OAS CLAUDE.md description ("antenna spiral on the long side
opposite the pin block").

### Body Z-height above the OAS PCB

Composed of:

- Female pin socket (2× 1×8) on OAS PCB: typical body height ~8.5 mm (e.g. Samtec
  SSW-108-01-G-D, or generic 0.1"-pitch socket strip ~8.0–8.5 mm).
- Click board PCB thickness: ~1.6 mm.
- Tallest top-side component on the Click board: the NT3H1101 IC (TSSOP14, ~1.1 mm
  body) and the FD LED (~1.0 mm). Negligible compared to pin socket.
- Bottom-side components on the Click board: none of significance.

**Estimated total height above the OAS PCB top surface**: ~**10–11 mm** (socket
body 8.5 mm + Click PCB 1.6 mm + ~1 mm slack). The CLAUDE.md value of "~7 mm"
under-estimates by ~3–4 mm and should be revised if the OAS uses standard 8.5 mm
female sockets; the value matches only if a **low-profile 5 mm socket** is used
(e.g. SAMTEC ESQ-108-39-G-D, body ~5.3 mm — possible but less common).

**For the 17 mm front-side height budget**: even at 11 mm, the NFC Click clears
the 17 mm peripheral hard constraint with ~6 mm margin. Inside the SEN66 zone
(≥22 mm), no issue.

---

## Electrical

| Parameter | Value | Source |
|---|---|---|
| Power supply | **3.3 V only** (NOT 5 V tolerant) | MikroE datasheet PDF, "Specification" table |
| Interface | I²C (fast mode, up to 400 kHz) | MikroE datasheet PDF |
| I²C address (7-bit) | **0x55** | NXP NT3H1101 datasheet (default address) |
| Field-detection output | Open-drain, asserted low when NFC RF field present | NT3H1101 datasheet; LED LD2 driven from same pin |
| Operating frequency (NFC) | 13.56 MHz | MikroE datasheet PDF |
| Contactless data rate | 106 kbit/s | MikroE datasheet PDF |
| EEPROM size (NT3H1101) | 888 bytes user memory | NT3H1101 datasheet; MikroE code example |
| SRAM (volatile pass-through buffer) | 64 bytes | NT3H1101 datasheet |
| Energy harvesting | Yes — up to ~5 mA @ 2 V at NT3H1101 VOUT (room temp), routed to FD LED on this board | MikroE datasheet PDF |

---

## Pin assignment — mikroBUS socket

The mikroBUS standard defines 16 pins in two columns of 8 (2.54 mm pitch, row
spacing 22.86 mm). The MikroE datasheet uses an **internal numbering convention**
where the **left column is pins 1–8 top-to-bottom (AN at top, GND at bottom)** and
the **right column is pins 16–9 top-to-bottom (PWM at top, GND at bottom)**.

| MikroE pin # | mikroBUS signal | NFC Tag 2 Click usage | OAS net |
|---:|---|---|---|
| **1** | AN | NC (not connected on Click) | — |
| **2** | RST | NC | — |
| **3** | CS | NC | — |
| **4** | SCK | NC | — |
| **5** | MISO | NC | — |
| **6** | MOSI | NC | — |
| **7** | +3.3V | **Power supply** | **OAS +3V3 rail** |
| **8** | GND | **Ground** | **OAS GND** |
| **9** | GND | **Ground** | **OAS GND** |
| **10** | +5V | NC | — (do NOT wire; Click is 3.3 V only) |
| **11** | SDA | **I²C Data** | **OAS SDA (ESP32-C6 GPIO 6)** |
| **12** | SCL | **I²C Clock** | **OAS SCL (ESP32-C6 GPIO 7)** |
| **13** | RX | NC | — |
| **14** | TX | NC | — |
| **15** | INT | **FD — Field-detection output** (open-drain) | **OAS NFC_FD (ESP32-C6 GPIO 3)** |
| **16** | PWM | NC | — |

### IMPORTANT: pin-number convention discrepancy

OAS `CLAUDE.md` v0.12 lists the click-side connections as:

> mikroBUS pin 7 (+3V3), pin 8 (GND), **pin 10 (INT)**, **pin 13 (SCL)**, **pin 14
> (SDA)**, pin 16 (GND)

The **signal assignment is correct**, but the **pin numbers use a different
convention** (the Zephyr / SparkFun "standard mikroBUS" numbering where INT=10,
SCL=13, SDA=14, +5V=15). MikroE's own NFC Tag 2 Click datasheet numbers the same
**physical pins** as INT=15, SCL=12, SDA=11.

This is a documentation discrepancy only, not an electrical error: the physical
pin positions are identical in both conventions, only the integer labels differ.

**Recommendation for OAS KiCad schematic**: use the **MikroE-internal numbering**
(INT=15, SCL=12, SDA=11, +5V=10) for consistency with the MikroE datasheet —
otherwise a future reader cross-referencing the Click datasheet against the
schematic will hit confusion. Update `CLAUDE.md` v0.12 changelog entry and the
hierarchical-label names in `sensors.kicad_sch` accordingly.

The KiCad symbol `Connector_Generic:Conn_02x08_Top_Bottom` already used in
chunk #5c should map its 16 pins to the MikroE numbering convention; the
silkscreen label on the OAS PCB should read pin numbers in the same convention.

### Physical pin 1 corner

In the MikroE numbering, **pin 1 (AN) is the top-left pin** when the board is held
with the antenna pointing AWAY from the viewer (i.e. antenna at the far end, pin
block nearest the viewer, board top-side facing up). On the OAS PCB, the matching
female socket should mark pin 1 at the corresponding corner.

---

## OAS pinout verification (against CLAUDE.md v0.12)

| OAS net | OAS docs (CLAUDE.md, signal name) | Verified click-pin | Verdict |
|---|---|---|---|
| +3V3 | "mikroBUS pin 7 (+3.3V)" | Pin 7 (MikroE: 3.3V) | **OK** |
| GND | "mikroBUS pin 8 (GND)" | Pin 8 (MikroE: GND, left column) | **OK** |
| GND | "mikroBUS pin 16 (GND)" — but in MikroE numbering pin 16 = PWM = NC ! | Click GND on **right column** is **pin 9** in MikroE numbering | **Correct signal, wrong number.** OAS docs say "pin 16 GND" — that is the SparkFun/Zephyr-numbered pin 8 of left column? Re-check. Below clarifies. |
| NFC_FD → GPIO 3 | "mikroBUS pin 10 (INT)" | MikroE numbering: pin 15 = INT/FD | **Correct signal, different pin number** (SparkFun/Zephyr numbering uses 10; MikroE uses 15). |
| SCL → GPIO 7 | "mikroBUS pin 13 (SCL)" | MikroE numbering: pin 12 = SCL | **Correct signal, different pin number.** |
| SDA → GPIO 6 | "mikroBUS pin 14 (SDA)" | MikroE numbering: pin 11 = SDA | **Correct signal, different pin number.** |

**Net-list-level verdict**: every signal connection in CLAUDE.md v0.12 maps to the
correct physical pad on the MIKROE-2462. The recorded **pin numbers** follow the
Zephyr/SparkFun convention while the MikroE datasheet uses its own (older,
established) numbering. No PCB-level fix is needed; the OAS net list will route
correctly either way as long as the KiCad symbol's pad numbering matches the
chosen convention.

### Action items for CLAUDE.md v0.12 entry

1. Either: (a) renumber the CLAUDE.md citation to MikroE convention (INT=15,
   SCL=12, SDA=11, +3V3=7, GND=8 & 9) — preferred, since the MikroE datasheet is
   the closest authoritative reference; OR (b) leave the Zephyr numbering and add
   an explicit note that "pin numbers cited use Zephyr/SparkFun mikroBUS
   convention; on MikroE's datasheet the same pins are 15/12/11/7/8/9."
2. The CLAUDE.md "pin 16 (GND)" citation is **incorrect under either
   convention** — there is no GND on pin 16 in either numbering. The two GNDs on
   the MikroE board are pin 8 (left column bottom) and pin 9 (right column
   bottom, MikroE numbering). In Zephyr numbering those are still pin 8 (left
   column) and pin 16 (right column). The CLAUDE.md citation is therefore
   correct under Zephyr numbering, NOT under MikroE numbering. Pick one and
   stick to it.

### Unused mikroBUS pins (must be NC / `no_connect` in OAS schematic)

In MikroE numbering: pins **1, 2, 3, 4, 5, 6, 10, 13, 14, 16** are NC on the
Click board itself. The OAS schematic for U4 (the NFC daughterboard socket)
should place `no_connect` markers on these 10 pins to keep ERC silent.

(In Zephyr numbering the equivalents are pins 1, 2, 3, 4, 5, 6, 9, 11, 12, 15.)

---

## On-board LEDs

| Designator | Name | Description |
|---|---|---|
| LD1 | PWR | Indicates power is applied to the click board |
| LD2 | FD | Lights when an external NFC RF field is detected (driven from NT3H1101 VOUT/FD pin) |

Both LEDs are visible from the top side. Inside the OAS sealed enclosure these
LEDs are not externally visible, so they contribute only to the internal heat /
optical-leakage budget — negligible (~1 mA at idle for PWR, FD only on RF
activity).

---

## ESPHome integration

- **No native ESPHome component** for NT3H1101/NT3H2111 as of 2026-05-13. Custom
  `external_component` wrapper required.
- **Reference Arduino library**: [`thijses/NT3H_thijs`](https://github.com/thijses/NT3H_thijs)
  — supports NT3H2111, NT3H2211, NT3H1101, NT3H1201. Works under Arduino-ESP32 /
  ESP-IDF wrapper.
- **Narrower variant library**: [`thijses/NT3H2x11_thijs`](https://github.com/thijses/NT3H2x11_thijs)
  — supports only NT3H2111 / NT3H2211. **Avoid for MIKROE-2462** since the
  actual chip is the older NT3H1101 (use `NT3H_thijs` instead).
- I²C address (default): `0x55` (7-bit). No address-strap pins on the click
  board — fixed.
- Field-detection (FD) pin: open-drain, asserted **low** when external RF field
  is present. On ESP32-C6, configure as `INPUT_PULLUP` on GPIO 3; trigger on
  falling edge.

---

## Bill-of-materials summary

| Field | Value |
|---|---|
| OAS designator | U4 (NFC daughterboard socket footprint on the OAS PCB) |
| Order under MPN | `MIKROE-2462` |
| Quantity per OAS unit | 1 |
| Indicative price (DigiKey 2026-05-13) | ~$14 USD (12+ in stock) |
| Indicative price (RS Components) | ~£12 GBP |
| Indicative price (TME) | ~€13 EUR |
| EU stock | Bürklin, TME (EU), RS (export), Distrelec, Farnell |
| Recommended companion: 2× 1×8 female pin socket (2.54 mm) | Generic, e.g. Samtec SSW-108-01-G-D or similar; or low-profile 5 mm body if vertical clearance is tight |
| Companion: 1× 100 nF 0402 decoupling cap (C12 in OAS schematic) | Across +3V3/GND at socket |

---

## Sources

1. MikroElektronika, *NFC Tag 2 Click — PID: MIKROE-2462* (datasheet PDF), <https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/2165/MIKROE-2462_Web.pdf> — authoritative chip/dimensions/pinout.
2. MikroElektronika product page, <https://www.mikroe.com/nfc-tag-2-click> — current marketing description (mentions NT3H2111; see chip-variant discussion above).
3. MikroElektronika schematic PDF, <https://download.mikroe.com/documents/add-on-boards/click/nfc-tag-2/nfc-tag-2-click-schematic-v101-a.pdf> — v1.01 schematic.
4. TME (EU) product page, <https://www.tme.eu/en/details/mikroe-2462/add-on-boards/mikroe/nfc-tag-2-click/> — confirms `Comp: NT3H1101`, size L, 3.3 V DC.
5. Mouser, <https://www.mouser.com/ProductDetail/Mikroe/MIKROE-2462> — distributor stock.
6. DigiKey, <https://www.digikey.com/en/products/detail/mikroelektronika/MIKROE-2462/6691194> — distributor stock; lists NT3H2111 in description.
7. RS Components, <https://export.rsdelivers.com/product/mikroelektronika/mikroe-2462/mikroelektronika-nfc-tag-2-click-arduino-board/1360855> — RS code 136-0855.
8. MikroElektronika, *mikroBUS Standard Specification v2.00*, <https://download.mikroe.com/documents/standards/mikrobus/mikrobus-standard-specification-v200.pdf> — physical and electrical specification.
9. MikroE blog, *mikroBUS pinout standard specification*, <https://www.mikroe.com/blog/mikrobus-pinout-standard-specification>.
10. Zephyr Project documentation, *mikro-bus device-tree binding*, <https://docs.zephyrproject.org/latest/build/dts/api/bindings/gpio/mikro-bus.html> — pin-numbering convention 1–16 (alternative to MikroE-internal numbering).
11. NXP Semiconductors, *NT3H1101/NT3H1201 NTAG I²C Product Data Sheet*, <https://www.nxp.com/docs/en/data-sheet/NT3H1101_1201.pdf> — chip-level specs (EEPROM 888 B, SRAM 64 B, I²C 0x55).
12. thijses/NT3H_thijs Arduino library, <https://github.com/thijses/NT3H_thijs>.
