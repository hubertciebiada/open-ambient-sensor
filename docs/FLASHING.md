# Flashing

**Status:** preliminary draft.

The ESP32-C6 SuperMini has native USB-C. First-time flashing is done over USB.

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

The ESP32-C6 SuperMini has strap pins that affect boot behaviour. The pinout in `ARCHITECTURE.md` is **tentative** and must be validated against the strap-pin constraints before the PCB is finalised. If a future hardware revision changes a strap pin, this document must be updated.
