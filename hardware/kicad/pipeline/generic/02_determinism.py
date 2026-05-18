"""Stage 02/11: determinism self-check (v0.23 review Nt2).

Snapshots every generated KiCad source file's SHA-256 hash, runs
`generate.py` a SECOND time, hashes again, and aborts on any drift.

All UUIDs in generate.py are deterministic v5 (namespaced under the
OAS project). Two consecutive runs MUST produce bit-identical sources.
If they don't, there's a real bug to fix (e.g. an accidental dependency
on Python's hash randomization or dict-iteration order) — flag loudly
rather than silently committing flapping diffs.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _common import Stage, run, KICAD_ROOT, sha256  # noqa: E402
from _project import GENERATE_SCRIPT, SOURCE_FILES_FIXED, SOURCE_FILES_GLOBS  # noqa: E402

STAGE_NAME = "determinism"


def collect_source_files() -> list[Path]:
    """Resolve _project.SOURCE_FILES_FIXED + SOURCE_FILES_GLOBS against
    KICAD_ROOT, returning existing files only."""
    files: list[Path] = [KICAD_ROOT / name for name in SOURCE_FILES_FIXED]
    for pattern in SOURCE_FILES_GLOBS:
        files.extend(sorted(KICAD_ROOT.glob(pattern)))
    return [p for p in files if p.exists()]


def main() -> int:
    with Stage(STAGE_NAME) as st:
        sources = collect_source_files()
        st.info(f"computing baseline hashes ({len(sources)} files)")
        pre_hashes: dict[Path, str] = {p: sha256(p) for p in sources}

        st.info(f"re-running {GENERATE_SCRIPT.name}")
        run([sys.executable, str(GENERATE_SCRIPT)])

        st.info("re-computing hashes")
        post_hashes: dict[Path, str] = {p: sha256(p) for p in collect_source_files()}

        drifted: list[Path] = []
        for p, post_h in post_hashes.items():
            pre_h = pre_hashes.get(p)
            if pre_h is None or pre_h != post_h:
                drifted.append(p)

        if drifted:
            for p in drifted:
                print(f"[FAIL] DRIFT: {p.relative_to(KICAD_ROOT)}")
            st.fail(f"{GENERATE_SCRIPT.name} is not deterministic — see drifted files above")

        st.ok(f"{len(post_hashes)}/{len(post_hashes)} hashes match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
