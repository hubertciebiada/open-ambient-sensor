"""boardgen stage 10: write fp-lib-table and sym-lib-table."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from boardgen._common import HERE
from boardgen._project_files import gen_fp_lib_table, gen_sym_lib_table


def run(ctx) -> None:
    (HERE / "fp-lib-table").write_text(gen_fp_lib_table(), encoding="utf-8")
    (HERE / "sym-lib-table").write_text(gen_sym_lib_table(), encoding="utf-8")


if __name__ == "__main__":
    from boardgen._common import Context
    run(Context())
