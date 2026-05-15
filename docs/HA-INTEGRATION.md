# Home Assistant integration

How OAS integrates with Home Assistant — auto-discovery, entity inventory, dashboard layout suggestions, and automation recipes.

Pre-requisite: a device that has been flashed and is on the LAN. See [`FLASHING.md`](./FLASHING.md) for the bring-up workflow.

---

## Auto-discovery

OAS uses the **ESPHome native API** (encrypted, password-protected, lossless). No MQTT broker is required.

1. Flash a device using `firmware/esphome/oas.yaml`.
2. Within ~30 seconds of the device joining your WiFi, Home Assistant should show it under **Settings → Devices & Services → Discovered**.
3. Click **Configure**, paste the `api_encryption_key` from your `secrets.yaml`, and confirm.
4. Every entity exposed by the device appears under one Device card.

If auto-discovery fails (typically a VLAN / mDNS issue on your network), add the integration manually:

- **Settings → Devices & Services → Add Integration → ESPHome**
- Host: `oas-<device_id>.local` or the device's IP
- Encryption key: the value of `api_encryption_key` from `secrets.yaml`

---

## Exposed entities

Each OAS unit exposes the entities below. Exact list is firmware-dependent — when in doubt, the device card in Home Assistant is authoritative.

### Sensors (`sensor.*`)

| Entity (suffix) | Unit | Source | Notes |
|---|---|---|---|
| `co2` | ppm | SEN66 (NDIR) | 400-40 000 ppm range |
| `pm1` | µg/m³ | SEN66 (laser scatter) | |
| `pm2_5` | µg/m³ | SEN66 | |
| `pm4` | µg/m³ | SEN66 | |
| `pm10` | µg/m³ | SEN66 | |
| `voc_index` | (1-500) | SEN66 (MOX, Sensirion VOC index) | 100 = typical baseline; higher = more VOCs |
| `nox_index` | (1-500) | SEN66 (MOX) | 1 = baseline; rises with combustion / outdoor NOx ingress |
| `temperature` | °C | SEN66 (SHT4x integrated) | STAR-Engine compensated |
| `humidity` | %RH | SEN66 (SHT4x integrated) | |
| `presence_distance` | cm | LD2410 | 0-600 cm, reported every ~100 ms while presence is detected |
| `moving_target_energy` | (0-100) | LD2410 | radar return amplitude for moving targets |
| `still_target_energy` | (0-100) | LD2410 | radar return amplitude for still targets (e.g. someone seated) |
| `wifi_rssi` | dBm | ESPHome built-in | LAN signal strength |
| `uptime` | s | ESPHome built-in | seconds since last boot |

### Binary sensors (`binary_sensor.*`)

| Entity (suffix) | Source | Notes |
|---|---|---|
| `presence` | LD2410 OUT pin (GPIO 2) | hardware-level presence flag, fastest path |
| `moving_target` | LD2410 protocol | someone is moving in the field of view |
| `still_target` | LD2410 protocol | someone is in the field but stationary (e.g. seated) |
| `api_connected` | ESPHome | True when the API is paired with Home Assistant |

### Light (`light.*`)

| Entity (suffix) | Type | Notes |
|---|---|---|
| `led_ring` | RGB addressable (11 LEDs) | Brightness, colour, and effect controllable from Home Assistant. Use `select.led_mode` to switch between Auto-AQI, Manual, Off, and Test-Rainbow. |

### Numbers (`number.*`)

User-tunable calibration and behaviour offsets, persistent across reboots:

| Entity (suffix) | Range | Default | Notes |
|---|---|---|---|
| `temperature_offset` | -10.0 to +10.0 °C | 0.0 | Subtract self-heating bias |
| `humidity_offset` | -20 to +20 %RH | 0 | Trim against a reference hygrometer |
| `co2_offset` | -500 to +500 ppm | 0 | Trim against a reference CO₂ meter |
| `ld2410_max_distance` | 1-8 (×0.75 m gates) | 6 | Trim radar reach for small rooms |
| `ld2410_presence_timeout` | 0-65535 s | 5 | How long after the last detection the device still reports presence |
| `ld2410_gate_*_sensitivity` | 0-100 per gate | varies | Per-gate radar sensitivity (8 moving + 8 still gates) — for fine-tuning false positives |
| `led_brightness_day` | 0-255 | 200 | LED brightness during daytime hours |
| `led_brightness_night` | 0-15 | 5 | LED brightness during night hours |

### Selects (`select.*`)

| Entity (suffix) | Options | Notes |
|---|---|---|
| `led_mode` | Auto-AQI, Manual, Off, Test-Rainbow | LED ring high-level mode |
| `led_effect` | (8+ effects) | Active when `led_mode = Manual`. Includes: solid, breathing, rainbow, pulse, comet, fire, etc. (final list per `leds.yaml`) |

### Text (`text.*`)

| Entity (suffix) | Notes |
|---|---|
| `dashboard_url` | URL the NFC tag redirects to when tapped. Editable from the dashboard — change it at runtime without re-flashing. |

### Buttons (`button.*`)

| Entity (suffix) | Notes |
|---|---|
| `restart` | Soft reboot |
| `sen66_force_clean` | Triggers SEN66 fan auto-clean (~10 s cycle, runs immediately) |
| `ld2410_factory_reset` | Resets LD2410 internal settings to factory defaults |

### Switches (`switch.*`)

| Entity (suffix) | Notes |
|---|---|
| `bluetooth_proxy` | Enable / disable the BLE proxy at runtime (default on) |
| `prevent_sleep` | Force WiFi power-save off (useful for debugging) |

### Diagnostic / debug

ESPHome auto-exposes `uptime`, `wifi_signal`, `last_reset_reason`, internal memory stats etc. — visible in HA but typically hidden from regular dashboards.

---

## Dashboard ideas

A starter Lovelace card for a single OAS unit. Drop into the **Dashboards** raw config:

```yaml
type: vertical-stack
title: Living Room
cards:
  - type: glance
    entities:
      - entity: sensor.oas_livingroom_co2
        name: CO₂
      - entity: sensor.oas_livingroom_pm2_5
        name: PM2.5
      - entity: sensor.oas_livingroom_temperature
        name: Temp
      - entity: sensor.oas_livingroom_humidity
        name: RH
      - entity: binary_sensor.oas_livingroom_presence
        name: Presence
  - type: gauge
    entity: sensor.oas_livingroom_co2
    min: 400
    max: 2500
    severity:
      green: 400
      yellow: 900
      red: 1400
    name: CO₂ (ppm)
  - type: history-graph
    title: Air quality (24 h)
    entities:
      - sensor.oas_livingroom_co2
      - sensor.oas_livingroom_voc_index
      - sensor.oas_livingroom_pm2_5
    hours_to_show: 24
  - type: entities
    title: LED ring
    entities:
      - light.oas_livingroom_led_ring
      - select.oas_livingroom_led_mode
      - select.oas_livingroom_led_effect
      - number.oas_livingroom_led_brightness_day
      - number.oas_livingroom_led_brightness_night
```

Multi-room overview: combine a `picture-elements` floorplan card with `sensor.oas_<room>_co2` badges per room.

---

## Sample automations

### 1. Ventilate when CO₂ climbs

```yaml
alias: "Ventilation on high CO₂"
trigger:
  - platform: numeric_state
    entity_id: sensor.oas_livingroom_co2
    above: 1200
    for: "00:05:00"
action:
  - service: switch.turn_on
    target:
      entity_id: switch.bedroom_ventilator
mode: single
```

Use `for: "00:05:00"` to debounce — a brief CO₂ spike (someone exhales on the device) shouldn't fire the automation.

### 2. Desk lamp follows presence in a dark room

```yaml
alias: "Desk lamp on presence"
trigger:
  - platform: state
    entity_id: binary_sensor.oas_office_presence
    to: "on"
condition:
  - condition: numeric_state
    entity_id: sensor.outdoor_illuminance
    below: 50
action:
  - service: light.turn_on
    target:
      entity_id: light.desk_lamp
    data:
      brightness_pct: 70
      kelvin: 3500
mode: single
```

OAS itself does not measure light (deliberately — see CLAUDE.md "Out of scope"). Pair with any HA-known illuminance source.

### 3. LED ring alerts on poor air quality

The LED ring runs in **Auto-AQI** mode by default — the colour reflects current AQI without any HA wiring. If you want a stronger alert (e.g. flash on CO₂ > 1500 ppm), drop the ring into Manual mode and apply an effect:

```yaml
alias: "Flash LED ring on CO₂ spike"
trigger:
  - platform: numeric_state
    entity_id: sensor.oas_livingroom_co2
    above: 1500
action:
  - service: select.select_option
    target:
      entity_id: select.oas_livingroom_led_mode
    data:
      option: Manual
  - service: select.select_option
    target:
      entity_id: select.oas_livingroom_led_effect
    data:
      option: Pulse
  - service: light.turn_on
    target:
      entity_id: light.oas_livingroom_led_ring
    data:
      rgb_color: [255, 0, 0]
      brightness: 255
```

Pair with a recovery automation that switches back to Auto-AQI when CO₂ drops below 1000 ppm.

### 4. Multi-unit average for whole-home air quality

```yaml
sensor:
  - platform: average
    name: "Average CO₂"
    entities:
      - sensor.oas_livingroom_co2
      - sensor.oas_bedroom_co2
      - sensor.oas_office_co2
      - sensor.oas_kitchen_co2
```

Use the average for a single dashboard gauge that summarises the whole deployment.

---

## NFC tap → dashboard

Each OAS unit ships with a dynamic NFC tag (NXP NT3H1101 + onboard antenna on the MIKROE-2462 daughterboard). Tapping a phone on the device:

1. Reads the NDEF record currently stored on the tag.
2. Opens the URL from the record in the phone's default browser.

The firmware re-writes the NDEF record every 60 seconds to keep the URL fresh. The URL is set by the `text.oas_<device>_dashboard_url` entity, which is initialised from the `dashboard_url` substitution in `oas.yaml` but can be edited at runtime via:

- The on-device web dashboard (`http://oas-<device_id>.local/`)
- Home Assistant (set the text entity to a new value)

Typical values:

- `https://homeassistant.local/lovelace/livingroom` — your HA Lovelace page for that room
- A Grafana panel URL with that device's metrics filtered in
- A wiki page describing what the room's readings mean

Some firmwares additionally embed the latest sensor readings as URL query parameters (e.g. `?co2=850&pm25=12&t=21.3`) so a serverless landing page can show live values without making an HA API call. See `nfc.yaml` for the exact format.

---

## Bluetooth proxy

OAS includes `bluetooth_proxy:` in firmware. In a multi-unit deployment (typical: 5-20 units across a home), this gives near-whole-home BLE coverage for HA's BLE integrations (e.g. xiaomi_ble plant sensors, govee BLE thermometers, presence beacons) without dedicated proxies.

Home Assistant auto-discovers the proxy. No extra configuration is required. The proxy can be enabled / disabled at runtime via `switch.oas_<device>_bluetooth_proxy`.
