"""Extract the real OAS board geometry for the brag video.

Reads hardware/kicad/oas.kicad_pcb (Edge.Cuts outline, footprints, pads) and
hardware/kicad/oas_routes.py (tracks, vias) and writes board.json in
board-local millimetres (origin = PCB centre, +y down, as in KiCad).
"""
import importlib.util
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KICAD = ROOT / "hardware" / "kicad"
CX, CY = 148.5, 105.0  # page position of the PCB centre (boardgen fx/fy)


def tokenize(s):
    for m in re.finditer(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+', s):
        yield m.group(0)


def parse(s):
    stack, cur = [], []
    for tok in tokenize(s):
        if tok == "(":
            stack.append(cur)
            cur = []
        elif tok == ")":
            done = cur
            cur = stack.pop()
            cur.append(done)
        else:
            cur.append(tok[1:-1] if tok.startswith('"') else tok)
    return cur[0]


def find(node, key):
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def findall(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def xy(node):
    return float(node[1]) - CX, float(node[2]) - CY


def rot(dx, dy, deg):
    # KiCad: y down, positive angle = counter-clockwise on screen.
    a = math.radians(deg)
    return dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)


pcb = parse((KICAD / "oas.kicad_pcb").read_text())

outline = []
for kind in ("gr_line", "gr_arc", "gr_circle"):
    for g in findall(pcb, kind):
        layer = find(g, "layer")
        if not layer or layer[1] != "Edge.Cuts":
            continue
        if kind == "gr_line":
            outline.append({"t": "line", "a": xy(find(g, "start")), "b": xy(find(g, "end"))})
        elif kind == "gr_arc":
            outline.append({"t": "arc", "a": xy(find(g, "start")), "m": xy(find(g, "mid")), "b": xy(find(g, "end"))})
        else:
            c = xy(find(g, "center"))
            e = xy(find(g, "end"))
            outline.append({"t": "circle", "c": c, "r": math.dist(c, e)})

footprints = []
for fp in findall(pcb, "footprint"):
    at = find(fp, "at")
    fx, fy = float(at[1]) - CX, float(at[2]) - CY
    frot = float(at[3]) if len(at) > 3 else 0.0
    ref = next((p[2] for p in findall(fp, "property") if p[1] == "Reference"), "?")
    side = find(fp, "layer")[1]
    pads = []
    for p in findall(fp, "pad"):
        pat = find(p, "at")
        dx, dy = float(pat[1]), float(pat[2])
        prot = float(pat[3]) if len(pat) > 3 else frot
        ox, oy = rot(dx, dy, frot)
        size = find(p, "size")
        drill = find(p, "drill")
        dval = None
        if drill:
            nums = [x for x in drill[1:] if not isinstance(x, list) and re.match(r"^[\d.]+$", x)]
            dval = float(nums[0]) if nums else None
        pads.append({
            "n": p[1], "type": p[2], "shape": p[3],
            "x": round(fx + ox, 4), "y": round(fy + oy, 4), "rot": prot,
            "w": float(size[1]), "h": float(size[2]), "drill": dval,
        })
    fab = []
    if ref in ("SENS1", "LDR1", "MOD1"):
        def tp(node):
            ox, oy = rot(float(node[1]), float(node[2]), frot)
            return [round(fx + ox, 4), round(fy + oy, 4)]
        for g in fp:
            if not (isinstance(g, list) and g and g[0].startswith("fp_")):
                continue
            layer = find(g, "layer")
            if not layer or layer[1] != "F.Fab":
                continue
            if g[0] == "fp_line":
                fab.append({"t": "poly", "pts": [tp(find(g, "start")), tp(find(g, "end"))], "closed": False})
            elif g[0] == "fp_rect":
                s, e = find(g, "start"), find(g, "end")
                x0, y0, x1, y1 = float(s[1]), float(s[2]), float(e[1]), float(e[2])
                corners = [["", x0, y0], ["", x1, y0], ["", x1, y1], ["", x0, y1]]
                fab.append({"t": "poly", "pts": [tp(c) for c in corners], "closed": True})
            elif g[0] == "fp_poly":
                pts = find(g, "pts")
                fab.append({"t": "poly", "pts": [tp(c) for c in findall(pts, "xy")], "closed": True})
            elif g[0] == "fp_circle":
                c, e = find(g, "center"), find(g, "end")
                r = math.dist((float(c[1]), float(c[2])), (float(e[1]), float(e[2])))
                fab.append({"t": "circle", "c": tp(c), "r": round(r, 4)})
            elif g[0] == "fp_arc":
                fab.append({"t": "arc", "a": tp(find(g, "start")), "m": tp(find(g, "mid")), "b": tp(find(g, "end"))})
    footprints.append({"ref": ref, "lib": fp[1], "side": side, "x": round(fx, 4), "y": round(fy, 4), "rot": frot, "pads": pads, "fab": fab})

spec = importlib.util.spec_from_file_location("oas_routes", KICAD / "oas_routes.py")
routes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routes)
tracks = [{"net": s["net_name"], "layer": s["layer"], "a": s["start"], "b": s["end"], "w": s["width"]} for s in routes.ROUTES_SEGMENTS]
vias = [{"net": v["net_name"], "at": v["at"], "size": v["size"], "drill": v["drill"]} for v in routes.ROUTES_VIAS]

out = {"outline": outline, "footprints": footprints, "tracks": tracks, "vias": vias}
(Path(__file__).parent / "board.json").write_text(json.dumps(out))
print(f"outline {len(outline)}  footprints {len(footprints)}  pads {sum(len(f['pads']) for f in footprints)}  tracks {len(tracks)}  vias {len(vias)}")
for f in footprints:
    if f["ref"].startswith(("D1", "MOD", "SENS", "LDR", "J5", "J6", "H")):
        print(f["ref"], f["lib"], f["x"], f["y"], f["rot"], len(f["pads"]))
