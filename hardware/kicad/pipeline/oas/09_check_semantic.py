"""Stage 09: schematic semantic checks via kicad-skip.

Three OAS-specific invariants that ERC / DRC don't catch on their own,
because they require domain knowledge ("this exact resistor with this
exact value must exist on this exact net for the design to work"):

  A. I²C bus pull-ups: R5 = 4.7 kΩ on SDA, R6 = 4.7 kΩ on SCL. Without
     either, the SEN66 / NT3H1101 / Qwiic bus does not transact.
     Hard-coded in CLAUDE.md hardware section ("4.7 kΩ pull-ups on MCU
     side"). A missing pull-up shows as a silent comms failure on first
     boot, not as an ERC warning.

  B. GPIO 8 WS2812 DIN pull-up: R7 = 10 kΩ to +3V3. DevKitM-1's onboard
     pull-up depends on VCC_5V which OAS leaves floating, so we feed
     +3V3 directly via J5.1 — but then GPIO 8 floats unless R7 is
     present. CLAUDE.md hardware section explicitly mandates this.

  C. ESP32-C6 unused-pin coverage: the MCU schematic must carry at
     least 10 no_connect markers. ESP32-C6 SiP-flash exposes ~22 GPIO
     pins; OAS uses 8; the remaining ~14 are either reserved (strap /
     SPI flash) or unused. Bare-minimum threshold catches accidental
     bulk-deletion of nc markers (which would silently flip a strap
     pin's net binding).

Loads kicad-skip from `third_party/kicad-skip/src` (submodule). Hard-
fails if the submodule is not initialized — these invariants protect
against entire classes of silent design errors, the check must not
be skippable.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT, EXIT_MISSING_DEP  # noqa: E402

STAGE_NAME = "check_semantic"

MCU_SCH = KICAD_ROOT / "mcu.kicad_sch"

# Expected pull-up resistors (reference, expected_value, semantic).
EXPECTED_PULLUPS = [
    ("R5", "4.7k 1%", "I2C SDA pull-up (SEN66/NT3H1101/Qwiic bus)"),
    ("R6", "4.7k 1%", "I2C SCL pull-up (SEN66/NT3H1101/Qwiic bus)"),
    ("R7", "10k 1%",  "GPIO 8 WS2812 DIN pull-up (ring AQI signal)"),
]

# Minimum number of no_connect markers expected in mcu.kicad_sch. ESP32-C6
# has many unused pins; bare lower bound to detect accidental deletion.
MIN_NO_CONNECT = 10


def _load_skip():
    """Import the `skip` package from the local submodule. Returns None
    if the submodule is absent (soft-skip path)."""
    skip_src = KICAD_ROOT / "third_party" / "kicad-skip" / "src"
    if not skip_src.exists():
        return None
    if str(skip_src) not in sys.path:
        sys.path.insert(0, str(skip_src))
    try:
        import skip  # noqa: E402
        return skip
    except ImportError:
        return None


def main() -> int:
    with Stage(STAGE_NAME) as st:
        skip = _load_skip()
        if skip is None:
            st.fail(
                "kicad-skip submodule not initialized — "
                "run `git submodule update --init --recursive`",
                code=EXIT_MISSING_DEP,
            )

        if not MCU_SCH.exists():
            st.fail(f"{MCU_SCH} not found — run build.py first")

        # kicad-skip prints "Passed key -- can't parsy" warnings during
        # initial parse on KiCad 10 files; harmless but noisy. Silence
        # the parse phase across BOTH stdout and stderr.
        import contextlib, io  # noqa: E402
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            sch = skip.Schematic(str(MCU_SCH))

        # ---- Check A + B: expected pull-up resistors ----
        symbols_by_ref: dict[str, str] = {}
        for sym in sch.symbol:
            ref = sym.property.Reference.value
            val = sym.property.Value.value
            symbols_by_ref[ref] = val

        missing: list[str] = []
        wrong_value: list[str] = []
        for ref, expected_val, semantic in EXPECTED_PULLUPS:
            if ref not in symbols_by_ref:
                missing.append(f"{ref} ({semantic}) — not present in mcu.kicad_sch")
                continue
            actual = symbols_by_ref[ref]
            if actual != expected_val:
                wrong_value.append(
                    f"{ref} value {actual!r} != expected {expected_val!r} ({semantic})"
                )

        # ---- Check C: no_connect threshold ----
        nc_count = len(sch.no_connect)
        nc_short = nc_count < MIN_NO_CONNECT

        errors = missing + wrong_value
        if nc_short:
            errors.append(
                f"mcu.kicad_sch has {nc_count} no_connect markers "
                f"(< minimum {MIN_NO_CONNECT}) — strap-pin coverage at risk"
            )

        if errors:
            for e in errors:
                print(f"[FAIL] {e}")
            st.fail(f"{len(errors)} semantic invariant violation(s)")

        st.ok(
            f"{len(EXPECTED_PULLUPS)} pull-up resistors verified, "
            f"{nc_count} no_connect markers present"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
