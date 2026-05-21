"""
Extract every `(segment ...)` and `(via ...)` clause from oas.kicad_pcb and
serialize them as a Python data file (`oas_routes.py`) for boardgen to
reproduce bit-identically on every regeneration.

Use after a routing tool (Freerouting, KiCad's interactive router) has
written tracks into `oas.kicad_pcb`. Run once, then commit `oas_routes.py`
alongside the source-of-truth `boardgen/`.

The extracted records carry:
  - net_name (string) — looked up via _net_code() at apply-routing time
  - layer (segment) or layers tuple (via)
  - start / end / width (segment) or at / size / drill (via)
  - uuid_tag (e.g. "seg:0001") — deterministically maps to a v5 UUID via
    `uuid.uuid5(_OAS_NS, f"oas-track:<tag>")` in _RouteEmitter, so the
    file is bit-identical across regens.

NOTE: this script does NOT modify the source PCB. It only reads.

Usage:  python tools/extract_routes.py
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).parent.parent
PCB = HERE / "oas.kicad_pcb"
OUT = HERE / "oas_routes.py"

# A4 page-centre offset used by boardgen to convert between page and
# PCB-local coordinates. Kept here to convert PCB coordinates as written
# in oas.kicad_pcb (page-space) into the PCB-local frame that boardgen
# uses everywhere else.
PAGE_CENTRE_X = 148.5
PAGE_CENTRE_Y = 105.0


def _find_balanced_blocks(text: str, opener: str) -> list[str]:
    """Yield every balanced-parenthesis block beginning with `opener`.

    `opener` is a string like '(segment' or '(via' — the function locates
    each occurrence at a line start (any indentation) followed by a non-
    word boundary, then returns the substring through the matching `)`.

    Uses a simple depth counter that respects double-quoted strings (no
    parenthesis counts inside string literals).
    """
    blocks: list[str] = []
    # Match opener at any indent, requiring it to NOT be followed by an
    # identifier character (excludes substrings like `(via_dia` or
    # `(segment_locked`).
    pat = re.compile(r'^\s*' + re.escape(opener) + r'(?=\s|$)', re.MULTILINE)
    for m in pat.finditer(text):
        start = m.start() + (len(m.group(0)) - len(m.group(0).lstrip()))
        # `start` is the position of the opening '('.
        depth = 0
        in_str = False
        esc = False
        j = start
        while j < len(text):
            ch = text[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        blocks.append(text[start:j + 1])
                        break
            j += 1
    return blocks


_FLOAT = r'(-?\d+(?:\.\d+)?)'


def _f(s: str) -> float:
    return float(s)


def _parse_segment(block: str) -> dict | None:
    m_start = re.search(rf'\(start\s+{_FLOAT}\s+{_FLOAT}\s*\)', block)
    m_end = re.search(rf'\(end\s+{_FLOAT}\s+{_FLOAT}\s*\)', block)
    m_w = re.search(rf'\(width\s+{_FLOAT}\s*\)', block)
    m_layer = re.search(r'\(layer\s+"([^"]+)"\s*\)', block)
    m_net = re.search(r'\(net\s+(?:\d+\s+)?"([^"]*)"\s*\)', block)
    if not (m_start and m_end and m_w and m_layer and m_net):
        return None
    return {
        "net_name": m_net.group(1),
        "layer": m_layer.group(1),
        "start": (_f(m_start.group(1)) - PAGE_CENTRE_X,
                  _f(m_start.group(2)) - PAGE_CENTRE_Y),
        "end": (_f(m_end.group(1)) - PAGE_CENTRE_X,
                _f(m_end.group(2)) - PAGE_CENTRE_Y),
        "width": _f(m_w.group(1)),
    }


def _parse_via(block: str) -> dict | None:
    m_at = re.search(rf'\(at\s+{_FLOAT}\s+{_FLOAT}\s*\)', block)
    m_size = re.search(rf'\(size\s+{_FLOAT}\s*\)', block)
    m_drill = re.search(rf'\(drill\s+{_FLOAT}\s*\)', block)
    m_layers = re.search(r'\(layers\s+((?:"[^"]+"\s*)+)\)', block)
    m_net = re.search(r'\(net\s+(?:\d+\s+)?"([^"]*)"\s*\)', block)
    if not (m_at and m_size and m_drill and m_layers and m_net):
        return None
    layers = re.findall(r'"([^"]+)"', m_layers.group(1))
    return {
        "net_name": m_net.group(1),
        "at": (_f(m_at.group(1)) - PAGE_CENTRE_X,
               _f(m_at.group(2)) - PAGE_CENTRE_Y),
        "size": _f(m_size.group(1)),
        "drill": _f(m_drill.group(1)),
        "layers": tuple(layers),
    }


def _seg_sort_key(s: dict) -> tuple:
    return (
        s["net_name"],
        s["layer"],
        s["start"][0], s["start"][1],
        s["end"][0], s["end"][1],
        s["width"],
    )


def _via_sort_key(v: dict) -> tuple:
    return (
        v["net_name"],
        v["at"][0], v["at"][1],
        v["size"], v["drill"],
        ",".join(v["layers"]),
    )


def _fmt_float(x: float) -> str:
    """Float formatting that preserves up to 6 decimals (matches KiCad)."""
    return f"{x:.6f}".rstrip("0").rstrip(".") or "0"


def _fmt_tuple(t: tuple) -> str:
    return "(" + ", ".join(_fmt_float(v) for v in t) + ")"


def _emit_segment_repr(rec: dict, idx: int) -> str:
    return (
        "    {"
        f'"net_name": {rec["net_name"]!r}, '
        f'"layer": {rec["layer"]!r}, '
        f'"start": {_fmt_tuple(rec["start"])}, '
        f'"end": {_fmt_tuple(rec["end"])}, '
        f'"width": {_fmt_float(rec["width"])}, '
        f'"uuid_tag": "seg:{idx:04d}"'
        "},"
    )


def _emit_via_repr(rec: dict, idx: int) -> str:
    layers_repr = "(" + ", ".join(repr(l) for l in rec["layers"]) + ")"
    return (
        "    {"
        f'"net_name": {rec["net_name"]!r}, '
        f'"at": {_fmt_tuple(rec["at"])}, '
        f'"size": {_fmt_float(rec["size"])}, '
        f'"drill": {_fmt_float(rec["drill"])}, '
        f'"layers": {layers_repr}, '
        f'"uuid_tag": "via:{idx:04d}"'
        "},"
    )


def main() -> None:
    text = PCB.read_text(encoding="utf-8")
    seg_blocks = _find_balanced_blocks(text, "(segment")
    via_blocks = _find_balanced_blocks(text, "(via")

    # GND is realized as a copper pour plus a deterministic stitching-via
    # grid emitted by the boardgen "gnd" chunk (_route_gnd_pour /
    # _gnd_stitch_via_grid). It must NOT also be captured into the routing
    # snapshot, or the "autoroute" chunk would re-emit every GND grid via
    # on top of the "gnd" chunk's copy. Skip every GND segment/via here;
    # oas_routes.py carries only the non-GND signal routing.
    segments: list[dict] = []
    for b in seg_blocks:
        rec = _parse_segment(b)
        if rec is not None and rec["net_name"] != "GND":
            segments.append(rec)
    vias: list[dict] = []
    for b in via_blocks:
        rec = _parse_via(b)
        if rec is not None and rec["net_name"] != "GND":
            vias.append(rec)

    # Sort for determinism — net name, then geometry. Same net_name in
    # the same layer is grouped; per-net ordering does not affect the
    # board electrically, only the file-byte layout. Sorting gives a
    # stable diff between regenerations even if the routing tool emits
    # records in arbitrary order.
    segments.sort(key=_seg_sort_key)
    vias.sort(key=_via_sort_key)

    # Re-number uuid_tags AFTER the sort so they reflect the canonical
    # post-sort order. This means boardgen's UUIDs are tied to the
    # sorted index, not to the routing tool's emission order — which is
    # exactly what we want for deterministic regens.
    lines: list[str] = []
    lines.append('"""')
    lines.append("Routing data extracted from oas.kicad_pcb after autoroute.")
    lines.append("")
    lines.append("AUTO-GENERATED by tools/extract_routes.py. Re-generate when the")
    lines.append("routing tool has been re-run; do NOT hand-edit. The contents")
    lines.append("are loaded by boardgen's `_route_autoroute_tracks()` chunk.")
    lines.append("")
    lines.append(f"Source snapshot: {len(segments)} segments, {len(vias)} vias.")
    lines.append("")
    lines.append("Coordinates are PCB-local (origin = PCB centre); page-space")
    lines.append("conversion is applied automatically at emit time via fx()/fy().")
    lines.append('"""')
    lines.append("")
    lines.append("ROUTES_SEGMENTS = [")
    for i, rec in enumerate(segments):
        lines.append(_emit_segment_repr(rec, i))
    lines.append("]")
    lines.append("")
    lines.append("ROUTES_VIAS = [")
    for i, rec in enumerate(vias):
        lines.append(_emit_via_repr(rec, i))
    lines.append("]")
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Extracted {len(segments)} segments + {len(vias)} vias -> {OUT.name}")


if __name__ == "__main__":
    main()
