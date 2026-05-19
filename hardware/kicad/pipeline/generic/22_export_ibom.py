"""Stage 22: emit InteractiveHtmlBom (oas-ibom.html).

Human-review artefact: a self-contained HTML file with embedded JS that
shows the PCB top + bottom views with hover/click cross-reference into
the BOM. Click a part in the BOM → it highlights on the PCB; click a
footprint on the PCB → it scrolls the BOM to the matching row.

Primary use: JLCPCB Assembly Order XLS pre-payment cross-check
(Lesson 5). The XLS preview that JLCPCB downloads after part matching
needs human eyes to verify each row's part description vs the project's
intent — `oas-ibom.html` shows the same data with visual context, so
mismatches like 'R3 30.9k vs 806 Ω' are easier to spot.

Vendor-neutral: output lands at `hardware/output/oas-ibom.html` (NOT
inside any per-vendor folder). Every assembler can use the same HTML
regardless of fab choice.

Loads the iBom CLI from `third_party/InteractiveHtmlBom` (submodule).
The CLI requires the `pcbnew` Python module that ships only with the
KiCad-bundled python.exe — locate it under `C:/Program Files/KiCad/*/
bin/python.exe`. Hard-fails if either the submodule or the KiCad-
bundled python is missing — the harness must produce the iBom
artefact on every successful build, not silently omit it.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT  # noqa: E402
from _project import PCB_PATH, OUTPUT_ROOT  # noqa: E402

STAGE_NAME = "export_ibom"

IBOM_SRC_DIR = KICAD_ROOT / "third_party" / "InteractiveHtmlBom"
IBOM_GENERATOR = IBOM_SRC_DIR / "InteractiveHtmlBom" / "generate_interactive_bom.py"
IBOM_OUTPUT_FILE = OUTPUT_ROOT / "oas-ibom.html"

# iBom imports the `pcbnew` Python module, which is bundled only with
# KiCad's own Python interpreter (NOT the system Python). Locate the
# KiCad-shipped python.exe alongside the kicad-cli we already find via
# `find_kicad_cli`. Same install root, same major version.
KICAD_PYTHON_CANDIDATES = [
    Path(r"C:/Program Files/KiCad/10.0/bin/python.exe"),
    Path(r"C:/Program Files/KiCad/9.0/bin/python.exe"),
]


def _find_kicad_python() -> Path | None:
    for c in KICAD_PYTHON_CANDIDATES:
        if c.exists():
            return c
    return None


def main() -> int:
    with Stage(STAGE_NAME) as st:
        if not IBOM_GENERATOR.exists():
            st.fail(
                "InteractiveHtmlBom submodule not initialized — "
                "run `git submodule update --init --recursive`"
            )
        kicad_python = _find_kicad_python()
        if kicad_python is None:
            st.fail(
                "KiCad-bundled python.exe not found at any of "
                f"{[str(p) for p in KICAD_PYTHON_CANDIDATES]} — "
                "iBom needs the `pcbnew` module that ships only inside "
                "KiCad's own interpreter; install KiCad 10 or update the "
                "candidate list"
            )
        if not PCB_PATH.exists():
            st.fail(f"{PCB_PATH} not found — run build.py first")

        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

        # iBom interprets --dest-dir as relative to the PCB file's parent
        # directory. Use a relative path so the embedded reference inside
        # the HTML is portable across machines.
        try:
            dest_rel = OUTPUT_ROOT.relative_to(PCB_PATH.parent)
        except ValueError:
            dest_rel = OUTPUT_ROOT.resolve()

        env = {
            **os.environ,
            "INTERACTIVE_HTML_BOM_NO_DISPLAY": "1",
        }

        cmd = [
            str(kicad_python),
            str(IBOM_GENERATOR),
            str(PCB_PATH),
            "--no-browser",
            "--dest-dir", str(dest_rel),
            "--name-format", "oas-ibom",
        ]

        st.info(f"running iBom -> {IBOM_OUTPUT_FILE.relative_to(KICAD_ROOT.parent.parent)}")
        r = subprocess.run(
            cmd, env=env,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr, file=sys.stderr)
            st.fail("InteractiveHtmlBom generation failed")

        if not IBOM_OUTPUT_FILE.exists():
            st.fail(f"iBom returned 0 but {IBOM_OUTPUT_FILE} was not created")

        size_kb = IBOM_OUTPUT_FILE.stat().st_size // 1024
        st.ok(f"wrote {IBOM_OUTPUT_FILE.name} ({size_kb} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
