"""Stage 19: metadata integrity checks on OAS source-of-truth dicts.

Two checks, one stage:

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

# At least one of these keys (case-sensitive) must be present in every
# EXTERNAL_MODULES entry. Suffix match counts (so "supplier_pl",
# "supplier_eu", "supplier_global" all satisfy the "supplier_*" intent).
IDENTITY_KEYS = ("mpn", "ean", "material")
IDENTITY_KEY_PREFIXES = ("supplier",)


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
        if not isinstance(entry, dict):
            errors.append(f"EXTERNAL_MODULES[{name!r}] is not a dict")
            continue
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
        if not isinstance(entry, dict):
            errors.append(f"{loc} is not a dict")
            continue

        lcsc = entry.get("lcsc", "")
        if not isinstance(lcsc, str) or not LCSC_PATTERN.match(lcsc):
            if not (isinstance(lcsc, str) and lcsc.startswith("DEPRECATED-")):
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
            if not isinstance(v, str) or not v.strip():
                errors.append(f"{loc}[{field!r}] missing or empty")

        ds = entry.get("datasheet", "")
        if not isinstance(ds, str):
            errors.append(f"{loc}['datasheet'] is not a string ({type(ds).__name__})")

    return len(LCSC_MAPPING)


def main() -> int:
    with Stage(STAGE_NAME) as st:
        errors: list[str] = []
        n_modules = _check_external_modules(errors)
        n_lcsc = _check_lcsc_mapping(errors)

        if errors:
            for e in errors:
                print(f"[FAIL] {e}")
            st.fail(f"{len(errors)} metadata integrity violation(s)")

        st.ok(
            f"{n_modules} EXTERNAL_MODULES entries have valid identifiers; "
            f"{n_lcsc} LCSC_MAPPING entries match expected schema"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
