# OAS ESPHome project

Developer-facing notes for the ESPHome firmware. For the end-user flashing workflow, see [`../../docs/FLASHING.md`](../../docs/FLASHING.md). For Home Assistant integration, see [`../../docs/HA-INTEGRATION.md`](../../docs/HA-INTEGRATION.md).

---

## Project layout

```
firmware/esphome/
├── oas.yaml                # top-level config + per-device substitutions
├── packages/
│   ├── core.yaml           # WiFi, AP fallback, captive portal, OTA, API, web_server, mDNS, time, logger, Improv
│   ├── leds.yaml           # SK6812-SIDE ring (11 LEDs on GPIO 8), 8+ effects, AQI mode, day-night dim
│   ├── air-quality.yaml    # Sensirion SEN66 (CO2, PM1/2.5/4/10, VOC, NOx, T, RH) + STAR-Engine + offsets
│   ├── presence.yaml       # HiLink LD2410 mmWave radar (UART @ 256000 baud + GPIO 2 interrupt)
│   ├── nfc.yaml            # NXP NT3H1101 dynamic NFC tag (I²C 0x55, FD interrupt GPIO 3) + dashboard URL
│   └── bt-proxy.yaml       # Bluetooth proxy
├── examples/               # anonymized per-device override examples
└── README.md               # this file
```

`oas.yaml` is the canonical entry point. The packages are pulled in via `!include packages/<name>.yaml`. Each package is self-contained — you can comment one out in `oas.yaml` to build a stripped-down image (e.g. without BLE proxy if you're tight on flash).

---

## Per-package responsibilities

One line per package — the canonical contract each file owns:

| Package | Responsibility |
|---|---|
| **core.yaml** | WiFi (with AP fallback + captive portal + Improv Serial), Home Assistant native API (encrypted), ESPHome OTA, on-device web_server v3 dashboard, mDNS hostname `oas-<device_id>.local`, SNTP + Home Assistant time sources, Prometheus `/metrics` endpoint, logger (USB-only — UART pins are owned by LD2410). |
| **leds.yaml** | SK6812-SIDE 11-LED ring on GPIO 8 (D14 vacant), 8+ user-selectable effects, `select.led_mode` (Auto-AQI / Manual / Off / Test-Rainbow), `number.led_brightness_day` + `number.led_brightness_night` with sunrise/sunset auto-dim, AQI colour mapping from SEN66 readings. |
| **air-quality.yaml** | Sensirion SEN66 over I²C 0x6B — CO₂, PM1/2.5/4/10, VOC index, NOx index, temperature, humidity. STAR-Engine IAQM Light preset (T1=1000, T2=3000, K=200, P=200 raw 16-bit values — ×10 of post-scale display values) re-uploaded on every boot via `on_boot:` lambda because Sensirion params are volatile. User-tunable `number.temperature_offset`, `number.humidity_offset`, `number.co2_offset` persisted across reboots with `restore_value: yes`. `button.sen66_force_clean` triggers the SEN66 fan auto-clean cycle. |
| **presence.yaml** | HiLink LD2410 mmWave radar on UART1 (GPIO 16 TX, GPIO 17 RX, 256000 baud) + presence-interrupt on GPIO 2. Exposes presence binary sensor, moving/still target binaries, distance, target energies. Per-gate sensitivity (8 moving + 8 still), max-distance gate, and presence timeout exposed as `number:` entities so the user can tune the radar from the web UI without re-flashing. |
| **nfc.yaml** | MIKROE-2462 (NXP NT3H1101 NTAG I²C) on I²C 0x55 + FD interrupt on GPIO 3. Writes a single NDEF URL record to NTAG memory every 60 s. URL is set by `text.dashboard_url` (initialised from `dashboard_url` substitution, editable at runtime via web_server or HA). Phone tap → browser opens the URL. |
| **bt-proxy.yaml** | `bluetooth_proxy:` enabled so HA can use this device as a BLE forwarder. `switch.bluetooth_proxy` to enable/disable at runtime. Default on. |

---

## Developer workflow

### Validate config (no flash, no compile)

```bash
esphome config firmware/esphome/oas.yaml
```

Expands all substitutions and `!include` directives, parses every component, and prints the full merged YAML to stdout. Fast (~2 s) — useful as a pre-commit check. Catches typos, missing secrets, malformed effect definitions, missing pins, etc.

### Compile without flashing

```bash
esphome compile firmware/esphome/oas.yaml
```

Runs the full build (~3-5 min on a cold cache, seconds on subsequent builds). Produces `.esphome/build/<name>/.pioenvs/<name>/firmware.bin`. Useful for size profiling and for producing an artifact to upload via the web flasher.

### Flash (USB or OTA)

```bash
esphome run firmware/esphome/oas.yaml
```

ESPHome auto-detects whether to use USB (if a serial port matches the device) or OTA (if the device is discoverable on the LAN). Override with `--device <hostname-or-ip>` or `--device /dev/cu.usbserial-XXXX`.

### Live log viewer

```bash
esphome logs firmware/esphome/oas.yaml
```

Streams logs over USB or via the API. Useful for first-bringup debugging.

### Local-only debug build (no Home Assistant)

Comment out the API encryption requirement and bump the logger level:

```yaml
api:
  encryption:
    key: !secret api_encryption_key   # comment this if you don't want HA pairing

logger:
  level: VERBOSE                       # or DEBUG for less noise
```

The web_server dashboard (`http://oas-<device>.local/`) remains the primary debugging surface — every sensor, switch, number, and select is interactive there.

---

## Versioning

The `esphome.project` field in `oas.yaml` tracks the OAS hardware revision:

```yaml
esphome:
  project:
    name: ${project_name}              # "HubertCiebiada.open-ambient-sensor"
    version: ${project_version}        # e.g. "v0.40"
```

Bump `project_version` in `oas.yaml` (or the per-device override) whenever the firmware reflects a new hardware revision. Home Assistant surfaces this version on the Device card, making it easy to tell which boards in a fleet need a re-flash.

The CLAUDE.md changelog is the source of truth for the project version — every meaningful change (HW or FW) lands a new entry.

---

## Adding a new sensor

When extending OAS with another I²C or UART peripheral (e.g. via the Qwiic expansion port):

1. **Pick a free GPIO.** The pinout table in [`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) lists the safe non-strap pins still available on the DevKitM-1.
2. **Create a new package file** under `packages/` (e.g. `packages/co2-secondary.yaml`).
3. **Include it from `oas.yaml`** under the `packages:` block.
4. **Validate with `esphome config`** before flashing.

Keep one peripheral per package — easier to read, easier to disable, easier to merge.

---

## Common pitfalls

- **Pull `secrets.yaml` from the right place.** It must live at `firmware/esphome/secrets.yaml`, NOT at the repo root. The template is at `firmware/secrets.yaml.example` for historical reasons.
- **Don't enable `arduino` framework.** The C6 + BLE proxy + WiFi + SEN66 + LD2410 stack runs out of IRAM on `arduino`. `esp-idf` is the only viable framework.
- **GPIO 10 and GPIO 11 do not exist** on the ESP32-C6FH4 chip used in the MINI-1 SoM (internal SiP flash bonds them internally). Don't assign signals there even if generic ESP32-C6 docs imply they're available. See CLAUDE.md "Module identification" rule.
- **The `web_server` v3 OTA endpoint is disabled** (`ota: false` in `core.yaml`). Canonical OTA goes through the encrypted ESPHome API channel. The bundled web_server OTA is older and less secure.
- **The LED ring has 11 LEDs, not 12.** D14 was vacated in v0.18 so the 24 V terminal block J1 could sit on the south side. If you have an early-revision board with 12 LEDs, override `num_leds` in your per-device substitutions.

---

## Status

**Preliminary.** Firmware lands here so the user can flash on day-1 of the v0.40 prototype boards arriving from JLCPCB. First end-to-end validation (compile-clean + each sensor exercised on real hardware) follows once boards are physically in hand.
