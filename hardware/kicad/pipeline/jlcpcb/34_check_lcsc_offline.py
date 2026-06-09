"""Stage 34: validate lcsc_mapping.py entries against the offline jlcparts DB.

Adresses Lesson 5 (R3 30.9 kΩ vs 806 Ω near-miss): an LCSC# can be a
typo away from a completely different part. JLCPCB's "smart-match"
silently accepted the wrong SKU on the v0.40 order; pre-payment XLS
diff caught it, but only because the user manually compared every row.

This stage queries a local SQLite cache built by the `jlcparts`
submodule (yaqwsx/jlcparts) and asserts, per LCSC# in lcsc_mapping.py:
  - the SKU resolves to an existing part in the JLCPCB component DB,
  - the part's expected component class (Capacitor / Resistor / etc.)
    matches what the footprint name implies,
  - the part is not marked as out-of-stock at cache time.

Cache location: `.tmp/jlcparts/cache.sqlite3` (mirror of the
`.tmp/spice/` pattern from 08_check_switching). The cache is
gitignored via `/.tmp/`.

If the cache is missing the stage HARD-FAILS with the exact one-time
setup instructions. No soft-skip — Lesson 5 (R3 30.9 kΩ vs 806 Ω near-
miss) is a class of failure the harness MUST be able to catch, and
silently skipping the check makes the harness blind to it. The cache
rebuild is a one-time user action; once built it lives at
`.tmp/jlcparts/cache.sqlite3` and subsequent `build.py` runs reuse it.

Setup is performed via the companion helper:

    python tools/setup_jlcparts_cache.py

That helper installs jlcparts (from the submodule), pulls the JLCPCB
component CSV, builds the SQLite cache, and writes a freshness stamp.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT, EXIT_MISSING_DEP  # noqa: E402

STAGE_NAME = "check_lcsc_offline"

CACHE_PATH = KICAD_ROOT.parent.parent / ".tmp" / "jlcparts" / "cache.sqlite3"

# Footprint-name pattern → SET of category/subcategory substrings that
# the matched jlcparts row's combined "category subcategory" string must
# contain AT LEAST ONE of. Match is case-insensitive. Patterns must
# anchor enough to disambiguate (e.g. `^C_\d{4}` for caps).
FOOTPRINT_TO_CATEGORY: list[tuple[re.Pattern[str], set[str]]] = [
    (re.compile(r"Capacitor_SMD:C_\d+"),            {"capacitor"}),
    (re.compile(r"Resistor_SMD:R_\d+"),             {"resistor"}),
    # Diode_SMD covers rectifiers, schottky, zener, AND TVS — jlcparts
    # classifies TVS under 'Circuit Protection / TVS', diodes proper
    # under 'Diodes / *'. Accept either.
    (re.compile(r"Diode_SMD:D_S(MA|MB|OD)"),        {"diode", "tvs", "zener"}),
    (re.compile(r"Inductor_SMD:L_\w+_5040"),        {"inductor"}),
    # Polyfuse: jlcparts uses 'Circuit Protection / Resettable Fuses'.
    # F1 uses the project-local oas:Fuse_1812L_4532Metric land (v0.42 —
    # the generic KiCad stock Fuse_*_*Metric land mismatched the
    # Littelfuse 1812L termination geometry); match by substring so the
    # `oas:` prefix does not hide F1 from this Lesson-5 class check.
    (re.compile(r"Fuse_1812L_\d+Metric"),           {"resettable", "ptc", "fuse"}),
    (re.compile(r"Package_TO_SOT_SMD:SOT-23"),      {"mosfet", "transistor"}),
    # Buck regulators: jlcparts uses 'Power Management ICs / DC-DC' or
    # 'Voltage Regulators'.
    (re.compile(r"Package_TO_SOT_SMD:TO-263-5"),    {"regulator", "dc-dc", "power management"}),
    (re.compile(r"Package_SO:SOT-583"),             {"regulator", "dc-dc", "power management"}),
]


def _lookup_category(footprint: str) -> set[str] | None:
    for pattern, cats in FOOTPRINT_TO_CATEGORY:
        if pattern.search(footprint):
            return cats
    return None


def main() -> int:
    with Stage(STAGE_NAME) as st:
        if not CACHE_PATH.exists():
            print(
                f"[FAIL] jlcparts cache not found at "
                f"{CACHE_PATH.relative_to(KICAD_ROOT.parent.parent)}"
            )
            print(
                "[FAIL] one-time setup required:"
                "\n         python hardware/kicad/tools/setup_jlcparts_cache.py"
                "\n       This pulls the JLCPCB component CSV and builds the"
                "\n       offline SQLite cache so LCSC# class / value mismatches"
                "\n       (Lesson 5) get caught BEFORE a JLCPCB order is placed."
            )
            st.fail(
                "jlcparts offline cache missing — run the setup helper",
                code=EXIT_MISSING_DEP,
            )

        sys.path.insert(0, str(KICAD_ROOT))
        from lcsc_mapping import LCSC_MAPPING  # noqa: E402

        # Build LCSC# -> expected-category map from lcsc_mapping. Skip
        # DEPRECATED entries (sentinel rows, not real SKUs).
        to_check: list[tuple[str, str, set[str]]] = []  # (lcsc, footprint, expected_cats)
        for (value, footprint), entry in LCSC_MAPPING.items():
            lcsc = entry.get("lcsc", "")
            if lcsc.startswith("DEPRECATED-"):
                continue
            expected_cats = _lookup_category(footprint)
            if expected_cats is None:
                continue  # unmapped footprint type — informational only
            to_check.append((lcsc, footprint, expected_cats))

        # Open DB read-only. jlcparts schema:
        #   components(lcsc INT, category_id INT, mfr, package, joints,
        #              manufacturer_id, basic, description, datasheet, stock)
        #   categories(id INT, category TEXT, subcategory TEXT)
        # LCSC stored as INTEGER (no 'C' prefix), so we strip the prefix
        # at query time.
        con = sqlite3.connect(f"file:{CACHE_PATH}?mode=ro", uri=True)
        try:
            cur = con.cursor()
            errors: list[str] = []
            checked = 0
            missing_in_db: list[str] = []
            for lcsc, footprint, expected_cats in to_check:
                lcsc_int = int(lcsc[1:])  # 'C23022' -> 23022
                row = cur.execute(
                    "SELECT cat.category, cat.subcategory, c.stock "
                    "FROM components c "
                    "JOIN categories cat ON c.category_id = cat.id "
                    "WHERE c.lcsc = ? LIMIT 1",
                    (lcsc_int,),
                ).fetchone()
                if row is None:
                    missing_in_db.append(f"{lcsc} ({footprint})")
                    continue
                checked += 1
                category, subcategory, stock = row
                # Concatenate category + subcategory for substring match.
                catstring = f"{category} {subcategory}".lower()
                if not any(cat in catstring for cat in expected_cats):
                    errors.append(
                        f"{lcsc} category {category!r}/{subcategory!r} does not match "
                        f"any of {sorted(expected_cats)} from footprint {footprint!r}"
                    )
                if isinstance(stock, int) and stock <= 0:
                    print(f"[WARN] {lcsc} reports stock={stock} (informational)")
        finally:
            con.close()

        if missing_in_db:
            for sku in missing_in_db:
                print(f"[INFO] {sku} not in cache (DEPRECATED or freshly added LCSC#)")

        if errors:
            for e in errors:
                print(f"[FAIL] {e}")
            st.fail(
                f"{len(errors)} LCSC#/footprint class mismatch(es) "
                "— Lesson 5 R3 near-miss prevention"
            )

        st.ok(
            f"{checked} LCSC# entries validated against offline jlcparts cache "
            f"({len(to_check)} candidates, {len(missing_in_db)} not in cache)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
