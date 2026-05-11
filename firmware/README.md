# Firmware — ESPHome

OAS runs on **ESPHome** (YAML configuration) and integrates with Home Assistant via the native ESPHome API.

## Layout

```
firmware/
├── esphome/
│   ├── oas.yaml          # base configuration
│   ├── packages/         # shared YAML fragments (sensors, LED effects, NFC, BLE proxy)
│   └── examples/         # anonymised example device overrides
├── secrets.yaml.example  # template; copy to secrets.yaml (gitignored) and fill in
└── README.md             # this file
```

## Quick start (once hardware is built)

1. Install ESPHome (`pip install esphome` or use the Home Assistant add-on).
2. Copy `secrets.yaml.example` to `secrets.yaml` next to `oas.yaml` and fill in your WiFi credentials and HA API key.
3. Connect the device via USB-C and flash:

   ```bash
   esphome run esphome/oas.yaml
   ```

4. The device should announce itself to Home Assistant via mDNS — accept the discovery prompt.

## ESPHome components used

- `sensor.sen66` — air-quality combo (CO₂, PM1/2.5/4/10, VOC, NOx, T, RH). Native availability **TBD** — fallback to a custom external component if unavailable.
- `binary_sensor.ld2410` and `sensor.ld2410` — mmWave presence + stillness
- `sensor.veml7700` — ambient light
- `light.neopixelbus` — WS2812B with breathing effect
- `bluetooth_proxy` — extends BLE range for the rest of the home

## Status

**Preliminary draft.** No working firmware has been validated yet. See `CLAUDE.md` for the open firmware TODO list.
