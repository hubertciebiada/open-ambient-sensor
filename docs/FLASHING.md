# Flashing

How to take a freshly-assembled OAS PCB from a bare module to a running device on your WiFi and Home Assistant.

For the developer-facing layout of the ESPHome project (which package does what, how to validate a config), see [`../firmware/esphome/README.md`](../firmware/esphome/README.md). For the pinout and hardware constraints referenced below, see [`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

## Prerequisites

- **ESPHome CLI installed.** Either:
  - `pip install esphome` (Python 3.9+), or
  - The Home Assistant **ESPHome Builder** add-on (manages the same configs from inside HA), or
  - The browser-based [ESPHome web flasher](https://web.esphome.io/) for a one-off first flash without a local install.
- **A USB-C cable** with data lines (charge-only cables do nothing).
- **A computer** running Windows, macOS or Linux to flash from. The DevKitM-1's onboard USB-UART bridge is recognised by every modern OS without extra drivers; the native USB-Serial-JTAG port is also driver-free on Windows 11 / macOS 13+ / Linux 5.x+.
- **A populated `secrets.yaml`** (see step 1 of the first-flash workflow below).

---

## First flash workflow (over USB-C)

This is the workflow for a brand-new device that has never been flashed before. The ESP32-C6 ships from Espressif with no ESPHome firmware, so the first flash always happens over USB. After that, every update can flow over the air.

### 1. Create your `secrets.yaml`

```bash
cp firmware/secrets.yaml.example firmware/esphome/secrets.yaml
```

Open the new file and fill in:

| Field | What goes in it |
|---|---|
| `wifi_ssid` | Your LAN's WiFi SSID. 2.4 GHz only (ESP32-C6 supports 5 GHz but most home routers fragment 2.4/5 onto the same SSID — ESPHome lands on whichever radio answers first; 2.4 GHz reaches farther through walls). |
| `wifi_password` | Your WiFi PSK. |
| `ap_password` | Password for the OAS's own fallback hotspot. Minimum 8 characters (WPA2 requirement). The device exposes this hotspot if your main WiFi is unreachable, letting you re-enter credentials via a captive portal without re-flashing. |
| `api_encryption_key` | 32 random bytes, base64-encoded. Generate one with `esphome --encryption-key` (recommended) or `openssl rand -base64 32`. Paste the result here. |
| `ota_password` | Any strong password. Used to authenticate OTA updates. If you lose it, you must re-flash over USB. |

`secrets.yaml` is gitignored — never commit it. The same file can be shared by every OAS device in a deployment; per-device identity lives in substitutions (next step).

### 2. Set per-device identity in `oas.yaml`

Open `firmware/esphome/oas.yaml` and edit the `substitutions:` block near the top:

```yaml
substitutions:
  device_id: livingroom            # short slug, lowercase + dashes
  friendly_name: "Living Room"     # display name in Home Assistant
  dashboard_url: "https://homeassistant.local/lovelace/livingroom"
```

- `device_id` becomes the device hostname (`oas-livingroom.local`) and the WiFi AP fallback SSID (`OAS-livingroom-Setup`). Keep it short and unique across your deployment.
- `friendly_name` is the human-readable name shown in Home Assistant.
- `dashboard_url` is the URL the NFC tag redirects to when tapped with a phone (typically your HA Lovelace dashboard for that room — see [`HA-INTEGRATION.md`](./HA-INTEGRATION.md)).

For a multi-unit fleet, copying `oas.yaml` to per-device files (e.g. `firmware/esphome/devices/livingroom.yaml`) is cleaner — see the firmware README for details.

### 3. Connect the device

The ESP32-C6-DevKitM-1-N4 has **two USB-C ports**. Either one will work for first flash:

- The port labelled **USB** is wired through an onboard USB-to-UART bridge IC. This is the most compatible option; works the same way on every OS that has ever shipped a CP210x or CH340-class driver (so: every OS made since 2010). Pick this one if in doubt.
- The port labelled **UART** is wired directly to the ESP32-C6's native USB-Serial-JTAG (GPIO 12/13). Marginally faster and driver-free on modern Windows 11 / macOS 13+ / Linux 5.x+ kernels.

The OAS board is designed so both ports remain accessible while the device is on the bench before the case is closed — you can pull the DevKitM-1 module out of its J5/J6 sockets if you ever need to flash it standalone.

### 4. Flash

From the repo root:

```bash
esphome run firmware/esphome/oas.yaml
```

ESPHome auto-detects the serial port. If it asks, pick the COM port (Windows) or `/dev/tty.usb*` device (macOS/Linux) for the USB cable you just plugged in.

The first compile takes ~3-5 minutes (it pulls esp-idf and builds every component). Subsequent builds are incremental and complete in seconds.

If you don't want to install Python on your host, you can also use the [ESPHome web flasher](https://web.esphome.io/): in Chrome or Edge, click **Connect**, select the serial port, then upload the pre-built `.bin` file ESPHome produced. The web flasher uses WebSerial — no driver install needed.

### 5. First boot

After flashing, the device reboots and tries to join the WiFi network from `secrets.yaml`.

- **If WiFi credentials are correct:** the device joins your LAN within ~10 seconds. The power LED on the DevKitM-1 stays steady; the SK6812-SIDE LED ring runs the "AQI auto" effect (initially shows a startup ramp, then settles to a colour reflecting current air quality).
- **If WiFi credentials are wrong or the network is unreachable:** the device falls back to its own AP. Look for `OAS-<device_id>-Setup` in your phone's WiFi list, connect using the `ap_password` from `secrets.yaml`, and a captive portal opens automatically for you to re-enter credentials.
- **Alternative — Improv WiFi over USB:** the firmware also enables [Improv Serial](https://www.improv-wifi.com/). Keep the device plugged in via USB, open <https://www.improv-wifi.com/> in Chrome/Edge, click **Connect**, and provision the WiFi credentials interactively. Useful for shipping pre-flashed devices without baking in real credentials.

### 6. Reach the device

Once on WiFi, the device announces itself via mDNS. Open in your browser:

- `http://oas-<device_id>.local/` (mDNS hostname — works on most modern OSes), or
- `http://<device-ip>/` (find the IP in your router admin, or in Home Assistant after step 7)

The on-device dashboard (web_server v3) shows live sensor readings, lets you adjust the LED ring effect/brightness/mode, exposes calibration offset sliders, and includes a live log viewer. Useful for verification before Home Assistant is configured.

### 7. Add to Home Assistant

Home Assistant should auto-discover the device within ~30 seconds. If it doesn't, go to **Settings → Devices & Services → Add Integration → ESPHome**:

- **Host:** `oas-<device_id>.local` (or the IP)
- **Encryption key:** paste the `api_encryption_key` from `secrets.yaml`

After pairing, every entity exposed by OAS shows up under one Device card. See [`HA-INTEGRATION.md`](./HA-INTEGRATION.md) for the full entity list and dashboard / automation suggestions.

---

## OTA flash workflow (subsequent updates)

Once a device is on the network, you never need USB again. From any machine on the same LAN that has ESPHome installed:

```bash
esphome run firmware/esphome/oas.yaml
```

ESPHome auto-discovers the device via mDNS, compiles the new firmware, and pushes it over the encrypted OTA channel. The device reboots into the new firmware automatically; sensor history in Home Assistant is preserved.

If mDNS doesn't work across your VLANs, force the target:

```bash
esphome run firmware/esphome/oas.yaml --device oas-livingroom.local
# or by IP:
esphome run firmware/esphome/oas.yaml --device 192.0.2.42
```

You can also push OTA updates from the **ESPHome Builder** add-on inside Home Assistant — pick the device, click **Update**.

---

## Recovery flash workflow

Things go wrong; here's how to recover.

### OTA failed (wrong password, partial update, etc.)

Open the case, plug into either USB-C port on the DevKitM-1 module, and re-flash over USB exactly like the first-flash workflow. ESPHome will overwrite whatever is on the device.

Lost OTA passwords are not recoverable — the device will not accept OTAs with a different password than the one currently flashed. USB re-flash is the only path back.

### Both DevKitM-1 USB-C ports damaged

Rare, but possible (e.g. mechanical damage during enclosure assembly). The OAS board exposes a fallback recovery header **J10** (a 6-pin 2.54 mm DNP through-hole header, populated only if you need it). Solder pogopins or a small header strip to J10 and use a USB-Serial-JTAG breakout connected to the pinout:

| J10 pin | Net |
|---|---|
| 1 | GND |
| 2 | +3V3 |
| 3 | USB_DM (GPIO 12) |
| 4 | USB_DP (GPIO 13) |
| 5 | EN (chip reset) |
| 6 | BOOT (GPIO 9 strap) |

To enter download mode: hold BOOT low, pulse EN low briefly, release EN, release BOOT. Then flash with `esptool` or `esphome run` against the J10 USB-Serial-JTAG channel exactly like a normal first flash.

This is a belt-and-suspenders fallback. In practice, OTA + the two onboard USB-C ports cover everything.

### Forgotten WiFi credentials / device unreachable

Power-cycle the device and wait ~60 seconds for the WiFi connect timeout. The device will fall back to its `OAS-<device_id>-Setup` AP. Connect from your phone (password = `ap_password` from `secrets.yaml`), and re-provision via the captive portal.

If you also forgot the `ap_password`, you must re-flash over USB.

---

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Power LED on DevKitM-1 not lit at all | No +5V at the module. Check the 24 V terminal block J1 polarity, then the LM2596S-5.0 output. The buck output should sit at 5.0 V ±0.1 V at the +5V net on the daughterboard socket. |
| Power LED steady but no AP, no mDNS | Firmware did not boot. Connect USB and watch the log via `esphome logs firmware/esphome/oas.yaml` — likely a configuration error from your edits. |
| Can't reach `oas-<device_id>.local` | Most consumer routers block mDNS across VLANs. Find the IP via your router admin or Home Assistant, and use `http://<ip>/` directly. |
| `secrets.yaml not found` during build | The file must live at `firmware/esphome/secrets.yaml`, **not** at the repo root. The example template is at `firmware/secrets.yaml.example` for historical reasons; copy it to the firmware/esphome/ directory. |
| SEN66 readings stuck at "unavailable" | I²C wiring issue. Verify the SEN66 JST-GH cable is seated correctly on both ends. The I²C bus scan log line (enabled by default) should show device 0x6B. Pull-up resistors are 4.7 kΩ on the MCU side (v0.22+); if you have an older board with 10 kΩ, the bus may not meet rise-time spec at the full 220 mm bus length. |
| LD2410 presence never triggers | Verify UART wiring on the daughterboard socket — TX on the MCU side (GPIO 16) goes to RX on the LD2410 side, and vice versa. Baud must be 256000. Set `logger:` to `VERBOSE` to see raw protocol frames. |
| LED ring shows wrong number of LEDs (e.g. last 1-2 LEDs unlit, or colours shifted) | `num_leds` in `leds.yaml` must match your physical ring. OAS v0.18+ ships **11 LEDs** (D14 was dropped to free space for the 24 V terminal block on the south side). If you have an earlier board variant with 12 LEDs, override `num_leds: 12` in your per-device substitutions. |
| LED ring full white at boot, not animating | Firmware crash before main loop. Check USB serial logs. Common cause: bad `api_encryption_key` format (must be exactly base64-encoded 32 bytes, no whitespace). |
| Web dashboard reachable but Home Assistant doesn't discover | mDNS may be filtered on your network; add manually via Settings → Devices & Services. Also confirm the API encryption key in HA matches `secrets.yaml`. |
| OTA fails after a few seconds | Network blocking traffic on port 3232. Some corporate / guest WiFi filters block this; flash over USB once on a permissive network. |
