# Firmware — ESPHome

OAS runs on **ESPHome** (YAML configuration) and integrates with Home Assistant via the native ESPHome API.

Hardware target: **ESP32-C6-DevKitM-1-N4** (ESP32-C6-MINI-1 SoM, 4 MB flash) on the OAS v0.40 PCB. Framework: **esp-idf** (required for BLE proxy memory headroom — `arduino` runs out of IRAM with the C6 + BLE + WiFi + sensors all enabled).

## Layout

```
firmware/
├── esphome/
│   ├── oas.yaml             # top-level config, per-device substitutions
│   ├── packages/
│   │   ├── core.yaml        # WiFi, AP fallback, API, OTA, web_server, time, logger
│   │   ├── leds.yaml        # SK6812-SIDE AQI ring (7 LEDs on GPIO 8; 8-slot ring with D13 vacated for J1)
│   │   ├── air-quality.yaml # Sensirion SEN66 (I²C 0x6B)
│   │   ├── presence.yaml    # HiLink LD2410 (UART @ 256000 baud)
│   │   ├── nfc.yaml         # MIKROE-2462 NT3H1101 dynamic tag (I²C 0x55)
│   │   └── bt-proxy.yaml    # Bluetooth proxy for Home Assistant
│   └── examples/            # anonymized per-device override examples
├── secrets.yaml.example     # template; copy to secrets.yaml (gitignored)
└── README.md                # this file
```

## Quick start

### 1. Install ESPHome

```bash
pip install esphome
```

Or use the Home Assistant ESPHome add-on, or the [ESPHome web flasher](https://web.esphome.io/) for first flash without a CLI.

### 2. Prepare secrets

```bash
cp firmware/secrets.yaml.example firmware/esphome/secrets.yaml
```

Edit `firmware/esphome/secrets.yaml` and fill in:

- `wifi_ssid` / `wifi_password` — your LAN credentials
- `ap_password` — fallback hotspot password (min 8 chars)
- `api_encryption_key` — generate with `openssl rand -base64 32` (paste the result as the `api_encryption_key` value in `secrets.yaml`)
- `ota_password` — any strong password

`secrets.yaml` is gitignored and must never be committed.

### 3. Set per-device identity

Each physical OAS unit needs a unique `device_id` and `friendly_name`. You have three options:

**Option A — Edit substitutions in `oas.yaml` directly** (fine for a single prototype):

```yaml
substitutions:
  device_id: livingroom
  friendly_name: "Living Room"
  dashboard_url: "http://homeassistant.local:8123/lovelace/living-room"
```

**Option B — Copy `oas.yaml` to a per-device file** (better for fleets):

```bash
cp firmware/esphome/oas.yaml firmware/esphome/devices/livingroom.yaml
# edit substitutions at the top
esphome run firmware/esphome/devices/livingroom.yaml
```

**Option C — Use the ESPHome dashboard** (Home Assistant add-on): each device gets its own per-device YAML in the dashboard UI; substitutions are editable from the web interface.

### 4. Validate the config (recommended before first flash)

```bash
esphome config firmware/esphome/oas.yaml
```

This catches typos and missing secrets without touching the device.

### 5. First flash (over USB-C)

The ESP32-C6-DevKitM-1-N4 has **two USB-C ports**:

- The port labelled **USB** goes through an onboard USB-UART bridge IC — works with classic `esphome run` flashing on every host OS.
- The port labelled **UART** is wired directly to the ESP32-C6's native USB-Serial-JTAG (GPIO 12/13) — also works for flashing, slightly faster, no driver install needed on modern Linux/macOS/Windows 11.

Either port works. Plug in and run:

```bash
esphome run firmware/esphome/oas.yaml
```

ESPHome auto-detects the serial port. Pick it from the menu if prompted.

Alternative for first flash without a local Python install: open <https://web.esphome.io/> in Chrome/Edge, click "Connect", select the OAS device, and upload the compiled `.bin` ESPHome produced. The web flasher uses WebSerial — no driver install needed.

### 6. After first flash

Once the device is on your WiFi, the on-device web dashboard is reachable at:

- `http://oas-<device_id>.local/` (mDNS — works on most modern OSes)
- `http://<device-ip>/` (find the IP in your router admin or in Home Assistant)

The dashboard is **web_server v3** (modern post-2024 ESPHome UI) and supports:

- Live sensor readings (CO2, PM, VOC, NOx, temperature, humidity, presence)
- LED ring controls (brightness slider, effect picker, color picker)
- Number entity sliders to adjust sensor calibration offsets in real time
- Live log viewer
- Read-only Prometheus metrics endpoint at `/metrics` for scraping

All of this works without Home Assistant — useful for first-bringup verification.

### 7. Home Assistant integration

Home Assistant should auto-discover the device via mDNS within ~30 seconds of it joining the LAN. If it doesn't, add it manually:

- **Settings → Devices & Services → Add Integration → ESPHome**
- Host: `oas-<device_id>.local` (or the IP)
- Encryption key: paste the `api_encryption_key` from your `secrets.yaml`

After the initial pairing, all further updates flow over the air via the ESPHome dashboard inside Home Assistant.

### 8. Subsequent updates (OTA)

Once a device is on the network, you don't need USB any more. From any machine on the same LAN:

```bash
esphome run firmware/esphome/oas.yaml --device oas-<device_id>.local
```

Or just press "Update" in the Home Assistant ESPHome dashboard.

## First-time WiFi provisioning without secrets.yaml

If you don't want to write WiFi credentials into `secrets.yaml` before first flash (e.g. for a unit you're shipping to someone else), the `core.yaml` package enables **Improv Serial**:

1. Flash the device once with placeholder WiFi credentials (any string).
2. Plug it into a host running Chrome/Edge.
3. Visit <https://www.improv-wifi.com/>, click "Connect", select the device.
4. Enter the target SSID + password — the device commits them to flash and reboots onto WiFi.

Alternatively, the **AP fallback** (`OAS-<device_id>-Setup` SSID, gated by `ap_password`) and **captive portal** combination lets a phone connect to the device's own hotspot and re-enter credentials through a web form.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Device doesn't show up on mDNS | Most consumer routers block mDNS across VLANs. Find the IP via your router admin and use `http://<ip>/` directly. |
| `secrets.yaml not found` | The file lives next to `oas.yaml`, i.e. `firmware/esphome/secrets.yaml`, not at the repo root. |
| OTA fails with "wrong password" | Re-flash via USB-C with the new password baked in. Lost OTA passwords cannot be recovered. |
| LED ring doesn't light | Check that `+5V` is reaching the LM2596S output — `core.yaml` itself never touches the LED ring; that's `leds.yaml`'s job. |
| SEN66 measurements stuck on "unavailable" | Likely I²C bus issue; scan with `i2c.scan: true` (already enabled). SEN66 lives at 0x6B. |
| LD2410 presence never triggers | Verify UART pins (TX=GPIO16, RX=GPIO17) and 256000 baud rate. Use `logger: VERBOSE` to see the raw protocol. |

## Status

**Firmware skeleton complete (6 packages):** `core.yaml`, `leds.yaml`, `air-quality.yaml`, `presence.yaml`, `nfc.yaml`, `bt-proxy.yaml`. Validates clean against `esphome config`. Awaiting hardware delivery for first-flash and bench bring-up — see CLAUDE.md for the firmware TODO list (LD2410 UART shakedown, NFC NDEF updater verification, OTA setup, HA discovery validation).

---

## Home Assistant integration

### Exposed entities

#### Sensors (`sensor.*`)

| Entity (suffix) | Unit | Source |
|---|---|---|
| `co2` | ppm | SEN66 (NDIR, 400-40 000 ppm) |
| `pm1` / `pm2_5` / `pm4` / `pm10` | µg/m³ | SEN66 (laser scatter) |
| `voc_index` | (1-500) | SEN66 MOX (Sensirion VOC index, 100 = baseline) |
| `nox_index` | (1-500) | SEN66 MOX (1 = baseline) |
| `temperature` | °C | SEN66 SHT4x (STAR-Engine compensated) |
| `humidity` | %RH | SEN66 SHT4x |
| `presence_distance` | cm | LD2410 (0-600 cm, ~100 ms cadence) |
| `moving_target_energy` / `still_target_energy` | (0-100) | LD2410 radar return amplitude |
| `wifi_rssi` | dBm | ESPHome built-in |
| `uptime` | s | ESPHome built-in |

#### Binary sensors (`binary_sensor.*`)

| Entity (suffix) | Source |
|---|---|
| `presence` | LD2410 OUT pin (GPIO 2) — hardware-level flag, fastest path |
| `moving_target` / `still_target` | LD2410 protocol |
| `api_connected` | ESPHome (true when API paired with HA) |

#### Light, numbers, selects, text, buttons, switches

- `light.led_ring` — RGB addressable (7 LEDs); brightness / colour / effect controllable from HA
- `number.temperature_offset` (-10..+10 °C), `number.humidity_offset` (-20..+20 %RH), `number.co2_offset` (-500..+500 ppm) — persistent calibration trims
- `number.ld2410_max_distance` (1-8 gates × 0.75 m), `number.ld2410_presence_timeout` (0-65535 s), `number.ld2410_gate_*_sensitivity` (0-100 per gate)
- `number.led_brightness_day` (0-255), `number.led_brightness_night` (0-15)
- `select.led_mode` — Auto-AQI / Manual / Off / Test-Rainbow
- `select.led_effect` — 8+ effects (active when `led_mode = Manual`)
- `text.dashboard_url` — URL the NFC tag redirects to when tapped (editable at runtime)
- `button.restart` / `button.sen66_force_clean` / `button.ld2410_factory_reset`
- `switch.bluetooth_proxy` (default on) / `switch.prevent_sleep`

### Dashboard idea (starter Lovelace card)

```yaml
type: vertical-stack
title: Living Room
cards:
  - type: glance
    entities:
      - { entity: sensor.oas_livingroom_co2, name: CO₂ }
      - { entity: sensor.oas_livingroom_pm2_5, name: PM2.5 }
      - { entity: sensor.oas_livingroom_temperature, name: Temp }
      - { entity: sensor.oas_livingroom_humidity, name: RH }
      - { entity: binary_sensor.oas_livingroom_presence, name: Presence }
  - type: gauge
    entity: sensor.oas_livingroom_co2
    min: 400
    max: 2500
    severity: { green: 400, yellow: 900, red: 1400 }
    name: CO₂ (ppm)
  - type: history-graph
    title: Air quality (24 h)
    entities:
      - sensor.oas_livingroom_co2
      - sensor.oas_livingroom_voc_index
      - sensor.oas_livingroom_pm2_5
    hours_to_show: 24
```

### Sample automation: ventilate on high CO₂

```yaml
trigger:
  - platform: numeric_state
    entity_id: sensor.oas_livingroom_co2
    above: 1200
    for: "00:05:00"
action:
  - service: switch.turn_on
    target: { entity_id: switch.bedroom_ventilator }
```

The 5-minute `for:` debounces brief CO₂ spikes (someone exhaling on the device).

### LED ring AQI alert

The ring runs in **Auto-AQI** mode by default — colour reflects current AQI without any HA wiring. For stronger alerts, drop into Manual mode and apply an effect:

```yaml
trigger:
  - platform: numeric_state
    entity_id: sensor.oas_livingroom_co2
    above: 1500
action:
  - service: select.select_option
    target: { entity_id: select.oas_livingroom_led_mode }
    data: { option: Manual }
  - service: select.select_option
    target: { entity_id: select.oas_livingroom_led_effect }
    data: { option: Pulse }
  - service: light.turn_on
    target: { entity_id: light.oas_livingroom_led_ring }
    data: { rgb_color: [255, 0, 0], brightness: 255 }
```

Pair with a recovery automation that switches back to Auto-AQI when CO₂ drops below 1000 ppm.

### NFC tap → dashboard

Each OAS unit ships with a dynamic NFC tag (NXP NT3H1101 + onboard antenna on the MIKROE-2462 daughterboard). Tapping a phone opens the URL from the on-board NDEF record in the phone's default browser. The firmware re-writes the NDEF record every 60 s to keep the URL fresh. The URL is set by the `text.oas_<device>_dashboard_url` entity, initialised from the `dashboard_url` substitution in `oas.yaml` but editable at runtime via the on-device web dashboard or Home Assistant.

### Bluetooth proxy

`bluetooth_proxy:` is enabled in firmware. In a multi-unit deployment, this gives near-whole-home BLE coverage for HA's BLE integrations (xiaomi_ble plant sensors, govee BLE thermometers, presence beacons) without dedicated proxies. Home Assistant auto-discovers the proxy. Runtime control via `switch.oas_<device>_bluetooth_proxy`.
