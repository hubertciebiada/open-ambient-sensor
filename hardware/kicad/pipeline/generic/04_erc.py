"""Stage 04/11: schematic ERC (kicad-cli sch erc strict).

v0.24 fix (review iteration 2 Mj2): make ERC strict on warnings.
`--severity-warning` includes warning-level violations in the report;
`--exit-code-violations` makes kicad-cli return non-zero when any
violation (error OR warning) exists. Without both flags, the v0.23
Mn3 regression (15 `footprint_link_issues` warnings) silently passed
CI because the subprocess returned 0. Every ERC issue now aborts the
regenerate run.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, run, find_kicad_cli, RENDERS  # noqa: E402
from _project import SCH_PATH  # noqa: E402

STAGE_NAME = "erc"


def main() -> int:
    with Stage(STAGE_NAME) as st:
        kcli = find_kicad_cli()
        RENDERS.mkdir(exist_ok=True)
        erc_report = RENDERS / "_erc.rpt"

        st.info("kicad-cli sch erc --severity-error --severity-warning --exit-code-violations")
        run([
            kcli, "sch", "erc",
            "--output", str(erc_report),
            "--severity-error", "--severity-warning",
            "--exit-code-violations",
            str(SCH_PATH),
        ])
        st.ok(f"clean — see {erc_report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
