"""Generic helpers for a KiCad build pipeline.

This module contains ONLY project-agnostic helpers: subprocess wrapper,
kicad-cli locator, SHA-256 hash, the Stage context manager. NO OAS-
specific paths or lists — those live in `_project.py`. Together with
`pipeline/generic/`, this file is portable to any KiCad project that
provides a matching `_project.py`.

Stages under `pipeline/<subdir>/NN_<name>.py` import from this module via:

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from _common import Stage, run, find_kicad_cli, ...

The numeric-prefix filenames cannot be `import`-ed directly, so each
stage runs as its own subprocess (the orchestrator in `build.py`
invokes them via `subprocess.run`) and `_common` is loaded via the
sys.path trick.

Format contract (consumed by `build.py`):
  - Every stage prints `=== STAGE NN: name ===` on entry.
  - Every stage emits `[INFO] ...`, `[OK] ...`, `[WARN] ...`, `[FAIL] ...`
    log lines (uniform 4-char tag column with a 3-space pad after `OK`).
  - On clean exit a stage prints `[OK]   stage passed in X.Xs` and returns 0.
  - On failure a stage prints `[FAIL] <reason>` and returns 1.

The orchestrator parses nothing from stdout; it relies purely on the
subprocess return code. The structured log format is for humans reading
the terminal and for LLMs grepping logs after the fact.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Paths ---------------------------------------------------------------------
HERE = Path(__file__).parent              # hardware/kicad/pipeline
KICAD_ROOT = HERE.parent                  # hardware/kicad
RENDERS = KICAD_ROOT.parent / "renders"   # hardware/renders/ (sibling of kicad/)

# kicad-cli locator ---------------------------------------------------------
KICAD_CLI_CANDIDATES = [
    r"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe",
    r"C:/Program Files/KiCad/9.0/bin/kicad-cli.exe",
    "kicad-cli",
]


def find_kicad_cli() -> str:
    for c in KICAD_CLI_CANDIDATES:
        if Path(c).exists() or shutil.which(c):
            return c
    sys.exit("ERROR: kicad-cli not found. Install KiCad 10 or add it to PATH.")


# Subprocess wrapper --------------------------------------------------------
def run(cmd: list[str], *, hide_output: bool = False) -> None:
    """Run a subprocess, abort on non-zero exit. Decodes output as UTF-8
    with replacement so kicad-cli localized messages (e.g. Polish on
    Windows) don't break the script."""
    if hide_output:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr, file=sys.stderr)
            sys.exit(f"command failed: {' '.join(cmd)}")
    else:
        subprocess.run(cmd, check=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Silkscreen-to-pad strip ---------------------------------------------------
def strip_silk_near_pads(pcb_path: Path, min_clearance: float = 0.15) -> int:
    """Drop every footprint-internal F/B.SilkS `fp_line` / `fp_rect` whose
    nearest edge sits closer than `min_clearance` mm to one of that
    footprint's own pads, rewriting `pcb_path` in place. Returns the
    count of silk elements removed.

    JLCPCB (and most fabs) flag silkscreen within ~0.15 mm of a pad in
    DFM; stock KiCad library footprints routinely draw component body
    outlines ~0.10 mm off the pads. KiCad's own DRC trusts footprint-
    internal silk and never flags it — and editing a placed footprint in
    the committed project PCB would trip `lib_footprint_mismatch`. So
    callers run this on a throwaway gerber-export copy, never on the
    committed PCB.

    Scope is limited to `fp_line` / `fp_rect` (component body outlines):
    `fp_circle` (pin-1 dots) and `fp_poly` (polarity wedges) sit close to
    pads BY DESIGN and are left intact.

    Pure deterministic text processing: string-aware paren matching,
    source-ordered iteration."""
    text = pcb_path.read_text(encoding="utf-8")
    n = len(text)

    def block_end(i: int) -> int:
        """Index just past the ')' matching the '(' at `i` (string-aware)."""
        depth = 0
        in_str = False
        j = i
        while j < n:
            c = text[j]
            if in_str:
                if c == "\\":
                    j += 2
                    continue
                if c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return j + 1
            j += 1
        raise ValueError(f"unbalanced S-expression in {pcb_path}")

    def direct_children(start: int, end: int) -> list[tuple[str, int, int]]:
        """(keyword, child_start, child_end) for each direct child block."""
        out: list[tuple[str, int, int]] = []
        i = start + 1
        in_str = False
        while i < end - 1:
            c = text[i]
            if in_str:
                if c == "\\":
                    i += 2
                    continue
                if c == '"':
                    in_str = False
                i += 1
                continue
            if c == '"':
                in_str = True
                i += 1
                continue
            if c == "(":
                ce = block_end(i)
                kw = text[i + 1:ce].split(None, 1)[0]
                out.append((kw, i, ce))
                i = ce
                continue
            i += 1
        return out

    def pt_rect_dist(px: float, py: float, rx: float, ry: float,
                     rhw: float, rhh: float) -> float:
        dx = max(rx - rhw - px, 0.0, px - rx - rhw)
        dy = max(ry - rhh - py, 0.0, py - ry - rhh)
        return math.hypot(dx, dy)

    def seg_rect_dist(ax: float, ay: float, bx: float, by: float,
                      rx: float, ry: float, rhw: float, rhh: float) -> float:
        # Distance from a point sliding along the segment to an axis-
        # aligned rect is convex -> a 65-sample sweep finds the minimum
        # to within seg_len/64 (silk lines are short; ample resolution).
        best = float("inf")
        for k in range(65):
            t = k / 64.0
            d = pt_rect_dist(ax + (bx - ax) * t, ay + (by - ay) * t,
                             rx, ry, rhw, rhh)
            if d < best:
                best = d
        return best

    drops: list[tuple[int, int]] = []
    for fm in re.finditer(r"\(footprint ", text):
        fp_start = fm.start()
        fp_end = block_end(fp_start)
        kids = direct_children(fp_start, fp_end)

        pads: list[tuple[float, float, float, float]] = []
        for kw, cs, ce in kids:
            if kw != "pad":
                continue
            at = size = None
            for skw, scs, sce in direct_children(cs, ce):
                if skw == "at" and at is None:
                    at = text[scs:sce]
                elif skw == "size" and size is None:
                    size = text[scs:sce]
            if at is None or size is None:
                continue
            anums = re.findall(r"-?\d+\.?\d*", at)
            snums = re.findall(r"-?\d+\.?\d*", size)
            if len(anums) < 2 or len(snums) < 2:
                continue
            pads.append((float(anums[0]), float(anums[1]),
                         float(snums[0]) / 2.0, float(snums[1]) / 2.0))
        if not pads:
            continue

        for kw, cs, ce in kids:
            if kw not in ("fp_line", "fp_rect"):
                continue
            block = text[cs:ce]
            if '"F.SilkS"' not in block and '"B.SilkS"' not in block:
                continue
            ms = re.search(r"\(start\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\)", block)
            me = re.search(r"\(end\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\)", block)
            if not ms or not me:
                continue
            sx, sy = float(ms.group(1)), float(ms.group(2))
            ex, ey = float(me.group(1)), float(me.group(2))
            mw = re.search(r"\(width\s+(-?\d+\.?\d*)\)", block)
            half = float(mw.group(1)) / 2.0 if mw else 0.075
            if kw == "fp_line":
                segs = [(sx, sy, ex, ey)]
            else:  # fp_rect -> 4 edges
                segs = [(sx, sy, ex, sy), (ex, sy, ex, ey),
                        (ex, ey, sx, ey), (sx, ey, sx, sy)]
            worst = float("inf")
            for ax, ay, bx, by in segs:
                for px, py, phw, phh in pads:
                    d = seg_rect_dist(ax, ay, bx, by, px, py, phw, phh) - half
                    if d < worst:
                        worst = d
            if worst < min_clearance:
                ds = text.rfind("\n", 0, cs) + 1
                de = ce + 1 if ce < n and text[ce] == "\n" else ce
                drops.append((ds, de))

    if not drops:
        return 0
    drops.sort()
    out: list[str] = []
    cursor = 0
    for ds, de in drops:
        if ds < cursor:
            ds = cursor
        if de <= cursor:
            continue
        out.append(text[cursor:ds])
        cursor = de
    out.append(text[cursor:])
    pcb_path.write_text("".join(out), encoding="utf-8")
    return len(drops)


def strip_footprint_silk(pcb_path: Path, rules: dict) -> int:
    """Drop selected F/B.SilkS drawing elements from named footprints,
    rewriting `pcb_path` in place. Returns the count removed.

    `rules` maps a footprint-name substring to a spec:
      "all"        -> drop every F/B.SilkS fp_line / fp_rect / fp_poly /
                      fp_circle inside the footprint.
      ("x_ge", v)  -> drop every F/B.SilkS fp_line / fp_rect / fp_poly
                      whose every coordinate has footprint-local x >= v
                      (fp_circle is kept).

    Handles stock-library silk that `strip_silk_near_pads` cannot reach
    (it only strips body outlines WITHIN min_clearance of a pad):
      - SW1 C&K PTS645: the body-outline brackets only clutter the board
        and crowd the THT pads -> dropped outright ("all").
      - CP_Radial electrolytics: the polarity HATCH fill is hundreds of
        dense silk lines crowding the cathode pinhole. ("x_ge", v) drops
        the hatch (positive local x) while keeping the "+" mark (negative
        local x, clear of every pad) and the body circle.

    Runs on the throwaway gerber-export copy only — the committed PCB
    stays library-faithful (an in-place edit trips lib_footprint_mismatch).
    Pure deterministic text processing: string-aware paren matching,
    source-ordered iteration."""
    text = pcb_path.read_text(encoding="utf-8")
    n = len(text)

    def block_end(i: int) -> int:
        depth = 0
        in_str = False
        j = i
        while j < n:
            c = text[j]
            if in_str:
                if c == "\\":
                    j += 2
                    continue
                if c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return j + 1
            j += 1
        raise ValueError(f"unbalanced S-expression in {pcb_path}")

    drops: list[tuple[int, int]] = []
    for fm in re.finditer(r'\(footprint\s+"([^"]+)"', text):
        fp_name = fm.group(1)
        spec = None
        for sub, s in rules.items():
            if sub in fp_name:
                spec = s
                break
        if spec is None:
            continue
        fp_start = fm.start()
        fp_end = block_end(fp_start)
        for em in re.finditer(r"\((fp_line|fp_rect|fp_poly|fp_circle)(?=[\s(])",
                              text[fp_start:fp_end]):
            kind = em.group(1)
            es = fp_start + em.start()
            ee = block_end(es)
            block = text[es:ee]
            if '"F.SilkS"' not in block and '"B.SilkS"' not in block:
                continue
            if spec == "all":
                drop = True
            elif isinstance(spec, tuple) and spec[0] == "x_ge":
                if kind == "fp_circle":
                    continue
                xs = [float(x) for x in re.findall(
                    r"(?:start|end|xy)\s+(-?\d+\.?\d*)\s+-?\d+\.?\d*", block)]
                drop = bool(xs) and all(x >= spec[1] for x in xs)
            else:
                continue
            if drop:
                ds = text.rfind("\n", 0, es) + 1
                de = ee + 1 if ee < n and text[ee] == "\n" else ee
                drops.append((ds, de))

    if not drops:
        return 0
    drops.sort()
    out: list[str] = []
    cursor = 0
    for ds, de in drops:
        if ds < cursor:
            ds = cursor
        if de <= cursor:
            continue
        out.append(text[cursor:ds])
        cursor = de
    out.append(text[cursor:])
    pcb_path.write_text("".join(out), encoding="utf-8")
    return len(drops)


def expand_thru_hole_mask_margin(pcb_path: Path, margin: float = 0.05) -> int:
    """Add `(solder_mask_margin <margin>)` to every through-hole pad in
    `pcb_path` that does not already carry one, rewriting in place.
    Returns the count of pads modified.

    A 0 mm solder-mask expansion (KiCad default) makes the mask opening
    exactly equal the copper pad — JLCPCB DFM flags it "Negative
    soldermask expansion". Through-hole pads are generously spaced (no
    fine-pitch mask-sliver risk), so a small positive margin is always
    safe there; fine-pitch SMD pads are deliberately left untouched.

    Like `strip_silk_near_pads`, callers run this on a throwaway gerber-
    export copy so the committed PCB keeps the stock footprints verbatim
    (an in-place pad edit would trip KiCad's lib_footprint_mismatch).

    Pure deterministic text processing: depth-counted block extraction,
    source-ordered iteration."""
    text = pcb_path.read_text(encoding="utf-8")
    n = len(text)
    out: list[str] = []
    cursor = 0
    count = 0
    i = 0
    while True:
        k = text.find('(pad "', i)
        if k < 0:
            break
        depth = 0
        j = k
        while j < n:
            c = text[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = text[k:j]
        i = j
        if "thru_hole" not in block or "solder_mask_margin" in block:
            continue
        # Insert a new child line just before the block's closing ')'.
        close_line_start = text.rfind("\n", k, j) + 1
        close_indent = text[close_line_start:j - 1]  # whitespace before ')'
        ins = f"{close_indent}\t(solder_mask_margin {margin})\n"
        out.append(text[cursor:close_line_start])
        out.append(ins)
        cursor = close_line_start
        count += 1
    if not count:
        return 0
    out.append(text[cursor:])
    pcb_path.write_text("".join(out), encoding="utf-8")
    return count


# Stage reporter ------------------------------------------------------------
class Stage:
    """Context manager for a single pipeline stage.

    Prints the entry banner on `__enter__`, captures elapsed wall-clock
    time, prints `[OK] stage passed in X.Xs` on clean exit. On exception
    inside the `with` block, prints `[FAIL] <exc>` then re-raises so the
    sub-process exits non-zero.

    Position-in-pipeline (`NN/TT`) is picked up from the env vars
    `PIPELINE_IDX` and `PIPELINE_TOTAL` that the orchestrator
    (`build.py`) injects per subprocess call. When the stage script
    is run standalone for debug, those vars are unset and the banner
    omits the position counter.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.idx = os.environ.get("PIPELINE_IDX")
        # When the orchestrator already printed the banner, skip ours
        # to avoid the duplicate `=== STAGE NN: name ===` line.
        self._banner_already = os.environ.get("PIPELINE_BANNER_EMITTED") == "1"
        self._t0: float = 0.0

    def __enter__(self) -> "Stage":
        if not self._banner_already:
            if self.idx:
                print(f"\n=== STAGE {self.idx}: {self.name} ===")
            else:
                print(f"\n=== STAGE: {self.name} ===")
        self._t0 = time.time()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        elapsed = time.time() - self._t0
        if exc_type is None:
            print(f"[OK]   stage passed in {elapsed:.1f}s")
            return
        # Let SystemExit (from .fail()) propagate verbatim — it already
        # printed [FAIL]. Other exceptions get a generic FAIL line.
        if not isinstance(exc, SystemExit):
            print(f"[FAIL] {exc_type.__name__}: {exc}")
        # Never suppress; returning None (or any falsy) lets the
        # exception propagate as normal.

    @staticmethod
    def info(msg: str) -> None:
        print(f"[INFO] {msg}")

    @staticmethod
    def ok(msg: str) -> None:
        print(f"[OK]   {msg}")

    @staticmethod
    def warn(msg: str) -> None:
        print(f"[WARN] {msg}")

    @staticmethod
    def fail(msg: str) -> None:
        print(f"[FAIL] {msg}")
        sys.exit(1)
