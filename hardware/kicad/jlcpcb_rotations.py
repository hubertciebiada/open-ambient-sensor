"""JLCPCB rotation corrections for OAS pos.csv export — single source of truth.

KiCad footprint "0 deg rotation" reference != JLCPCB tape-feeder "0 deg rotation"
reference for many packages. Each pos.csv row needs a per-footprint offset
applied before upload. This module aggregates two sources:

  1. UPSTREAM:    third_party/JLCKicadTools/jlc_kicad_tools/cpl_rotations_db.csv
                  (Matthew Lai, MIT, ~60 regex entries, community-validated
                  on thousands of boards). Pipeline reads this file from the
                  pinned git submodule — no network access at runtime.

  2. OAS-SPECIFIC: JLCPCB_ROTATIONS_OAS list below. Catches footprints that
                   upstream does NOT match — typically project-local custom
                   footprints (oas:SK6812-SIDE) or packages missing from
                   upstream coverage (TO-263, SOT-583).

Lookup precedence (per `load_combined()`):
  - Iterate upstream entries FIRST (in CSV order)
  - If no upstream match → iterate OAS-SPECIFIC entries
  - First regex match wins → apply offset, log source
  - No match → unchanged, log warning

User intent (2026-05-19): "Zrób oas specific rotations PO tych Z biblioteki.
Osobny skrypt który domyka to co ucieka bibliotece". → OAS list serves as
gap-filler for upstream coverage, not an override mechanism.

To add an OAS-specific entry:
  1. Reproduce the issue: upload current pos.csv to JLCPCB DFM (manually,
     via tools/jlcdfm_upload.py) and confirm visual mismatch in their
     renderer.
  2. Determine offset empirically (typically 90° / 180° / 270° steps).
  3. Append entry to JLCPCB_ROTATIONS_OAS with `(regex, offset, rationale)`.
     The rationale MUST cite the observation (which board version, which
     designator, what was wrong) — future developers need to understand
     why the offset exists.
  4. Re-run pipeline. Stage 21 log shows the offset applied.
  5. Re-upload to JLCPCB DFM, verify the fix worked.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
UPSTREAM_CSV = HERE / "third_party" / "JLCKicadTools" / "jlc_kicad_tools" / "cpl_rotations_db.csv"


# ---------------------------------------------------------------------------
# OAS-specific entries — gap-fillers for footprints upstream does not match.
# ---------------------------------------------------------------------------
# Each tuple: (compiled_regex, offset_deg, rationale_string).
# Rationale is mandatory and shown in stage 21 log.
JLCPCB_ROTATIONS_OAS: list[tuple[re.Pattern, float, str]] = [
    # U1 LM2596S-5.0 — DPAK family. v0.40 JLCPCB DFM render: chip body
    # rotated 180° relative to pads, leads landing off-pad. Empirical fix
    # +180° flips body so leads sit on lead pads, TAB sits on tab pad.
    (
        re.compile(r"^TO-263"),
        180,
        "v0.40 DFM: U1 LM2596S body 180 deg vs pads. Empirical fix.",
    ),

    # U2 TPS62933 SOT-583-8. v0.40 JLCPCB DFM render: package mirrored.
    # Conservative +180° (matches SOT-89/SOT-223 family convention in
    # upstream CSV). Verify via DFM re-upload before order.
    (
        re.compile(r"^SOT-583"),
        180,
        "v0.40 DFM: U2 TPS62933 body flipped. Empirical fix (SOT-8x family convention).",
    ),

    # D11..D22 SK6812-SIDE (oas:SK6812-SIDE custom footprint). v0.40
    # JLCPCB DFM render: LEDs on Ø22 mm ring emitting INWARD (toward
    # central cable hole) instead of OUTWARD (toward perforated cover).
    # +180° flip per LED inverts the emission direction. Combined with
    # the (270 - theta) ring placement formula, each LED's die ends up
    # pointing radially outward as intended.
    (
        re.compile(r"^SK6812-SIDE$"),
        180,
        "v0.40 DFM: LED ring emitting inward. +180 flips die to outward radial.",
    ),
]


def _parse_upstream_csv() -> list[tuple[re.Pattern, float, str]]:
    """Parse JLCKicadTools cpl_rotations_db.csv from the pinned submodule.

    Schema per row: `<regex>,<rotation_offset>[,<dx>,<dy>]`. Header row
    skipped. Returns (compiled_regex, offset_deg, source_tag) tuples.
    Hard FAIL if submodule not initialized — clear error tells the
    developer the single fix command.
    """
    if not UPSTREAM_CSV.exists():
        sys.exit(
            "[FAIL] rotation correction CSV missing at "
            f"{UPSTREAM_CSV.relative_to(HERE.parent.parent)} — "
            "run: git submodule update --init --recursive"
        )
    out: list[tuple[re.Pattern, float, str]] = []
    with UPSTREAM_CSV.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            pattern = row[0].strip().strip('"')
            try:
                offset = float(row[1])
            except ValueError:
                continue
            out.append((re.compile(pattern), offset, "upstream"))
    return out


def load_combined() -> list[tuple[re.Pattern, float, str]]:
    """Return upstream entries + OAS-specific entries as one list.

    Order matters: upstream FIRST, OAS SECOND. Stage 21 takes the first
    regex match per footprint, so OAS entries only fire when upstream
    doesn't match — gap-filler semantics, not override.
    """
    upstream = _parse_upstream_csv()
    oas = [
        (rx, off, f"oas: {rationale}")
        for (rx, off, rationale) in JLCPCB_ROTATIONS_OAS
    ]
    return upstream + oas


def stats() -> tuple[int, int]:
    """Return (n_upstream, n_oas_specific) for stage 21 banner."""
    return len(_parse_upstream_csv()), len(JLCPCB_ROTATIONS_OAS)
