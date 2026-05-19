"""boardgen stage 09: write oas.kicad_pro."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from boardgen._common import HERE
from boardgen._project_files import gen_pro


def run(ctx) -> None:
    (HERE / "oas.kicad_pro").write_text(gen_pro(), encoding="utf-8")


if __name__ == "__main__":
    from boardgen._common import Context
    run(Context())
