"""boardgen stage 11: write libraries/OAS.kicad_sym."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from boardgen._common import HERE
from boardgen._project_files import gen_oas_symbol_library


def run(ctx) -> None:
    (HERE / "libraries").mkdir(parents=True, exist_ok=True)
    (HERE / "libraries" / "OAS.kicad_sym").write_text(
        gen_oas_symbol_library(), encoding="utf-8",
    )


if __name__ == "__main__":
    from boardgen._common import Context
    run(Context())
