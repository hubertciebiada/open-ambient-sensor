"""JLCPCB rotation corrections for OAS pos.csv export — single source of truth.

ARCHITECTURE (audit-19, 2026-05-19): JLCPCB tape-feeder rotation offsets
apply ONLY at stage 30_export_pos.py against the kicad-cli-emitted
pos.csv. They NEVER touch `oas.kicad_pcb`, the schematic, or any
2D / 3D / preflight render. This separation is intentional:

  - `oas.kicad_pcb`             = KiCad ground truth (natural rotation)
  - `hardware/renders/pcb/*`    = visual verification of KiCad placement
  - `hardware/output/jlcpcb/oas-top-pos.csv` = JLCPCB tape-feeder-correct

Consequence: visual sanity-checking in renders reflects placement
INTENT (what KiCad believes the chip body sits like on the PCB),
free of JLCPCB-specific tape orientation quirks. The pos.csv on disk
is the only artefact that JLCPCB ever sees, and it gets the offsets
applied at emit time via this module.

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
  4. Re-run pipeline. Stage 30 log shows the offset applied.
  5. Re-upload to JLCPCB DFM, verify the fix worked.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent                  # hardware/kicad/pipeline/jlcpcb
KICAD_ROOT = HERE.parent.parent               # hardware/kicad (sibling: third_party/)
UPSTREAM_CSV = KICAD_ROOT / "third_party" / "JLCKicadTools" / "jlc_kicad_tools" / "cpl_rotations_db.csv"


# ---------------------------------------------------------------------------
# OAS-specific entries — gap-fillers for footprints upstream does not match.
# ---------------------------------------------------------------------------
# Each tuple: (compiled_regex, offset_deg, rationale_string).
# Rationale is mandatory and shown in stage 30 log.
#
# Audit-19 (2026-05-19): TO-263 and SOT-583 entries removed. Those were
# empirical without JLCPCB DFM re-upload validation. KiCad's stock
# footprint pad geometry for U1 / U2 is verbatim correct (audit-15/16
# refactor) so absent confirmed JLCPCB tape-feeder offset, no
# compensation is needed. If DFM upload of a future revision shows
# U1 or U2 mis-oriented, re-add the entry with the screenshot path
# in the rationale.
#
# The SK6812-SIDE entry is kept at 0 deg deliberately (see the entry's
# own comment block): the boardgen (90 - theta) LED placement formula
# already carries the 180 deg tape-feeder compensation, so no extra
# pos.csv offset is needed. A stale +180 here — left over from the
# older (270 - theta) placement — double-compensated and put the AQI
# ring 180 deg off (emission inward, "pin outer edge") on JLCPCB DFM.
JLCPCB_ROTATIONS_OAS: list[tuple[re.Pattern, float, str]] = [
    # D11..D18 SK6812-SIDE (oas:SK6812-SIDE custom footprint).
    # Offset 0 deg — and that is DELIBERATE. Do NOT re-add +180.
    #
    # A +180 entry lived here while the boardgen LED placement used the
    # (270 - theta) formula. v0.41 (2026-05-19) changed that formula to
    # (90 - theta) so the KiCad 3D render shows the ring emitting
    # radially OUTWARD. (90 - theta) already differs from (270 - theta)
    # by 180 deg, so the placement now bakes in the tape-feeder
    # compensation. The +180 left here on top of it double-compensated:
    # JLCPCB DFM then rendered the ring emitting INWARD and flagged
    # "pin outer edge" (the asymmetric land 180 deg off its pins).
    # Offset 0 makes the CPL rotation == boardgen placement == the
    # KiCad 3D render: emission outward, pins on pads.
    (
        re.compile(r"^SK6812-SIDE$"),
        0,
        "SK6812-SIDE: 0 deg by design — the (90 - theta) boardgen placement already carries the 180 deg tape-feeder compensation; an extra +180 double-compensates (JLCPCB DFM: emission inward + pin-outer-edge).",
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
            f"{UPSTREAM_CSV.relative_to(KICAD_ROOT.parent)} — "
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

    Order matters: upstream FIRST, OAS SECOND. Stage 30 takes the first
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
    """Return (n_upstream, n_oas_specific) for stage 30 banner."""
    return len(_parse_upstream_csv()), len(JLCPCB_ROTATIONS_OAS)
