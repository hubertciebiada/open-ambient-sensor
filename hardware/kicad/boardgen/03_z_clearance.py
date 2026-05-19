"""boardgen stage 03: Z-clearance audit.

Asserts every component placed under a daughterboard body shadow has
height <= the under-board clearance budget. DRC has no third-dimension
awareness; this stage fills that gap. Aborts on any violation.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from boardgen._postprocess import (
    check_z_clearance_violations, _parse_footprint_placements,
)


def run(ctx) -> None:
    print()
    print("Checking daughterboard Z-clearance violations...")
    violations = check_z_clearance_violations()
    if violations:
        print()
        print("ERROR: Z-clearance violations under daughterboards:")
        for v in violations:
            print(v)
        print()
        sys.exit(
            "Aborting: relocate the offending components out of the "
            "daughterboard body shadow, or update DAUGHTERBOARD_Z_CLEARANCE "
            "if the socket spec has changed."
        )
    print(f"  OK - no Z-clearance violations (checked {len(_parse_footprint_placements())} placed footprints).")


if __name__ == "__main__":
    from boardgen._common import Context
    run(Context())
