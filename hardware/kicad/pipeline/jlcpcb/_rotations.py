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
reference for many packages — and for a few asymmetric packages (TO-263)
the KiCad footprint ORIGIN sits at a different point than JLCPCB's. So a
pos.csv row may need a per-footprint rotation correction AND an X/Y
position offset before upload. This module aggregates two sources:

  1. UPSTREAM:    third_party/JLCKicadTools/jlc_kicad_tools/cpl_rotations_db.csv
                  (Matthew Lai, MIT, ~60 regex entries, community-validated
                  on thousands of boards). Pipeline reads this file from the
                  pinned git submodule — no network access at runtime.
                  Rows whose pattern is listed in JLCPCB_UPSTREAM_SKIP are
                  dropped at load time — see that dict.

  2. OAS-SPECIFIC: JLCPCB_ROTATIONS_OAS list below. Catches footprints that
                   upstream does NOT match — typically project-local custom
                   footprints (oas:SK6812-SIDE) or packages missing from
                   upstream coverage.

Lookup precedence (per `load_combined()`):
  - Iterate upstream entries FIRST (CSV order, minus JLCPCB_UPSTREAM_SKIP)
  - If no upstream match → iterate OAS-SPECIFIC entries
  - First regex match wins → apply offset, log source
  - No match → unchanged (the footprint keeps its KiCad rotation)

User intent (2026-05-19): "Zrób oas specific rotations PO tych Z biblioteki.
Osobny skrypt który domyka to co ucieka bibliotece". → the OAS list is a
gap-filler (runs AFTER upstream), not an override mechanism. When an
upstream row is instead provably WRONG for an OAS footprint (not merely
missing), the fix is to DROP that row via JLCPCB_UPSTREAM_SKIP rather than
add an override tier — a footprint with no matching rule simply keeps its
KiCad ground-truth rotation. That is what J3 (JST GH) needed (2026-05-21).

To add an OAS-specific entry:
  1. Reproduce the issue: upload current pos.csv to JLCPCB DFM (manually,
     via tools/jlcdfm_upload.py) and confirm visual mismatch in their
     renderer.
  2. Determine offset empirically (typically 90° / 180° / 270° steps).
  3. Append entry to JLCPCB_ROTATIONS_OAS with
     `(regex, rotation_deg, dx_mm, dy_mm, rationale)`. Most entries need
     only a rotation (dx = dy = 0); add an X/Y offset only when the KiCad
     footprint origin differs from JLCPCB's (see the TO-263 entry).
     The rationale MUST cite the observation (which board version, which
     designator, what was wrong) — future developers need to understand
     why the correction exists.
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
# Each tuple: (compiled_regex, rotation_deg, dx_mm, dy_mm, rationale).
# dx/dy is a position offset added to the CPL Mid X / Mid Y (mm,
# specified for the part at 0 deg, rotated by its placement angle) —
# needed when the KiCad footprint origin differs from JLCPCB's, as for
# the asymmetric TO-263. Rotation-only entries set dx = dy = 0.
# Rationale is mandatory and shown in the stage 30 log.
#
# History: audit-19 (2026-05-19) removed earlier TO-263 and SOT-583
# entries as empirical / DFM-unvalidated. The TO-263 entry is now BACK
# (2026-05-21), re-added WITH JLCPCB DFM confirmation — see the U1
# entry's rationale below. The SOT-583 entry is also BACK (2026-05-25),
# re-added after JLCPCB's Confirm-Parts-Placement review of the v0.51
# order asked for orientation confirmation on U2 — see the U2 entry's
# rationale below.
#
# The SK6812-SIDE entry is kept at 0 deg deliberately (see the entry's
# own comment block): the boardgen (90 - theta) LED placement formula
# already carries the 180 deg tape-feeder compensation, so no extra
# pos.csv offset is needed. A stale +180 here — left over from the
# older (270 - theta) placement — double-compensated and put the AQI
# ring 180 deg off (emission inward, "pin outer edge") on JLCPCB DFM.
JLCPCB_ROTATIONS_OAS: list[tuple[re.Pattern, float, float, float, str]] = [
    # D11..D18 SK6812-SIDE (oas:SK6812-SIDE custom footprint).
    # Rotation 0 deg — and that is DELIBERATE. Do NOT re-add +180.
    #
    # A +180 entry lived here while the boardgen LED placement used the
    # (270 - theta) formula. v0.41 (2026-05-19) changed that formula to
    # (90 - theta) so the KiCad 3D render shows the ring emitting
    # radially OUTWARD. (90 - theta) already differs from (270 - theta)
    # by 180 deg, so the placement now bakes in the tape-feeder
    # compensation. The +180 left here on top of it double-compensated:
    # JLCPCB DFM then rendered the ring emitting INWARD and flagged
    # "pin outer edge" (the asymmetric land 180 deg off its pins).
    # Rotation 0 makes the CPL rotation == boardgen placement == the
    # KiCad 3D render: emission outward, pins on pads.
    (
        re.compile(r"^SK6812-SIDE$"),
        0, 0.0, 0.0,
        "SK6812-SIDE: 0 deg by design — the (90 - theta) boardgen placement already carries the 180 deg tape-feeder compensation; an extra +180 double-compensates (JLCPCB DFM: emission inward + pin-outer-edge).",
    ),
    # U1 — LM2596S-5.0 in oas:TO-263-5_LM2596 (project-local land — the
    # verbatim LCSC C116713 / EasyEDA geometry; see CLAUDE.md Deviation
    # budget and gen_to263_5_lm2596_footprint).
    #
    # v0.43 replaced the KiCad stock TO-263-5_TabPin3 land here: its
    # 9.15 mm lead-tab pitch did not match the part's 10.252 mm, so no
    # CPL offset could seat both the leads and the tab — U1's thermal
    # tab stayed ~25 % overlapped on JLCPCB DFM ("Lead area overlapping
    # pad" Danger, jlcdfm.com 2026-05-21). With the matched land the
    # part now sits on a copy of its own footprint; only the
    # KiCad-vs-JLCPCB anchor + orientation difference is corrected here:
    #   * Rotation +180 — our land is drawn in KiCad orientation (leads
    #     on -X); the EasyEDA C116713 footprint has leads on +X.
    #   * Offset dx = -3.104 mm — our footprint anchor is the body
    #     centre (kept from the stock silk/courtyard/F.Fab donor);
    #     JLCPCB anchors the EasyEDA footprint at the lead/tab-pad
    #     midpoint, which in our land sits at footprint-local
    #     X = (-8.230 + 2.022)/2 = -3.104 mm. dy = 0 (leads Y-centred).
    # No land-geometry residual remains — the footprint now equals the
    # part's own land.
    (
        re.compile(r"^TO-263-5_LM2596"),
        180, -3.104, 0.0,
        "U1 oas:TO-263-5_LM2596: project-local land = verbatim LCSC C116713 geometry. +180 (KiCad-vs-EasyEDA orientation) and dx=-3.104 mm (body-centre anchor vs lead/tab-pad midpoint). v0.43 — replaced the mismatched KiCad stock TO-263 land that tripped JLCPCB DFM lead/pad overlap.",
    ),
    # U2 — TPS62933DRLR sync buck in SOT-583 (KiCad stock
    # Package_TO_SOT_SMD:SOT-583-8). Local renders (2D / 3D / preflight)
    # stay at the KiCad-natural 0 deg — pin 1 (RT) upper-left, matching
    # TI SLUSEA4D Rev D Figure 7-1 top-view. The CPL applies +180 so
    # JLCPCB's tape-feeder orientation for C3200405 lines up with the
    # KiCad pad geometry.
    #
    # Trigger: JLCPCB Confirm-Parts-Placement review of the v0.51 order
    # (2026-05-25) flagged U2 with a render rotated 180 deg from our
    # natural KiCad view and asked the customer to confirm. The render
    # we sent back (KiCad-natural pin-1 upper-left) was accepted, but
    # the round-trip indicates JLCPCB's tape feeder for this LCSC# is
    # 180 deg off the KiCad footprint orientation — exactly what this
    # table is for. Baking +180 in here so the next CPL upload matches
    # JLCPCB's expected tape orientation without a manual question.
    (
        re.compile(r"^SOT-583-8$"),
        180, 0.0, 0.0,
        "U2 SOT-583-8 (TPS62933 / C3200405): +180 — JLCPCB Confirm-Parts-Placement review of v0.51 order (2026-05-25) showed U2 rotated 180 deg from KiCad natural; tape-feeder orientation for this LCSC# is 180 off the footprint. Local renders stay at 0 deg (KiCad ground truth, pin 1 RT upper-left per TI SLUSEA4D Fig 7-1); CPL applies +180.",
    ),
    # Q1 — AO3401A P-MOSFET, SOT-23 (KiCad stock Package_TO_SOT_SMD:SOT-23).
    # The upstream `^SOT-23,-90` row is dropped via JLCPCB_UPSTREAM_SKIP
    # (see that dict) because it placed Q1 90 deg off on JLCPCB DFM. This
    # gap-filler supplies the correct correction. The EasyEDA footprint of
    # LCSC C15127 (the exact ordered part) is the KiCad-stock SOT-23
    # rotated EXACTLY 180 deg — its pads sit at footprint-local
    # (+1.15,+/-0.95) / (-1.15,0) vs KiCad's (-0.9375,-/+0.95) /
    # (+0.9375,0). Both footprints anchor the origin at the geometric
    # centre of the three pads, so a pure +180 rotation aligns the part —
    # no X/Y offset (unlike the asymmetric TO-263 above). Q1 was observed
    # 90 deg off (CPL rotation 270, 2/3 pins off pads, "Pin without pad"
    # Danger x2) on JLCPCB DFM (jlcdfm.com, v0.43 board, 2026-05-21);
    # +180 is derived from the EasyEDA pad geometry above.
    (
        re.compile(r"^SOT-23$"),
        180, 0.0, 0.0,
        "Q1 SOT-23: upstream -90 dropped (JLCPCB_UPSTREAM_SKIP) — EasyEDA C15127 footprint is the KiCad-stock SOT-23 rotated 180 deg, both origins centred, so a pure +180 (no offset) aligns it. Upstream -90 left Q1 90 deg off on JLCPCB DFM (2026-05-21).",
    ),
]


# ---------------------------------------------------------------------------
# Upstream rows DROPPED at load time — exceptions, not overrides.
# ---------------------------------------------------------------------------
# When an upstream cpl_rotations_db.csv row is provably WRONG for the exact
# footprint OAS ships (confirmed on JLCPCB DFM), the cheapest correct fix
# is to simply NOT load that row: the footprint then matches no rule and
# keeps its KiCad ground-truth rotation. This needs no extra precedence
# tier — every other SMD part is unaffected and the corrections list is
# one entry SHORTER, not longer.
#
# Key = the EXACT pattern string from the CSV's first column.
# _parse_upstream_csv() hard-fails if a key here no longer matches any CSV
# row (the pinned submodule changed → the skip must be re-validated).
JLCPCB_UPSTREAM_SKIP: dict[str, str] = {
    # J3 — JST GH SM06B-GHS-TB 6-pin horizontal SMD socket (SEN66 cable).
    # Upstream `^JST_GH_SM,180`: with J3_ROTATION=0 in oas.kicad_pcb that
    # gives CPL rotation 180, and JLCPCB DFM (jlcdfm.com, v0.43 board,
    # 2026-05-21) renders J3 180 deg off the KiCad placement — its 6 pins
    # + 2 mounting tabs land off the copper ("Pin without pad" Danger x8).
    # The KiCad-stock JST_GH_SM06B-GHS-TB footprint's 0 deg already
    # matches JLCPCB's tape-feeder 0 deg (the upstream +180 was calibrated
    # against an older footprint orientation). Dropping the row leaves J3
    # unmatched → CPL rotation == KiCad ground truth, which the local
    # render verifies as the correct physical orientation.
    "^JST_GH_SM": "J3 JST_GH_SM06B-GHS-TB: upstream +180 verified wrong on JLCPCB DFM (2026-05-21) — J3 rendered 180 deg off, pins off pads; KiCad-stock 0 deg already matches the tape feeder.",
    # Q1 — AO3401A P-MOSFET in SOT-23 (KiCad stock Package_TO_SOT_SMD:SOT-23).
    # Upstream `^SOT-23,-90`: with Q1's KiCad placement rotation 0 that
    # gives CPL rotation 270, and JLCPCB DFM (jlcdfm.com, v0.43 board,
    # 2026-05-21) renders Q1 90 deg off — 2 of its 3 pins land off the
    # copper ("Pin without pad" Danger x2). The EasyEDA footprint of LCSC
    # C15127 (the exact ordered AO3401A) is the KiCad-stock SOT-23 rotated
    # exactly 180 deg (pads at local (+1.15,+/-0.95) / (-1.15,0) vs
    # KiCad's (-0.9375,-/+0.95) / (+0.9375,0); both origins centred), so
    # the correct CPL rotation is +180, NOT -90. Dropping this row leaves
    # SOT-23 unmatched by upstream → the OAS gap-filler entry above
    # applies the +180. (Skip alone would give 0 deg, also wrong — Q1
    # genuinely needs +180, not the KiCad ground-truth rotation.)
    "^SOT-23": "Q1 SOT-23: upstream -90 verified wrong on JLCPCB DFM (2026-05-21) — Q1 rendered 90 deg off, 2/3 pins off pads. EasyEDA C15127 footprint is the KiCad-stock SOT-23 rotated 180 deg; the OAS gap-filler entry applies +180 instead.",
}


def _parse_upstream_csv() -> list[tuple[re.Pattern, float, float, float, str]]:
    """Parse JLCKicadTools cpl_rotations_db.csv from the pinned submodule.

    Schema per row: `<regex>,<rotation>[,<offset_x>,<offset_y>]`. Header
    row skipped. Rows whose pattern is in JLCPCB_UPSTREAM_SKIP are
    dropped. Returns (compiled_regex, rotation_deg, dx_mm, dy_mm,
    source_tag) tuples. Hard FAIL if the submodule is not initialized,
    or if a skip key no longer matches any CSV row (the pinned file
    changed — re-validate).
    """
    if not UPSTREAM_CSV.exists():
        sys.exit(
            "[FAIL] rotation correction CSV missing at "
            f"{UPSTREAM_CSV.relative_to(KICAD_ROOT.parent)} — "
            "run: git submodule update --init --recursive"
        )
    out: list[tuple[re.Pattern, float, float, float, str]] = []
    seen_skips: set[str] = set()
    with UPSTREAM_CSV.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            pattern = row[0].strip().strip('"')
            if pattern in JLCPCB_UPSTREAM_SKIP:
                seen_skips.add(pattern)          # dropped — see the dict
                continue
            try:
                rotation = float(row[1])
            except ValueError:
                continue
            # CSV columns 3-4 (Offset X, Offset Y) are optional
            dx = float(row[2]) if len(row) > 2 and row[2].strip() else 0.0
            dy = float(row[3]) if len(row) > 3 and row[3].strip() else 0.0
            out.append((re.compile(pattern), rotation, dx, dy, "upstream"))
    stale = set(JLCPCB_UPSTREAM_SKIP) - seen_skips
    if stale:
        sys.exit(
            f"[FAIL] JLCPCB_UPSTREAM_SKIP keys not found in {UPSTREAM_CSV.name}: "
            f"{sorted(stale)} — the pinned cpl_rotations_db.csv changed; "
            "re-validate each skip against the new file."
        )
    return out


def load_combined() -> list[tuple[re.Pattern, float, float, float, str]]:
    """Return upstream entries + OAS-specific entries as one list.

    Order matters: upstream FIRST, OAS SECOND. Stage 30 takes the first
    regex match per footprint, so OAS entries only fire when upstream
    doesn't match — gap-filler semantics, not override. Upstream rows
    listed in JLCPCB_UPSTREAM_SKIP are already dropped by the parser.
    """
    upstream = _parse_upstream_csv()
    oas = [
        (rx, rot, dx, dy, f"oas: {rationale}")
        for (rx, rot, dx, dy, rationale) in JLCPCB_ROTATIONS_OAS
    ]
    return upstream + oas


def stats() -> tuple[int, int]:
    """Return (n_upstream, n_oas_specific) for stage 30 banner."""
    return len(_parse_upstream_csv()), len(JLCPCB_ROTATIONS_OAS)
