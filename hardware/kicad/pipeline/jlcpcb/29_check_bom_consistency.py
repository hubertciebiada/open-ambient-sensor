"""Stage 29: BOM consistency — LCSC# vs (Value, Footprint) must be bijective.

Catches the typical "copy-paste bug" in `lcsc_mapping.py` where two different
(Value, Footprint) entries point to the same LCSC# — meaning JLCPCB will pull
the WRONG part for one of them at assembly time. Bouni's kicad-jlcpcb-tools
has the equivalent check as `get_part_consistency_warnings()`.

Rules enforced:
  1. Each non-empty, non-DEPRECATED LCSC# appears in AT MOST ONE entry.
     (Same LCSC# in two entries = ambiguity → which (Value, Footprint) does
     JLCPCB actually receive? → FAIL)
  2. Each (Value, Footprint) key appears in AT MOST ONE entry.
     (Guaranteed by Python dict semantics, but verify defensively.)

DEPRECATED-* LCSC#'s skipped (intentional historical markers).

Pure-Python, zero deps, deterministic. Runs early so a copy-paste bug
fails before any expensive export stage runs.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT  # noqa: E402

sys.path.insert(0, str(KICAD_ROOT))
from lcsc_mapping import LCSC_MAPPING  # noqa: E402

STAGE_NAME = "check_bom_consistency"


def main() -> int:
    with Stage(STAGE_NAME) as st:
        n_entries = len(LCSC_MAPPING)
        st.info(f"loaded {n_entries} entries from lcsc_mapping.py")

        # Build reverse index: LCSC# -> list of (Value, Footprint) keys.
        # Skip entries flagged DEPRECATED-* (intentional historical markers
        # kept for BOM matcher robustness on pre-vN schematics).
        lcsc_to_keys: dict[str, list[tuple[str, str]]] = defaultdict(list)
        skipped = 0
        for key, entry in LCSC_MAPPING.items():
            lcsc = entry.get("lcsc", "").strip()
            if not lcsc or lcsc.startswith("DEPRECATED-"):
                skipped += 1
                continue
            lcsc_to_keys[lcsc].append(key)

        st.info(f"{n_entries - skipped} active entries, {skipped} skipped (empty / DEPRECATED-*)")

        # Rule 1: bijection LCSC# -> (Value, Footprint)
        collisions = {lcsc: keys for lcsc, keys in lcsc_to_keys.items() if len(keys) > 1}
        if collisions:
            for lcsc, keys in sorted(collisions.items()):
                st.info(f"  COLLISION: LCSC# {lcsc} used by {len(keys)} entries:")
                for value, footprint in keys:
                    st.info(f"    - ({value!r}, {footprint!r})")
            st.fail(
                f"{len(collisions)} LCSC# collision(s) in lcsc_mapping.py — "
                "each non-DEPRECATED LCSC# must map to a single (Value, Footprint)"
            )

        st.ok(f"all {len(lcsc_to_keys)} active LCSC#'s are unique (bijection OK)")

        # Rule 2: defensive — verify Python dict didn't somehow alias keys.
        # (Functionally impossible, but cheap to verify.)
        if len(LCSC_MAPPING) != len(set(LCSC_MAPPING.keys())):
            st.fail("duplicate (Value, Footprint) keys in LCSC_MAPPING — should be impossible")
        st.ok(f"all {n_entries} (Value, Footprint) keys are unique")
    return 0


if __name__ == "__main__":
    sys.exit(main())
