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
│   │   ├── leds.yaml        # SK6812-SIDE AQI ring (11 LEDs on GPIO 8)
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
- `api_encryption_key` — generate with `esphome --encryption-key` or `openssl rand -base64 32`
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

**Preliminary.** The base infrastructure (`oas.yaml` + `core.yaml`) is complete and validates clean against `esphome config`. Sensor packages (`air-quality.yaml`, `presence.yaml`, `nfc.yaml`, `bt-proxy.yaml`, `leds.yaml`) are being landed in parallel — see CLAUDE.md for the firmware TODO list. First end-to-end validation will follow once the v0.40 boards arrive from JLCPCB.
