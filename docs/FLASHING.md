# Flashing

**Status:** preliminary draft.

The ESP32-C6-DevKitM-1-N4 (EAN 5904422385651) has **two USB-C ports**: one routed through an onboard USB-to-UART bridge IC (classic-style flashing), the other direct to the ESP32-C6's native USB-Serial-JTAG. Either one works for first-time flashing.

## Prerequisites

- ESPHome installed:

  ```bash
  pip install esphome
  ```

  (or use the ESPHome Home Assistant add-on)

- USB-C cable
- The device's `secrets.yaml` populated next to `firmware/esphome/oas.yaml`:

  ```bash
  cp firmware/secrets.yaml.example firmware/esphome/secrets.yaml
  # edit the new secrets.yaml — fill in WiFi credentials, API key, OTA password
  ```

## First flash (USB)

1. Connect the device via USB-C
2. From the repository root:

   ```bash
   esphome run firmware/esphome/oas.yaml
   ```

3. Select the serial port when prompted
4. After the first flash completes, subsequent updates can be done over the air (OTA) via the ESPHome dashboard or `esphome run --device <hostname>`

## Boot / strap pins

The ESP32-C6 has strap pins that affect boot behaviour (GPIO 4 MTMS, 5 MTDI, 9 BOOT, 15 boot-mode select). The OAS pinout in `ARCHITECTURE.md` was validated against these constraints in v0.4 and uses only safe non-strap pins for signal I/O. **GPIO 10 and GPIO 11 are physically not bonded out** on the ESP32-C6FH4 chip variant (internal SiP flash uses them) — do not assign signals to those pins on any ESP32-C6-MINI-1 / DevKitM-1 / XIAO / SuperMini module. If a future hardware revision changes the chip or module, validate the pinout against the new datasheet before flashing.
