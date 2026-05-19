"""boardgen stage 08: write oas.kicad_sch (root sheet)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from boardgen._common import HERE
from boardgen._sch_root import gen_root_sch


def run(ctx) -> None:
    (HERE / "oas.kicad_sch").write_text(gen_root_sch(), encoding="utf-8")


if __name__ == "__main__":
    from boardgen._common import Context
    run(Context())
