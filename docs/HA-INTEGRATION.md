# Home Assistant integration

**Status:** preliminary draft.

OAS integrates with Home Assistant via the **native ESPHome API** — no MQTT broker required. Once flashed, the device announces itself via mDNS and appears as a discovered integration.

## Discovery

1. Flash the device with `firmware/esphome/oas.yaml` (see [`FLASHING.md`](./FLASHING.md))
2. The device should appear in **Settings → Devices & Services → Discovered**
3. Accept the discovery, enter the API encryption key from your `secrets.yaml`

## Exposed entities

Once integrated, the device exposes (subject to final firmware):

- **Sensors:** CO₂, PM1/2.5/4/10, VOC index, NOx index, temperature, humidity
- **Binary sensors:** presence, moving target, still target
- **Light:** status RGB LED (state + colour + breathing effect)
- **Bluetooth proxy:** automatically extends BLE range for the rest of HA

## Suggested dashboards

To be documented once a working prototype is producing data. Typical layouts:

- **Per-room card:** CO₂ + temperature + humidity + presence
- **Air quality history:** PM2.5 and VOC trends over 24 h
- **Multi-unit overview:** aggregated CO₂ / occupancy heatmap across the deployment

## Bluetooth proxy

The `bluetooth_proxy:` ESPHome component lets each OAS unit forward BLE traffic to Home Assistant. In a multi-unit deployment (typical: 5–20 units), this gives near-whole-building BLE coverage without dedicated proxies.

No additional Home Assistant configuration is required — the Bluetooth integration discovers ESPHome proxies automatically.

## NFC tag

The dynamic NFC tag exposes a URL to the device's HA dashboard. A phone tap reads live data (the firmware writes the latest measurements to the tag's user memory) and opens the dashboard in the browser. The exact URL and content format are TBD — see `CLAUDE.md` open work.
