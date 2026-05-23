"""Stage 17: structural lint on oas.kicad_pro.

Codifies CLAUDE.md Lesson 3 ("NO `rule_severities` suppression — fix the
cause, never paper over the warning") as a hard pipeline gate. The
previous incarnation of this guarantee was a written convention; now
it's a check that fails the build if anyone (human or AI agent) drops
an entry into either `rule_severities` dict to silence a real DRC / ERC
violation.

Checks:
  1. `board.design_settings.rule_severities` MUST be the empty dict `{}`.
  2. `erc.rule_severities` MUST be the empty dict `{}`.

Both dicts are reachable via boardgen/_project_files.py::gen_pro(). The
audit-16 sweep set them empty after removing the Q1 `lib_footprint_
mismatch` workaround; this stage holds the line.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT  # noqa: E402

STAGE_NAME = "lint_kicad_pro"

KICAD_PRO_PATH = KICAD_ROOT / "oas.kicad_pro"


def main() -> int:
    with Stage(STAGE_NAME) as st:
        if not KICAD_PRO_PATH.exists():
            st.fail(f"{KICAD_PRO_PATH} not found — run build.py first")

        # kicad-cli stages run earlier in build.py (pcb export svg, etc.)
        # re-save oas.kicad_pro with KiCad's *default* rule_severities
        # populated — not user-authored suppressions, just defaults. That
        # would trip this lint as a false positive. boardgen's gen_pro()
        # is the source of truth for the project file (always emits empty
        # rule_severities); re-emit it here so the check sees the
        # canonical state, not whatever kicad-cli last left behind.
        sys.path.insert(0, str(KICAD_ROOT))
        from boardgen._project_files import gen_pro  # noqa: E402
        KICAD_PRO_PATH.write_text(gen_pro(), encoding="utf-8")

        data = json.loads(KICAD_PRO_PATH.read_text(encoding="utf-8"))

        board_sev = (
            data.get("board", {})
                .get("design_settings", {})
                .get("rule_severities", {})
        )
        erc_sev = data.get("erc", {}).get("rule_severities", {})

        offenders: list[str] = []
        if board_sev != {}:
            offenders.append(
                f"board.design_settings.rule_severities = {board_sev!r} "
                "(must be empty — Lesson 3, no DRC suppression)"
            )
        if erc_sev != {}:
            offenders.append(
                f"erc.rule_severities = {erc_sev!r} "
                "(must be empty — Lesson 3, no ERC suppression)"
            )

        if offenders:
            for line in offenders:
                print(f"[FAIL] {line}")
            st.fail(
                "rule_severities suppression detected — "
                "fix the underlying violation, do not silence the warning"
            )

        st.ok("rule_severities empty in both board.design_settings and erc")
    return 0


if __name__ == "__main__":
    sys.exit(main())
