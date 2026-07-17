"""Stage 03/11: PCB DRC (kicad-cli pcb drc strict).

v0.28: `--refill-zones` makes DRC fill zones before checking connectivity.
Without this, GND pads inside the F.Cu / B.Cu GND pour would still appear
as "unconnected_items" because the connectivity check looks only at routed
tracks + filled zone polygons. We deliberately DO NOT pass `--save-board`:
KiCad's save would (a) re-write the PCB file in its compact native format
losing the (net N "name") integer codes that boardgen emits, and
(b) inject fresh random UUIDs on every save, breaking the determinism
guarantee.

v0.28e: split DRC enforcement into "real rule violations" vs "unconnected
pads". `--exit-code-violations` counts both the same, but they mean
different things:
  - Real violations (clearance, edge, thermal, shorts) = design bugs;
    MUST abort.
  - Unconnected pads = routing work-in-progress; SHOULD warn loudly but
    NOT abort.
Approach: run DRC WITHOUT --exit-code-violations, parse the report,
abort only on the "Found N DRC violations" count.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, run, find_kicad_cli, RENDERS  # noqa: E402
from _project import PCB_PATH  # noqa: E402

STAGE_NAME = "drc"


def main() -> int:
    with Stage(STAGE_NAME) as st:
        kcli = find_kicad_cli()
        RENDERS.mkdir(exist_ok=True)
        drc_report = RENDERS / "_drc.rpt"

        st.info("kicad-cli pcb drc --severity-error --severity-warning --refill-zones")
        run([
            kcli, "pcb", "drc",
            "--output", str(drc_report),
            "--severity-error", "--severity-warning",
            "--refill-zones",
            str(PCB_PATH),
        ])

        drc_text = drc_report.read_text(encoding="utf-8", errors="replace")
        m_viol = re.search(r"Found (\d+) DRC violations", drc_text)
        m_unc = re.search(r"Found (\d+) unconnected pads", drc_text)
        n_viol = int(m_viol.group(1)) if m_viol else 0
        n_unc = int(m_unc.group(1)) if m_unc else 0

        if n_viol > 0:
            st.fail(f"{n_viol} DRC violation(s) — see {drc_report}")
        st.ok(f"{n_viol} violations")

        # Unconnected-pad baseline.
        #
        # TEMPORARY (GitHub issue #8): signal routing is DELIBERATELY absent
        # while the placement tasks (issue #2 SEN66 recess cutout, etc.) land.
        # ROUTING_CHUNKS = ("gnd",) in boardgen/_routing.py emits GND pours
        # only, so every non-GND pad legitimately reads as unconnected. This
        # count is the exact pours-only baseline measured against the current
        # placement; a DIFFERENT value is a real regression (a pad moved,
        # appeared, or vanished unexpectedly). When issue #8 re-routes the
        # board to full coverage this MUST return to 0 — any non-zero value
        # is then a routing regression. DRC *violations* stay hard-zero
        # throughout (the GND pours clip cleanly around the new cutout).
        EXPECTED_UNCONNECTED = 83
        if n_unc != EXPECTED_UNCONNECTED:
            st.fail(
                f"{n_unc} unconnected pads — expected exactly "
                f"{EXPECTED_UNCONNECTED} (pours-only baseline pending the "
                f"issue #8 re-route). A different count means a pad moved / "
                f"appeared / vanished — see {drc_report}."
            )
        st.ok(f"{n_unc} unconnected pads — pours-only baseline (issue #8)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
