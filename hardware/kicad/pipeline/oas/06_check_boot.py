"""
OAS - ESP32-C6 boot-strap pin and signal-pin audit (pure Python).

Verifies that every safety-critical pin on the ESP32-C6-DevKitM-1-N4 module
sockets (J5/J6) is on the expected net at boot time. Catches the class
of bug where a strap pin is accidentally pulled to the wrong rail, an
external driver fights the module's onboard pull-up/down, or a signal
pin is wired to the wrong GPIO.

Specifically blocks the following classes of regression:

  1. **Boot-mode brick**: GPIO 9 (boot select) externally pulled LOW
     at power-on -> chip enters Download mode forever instead of running
     firmware. Module has onboard 10k pull-up to V3V3 + push-button to
     GND; J6.11 must either be NC or only on the /IO/BOOT recovery net
     (J10 header, DNP).
  2. **WS2812 idle storm**: GPIO 8 (also a boot ROM print strap) wired
     directly to the SK6812 ring without an external pull-up.
     DevKitM-1's onboard pull-up runs off VCC_5V, which is unpowered in
     OAS (we feed +3V3 directly into J5.1). R7 = 10 kohm to +3V3 must
     therefore sit on the WS2812_DIN net to hold GPIO 8 HIGH at boot.
  3. **JTAG mode strap conflict**: GPIO 15 (JTAG signal source select)
     bridged to anything other than the module's internal state.
  4. **Pinout swap**: a future schematic edit accidentally swaps two
     signal pins (e.g. moves UART_TX onto GPIO 17 instead of 16, or
     wires LD2410_OUT to GPIO 3 instead of 2 - which would make the
     LD2410 presence interrupt land on the NFC_FD ISR handler).

Approach
--------
Runs `kicad-cli sch export netlist --format kicadsexpr` against the
top-level oas.kicad_sch, parses every (net ...) block, then walks the
J5/J6 socket pins against a hardcoded `J_PIN_TO_GPIO` map sourced from
the Espressif ESP32-C6-DevKitM-1-N4 official schematic (the same
mapping documented in CLAUDE.md changelog v0.21).

The audit is intentionally HARDCODED to OAS's specific pin assignments;
a future board with a different MCU module will need its own table.
Trade-off: regression-tightness over generality.

Exit code 0 if all checks pass, 1 on any assertion failure. Run as a
`regenerate.py` step OR standalone (`python tools/check_boot.py`).
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).parent
KICAD_DIR = HERE.parent.parent  # pipeline/oas/ -> pipeline/ -> hardware/kicad
TOP_SCH = KICAD_DIR / "oas.kicad_sch"

# Pull GPIO_ASSIGNMENTS straight from generate.py — single source of truth for
# the OAS pinout. Each entry: {net: <bare label>, sheet: </PATH/>, desc: ...}.
sys.path.insert(0, str(KICAD_DIR))
from generate import GPIO_ASSIGNMENTS  # noqa: E402

# ---------------------------------------------------------------------------
# DevKitM-1-N4 socket pin -> ESP32-C6 chip GPIO mapping.
# Sourced from Espressif ESP32-C6-DevKitM-1 dimensions PDF (rev 1.0).
# J5 is the OAS PCB socket mating with DevKitM-1's J1 header (antenna side).
# J6 is the OAS PCB socket mating with DevKitM-1's J3 header (USB side).
# Pin numbering 1..15 follows the DevKitM-1 silk numbering (top of pin
# block is pin 1).
#
# Values:
#   * "GPIOnn"          - exposed ESP32-C6 GPIO pad
#   * "3V3" / "5V"      - power rails on the module
#   * "GND"             - ground
#   * "RST"             - chip reset (EN pin, active low)
# ---------------------------------------------------------------------------
J5_PIN_TO_GPIO = {
    1: "3V3",   2: "RST",   3: "GPIO2",  4: "GPIO3",  5: "GPIO4",
    6: "GPIO5", 7: "GPIO0", 8: "GPIO1",  9: "GPIO8", 10: "GPIO6",
   11: "GPIO7",12: "GPIO14",13: "GND",  14: "5V",   15: "GND",
}
J6_PIN_TO_GPIO = {
    1: "GND",   2: "GPIO16", 3: "GPIO17", 4: "GPIO23", 5: "GPIO22",
    6: "GPIO21",7: "GPIO20", 8: "GPIO19", 9: "GPIO18",10: "GPIO15",
   11: "GPIO9",12: "GND",   13: "GPIO13",14: "GPIO12",15: "GND",
}

# ESP32-C6 strap pins per Espressif ESP32-C6 TRM (rev 1.0) section "Boot Configuration".
# Each entry: (gpio_name, strap_function, allowed_state_at_boot).
STRAP_PINS = [
    ("GPIO4",  "MTMS / JTAG mode",
     "must be NC (module internal pull-up handles strap)"),
    ("GPIO5",  "MTDI / VDD_SPI voltage select",
     "must be NC (irrelevant for SiP-flash variant, internal pull-down)"),
    ("GPIO8",  "ROM print / UART download print",
     "must have external pull-up to +3V3 (DevKitM-1 onboard pull-up "
     "runs off VCC_5V which is unpowered in OAS)"),
    ("GPIO9",  "Boot mode select",
     "must be NC or on /IO/BOOT only (recovery header DNP); module has "
     "onboard 10k pull-up + BOOT button to GND"),
    ("GPIO15", "JTAG signal source select",
     "must be NC (module sets internal state)"),
]

# Signal pin assignments derived from generate.py::GPIO_ASSIGNMENTS (SOT).
# Each entry: (gpio_name, expected_net_name, semantic_description).
SIGNAL_PINS = [
    (f"GPIO{gpio}", f"{entry['sheet']}{entry['net']}", entry["desc"])
    for gpio, entry in sorted(GPIO_ASSIGNMENTS.items())
]

# Net name pattern for unconnected pins as emitted by KiCad's netlist exporter.
NC_NET_RE = re.compile(r"^unconnected-\([^)]+\)$")


@dataclass
class CheckResult:
    name: str
    value: str
    spec: str
    passed: bool

    def __str__(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        return f"  [{mark}] {self.name:38s} {self.value:30s} (spec: {self.spec})"


def export_netlist() -> str:
    """Invoke kicad-cli to export the OAS top-level schematic netlist."""
    with tempfile.NamedTemporaryFile(
        prefix="oas_boot_audit_", suffix=".net", delete=False
    ) as tf:
        netlist_path = Path(tf.name)
    cmd = [
        _kicad_cli(),
        "sch", "export", "netlist",
        "--format", "kicadsexpr",
        "--output", str(netlist_path),
        str(TOP_SCH),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(
            f"ERROR: kicad-cli netlist export failed (exit {result.returncode}):\n"
            f"{result.stderr}"
        )
    text = netlist_path.read_text(encoding="utf-8")
    try:
        netlist_path.unlink()
    except OSError:
        pass
    return text


def _kicad_cli() -> str:
    """Locate kicad-cli on the local system. Tries the OAS-standard
    Windows install path first, then falls back to PATH lookup."""
    win_path = Path(r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe")
    if win_path.exists():
        return str(win_path)
    return "kicad-cli"


def parse_net_assignments(netlist_text: str) -> dict[tuple[str, int], str]:
    """Walk the netlist and return a dict mapping (refdes, pin_number) -> net_name.
    Uses depth-counting parse to handle nested S-expressions."""
    mapping: dict[tuple[str, int], str] = {}
    i = 0
    n = len(netlist_text)
    while True:
        idx = netlist_text.find("(net\n", i)
        if idx == -1:
            break
        depth = 0
        j = idx
        while j < n:
            ch = netlist_text[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = netlist_text[idx:j]
        m_name = re.search(r'\(name "([^"]+)"\)', block)
        if not m_name:
            i = j
            continue
        net_name = m_name.group(1)
        for m in re.finditer(
            r'\(ref "([A-Za-z]+\d+)"\)\s*\(pin "(\d+)"', block
        ):
            mapping[(m.group(1), int(m.group(2)))] = net_name
        i = j
    return mapping


def lookup_socket_pin(
    pin_map: dict[tuple[str, int], str], refdes: str, gpio_name: str
) -> tuple[int, str] | None:
    """Find the socket pin number for the named GPIO on the given refdes,
    then return (pin_number, net_name). Returns None if the GPIO is not
    routed out of that socket."""
    table = J5_PIN_TO_GPIO if refdes == "J5" else J6_PIN_TO_GPIO
    for pin_no, name in table.items():
        if name == gpio_name:
            return pin_no, pin_map.get((refdes, pin_no), "<no-net>")
    return None


def find_gpio(
    pin_map: dict[tuple[str, int], str], gpio_name: str
) -> tuple[str, int, str]:
    """Find which socket (J5 or J6) exposes the named GPIO and return
    (refdes, pin_number, net_name). Aborts if the GPIO is on neither
    socket (which would mean the table is wrong)."""
    for refdes in ("J5", "J6"):
        hit = lookup_socket_pin(pin_map, refdes, gpio_name)
        if hit is not None:
            pin_no, net = hit
            return refdes, pin_no, net
    sys.exit(f"ERROR: {gpio_name} is not exposed on J5 or J6 per the table.")


def is_nc(net_name: str) -> bool:
    """Detect KiCad's auto-generated unconnected-net naming."""
    return bool(NC_NET_RE.match(net_name)) or net_name == "<no-net>"


def check_strap_pin(
    pin_map: dict[tuple[str, int], str],
    netlist_text: str,
    gpio_name: str,
    function_description: str,
    allowed_state: str,
) -> CheckResult:
    """Run the per-strap-pin rule. Each strap pin has its own acceptance
    logic encoded here; see STRAP_PINS table for the rules."""
    refdes, pin_no, net = find_gpio(pin_map, gpio_name)
    socket_pin = f"{refdes}.{pin_no:2d}"

    if gpio_name in ("GPIO4", "GPIO5", "GPIO15"):
        passed = is_nc(net)
        observed = f"{socket_pin} -> {net}"
        return CheckResult(
            name=f"{gpio_name} ({function_description})",
            value=observed,
            spec="net must be NC",
            passed=passed,
        )

    if gpio_name == "GPIO8":
        # Must be on a net that ALSO contains R7 (the external pull-up).
        net_has_r7 = ("R7", 1) in pin_map and pin_map[("R7", 1)] == net
        net_has_r7 = net_has_r7 or (
            ("R7", 2) in pin_map and pin_map[("R7", 2)] == net
        )
        # And R7 other pin must connect to +3V3.
        r7_other_pin = (
            pin_map.get(("R7", 1)) if pin_map.get(("R7", 2)) == net
            else pin_map.get(("R7", 2))
        )
        pull_up_to_3v3 = r7_other_pin in ("+3V3", "+3.3V")
        passed = net_has_r7 and pull_up_to_3v3
        observed = (
            f"{socket_pin} -> {net}; R7 on net={net_has_r7}, "
            f"R7 other pin={r7_other_pin!r}"
        )
        return CheckResult(
            name=f"{gpio_name} ({function_description})",
            value=observed,
            spec="R7 pull-up to +3V3 on same net",
            passed=passed,
        )

    if gpio_name == "GPIO9":
        passed = is_nc(net) or net == "/IO/BOOT"
        observed = f"{socket_pin} -> {net}"
        return CheckResult(
            name=f"{gpio_name} ({function_description})",
            value=observed,
            spec="NC or /IO/BOOT (recovery only)",
            passed=passed,
        )

    sys.exit(f"ERROR: no rule defined for strap pin {gpio_name}.")


def check_signal_pin(
    pin_map: dict[tuple[str, int], str],
    gpio_name: str,
    expected_net: str,
    description: str,
) -> CheckResult:
    refdes, pin_no, net = find_gpio(pin_map, gpio_name)
    return CheckResult(
        name=f"{gpio_name} -> {description}",
        value=f"{refdes}.{pin_no:2d} -> {net}",
        spec=f"net == {expected_net}",
        passed=net == expected_net,
    )


def main() -> None:
    print("OAS ESP32-C6 boot-strap and signal-pin audit")
    print("=" * 60)
    print()
    print("Exporting netlist from oas.kicad_sch ...")
    netlist_text = export_netlist()
    pin_map = parse_net_assignments(netlist_text)
    print(f"  parsed {len(pin_map)} pad-to-net assignments")
    print()

    all_results: list[CheckResult] = []

    print("Strap pin checks (chip would brick or misboot if any fail)")
    print("-" * 60)
    for gpio_name, fn, allowed in STRAP_PINS:
        r = check_strap_pin(pin_map, netlist_text, gpio_name, fn, allowed)
        all_results.append(r)
        print(r)
    print()

    print("Signal pin checks (firmware-vs-hardware pinout consistency)")
    print("-" * 60)
    for gpio_name, expected_net, desc in SIGNAL_PINS:
        r = check_signal_pin(pin_map, gpio_name, expected_net, desc)
        all_results.append(r)
        print(r)
    print()

    # Summary.
    total = len(all_results)
    failed = [r for r in all_results if not r.passed]
    print("=" * 60)
    if failed:
        print(f"FAIL: {len(failed)} of {total} boot-strap/signal checks failed.")
        for r in failed:
            print(f"  {r}")
        sys.exit(1)
    print(f"PASS: all {total} boot-strap/signal checks passed.")


if __name__ == "__main__":
    main()
