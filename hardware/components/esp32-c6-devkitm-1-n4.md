# ESP32-C6-DevKitM-1-N4

Verified specifications for the Espressif ESP32-C6-DevKitM-1-N4 development board
used as the OAS MCU module. Cross-checked against the official Espressif schematic,
mechanical dimensions drawing, user guide, and a third-party pinout reference.

Verification date: 2026-05-13.

---

## Identifiers

- **MPN**: `ESP32-C6-DevKitM-1-N4`  (Espressif official; `-N4` = 4 MB SiP flash variant)
- **EAN/GTIN**: `5904422385651` (Botland, Poland — verified in CLAUDE.md per project context; not re-fetched live)
- **Manufacturer**: Espressif Systems (Shanghai) Co., Ltd.
- **Onboard module**: ESP32-C6-MINI-1 (PCB antenna) **or** ESP32-C6-MINI-1U (U.FL connector) — the DevKitM-1-N4 SKU uses the **MINI-1** PCB-antenna variant
- **SoC**: ESP32-C6FH4 (RISC-V single-core 160 MHz, WiFi 6 / BLE 5 / 802.15.4, 320 KB SRAM, 4 MB SiP flash)
- **Schematic**: <https://dl.espressif.com/dl/schematics/esp32-c6-devkitm-1-schematics.pdf> (rev V1.0, 2023-03-03)
- **Dimensions drawing**: <https://dl.espressif.com/dl/schematics/esp32-c6-devkitm-1-dimensions.pdf>
- **PCB layout**: <https://dl.espressif.com/dl/schematics/esp32-c6-devkitm-1-pcb-layout.pdf>
- **User guide**: <https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32c6/esp32-c6-devkitm-1/user_guide.html>
- **Distributor (Botland, EU)**: <https://botland.store/> — search EAN 5904422385651
- **Third-party pinout reference**: <https://www.espboards.dev/esp32/esp32-c6-devkitm-1/>

---

## Mechanical

All values read directly from the official `esp32-c6-devkitm-1-dimensions.pdf`
(Espressif, units mm). Tolerances not specified in the drawing — assume the
standard PCB ±0.1 mm fabrication tolerance unless Espressif publishes otherwise.

| Dimension | Value | Notes |
|---|---|---|
| Board length | **48.26 mm** | Long axis. Imperial-origin (1.9 in). |
| Board width | **25.40 mm** | Short axis. Imperial-origin (1.0 in). |
| Pin pitch (within a row) | **2.54 mm** | Standard 0.1 in. |
| Row spacing (J1 to J3 centerline-to-centerline) | **22.86 mm** | = 9 × 2.54 mm. Header rows sit on opposite long edges of the board, **1.27 mm inset** from each long edge. |
| Distance, antenna short edge to pin 1 centre | **5.37 mm** | Pin block is **NOT** centered on the long axis — it is shifted toward the connector edge by (48.26 − 5.37 − 14×2.54)/2 = (48.26 − 5.37 − 35.56)/2 = **3.665 mm**. Centerline offset from board centre: +3.665 mm toward connectors. |
| USB-C connectors to nearest short edge (centerline) | **11.125 mm** | Both USB-C connectors sit at the connector (non-antenna) end of the board; their centerlines lie 11.125 mm from that short edge. |
| Pin header position relative to board long edges | **1.27 mm** inset | I.e. the pin row centreline is 1.27 mm from the long edge of the PCB. The 22.86 mm row-to-row spacing equals 25.40 − 2×1.27. |
| ESP32-C6-MINI-1 module footprint (approx.) | **13.20 mm wide** | Width of the module antenna keep-out on the dimensions drawing. The module is centred on the board width. |
| Board thickness | ~1.6 mm | Standard PCB; not annotated on the dimensions drawing. |
| Body height above OAS PCB (mated through-hole headers, no socket) | ~**8–9 mm** | Pin-header standoff (~2.5 mm) + PCB (1.6 mm) + tallest top-side component (USB-C connector body ~3.2 mm above the DevKit PCB top side, but on the side facing OAS PCB this is 0). Worst case if DevKitM-1 oriented "components-up": ~8.6 mm to USB-C top. If components-down: ~4.5 mm to PCB bottom. CLAUDE.md value of ~8.6 mm is consistent with the antenna-up / components-up orientation. |
| 3D STEP model | Not officially published by Espressif | Community STEP available on GitHub (search "ESP32-C6-DevKitM-1 step"). For OAS use the dimensions PDF as authoritative; build a own simplified STEP if needed. |

**Mounting holes**: none. The DevKitM-1 has **no mounting holes**. Retention on the
OAS PCB is via the two 1×15 through-hole pin headers (or female sockets) only.

---

## Pin headers

- **Layout**: 2× 1×15 through-hole pin headers (30 pins total), 2.54 mm pitch, vertical (perpendicular to board).
- **Pin count per row**: **15** (J1 left, J3 right when viewed top-side with antenna up).
- **Row spacing**: **22.86 mm** centerline-to-centerline (= 9 × 2.54 mm = 0.900 in).
- **Pin block offset along long axis**: pin 1 of each row sits **5.37 mm** from the antenna short edge (measured to pin 1 centre).
- **Pin block centred on body?**  **No.** With 14 pin-pitches (= 35.56 mm) of pins occupying the centre run, the remaining 48.26 − 35.56 = 12.70 mm of board is split asymmetrically: **5.37 mm on the antenna side** and **7.33 mm on the USB-C connector side**. Asymmetric by 1.96 mm; the pin block is shifted **toward the antenna edge**.
- **Pin 1 location (relative to each long edge)**: 1.27 mm inset.

---

## GPIO map (J1 and J3 board pin numbers → ESP32-C6 GPIO)

Pin numbering follows Espressif's schematic and user guide. J1 is on the left
when the board is viewed top-side with the antenna facing away (12 o'clock).
J3 is on the right.

### J1 (left header, 15 pins)

| Pin | Label | ESP32-C6 net | Type / role | OAS notes |
|---|---|---|---|---|
| J1.1 | 3V3 | ESP_3V3 / VCC_3V3 | 3.3 V output from onboard LDO (or input when LDO bypassed) | Power-rail tie point for OAS 3V3 (drives DevKit when LDO removed) |
| J1.2 | RST | CHIP_PU | EN/reset, active low | Wire to onboard RST button; can expose to OAS recovery header |
| J1.3 | 2 | GPIO2 | Safe non-strap I/O; ADC1_CH2 | **OAS: LD2410 OUT (presence interrupt)** ✓ |
| J1.4 | 3 | GPIO3 | Safe non-strap I/O; ADC1_CH3 | **OAS: NT3H2211 FD (NFC field detect)** ✓ |
| J1.5 | 4 | GPIO4 | **Strap (MTMS, JTAG)**; ADC1_CH4 | Avoid for general I/O. JTAG TMS at boot. |
| J1.6 | 5 | GPIO5 | **Strap (MTDI, JTAG)**; ADC1_CH5 | Avoid for general I/O. JTAG TDI at boot. |
| J1.7 | 0 | GPIO0 | Safe non-strap I/O; ADC1_CH0; XTAL_32K_P | Free spare |
| J1.8 | 1 | GPIO1 | Safe non-strap I/O; ADC1_CH1; XTAL_32K_N | Free spare |
| J1.9 | 8 | GPIO8 | **Strap + onboard RGB LED**; also routed to onboard WS2812 via R3 0 Ω | **OAS: WS2812 status LED (uses onboard NeoPixel)** ✓. Strap pin → must idle high at boot; LED idle-low after init is OK because boot strap is sampled at reset only. |
| J1.10 | 6 | GPIO6 | I²C_SDA (default mapping); ADC1_CH6; FSPICLK | **OAS: I²C SDA** ✓ |
| J1.11 | 7 | GPIO7 | I²C_SCL (default mapping); FSPID | **OAS: I²C SCL** ✓ |
| J1.12 | 14 | GPIO14 | Safe non-strap I/O | Free spare |
| J1.13 | G | GND | — | Ground tie |
| J1.14 | 5V | VCC_5V | 5 V input (from USB-C VBUS) | Not used by OAS (we feed 3V3 directly to J1.1) |
| J1.15 | G | GND | — | Ground tie |

### J3 (right header, 15 pins)

| Pin | Label | ESP32-C6 net | Type / role | OAS notes |
|---|---|---|---|---|
| J3.1 | G | GND | — | Ground tie |
| J3.2 | TX | GPIO16 (UART0_TXD) | UART0 default TX; remappable | **OAS: UART1 TX → LD2410 RX** ✓ (note: J3 silkscreen labels as "TX/RX" but ESPHome can remap UART0 freely) |
| J3.3 | RX | GPIO17 (UART0_RXD) | UART0 default RX; remappable | **OAS: UART1 RX ← LD2410 TX** ✓ |
| J3.4 | 23 | GPIO23 | Safe non-strap I/O; SDIO_DATA3 | Free spare |
| J3.5 | 22 | GPIO22 | Safe non-strap I/O; SDIO_DATA2 | Free spare |
| J3.6 | 21 | GPIO21 | Safe non-strap I/O; SDIO_DATA1 | Free spare |
| J3.7 | 20 | GPIO20 | Safe non-strap I/O; SDIO_DATA0 | Free spare |
| J3.8 | 19 | GPIO19 | Safe non-strap I/O; SDIO_CLK | Free spare |
| J3.9 | 18 | GPIO18 | Safe non-strap I/O; SDIO_CMD | Free spare |
| J3.10 | 15 | GPIO15 | **Strap (boot-mode select)** | Avoid for general I/O |
| J3.11 | 9 | GPIO9 | **Strap + onboard BOOT button** | Avoid for general I/O (and pressing BOOT pulls this low) |
| J3.12 | G | GND | — | Ground tie |
| J3.13 | 13 | GPIO13 | **USB D+** (native USB-Serial-JTAG) | **OAS: USB D+ (used via J2 USB-C native port; not OAS-side after enclosure sealed)** ✓ |
| J3.14 | 12 | GPIO12 | **USB D−** (native USB-Serial-JTAG) | **OAS: USB D− (used via J2 USB-C native port)** ✓ |
| J3.15 | G | GND | — | Ground tie |

### GPIOs NOT exposed on the headers

| GPIO | Reason |
|---|---|
| **GPIO 10** | Not bonded out — ESP32-C6FH4 uses this pin internally for SiP flash communication. |
| **GPIO 11** | Not bonded out — same as GPIO 10. |
| TXD0, RXD0 (module pins 31, 30) | Wired to onboard CP2102N USB-UART bridge (not to header). Same logical net as GPIO16/17 (`UART_TXD`/`UART_RXD`) — both header pins **and** the UART bridge are tied to the chip's UART0 pins. |
| Various NC (chip pins 4, 7, 21, 32, 33, 34, 35) | Not bonded internally by the ESP32-C6-MINI-1 module. |

### Strap pins summary (avoid for general I/O without care)

| GPIO | Strap function | Default at boot |
|---|---|---|
| GPIO 4 | MTMS (JTAG) | floating → JTAG TMS sampled |
| GPIO 5 | MTDI (JTAG) | floating → JTAG TDI sampled |
| GPIO 8 | Boot strap (must be HIGH for SPI boot) | onboard external pull-up via R3 0 Ω + WS2812 D6; idle-low after init is safe |
| GPIO 9 | Boot strap (LOW = download mode) | onboard 10 kΩ pull-up (R5); BOOT button pulls low |
| GPIO 15 | Boot-mode select / FSPI / JTAG select | (varies) |

### USB-reserved pins

| GPIO | Function | Note |
|---|---|---|
| GPIO 12 | USB_D− | Wired to J2 (native USB-C) **and** exposed on J3.14 |
| GPIO 13 | USB_D+ | Wired to J2 (native USB-C) **and** exposed on J3.13 |

In OAS we use these for flashing/debug via J2 before the case is sealed. After
sealing, GPIO 12/13 remain tied to the on-board USB-C connector, which sits
unused inside the enclosure (no harm — connector is detected only when a cable
is plugged in).

---

## Onboard hardware (relevant for OAS)

- **U1 — ESP32-C6-MINI-1 module** (top of board, antenna pointing to the short
  edge opposite the USB-C ports). Antenna keep-out: 13.20 mm wide.
- **U2 — SGM2212-3.3 LDO** (3.3 V output, 5 V input). Converts USB-C VBUS to
  3V3 for the chip. **OAS bypasses this** by feeding 3V3 directly into J1.1 from
  the on-PCB TPS62933 buck; with no USB cable plugged in, no 5 V is present and
  the LDO is idle (zero quiescent loss). VCC_5V net stays floating, which is
  fine.
- **U3 — CP2102N-A02-GQFN28** USB-to-UART bridge. Sits between USB-C J4 and the
  ESP32-C6's UART0 (TXD0/RXD0). **Suspends to ~10 µW when no USB cable is
  attached** (CP2102N datasheet). Not a thermal concern in deployed OAS.
- **D5 — RED power LED** (3.3 V Power On LED). Driven through R16 = 1 kΩ from
  VCC_3V3. Approximate forward voltage of a red 0603 LED is ~1.8 V → current is
  (3.3 − 1.8) / 1000 = **1.5 mA**, dissipation ≈ **5 mW** (NOT 30 mW as
  estimated in CLAUDE.md v0.4/v0.5). **The desolder rework will save only
  ~5 mW** — likely below the threshold for any measurable SEN66 temperature
  bias. Re-evaluate whether the rework is worth doing.
- **D6 — WS2812B addressable RGB LED**. DIN connects to **GPIO 8** (also strap
  pin). VDD = VCC_5V (J2 or J4 USB VBUS). **Implication for OAS**: with the
  external USB cable removed, VCC_5V is unpowered → the onboard WS2812 will
  NOT light up. **This contradicts CLAUDE.md's plan to use D6 as the OAS status
  LED via GPIO 8.** Either (a) tie VCC_5V to a 5 V rail on the OAS board (we
  don't have one; OAS has only 3.3 V to the MCU), (b) jumper VCC_5V to VCC_3V3
  on the DevKitM-1 (WS2812B nominally needs ≥3.7 V, so this is marginal; some
  units work at 3.3 V, others do not — not deterministic), or (c) place an
  external WS2812B on the OAS PCB driven by GPIO 8 from J1.9 (deterministic).
  **This is a blocking issue for the v0.4 plan of "onboard NeoPixel as the OAS
  status LED."** See "Discrepancies" below.
- **SW1 — RESET button** (active low, ties CHIP_PU to GND).
- **SW2 — BOOT button** (active low, ties GPIO 9 to GND for download mode).
- **J4 — "USB Type-C to UART" port** (left/upper USB-C on board, depending on
  orientation). VBUS = VBUSA. Routes through CP2102N to chip UART0.
- **J2 — "ESP32-C6 USB Type-C" port** (right/lower USB-C). VBUS = VBUSB.
  Routes USB D+/D− directly to GPIO 13/12 for native USB-Serial-JTAG.
- **Both USB-C ports' centerlines are 11.125 mm from the connector-end short
  edge of the board.**

---

## OAS pinout verification

For each OAS GPIO assignment in `CLAUDE.md` v0.4, confirm against the schematic:

| OAS function | Assigned GPIO | Exposed on DevKitM-1 header? | Strap? | Verdict |
|---|---|---|---|---|
| I²C SDA | GPIO 6 | ✅ J1.10 | No | ✅ OK |
| I²C SCL | GPIO 7 | ✅ J1.11 | No | ✅ OK |
| UART1 TX → LD2410 RX | GPIO 16 | ✅ J3.2 ("TX") | No | ✅ OK |
| UART1 RX ← LD2410 TX | GPIO 17 | ✅ J3.3 ("RX") | No | ✅ OK |
| LD2410 OUT (presence) | GPIO 2 | ✅ J1.3 | No | ✅ OK |
| NT3H2111 FD (NFC) | GPIO 3 | ✅ J1.4 | No | ✅ OK |
| WS2812 DIN (status LED) | GPIO 8 | ✅ J1.9 | **Yes** (strap, but idle-low after boot is OK) | ⚠️ **GPIO 8 is correctly exposed and strap-pin behaviour is fine — BUT the onboard D6 WS2812B is powered from VCC_5V, which is unavailable in deployed OAS. See discrepancy #2 below.** |
| USB D+ (native) | GPIO 13 | ✅ J3.13 (also routed to onboard J2) | No (USB-reserved) | ✅ OK |
| USB D− (native) | GPIO 12 | ✅ J3.14 (also routed to onboard J2) | No (USB-reserved) | ✅ OK |
| GPIO 10 / 11 not used (correctly avoided) | — | **Not exposed** (correct) | — | ✅ OK — assumption verified |

All 7 signal assignments map onto exposed header pins.

### Available spare GPIOs (free for future expansion)

From the header pinout, the following safe non-strap, non-USB GPIOs are
available for OAS expansion: **GPIO 0, 1, 14, 18, 19, 20, 21, 22, 23**
— **9 free pins**. Matches CLAUDE.md.

### GPIOs to avoid

- **Strap pins**: GPIO 4 (MTMS), 5 (MTDI), 9 (BOOT), 15 (boot-mode). All
  exposed on the header but should not be used for general I/O.
- **GPIO 10, 11**: not bonded out (correctly omitted from OAS pinout).
- **GPIO 12, 13**: USB D+/D−. Usable as GPIO only if native USB is disabled in
  firmware — OAS uses native USB for programming, so leave these alone.

---

## Sources

1. <https://dl.espressif.com/dl/schematics/esp32-c6-devkitm-1-dimensions.pdf> — official mechanical dimensions (read directly): 48.26 × 25.40 mm board, 22.86 mm row spacing, 5.37 mm pin-1 offset, 2.54 mm pitch, 1.27 mm row inset from long edge, 11.125 mm USB-C centerline offset.
2. <https://dl.espressif.com/dl/schematics/esp32-c6-devkitm-1-schematics.pdf> rev V1.0 2023-03-03 — full schematic (read directly): J1 / J3 pin nets, ESP32-C6-MINI-1 chip pin nets, U2 = SGM2212-3.3 LDO, U3 = CP2102N USB-UART bridge, D5 = red power LED with R16 = 1 kΩ on VCC_3V3 (verified power LED dissipation ≈ 5 mW, NOT 30 mW), D6 = WS2812B (DIN = GPIO 8, **VDD = VCC_5V**), J2/J4 = two USB Type-C connectors (J4 → CP2102N UART bridge, J2 → native ESP USB).
3. <https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32c6/esp32-c6-devkitm-1/user_guide.html> — official user guide: header block layout, RGB LED on GPIO 8, strap pin list (GPIO 4, 5, 8, 9, 15), two USB-C port roles.
4. <https://www.espboards.dev/esp32/esp32-c6-devkitm-1/> — third-party pinout reference confirming GPIO 10/11 not bonded out, 22 digital I/O total, J1 + J3 pin-by-pin mapping.
5. CLAUDE.md (project file) — EAN 5904422385651 attribution to Botland (not re-fetched live).
