"""Stage 19: metadata integrity checks on OAS source-of-truth dicts.

Four checks, one stage:

A. `boardgen._project.EXTERNAL_MODULES` (Lesson 10): every dev-module /
   dev-board / breakout entry MUST carry at least one canonical part
   identifier. We accept ANY of:
     - `mpn`                 (manufacturer part number)
     - `ean`                 (EAN/GTIN — Polish/EU retail preferred)
     - `material`            (Sensirion's canonical SKU)
     - `supplier_*` field    (specific distributor SKU or URL)
   Pure descriptive entries ('ESP32-C6 SuperMini' without MPN/EAN) are
   exactly the foot-gun this check prevents.

B. `lcsc_mapping.LCSC_MAPPING` self-consistency (Gap H + Lesson 5):
   - LCSC key matches pattern `^C\\d+$`,
   - `library` ∈ {Basic, Extended, N/A},
   - `manufacturer` and `mpn` both non-empty strings,
   - `datasheet` is a string (URL or empty placeholder).

   These guard against copy-paste typos like `C2302` vs `C23022` where
   one digit off lands on a completely different part (Lesson 5 R3
   near-miss: C23022 = 30.9 kΩ vs C23116 = 806 Ω).

C. `boardgen._project.POWER_BUDGET` schema (Lesson 6 — don't hallucinate
   datasheet values): every entry MUST carry
     - `name`, `rail`, `typ_ma`, `peak_ma`, `datasheet`,
   and the `datasheet` MUST be a non-empty HTTP/HTTPS URL. This forces
   anyone touching the power budget to cite a real datasheet — caught
   the same class of "I remember the AO3401A is ±20 V Vgs" error
   audit-16 caught (actually ±12 V) before it can land in the budget.

D. J4 (HLK-LD2410B) pin order vs Lesson 20 canonical mapping. Authority:
   HLK V1.04 datasheet Table 1 (page 7), user-verified 2026-05-23 —
   pin 1 = OUT, pin 2 = UART TX, pin 3 = UART RX, pin 4 = GND,
   pin 5 = VCC. Two anchors are verified:
     - `boardgen/_sch_sensors.py` J4 wiring block: each J4 pin's wire
       (uuid tags "j4-p1-out" … "j4-p5-vcc-down") must terminate at the
       canonical net. Net-name nuance: the OAS net names are MCU-centric,
       so J4 pin 2 (the LD2410's UART_Tx OUTPUT) lands on net UART_RX
       (it arrives at the ESP32's RX, GPIO 17) and J4 pin 3 (the
       LD2410's UART_Rx INPUT) lands on net UART_TX (driven by GPIO 16)
       — the standard TX/RX crossover.
     - `boardgen/_project.py::J4_PCB_ROTATION` must stay 90 — the v0.43
       footprint-orientation fix that puts pad 1 (OUT) at the WEST end
       of the row, where the LD2410 module's OUT pin physically lands.
   The history (v0.15.8 schematic-reversal + v0.43 footprint-flip +
   re-revert) makes this exact spot regression-prone; the check also
   FAILS LOUDLY if any anchor vanishes (a moved/renamed structure means
   the check is blind, which is itself a failure).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT  # noqa: E402

STAGE_NAME = "check_oas_metadata"

LCSC_PATTERN = re.compile(r"^C\d+$")
LIBRARY_TIERS = {"Basic", "Extended", "N/A"}

# POWER_BUDGET entries must cite a real datasheet URL (Lesson 6 — don't
# hallucinate datasheet values). Empty / placeholder / "TBD" strings are
# rejected. We require the value to START with an http(s):// URL token;
# anything after (e.g. " (search LD2410B)") is descriptive and tolerated
# because some manufacturer datasheet roots have no direct deep-link.
DATASHEET_URL_PATTERN = re.compile(r"^https?://\S+")
POWER_BUDGET_REQUIRED_KEYS = ("name", "rail", "typ_ma", "peak_ma", "datasheet")
POWER_BUDGET_VALID_RAILS = {"3V3", "5V", "24V"}

# At least one of these keys (case-sensitive) must be present in every
# EXTERNAL_MODULES entry. Suffix match counts (so "supplier_pl",
# "supplier_eu", "supplier_global" all satisfy the "supplier_*" intent).
IDENTITY_KEYS = ("mpn", "ean", "material")
IDENTITY_KEY_PREFIXES = ("supplier",)

# --- Check D: J4 / LD2410B pin order (Lesson 20) ------------------------------
# Canonical order per HLK V1.04 datasheet Table 1 (page 7), user-verified
# 2026-05-23: pin 1 = OUT, 2 = UART TX, 3 = UART RX, 4 = GND, 5 = VCC.
#
# The schematic source of truth is the J4 wiring block in
# boardgen/_sch_sensors.py (no importable pin→net dict exists — the mapping
# lives inside the sheet-generator function body), so we parse the source
# text anchored on the deterministic wire uuid tags. Each entry:
#   pin -> (wire uuid tag, anchor kind, expected net/lib_id).
#
# TX/RX crossover: net names are MCU-centric. J4 pin 2 is the LD2410's
# UART_Tx OUTPUT — it drives the ESP32's RX (GPIO 17), hence net UART_RX.
# J4 pin 3 is the LD2410's UART_Rx INPUT — driven by the ESP32's TX
# (GPIO 16), hence net UART_TX. Pin 5 (VCC) is fed from the +5V rail
# (LM2596S), so its anchor is the power:+5V flag.
J4_SCH_SOURCE_REL = Path("boardgen") / "_sch_sensors.py"
J4_EXPECTED: dict[int, tuple[str, str, str]] = {
    1: ("j4-p1-out", "label", "LD2410_OUT"),
    2: ("j4-p2-tx", "label", "UART_RX"),    # LD2410 TX -> MCU RX (crossover)
    3: ("j4-p3-rx", "label", "UART_TX"),    # LD2410 RX <- MCU TX (crossover)
    4: ("j4-p4-gnd-hop", "power", "power:GND"),
    5: ("j4-p5-vcc-down", "power", "power:+5V"),
}
# Net/flag must appear in the parts.append(...) call immediately following
# the anchored wire — 600 chars is comfortably past the intervening
# coordinate arguments but well short of the NEXT pin's wiring.
J4_ANCHOR_WINDOW = 600
J4_HLABEL_PATTERN = re.compile(r'_sch_hierarchical_label\(\s*name="([A-Za-z0-9_]+)"')
J4_PWRFLAG_PATTERN = re.compile(r'_sch_power_flag\(\s*lib_id="([A-Za-z0-9_:+\-]+)"')
# v0.43 footprint-orientation fix: rotation 90 puts pad 1 (OUT) at the WEST
# end of the row, where the LD2410 module's OUT pin physically lands
# (rotation 270 was the pre-v0.43 end-for-end-wrong state). A deliberate
# placement rework must update BOTH J4_PCB_ROTATION and this constant.
J4_EXPECTED_PCB_ROTATION = 90


def _has_identity(entry: dict) -> bool:
    if any(k in entry and entry[k] for k in IDENTITY_KEYS):
        return True
    for key in entry:
        for prefix in IDENTITY_KEY_PREFIXES:
            if key.startswith(prefix) and entry[key]:
                return True
    return False


def _check_external_modules(errors: list[str]) -> int:
    sys.path.insert(0, str(KICAD_ROOT))
    from boardgen._project import EXTERNAL_MODULES  # noqa: E402

    for name, entry in EXTERNAL_MODULES.items():
        if not _has_identity(entry):
            present_keys = sorted(entry.keys())
            errors.append(
                f"EXTERNAL_MODULES[{name!r}] missing identifier — needs "
                f"one of {IDENTITY_KEYS} or supplier_* "
                f"(have: {present_keys})"
            )
    return len(EXTERNAL_MODULES)


def _check_lcsc_mapping(errors: list[str]) -> int:
    sys.path.insert(0, str(KICAD_ROOT))
    from lcsc_mapping import LCSC_MAPPING  # noqa: E402

    for key, entry in LCSC_MAPPING.items():
        loc = f"LCSC_MAPPING[{key!r}]"

        lcsc = entry.get("lcsc", "")
        if not LCSC_PATTERN.match(lcsc) and not lcsc.startswith("DEPRECATED-"):
            errors.append(
                f"{loc}['lcsc'] = {lcsc!r} — must match ^C\\d+$"
            )

        lib = entry.get("library", "")
        if lib not in LIBRARY_TIERS:
            errors.append(
                f"{loc}['library'] = {lib!r} — must be one of {sorted(LIBRARY_TIERS)}"
            )

        for field in ("manufacturer", "mpn"):
            v = entry.get(field, "")
            if not v.strip():
                errors.append(f"{loc}[{field!r}] missing or empty")

        # Datasheet field: only required to be present (URL or empty
        # placeholder). Type narrows to `str` from the dict typing
        # contract, no runtime type check needed.
        entry.get("datasheet", "")

    return len(LCSC_MAPPING)


def _check_power_budget(errors: list[str]) -> int:
    sys.path.insert(0, str(KICAD_ROOT))
    from boardgen._project import POWER_BUDGET  # noqa: E402

    for idx, entry in enumerate(POWER_BUDGET):
        # PowerBudgetEntry is a TypedDict (statically enforced by mypy on
        # boardgen/_project.py). Runtime is always a dict here; the legacy
        # `isinstance(entry, dict)` defensive branch was unreachable.
        loc = f"POWER_BUDGET[{idx}]"
        if entry.get("name"):
            loc = f"POWER_BUDGET[{idx}] ({entry['name']!r})"

        for k in POWER_BUDGET_REQUIRED_KEYS:
            if k not in entry:
                errors.append(f"{loc} missing required key {k!r}")

        rail = entry.get("rail", "")
        if rail and rail not in POWER_BUDGET_VALID_RAILS:
            errors.append(
                f"{loc}['rail'] = {rail!r} — must be one of "
                f"{sorted(POWER_BUDGET_VALID_RAILS)}"
            )

        for field in ("typ_ma", "peak_ma"):
            v = entry.get(field)
            if v is None:
                continue  # already reported by required-keys loop
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                errors.append(
                    f"{loc}[{field!r}] = {v!r} — must be int/float (mA)"
                )
            elif v < 0:
                errors.append(
                    f"{loc}[{field!r}] = {v!r} — must be non-negative"
                )

        datasheet = entry.get("datasheet", "")
        if not isinstance(datasheet, str) or not datasheet.strip():
            errors.append(
                f"{loc}['datasheet'] missing or empty — Lesson 6 requires "
                f"a real datasheet URL for every power-budget entry"
            )
        elif not DATASHEET_URL_PATTERN.match(datasheet.strip()):
            errors.append(
                f"{loc}['datasheet'] = {datasheet!r} — must be a real "
                f"http(s):// URL (Lesson 6: don't hallucinate datasheet "
                f"values)"
            )

    return len(POWER_BUDGET)


def _check_j4_pin_order(errors: list[str]) -> int:
    """Check D: J4 pin 1..5 net order vs Lesson 20 canonical mapping.

    Authority: HLK V1.04 datasheet Table 1 (page 7) — 1=OUT, 2=UART TX,
    3=UART RX, 4=GND, 5=VCC (MCU-centric net names UART_RX / UART_TX on
    pins 2 / 3 — see the J4_EXPECTED comment for the TX/RX crossover).
    Fails loudly if any anchor vanished: a moved/renamed J4 wiring block
    or J4_PCB_* constant means this check is blind, which is itself a
    failure.
    """
    sys.path.insert(0, str(KICAD_ROOT))
    import boardgen._project as _bg_project  # noqa: E402

    src_path = KICAD_ROOT / J4_SCH_SOURCE_REL
    try:
        src = src_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(
            f"J4 (Lesson 20) check is blind — cannot read {src_path}: {exc}"
        )
        return 0

    checked = 0
    for pin, (tag, kind, expected) in sorted(J4_EXPECTED.items()):
        pos = src.find(f'"{tag}"')
        if pos < 0:
            errors.append(
                f"J4 pin {pin}: wire anchor {tag!r} not found in "
                f"{J4_SCH_SOURCE_REL} — the J4 wiring block moved or was "
                f"renamed; the Lesson-20 check is blind and must be "
                f"re-anchored"
            )
            continue

        window = src[pos:pos + J4_ANCHOR_WINDOW]
        if kind == "label":
            m = J4_HLABEL_PATTERN.search(window)
            what = "hierarchical label"
        else:
            m = J4_PWRFLAG_PATTERN.search(window)
            what = "power flag"
        if m is None:
            errors.append(
                f"J4 pin {pin}: no {what} found after wire anchor {tag!r} "
                f"in {J4_SCH_SOURCE_REL} — structure changed; the "
                f"Lesson-20 check is blind and must be re-anchored"
            )
            continue

        actual = m.group(1)
        if actual != expected:
            errors.append(
                f"J4 pin {pin}: {what} {actual!r} != canonical {expected!r} "
                f"— Lesson 20 / HLK V1.04 datasheet Table 1 (page 7): "
                f"1=OUT, 2=LD2410 TX (net UART_RX), 3=LD2410 RX (net "
                f"UART_TX), 4=GND, 5=VCC"
            )
            continue
        checked += 1

    rotation = getattr(_bg_project, "J4_PCB_ROTATION", None)
    if rotation is None:
        errors.append(
            "J4_PCB_ROTATION vanished from boardgen/_project.py — the "
            "Lesson-20 placement anchor is blind and must be re-anchored"
        )
    elif rotation != J4_EXPECTED_PCB_ROTATION:
        errors.append(
            f"J4_PCB_ROTATION = {rotation!r} != {J4_EXPECTED_PCB_ROTATION} "
            f"— v0.43 fixed the footprint end-for-end orientation (rotation "
            f"90 puts pad 1 = OUT at the WEST end where the LD2410's OUT "
            f"pin physically lands; 270 was the pre-v0.43 wrong state). A "
            f"deliberate placement rework must update both the constant "
            f"and this check (Lesson 20)"
        )
    return checked


def main() -> int:
    with Stage(STAGE_NAME) as st:
        errors: list[str] = []
        n_modules = _check_external_modules(errors)
        n_lcsc = _check_lcsc_mapping(errors)
        n_budget = _check_power_budget(errors)
        n_j4 = _check_j4_pin_order(errors)

        if errors:
            for e in errors:
                print(f"[FAIL] {e}")
            st.fail(f"{len(errors)} metadata integrity violation(s)")

        st.ok(
            f"{n_modules} EXTERNAL_MODULES entries have valid identifiers; "
            f"{n_lcsc} LCSC_MAPPING entries match expected schema; "
            f"{n_budget} POWER_BUDGET entries have valid datasheet URLs; "
            f"{n_j4}/5 J4 pins match Lesson-20 canonical order "
            f"(1=OUT 2=TX 3=RX 4=GND 5=VCC, HLK V1.04 Table 1)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
