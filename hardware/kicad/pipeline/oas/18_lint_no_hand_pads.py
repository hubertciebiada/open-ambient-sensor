"""Stage 18: forbid hand-coded pad geometry in footprint generators.

Lesson 1 (CLAUDE.md): every `gen_*_pcb_footprint` must delegate to
`_emit_stock_lib_footprint(src_path=…, lib_nickname=…)` so the placed
footprint is verbatim parse-and-emit from a KiCad stock library entry —
never hand-coded `(at X Y)` pad coordinates with size guesses. Root
cause of the v0.40 JLCPCB rejection (U1 TO-263-5 land pattern rotated
90° + miniaturized) AND the ~24 SMD passive deviations caught later.

This stage AST-parses every boardgen/*.py, finds every
`gen_*_pcb_footprint` function, and asserts that its body contains a
call to `_emit_stock_lib_footprint`. The only exceptions are project-
local OAS custom footprints documented in the CLAUDE.md "Deviation
budget" — those legitimately do NOT have a stock-library origin (they
ARE the origin).

Whitelist criteria: function name must match an entry in
`WHITELIST_FUNCTIONS` AND there must be a clear domain justification.
Adding new entries here without a CLAUDE.md "Deviation budget" update
is the same anti-pattern this stage is meant to prevent.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, KICAD_ROOT  # noqa: E402

STAGE_NAME = "lint_no_hand_pads"

BOARDGEN = KICAD_ROOT / "boardgen"

# Functions excluded from the "must delegate to _emit_stock_lib_footprint"
# rule. Every entry MUST correspond to an OAS custom footprint listed in
# CLAUDE.md "Deviation budget". Order matches the table there.
WHITELIST_FUNCTIONS = {
    # MOD1 / LDR1 / SENS1 mechanical references (oas:*_Reference)
    "gen_sen66_reference_pcb_footprint",
    "gen_ld2410_reference_pcb_footprint",
    "gen_esp32_devkit_reference_pcb_footprint",
    # H1..H3 (oas:MountingHole_3.8mm_M3)
    "gen_mounting_hole_pcb_footprint",
    # ZT1..ZT4 (oas:ZipTieHole_3mm_NPTH)
    "gen_zip_tie_hole_pcb_footprint",
    # D11..D22 (oas:SK6812-SIDE) — 4020 side-emit LED, datasheet pinout
    # differs from KiCad's PLCC4 5050. CLAUDE.md Deviation budget #4.
    "gen_sk6812_side_pcb_footprint",
    # F1 (oas:Fuse_1812L_4532Metric) — Littelfuse 1812L-series PTC fuse
    # land. KiCad stock Fuse_1812_4532Metric is a generic IPC chip-fuse
    # land that mismatched the 1812L termination geometry (JLCPCB DFM
    # "pin inner edge"). CLAUDE.md Deviation budget.
    "gen_fuse_1812l_pcb_footprint",
    # OAS-version-line silk text emitter (no pads).
    "gen_oas_version_silk_pcb_footprint",
    # Dead-code helper kept for historical reference (no caller — audit-16
    # replaced every caller with _emit_stock_lib_footprint). Flagged here
    # to remind future agents NOT to revive it without the canonical
    # parse-and-emit pattern.
    "_emit_two_pad_smd_footprint",
}


def _function_uses_stock_emit(func: ast.FunctionDef) -> bool:
    """Return True if the function body sources its pad geometry from a
    KiCad stock library entry.

    Three accepted patterns (all = verbatim parse-and-emit):
      1. Direct call to the canonical helper `_emit_stock_lib_footprint`.
      2. Reads from a `_*_LIB_FOOTPRINT_PATH` module-level Path constant
         (e.g. `_J3_LIB_FOOTPRINT_PATH.read_text(...)`).
      3. Reads from a `_*_lib_footprint_path(...)` helper that returns a
         Path (e.g. `_pinsocket_lib_footprint_path(pin_count).read_text()`
         — needed because the pinsocket source path varies by pin count).

    Hand-coded pad geometry (BAD) has NONE of these — pads are
    constructed from Python literals in the function body.
    """
    for node in ast.walk(func):
        # Any reference (Name or Attribute) to something whose identifier
        # contains 'lib_footprint_path' (case-insensitive) signals
        # source = stock library file. Covers patterns 2 and 3.
        ident: str | None = None
        if isinstance(node, ast.Name):
            ident = node.id
        elif isinstance(node, ast.Attribute):
            ident = node.attr
        if ident and "lib_footprint_path" in ident.lower():
            return True
        # Pattern 1: direct call to `_emit_stock_lib_footprint`.
        if isinstance(node, ast.Call):
            target = node.func
            call_name: str | None = None
            if isinstance(target, ast.Name):
                call_name = target.id
            elif isinstance(target, ast.Attribute):
                call_name = target.attr
            if call_name == "_emit_stock_lib_footprint":
                return True
    return False


def main() -> int:
    with Stage(STAGE_NAME) as st:
        if not BOARDGEN.exists():
            st.fail(f"{BOARDGEN} not found")

        offenders: list[tuple[str, str]] = []
        scanned = 0
        for py in sorted(BOARDGEN.glob("*.py")):
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                fn = node.name
                if not (fn.startswith("gen_") and fn.endswith("_pcb_footprint")):
                    continue
                scanned += 1
                if fn in WHITELIST_FUNCTIONS:
                    continue
                if not _function_uses_stock_emit(node):
                    offenders.append((str(py.relative_to(KICAD_ROOT)), fn))

        if offenders:
            for rel, fn in offenders:
                print(f"[FAIL] {rel}::{fn} — no _emit_stock_lib_footprint call (Lesson 1)")
            st.fail(
                f"{len(offenders)} hand-coded pad geometry violation(s) — "
                "delegate to _emit_stock_lib_footprint or document in CLAUDE.md Deviation budget"
            )

        st.ok(
            f"{scanned} gen_*_pcb_footprint function(s) scanned; "
            f"{len(WHITELIST_FUNCTIONS)} documented OAS customs whitelisted"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
