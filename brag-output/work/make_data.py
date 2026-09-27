"""Build data.js for the composition (board geometry + real build.py stage list)
and copy in the two repository images the page draws.

Tracks are grouped per net and chained so that each net "routes itself"
from one end, the way a router would draw it.
"""
import json
import math
import shutil
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
board = json.loads((HERE / "board.json").read_text())

# --- per-net chaining ------------------------------------------------------
nets = {}
for tr in board["tracks"]:
    nets.setdefault(tr["net"], []).append(tr)


def chain(segs):
    segs = [dict(s) for s in segs]
    out = []
    # start at the segment end with the smallest x (left-most point)
    start = min(segs, key=lambda s: min(s["a"][0], s["b"][0]))
    if start["b"][0] < start["a"][0]:
        start["a"], start["b"] = start["b"], start["a"]
    segs.remove(start)
    out.append(start)
    cur = start["b"]
    while segs:
        best, flip, bd = None, False, 1e9
        for s in segs:
            da = math.dist(cur, s["a"])
            db = math.dist(cur, s["b"])
            if da < bd:
                best, flip, bd = s, False, da
            if db < bd:
                best, flip, bd = s, True, db
        if flip:
            best["a"], best["b"] = best["b"], best["a"]
        segs.remove(best)
        out.append(best)
        cur = best["b"]
    return out


ordered = []
for name, segs in nets.items():
    ch = chain(segs)
    cx = sum((s["a"][0] + s["b"][0]) / 2 for s in ch) / len(ch)
    ordered.append({"net": name, "cx": cx, "segs": [{"a": s["a"], "b": s["b"], "w": s["w"], "l": s["layer"][0]} for s in ch]})
ordered.sort(key=lambda n: n["cx"])

# --- vias: attach to the segment of the same net that touches them ----------
for v in board["vias"]:
    v["net_i"], v["seg_i"] = -1, -1
    for ni, n in enumerate(ordered):
        if n["net"] != v["net"]:
            continue
        for si, s in enumerate(n["segs"]):
            if math.dist(s["a"], v["at"]) < 0.05 or math.dist(s["b"], v["at"]) < 0.05:
                v["net_i"], v["seg_i"] = ni, si
                break

# --- stage names, straight from the pipeline directories --------------------
stages = []
for sub in ("generic", "oas", "jlcpcb"):
    for p in (ROOT / "hardware" / "kicad" / "pipeline" / sub).glob("[0-9][0-9]_*.py"):
        num, name = p.stem.split("_", 1)
        stages.append((int(num), name))
stages.sort()
assert len(stages) == 35, len(stages)

data = {
    "outline": board["outline"],
    "footprints": board["footprints"],
    "nets": ordered,
    "vias": board["vias"],
    "stages": [[f"{n:02d}", name] for n, name in stages],
}
(HERE / "data.js").write_text("window.DATA=" + json.dumps(data, separators=(",", ":")) + ";\n")

# the two real images the page draws (served from this folder)
shutil.copyfile(ROOT / "hardware" / "photos" / "v0.54-mounted-led-ring.jpg", HERE / "photo-ring.jpg")
shutil.copyfile(ROOT / "hardware" / "renders" / "pcb" / "3d-top.png", HERE / "render-top.png")
print("nets", len(ordered), "vias attached", sum(1 for v in board["vias"] if v["seg_i"] >= 0), "/", len(board["vias"]), "stages", len(stages))
print(stages[:3], stages[-3:])
