#!/usr/bin/env python3
"""OAS bench bring-up check — flash one unit and verify the same things every time.

Usage (from anywhere; paths are resolved relative to the YAML):

    python firmware/tools/bringup_check.py firmware/esphome/devices/<unit>.yaml
        [--port COM14] [--no-flash] [--no-reset] [--ip 192.168.x.y]
        [--boot-seconds 45] [--sse-seconds 25]

What it does, in order:
  1. finds the DevKit's native USB-Serial-JTAG port (VID 303A:1001) unless --port;
  2. `esphome run --no-logs` (compiles if needed, flashes) unless --no-flash;
  3. pulses a hard reset and captures the boot log over serial (unless --no-reset),
     then greps it: ESPHome/project version, SEN66 detected (serial / product /
     firmware), STAR preset upload, WiFi connected, no [E] lines, no panic,
     no "Last reset too quick";
  4. resolves the unit (mDNS via zeroconf, TXT record gives the WiFi MAC;
     falls back to the OS resolver, then --ip) and checks HTTP 200;
  5. reads the web_server SSE stream for --sse-seconds and checks the live
     entities: SEN66 readings in sane windows, STAR text sensor, LD2410
     UART alive (distance sensors numeric + baud select), OUT pin entity,
     ring ON, BLE proxy ON;
  6. prints a PASS/FAIL table, the MAC + IP (for a DHCP reservation), and
     writes the full report next to the YAML under reports/ (gitignored when
     the YAML lives in devices/).

Exit code 0 = every check passed, 1 = at least one failed, 2 = tooling error.

Serial-line discipline for the ESP32 USB-Serial-JTAG port (learned the hard
way on 2026-09-06):
  * the chip only transmits while the host holds DTR;
  * RTS high with DTR low resets it; DTR high while RTS releases = download
    mode; both high = nothing. pyserial applies DTR/RTS at open in driver
    order, so opening with both high can pass through the reset state — open
    with BOTH low and raise DTR alone afterwards;
  * on Windows usbser.sys forwards a control-line change only on a DTR write,
    so every RTS change is followed by a dummy DTR write (esptool does the
    same), otherwise the "reset" never reaches the chip;
  * the USB link survives a chip reset, so the reset is pulsed on the same
    handle that then reads the boot log;
  * never reopen on silence — an idle INFO log is quiet for minutes (this
    script's ancestor boot-looped a unit that way).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover
    print("pyserial missing — it ships with esphome: pip install esphome", file=sys.stderr)
    sys.exit(2)

ANSI = re.compile(r"\x1b\[[0-9;]*m")
USB_JTAG_VIDPID = (0x303A, 0x1001)
STAR_OK_TEXT = "uploaded"


# --------------------------------------------------------------------------- helpers
class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool | None, str]] = []
        self.lines: list[str] = []

    def check(self, name: str, ok: bool | None, detail: str = "") -> None:
        self.rows.append((name, ok, detail))
        tag = "PASS" if ok else ("SKIP" if ok is None else "FAIL")
        line = f"[{tag}] {name:<34} {detail}"
        print(line)
        self.lines.append(line)

    def note(self, text: str) -> None:
        print(text)
        self.lines.append(text)

    @property
    def failed(self) -> bool:
        return any(ok is False for _, ok, _ in self.rows)


def find_port(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    hits = [p.device for p in list_ports.comports() if (p.vid, p.pid) == USB_JTAG_VIDPID]
    if len(hits) == 1:
        return hits[0]
    return None


def port_present(port: str) -> bool:
    return any(p.device == port for p in list_ports.comports())


def wait_for_port(port: str, timeout: float = 15.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if port_present(port):
            return True
        time.sleep(0.5)
    return False


def port_mac(port: str) -> str | None:
    """USB serial string of the ESP32 USB-Serial-JTAG device = the chip's base
    MAC, which on the ESP32-C6 is also the Wi-Fi station MAC."""
    for p in list_ports.comports():
        if p.device == port and p.serial_number and re.fullmatch(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", p.serial_number):
            return p.serial_number.upper()
    return None


def open_port(port: str) -> serial.Serial:
    s = serial.Serial()
    s.port = port
    s.baudrate = 115200
    s.timeout = 0.5
    s.dtr = False
    s.rts = False
    s.open()
    return s


def capture_boot(port: str, seconds: float, do_reset: bool) -> list[str]:
    """Return decoded log lines; pulses a hard reset on the SAME handle first
    when do_reset — the USB-Serial-JTAG link survives a chip reset, so the
    handle stays valid and the app's first lines land in it."""
    out: list[str] = []
    deadline = time.time() + seconds
    opens = 0
    while time.time() < deadline and opens < 4:
        opens += 1
        got_any = False
        try:
            s = open_port(port)          # DTR=0, RTS=0: cannot reset, cannot strap
            if do_reset:
                do_reset = False
                # usbser.sys pushes the control-line state to the device only on
                # a DTR write, so each RTS change is followed by a dummy DTR
                # write (esptool's _setRTS work-around). RTS=1/DTR=0 = EN low.
                s.rts = True
                s.dtr = False
                time.sleep(0.15)
                s.rts = False
                s.dtr = False
                time.sleep(0.05)         # let the strap sample before DTR rises
                out.append("--- hard reset pulsed")
            s.dtr = True                 # host attached: the chip now transmits
            opened_at = time.time()
            while time.time() < deadline:
                raw = s.readline()
                if raw:
                    got_any = True
                    out.append(ANSI.sub("", raw.decode("utf-8", "replace")).rstrip("\r\n"))
                elif not got_any and time.time() - opened_at > 5.0:
                    # a handle opened mid-enumeration can be silently dead;
                    # bounded reopen, never on later silence (idle INFO logs
                    # are quiet for minutes)
                    out.append("--- no data 5 s after open, reopening")
                    break
            s.close()
            if got_any:
                break
        except serial.SerialException as e:
            out.append(f"--- port error: {e}")
            time.sleep(0.5)
    return out


def device_id_from_yaml(path: Path) -> str | None:
    m = re.search(r"^\s*device_id:\s*([A-Za-z0-9_-]+)", path.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def resolve_unit(host: str, explicit_ip: str | None) -> tuple[str | None, str | None, dict[str, str]]:
    """Return (ip, source, mdns_txt). Tries zeroconf, OS resolver, --ip."""
    txt: dict[str, str] = {}
    try:
        from zeroconf import Zeroconf  # ships with esphome

        zc = Zeroconf()
        try:
            info = zc.get_service_info("_esphomelib._tcp.local.", f"{host}._esphomelib._tcp.local.", timeout=6000)
        finally:
            zc.close()
        if info:
            for k, v in (info.properties or {}).items():
                txt[k.decode() if isinstance(k, bytes) else str(k)] = (
                    v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)
                )
            addrs = info.parsed_addresses() if hasattr(info, "parsed_addresses") else []
            ipv4 = [a for a in addrs if ":" not in a]
            if ipv4:
                return ipv4[0], "zeroconf", txt
    except Exception as e:  # zeroconf absent or blocked — fall through
        txt["_zeroconf_error"] = str(e)
    try:
        return socket.gethostbyname(f"{host}.local"), "os-resolver", txt
    except OSError:
        pass
    if explicit_ip:
        return explicit_ip, "--ip", txt
    return None, None, txt


def http_status(url: str, timeout: float = 5.0) -> int | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def read_sse(ip: str, seconds: float) -> dict[str, tuple[str | None, object]]:
    seen: dict[str, tuple[str | None, object]] = {}
    req = urllib.request.Request(f"http://{ip}/events", headers={"Accept": "text/event-stream"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            while time.time() - t0 < seconds:
                line = r.readline()
                if not line:
                    break
                line = line.decode("utf-8", "replace").rstrip()
                if not line.startswith("data:"):
                    continue
                try:
                    d = json.loads(line[5:].strip())
                except Exception:
                    continue
                if isinstance(d, dict) and "id" in d:
                    seen[d["id"]] = (d.get("state"), d.get("value"))
    except Exception as e:
        seen["_error"] = (str(e), None)
    return seen


def num(seen: dict, key: str) -> float | None:
    v = seen.get(key, (None, None))[1]
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def in_window(x: float | None, lo: float, hi: float) -> bool:
    return x is not None and lo <= x <= hi


def friendly_name_from_yaml(path: Path) -> str | None:
    m = re.search(r'^\s*friendly_name:\s*"?([^"\n]+?)"?\s*$', path.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def update_registry(yaml_path: Path, device_id: str, fields: dict[str, object]) -> Path:
    """Keep a per-fleet `units.json` next to the device configs — one entry per
    unit with what the check learned (MAC, IP, SEN66 serial, last result) plus
    hand-maintained deployment flags. The file carries room names and
    addresses, so it belongs in the gitignored devices/ directory."""
    reg = yaml_path.parent / "units.json"
    try:
        data = json.loads(reg.read_text(encoding="utf-8")) if reg.exists() else {}
    except (OSError, ValueError):
        data = {}
    entry = data.setdefault(device_id, {})
    for k, v in fields.items():
        if v is not None:
            entry[k] = v
    if entry.get("last_result") == "PASS":
        entry.setdefault("first_pass", entry["last_check"])
    for flag in ("dhcp_reserved", "ha_added", "installed"):
        entry.setdefault(flag, False)
    entry.setdefault("notes", "")
    reg.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return reg


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("yaml", type=Path)
    ap.add_argument("--port")
    ap.add_argument("--no-flash", action="store_true")
    ap.add_argument("--no-reset", action="store_true", help="skip the reset pulse (no boot-log checks)")
    ap.add_argument("--ip", help="fallback when mDNS does not resolve")
    ap.add_argument("--boot-seconds", type=float, default=45.0)
    ap.add_argument("--sse-seconds", type=float, default=25.0)
    args = ap.parse_args()

    yaml_path: Path = args.yaml.resolve()
    if not yaml_path.is_file():
        print(f"no such file: {yaml_path}", file=sys.stderr)
        return 2
    device_id = device_id_from_yaml(yaml_path)
    if not device_id:
        print("could not find `device_id:` in the YAML", file=sys.stderr)
        return 2
    host = f"oas-{device_id}"
    rep = Report()
    started = dt.datetime.now()
    rep.note(f"OAS bring-up check — {host} — {started:%Y-%m-%d %H:%M:%S}")
    rep.note(f"config: {yaml_path}")

    # 1. port — only needed to flash or to pulse the reset; a pure network
    #    re-check (--no-flash --no-reset) runs without a cable
    port = find_port(args.port)
    if args.no_flash and args.no_reset:
        rep.check("USB-Serial-JTAG port", None, port or "not needed (--no-flash --no-reset)")
    else:
        rep.check("USB-Serial-JTAG port found", port is not None, port or "none / ambiguous — pass --port")
        if port is None:
            return 1

    # 2. flash
    if args.no_flash:
        rep.check("flash", None, "skipped (--no-flash)")
    else:
        cmd = [sys.executable, "-m", "esphome", "run", str(yaml_path), "--device", port, "--no-logs"]
        rep.note("$ " + " ".join(cmd))
        proc = subprocess.run(cmd, cwd=yaml_path.parent, capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = "\n".join(proc.stdout.splitlines()[-3:])
        rep.check("flash (esphome run)", proc.returncode == 0, tail.strip().splitlines()[-1] if tail.strip() else f"rc={proc.returncode}")
        if proc.returncode != 0:
            rep.note(proc.stderr[-2000:])
            return 1
        time.sleep(2.0)
        wait_for_port(port, 15)

    # 3. boot log
    boot: list[str] = []
    boot_at: float | None = None
    if args.no_reset:
        rep.check("boot log", None, "skipped (--no-reset)")
    else:
        boot_at = time.time()
        boot = capture_boot(port, args.boot_seconds, do_reset=True)
        text = "\n".join(boot)
        m_ver = re.search(r"ESPHome version ([^\s]+)", text)
        m_proj = re.search(r"Project \S+ version (\S+)", text)
        rep.check("boot: ESPHome / project version", bool(m_ver and m_proj),
                  f"{m_ver.group(1) if m_ver else '?'} / {m_proj.group(1) if m_proj else '?'}")
        m_serial = re.search(r"sen6x[^\]]*\]: Serial number: (\S+)", text)
        m_prod = re.search(r"sen6x[^\]]*\]: Product: (\S+)", text)
        m_fw = re.search(r"sen6x[^\]]*\]: Firmware: (\S+)", text)
        rep.check("boot: SEN66 detected on I2C", bool(m_prod and m_prod.group(1) == "SEN66"),
                  f"serial {m_serial.group(1) if m_serial else '?'}, fw {m_fw.group(1) if m_fw else '?'}")
        m_star = re.search(r"STAR accel .*err=(\d+)", text)
        rep.check("boot: STAR preset uploaded", bool(m_star and m_star.group(1) == "0"),
                  m_star.group(0) if m_star else "no STAR line")
        rep.check("boot: WiFi connected", bool(re.search(r"\[wifi[^\]]*\]: Connected", text)),
                  "first attempt failed, connected after scan" if "Connecting to network failed" in text else "")
        # "[E][api]: No clients; rebooting" is api.reboot_timeout firing on a
        # unit not yet paired with Home Assistant — expected on the bench.
        errs = [l for l in boot if l.startswith("[E]") and "No clients; rebooting" not in l]
        rep.check("boot: no [E] lines", not errs, "; ".join(errs[:3]))
        bad = [l for l in boot if re.search(r"Last reset too quick|panic|Guru Meditation|abort\(\)|assert failed", l)]
        rep.check("boot: no reboot loop / panic", not bad, "; ".join(bad[:2]))

    # 4. network
    ip, src, txt = resolve_unit(host, args.ip)
    rep.check("mDNS / IP resolves", ip is not None, f"{ip} via {src}" if ip else "not resolved — pass --ip")
    mac = port_mac(port) if port else None
    if mac is None:  # no cable: reuse what an earlier run recorded
        try:
            mac = json.loads((yaml_path.parent / "units.json").read_text(encoding="utf-8")).get(device_id, {}).get("mac")
        except (OSError, ValueError):
            mac = None
    mdns_mac = txt.get("mac")
    if mdns_mac and len(mdns_mac) == 12:
        mdns_mac = ":".join(mdns_mac[i:i + 2] for i in range(0, 12, 2)).upper()
    rep.note(f"      WiFi MAC (USB serial = base MAC): {mac or '?'}"
             + (f" | mDNS TXT mac={mdns_mac}" if mdns_mac else " | mDNS TXT not received"))
    if mac and mdns_mac and mac != mdns_mac:
        rep.check("MAC from USB serial matches mDNS", False, f"{mac} vs {mdns_mac}")
    if ip is None:
        return 1
    st = http_status(f"http://{ip}/")
    rep.check("web_server HTTP 200", st == 200, f"status {st}")

    # 5. live entities — uptime / wifi_signal publish their first value 60 s
    # after boot, so the SSE read must not start before that
    if boot_at is not None:
        settle = boot_at + 65.0 - time.time()
        if settle > 0:
            rep.note(f"      waiting {settle:.0f} s for the 60 s-interval sensors to publish")
            time.sleep(settle)
    seen = read_sse(ip, args.sse_seconds)
    if "_error" in seen and len(seen) == 1:
        rep.check("SSE stream", False, seen["_error"][0])
        return 1
    co2, t, rh = num(seen, "sensor-co2"), num(seen, "sensor-temperature"), num(seen, "sensor-humidity")
    pm25, voc, nox = num(seen, "sensor-pm_2_5"), num(seen, "sensor-voc_index"), num(seen, "sensor-nox_index")
    rep.check("SEN66: CO2 380..5000 ppm", in_window(co2, 380, 5000), f"{co2}")
    rep.check("SEN66: temperature 5..45 C", in_window(t, 5, 45), f"{t}")
    rep.check("SEN66: humidity 5..95 %", in_window(rh, 5, 95), f"{rh}")
    rep.check("SEN66: PM2.5 present", pm25 is not None and pm25 >= 0, f"{pm25}")
    rep.check("SEN66: VOC / NOx index present", voc is not None and nox is not None, f"voc {voc} nox {nox}")
    star_state = str(seen.get("text_sensor-star-engine_state", (None, None))[0] or "")
    rep.check("SEN66: STAR text sensor", STAR_OK_TEXT in star_state, star_state or "missing")
    dists = [num(seen, k) for k in ("sensor-moving_distance", "sensor-still_distance", "sensor-detection_distance")]
    baud = str(seen.get("select-ld2410_baud_rate", (None, None))[0] or "")
    rep.check("LD2410C: UART alive", any(d is not None for d in dists) and baud == "256000",
              f"distances {dists} baud {baud or '?'}")
    rep.check("LD2410C: OUT pin entity", "binary_sensor-presence_pin" in seen,
              f"presence_pin={seen.get('binary_sensor-presence_pin', ('missing',))[0]} presence={seen.get('binary_sensor-presence', ('?',))[0]}")
    rep.check("LED ring ON", str(seen.get("light-ring", (None,))[0]) == "ON", str(seen.get("light-ring", ("missing",))[0]))
    rep.check("BLE proxy ON", str(seen.get("switch-ble_proxy", (None,))[0]) == "ON", str(seen.get("switch-ble_proxy", ("missing",))[0]))
    rssi = num(seen, "sensor-wifi_rssi")
    rep.check("WiFi RSSI better than -80 dBm", in_window(rssi, -80, 0), f"{rssi} dBm" if rssi is not None else "entity missing")
    rep.check("Uptime entity present", num(seen, "sensor-uptime") is not None, f"{num(seen, 'sensor-uptime')} s")

    # 6. summary + report file
    rep.note("")
    rep.note(f"RESULT: {'FAIL' if rep.failed else 'PASS'} — {host} at {ip} (MAC {mac or '?'})")
    rep.note("DHCP reservation: reserve this MAC -> this IP on the router before the unit moves to its room.")
    reports = yaml_path.parent / "reports"
    reports.mkdir(exist_ok=True)
    out = reports / f"{device_id}-{started:%Y%m%d-%H%M%S}.txt"
    out.write_text("\n".join(rep.lines) + "\n\n--- boot log ---\n" + "\n".join(boot) + "\n\n--- entities ---\n"
                   + "\n".join(f"{k}: {v[0]}" for k, v in sorted(seen.items())) + "\n", encoding="utf-8")
    rep.note(f"report: {out}")

    boot_text = "\n".join(boot)
    m_serial = re.search(r"sen6x[^\]]*\]: Serial number: (\S+)", boot_text)
    m_fw = re.search(r"sen6x[^\]]*\]: Firmware: (\S+)", boot_text)
    m_proj = re.search(r"Project \S+ version (\S+)", boot_text)
    reg = update_registry(yaml_path, device_id, {
        "friendly_name": friendly_name_from_yaml(yaml_path),
        "host": host,
        "mac": mac,
        "ip": ip,
        "sen66_serial": m_serial.group(1) if m_serial else None,
        "sen66_fw": m_fw.group(1) if m_fw else None,
        "firmware": m_proj.group(1) if m_proj else None,
        "rssi_dbm": rssi,
        "last_check": f"{started:%Y-%m-%d %H:%M}",
        "last_result": "FAIL" if rep.failed else "PASS",
        "last_report": out.name,
    })
    rep.note(f"registry: {reg}")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
