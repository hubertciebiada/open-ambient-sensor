"""boardgen/_postprocess.py — netlist sync, footprint backfill,
LCSC metadata injection, Z-clearance audit, sexp parsing helpers.

Functions here run AFTER `gen_pcb()` and the four per-sheet `gen_*_sch()`
generators have written their files. They:

  1. Parse the freshly-emitted `oas.kicad_pcb` for footprint ref -> footprint
     property mapping. Used to back-fill the schematic symbols' Footprint
     property so the schematic-driven netlist export matches the PCB.

  2. Build a (Value, Footprint) -> {Manufacturer, MPN, LCSC} map from
     `lcsc_mapping.py` and inject those properties on every matching
     schematic symbol — so the schematic-side BOM export carries supply-
     chain identification natively.

  3. Run a Z-clearance audit against `FOOTPRINT_HEIGHT` +
     `DAUGHTERBOARD_Z_CLEARANCE`: every component placed under a
     daughterboard body shadow must have a height <= that daughterboard's
     under-board clearance budget.

  4. Parse the schematic's netlist (via `kicad-cli sch export netlist`)
     and inject `(net code "name")` clauses into every PCB pad whose
     footprint reference + pad number matches a schematic node.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from boardgen._common import HERE
from boardgen._project import (
    PAGE_CENTRE_X, PAGE_CENTRE_Y,
    LD2410_ANCHOR_X, LD2410_ANCHOR_Y, LD2410_BODY_W, LD2410_BODY_H,
    LD2410_BODY_Z,
    ESP32_ANCHOR_X, ESP32_ANCHOR_Y, ESP32_BODY_W, ESP32_BODY_L,
    ESP32_ANTENNA_TAB_PROTRUSION,
)


def _parse_sexp_list(text: str, start: int) -> tuple[list, int]:
    """Tiny S-expression list parser. Returns (tokens, next_index)
    where tokens is a nested list of strings + sub-lists.
    Expects text[start] == '(' and returns at the index just past the
    matching close paren."""
    assert text[start] == "(", f"expected ( at {start}, got {text[start]!r}"
    out: list = []
    i = start + 1
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch == "(":
            sub, i = _parse_sexp_list(text, i)
            out.append(sub)
        elif ch == ")":
            return out, i + 1
        elif ch == '"':
            # quoted string — find next un-escaped quote
            j = i + 1
            while j < len(text):
                if text[j] == "\\" and j + 1 < len(text):
                    j += 2
                elif text[j] == '"':
                    break
                else:
                    j += 1
            # Decode standard escapes the same way KiCad writes them
            raw = text[i + 1:j]
            decoded = raw.encode().decode("unicode_escape")
            out.append(("str", decoded))
            i = j + 1
        else:
            # atom — read until whitespace or paren
            j = i
            while j < len(text) and not text[j].isspace() and text[j] not in "()":
                j += 1
            out.append(("atom", text[i:j]))
            i = j
    raise ValueError("unterminated S-expression")


def _sexp_head(node) -> str | None:
    """Return the 'head' atom of a sub-list (e.g. 'net', 'node', 'ref')."""
    if isinstance(node, list) and node:
        first = node[0]
        if isinstance(first, tuple) and first[0] == "atom":
            return first[1]
    return None


def _sexp_string_arg(node, index: int) -> str | None:
    """If node is a list and node[index] is a ('str', X) or ('atom', X),
    return X; otherwise None."""
    if isinstance(node, list) and len(node) > index:
        item = node[index]
        if isinstance(item, tuple) and item[0] in ("str", "atom"):
            return item[1]
    return None


def parse_netlist_for_pad_nets(netlist_path: Path) -> tuple[dict, list]:
    """Parse a KiCad S-expression netlist (exported with --format kicadsexpr)
    and return:
      - pad_nets: dict mapping (reference, pin_number_str) -> (net_code:int, net_name:str)
      - nets: list of (net_code, net_name) in order of appearance.

    Net code 0 (KiCad's "no net") is excluded. The netlist exporter
    starts numbering at 1.
    """
    text = netlist_path.read_text(encoding="utf-8")
    # Strip leading whitespace before first ( so the parser starts cleanly
    i = 0
    while i < len(text) and text[i].isspace():
        i += 1
    root, _ = _parse_sexp_list(text, i)
    # root is the (export ...) list. Find the (nets ...) child.
    nets_block = None
    for child in root[1:]:
        if _sexp_head(child) == "nets":
            nets_block = child
            break
    if nets_block is None:
        raise ValueError("no (nets ...) block in netlist")

    pad_nets: dict[tuple[str, str], tuple[int, str]] = {}
    nets: list[tuple[int, str]] = []
    for net in nets_block[1:]:
        if _sexp_head(net) != "net":
            continue
        code_str = None
        name = None
        nodes: list[tuple[str, str]] = []
        for entry in net[1:]:
            head = _sexp_head(entry)
            if head == "code":
                code_str = _sexp_string_arg(entry, 1)
            elif head == "name":
                name = _sexp_string_arg(entry, 1)
            elif head == "node":
                ref = None
                pin = None
                for sub in entry[1:]:
                    sh = _sexp_head(sub)
                    if sh == "ref":
                        ref = _sexp_string_arg(sub, 1)
                    elif sh == "pin":
                        pin = _sexp_string_arg(sub, 1)
                if ref is not None and pin is not None:
                    nodes.append((ref, pin))
        if code_str is None or name is None:
            continue
        code = int(code_str)
        if code == 0:
            continue
        nets.append((code, name))
        for (ref, pin) in nodes:
            pad_nets[(ref, pin)] = (code, name)
    return pad_nets, nets


def apply_nets_to_pcb(pcb_text: str, pad_nets: dict, nets: list) -> str:
    """Rewrite an oas.kicad_pcb text so that:
      - the (net 0 "") header is followed by (net N "<name>") declarations
        for every net in `nets`.
      - every (pad "<pin>" ...) inside a (footprint ... (property "Reference" "<R>") ...)
        block gets an additional (net <code> "<name>") clause IF (R, pin) is
        in pad_nets. Pads without a matching key are left alone (no
        (net 0 "") inserted — KiCad parses absent nets as net 0).

    Implementation: text-level scan that finds each top-level `(footprint`
    block, extracts the reference from its `(property "Reference" "..."`
    child, walks its pads, and re-emits each pad block with the inserted
    `(net ...)` clause."""

    # 1) Insert net dictionary right after `(net 0 "")` (which is unique
    #    in the file's top-level `(net 0 "")` declaration).
    net_decls = "\n".join(
        f"\t(net {code} {json.dumps(name)})"
        for code, name in nets
    )
    # KiCad accepts net names quoted with either " or escaped chars; using
    # json.dumps ensures we re-quote names like "+3V3" / "GND" / signal
    # names with slashes correctly. (No `Net-(...)` placeholder appears
    # in this design yet, but if KiCad ever emits one this still escapes
    # it cleanly.)
    marker = '\t(net 0 "")'
    if marker not in pcb_text:
        raise ValueError("expected '(net 0 \"\")' marker in PCB text")
    pcb_text = pcb_text.replace(marker, marker + "\n" + net_decls, 1)

    # 2) Walk top-level footprints. For each, find its Reference property,
    #    then find all its pads (sub-list whose head is 'pad') and inject
    #    `(net ...)` clauses.
    #
    # We use the same S-expression parser as the netlist parsing path but
    # locate each footprint by its raw text region in the original file so
    # we can produce a surgical edit (preserving every other byte of the
    # PCB file verbatim, which keeps round-tripping bit-stable and the
    # diff easy to review).

    # Find all top-level `(footprint ` openings — depth 1 inside the
    # outer `(kicad_pcb ...)` wrapper.
    out_chunks: list[str] = []
    cursor = 0
    depth = 0
    in_string = False
    string_escape = False
    fp_starts: list[int] = []
    fp_ends: list[int] = []
    for idx, ch in enumerate(pcb_text):
        if in_string:
            if string_escape:
                string_escape = False
            elif ch == "\\":
                string_escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "(":
            depth += 1
            if depth == 2 and pcb_text[idx:idx + len("(footprint")] == "(footprint":
                fp_starts.append(idx)
        elif ch == ")":
            if depth == 2 and fp_starts and len(fp_ends) < len(fp_starts):
                fp_ends.append(idx + 1)
            depth -= 1

    assert len(fp_starts) == len(fp_ends), (
        f"mismatched footprint paren count: {len(fp_starts)} starts vs {len(fp_ends)} ends"
    )

    rewritten_pieces: list[str] = []
    last = 0
    for fp_start, fp_end in zip(fp_starts, fp_ends):
        rewritten_pieces.append(pcb_text[last:fp_start])
        fp_text = pcb_text[fp_start:fp_end]
        fp_text_new = _patch_footprint_pad_nets(fp_text, pad_nets)
        rewritten_pieces.append(fp_text_new)
        last = fp_end
    rewritten_pieces.append(pcb_text[last:])
    return "".join(rewritten_pieces)


def _patch_footprint_pad_nets(fp_text: str, pad_nets: dict) -> str:
    """Given the source text of one (footprint ...) block, find its
    Reference property and inject (net ...) clauses into each pad that
    has a matching schematic node."""
    # 1) Extract Reference. Look for the (property "Reference" "<ref>" ...)
    #    child. The Reference property always appears before any (pad ...)
    #    child in our generated footprints, but we don't rely on order —
    #    we parse via a small state machine.
    ref = None
    # Search for the literal pattern; one Reference per footprint.
    m_idx = fp_text.find('(property "Reference" "')
    if m_idx >= 0:
        q_start = m_idx + len('(property "Reference" "')
        q_end = fp_text.find('"', q_start)
        if q_end > q_start:
            ref = fp_text[q_start:q_end]
    if ref is None:
        return fp_text  # no Reference -> leave untouched

    # Skip mech-only refs (these have attr `board_only` or `exclude_from_bom`).
    # They have no schematic counterpart by design.
    # We still walk pads (they may have nets explicitly assigned later) but
    # in practice pad_nets has no entries for these refs so nothing changes.

    # 2) Walk pads. We use a depth-counter scan over fp_text to find each
    #    top-level (pad ...) child (at depth 1 inside the footprint).
    out: list[str] = []
    i = 0
    depth = 0
    in_string = False
    string_escape = False
    pad_start = None
    while i < len(fp_text):
        ch = fp_text[i]
        if in_string:
            if string_escape:
                string_escape = False
            elif ch == "\\":
                string_escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "(":
            depth += 1
            if depth == 2 and fp_text[i:i + len("(pad ")] == "(pad ":
                pad_start = i
            i += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 1 and pad_start is not None:
                pad_end = i + 1
                pad_text = fp_text[pad_start:pad_end]
                # Stream-write everything before pad_start
                out.append(fp_text[len("".join(out)):pad_start] if not out else "")
                # That assertion is too messy — use index-based rewrite below.
                break
            i += 1
            continue
        i += 1

    # Reset and do an index-based rewrite (more robust than progressive `out` build).
    # Find every (pad "<pin>" ...) at depth 1 inside this footprint and
    # inject a (net ...) clause if matching.
    pad_blocks: list[tuple[int, int, str]] = []  # (start, end, pin_label)
    i = 0
    depth = 0
    in_string = False
    string_escape = False
    pad_start = None
    pad_pin = None
    while i < len(fp_text):
        ch = fp_text[i]
        if in_string:
            if string_escape:
                string_escape = False
            elif ch == "\\":
                string_escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "(":
            depth += 1
            if depth == 2 and fp_text[i:i + len("(pad ")] == "(pad ":
                pad_start = i
                # Extract pad pin number: pattern is `(pad "<pin>"`.
                q1 = fp_text.find('"', i + len("(pad"))
                q2 = fp_text.find('"', q1 + 1) if q1 >= 0 else -1
                pad_pin = fp_text[q1 + 1:q2] if q1 >= 0 and q2 > q1 else ""
            i += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 1 and pad_start is not None:
                pad_end = i + 1
                pad_blocks.append((pad_start, pad_end, pad_pin or ""))
                pad_start = None
                pad_pin = None
            i += 1
            continue
        i += 1

    if not pad_blocks:
        return fp_text

    pieces: list[str] = []
    cursor = 0
    for (p_start, p_end, pin) in pad_blocks:
        pieces.append(fp_text[cursor:p_start])
        pad_text = fp_text[p_start:p_end]
        key = (ref, pin)
        if pin and pin != "" and key in pad_nets:
            code, name = pad_nets[key]
            pad_text = _insert_net_into_pad(pad_text, code, name)
        pieces.append(pad_text)
        cursor = p_end
    pieces.append(fp_text[cursor:])
    return "".join(pieces)


def _insert_net_into_pad(pad_text: str, code: int, name: str) -> str:
    """Insert a (net code "name") clause just before the closing paren of
    the pad block. Indentation matches the pad's existing inner indent
    (one level deeper than the (pad ...) opening)."""
    # Find the closing paren position (last char before any trailing whitespace).
    # The pad block looks like:
    #   \t(pad "1" smd rect
    #   \t\t(at ...)
    #   \t\t...
    #   \t)
    # We insert before the last ')'. Detect the indentation of the inner
    # children by looking at the indent of the line containing the first
    # inner sub-clause (the `(at ` line is always present).
    lines = pad_text.split("\n")
    # Find leading whitespace of the last line that contains content other
    # than the closing paren.
    inner_indent = "\t\t"  # safe fallback
    for ln in lines:
        stripped = ln.lstrip("\t")
        if stripped and stripped.startswith("("):
            tabs = len(ln) - len(ln.lstrip("\t"))
            if tabs >= 1 and not stripped.startswith("(pad"):
                inner_indent = "\t" * tabs
                break

    # Locate position of the LAST ')' character in pad_text.
    close_idx = pad_text.rfind(")")
    if close_idx < 0:
        return pad_text
    net_str = f'{inner_indent}(net {code} {json.dumps(name)})\n'
    # Find the position right before the closing paren (skip back over the
    # whitespace/tabs that prefix the ')' on its own line).
    insert_at = close_idx
    while insert_at > 0 and pad_text[insert_at - 1] in (" ", "\t"):
        insert_at -= 1
    return pad_text[:insert_at] + net_str + pad_text[insert_at:]


def sync_pcb_nets_from_schematic(kicad_cli: str | None = None) -> int:
    """Sync electrical nets from the just-emitted schematic onto the PCB.

    1. Exports a netlist from oas.kicad_sch via kicad-cli sch export netlist.
    2. Parses the netlist into (ref, pin) -> (net_code, net_name) lookup.
    3. Rewrites oas.kicad_pcb so that:
       (a) the PCB header carries a (net N "<name>") declaration for every
           electrical net in the schematic, and
       (b) every pad whose (footprint_reference, pad_pin) appears in the
           netlist gains a matching (net code "name") clause.

    Returns the count of pads that received a net assignment.

    Skips silently if kicad-cli is not available (so the walker still runs
    under bare CI without a KiCad install). build.py finds kicad-cli on
    its own; when calling pipeline/generic/01_emit_sources.py standalone,
    set the OAS_KICAD_CLI env var or pass `kicad_cli`.
    """
    import os
    import shutil
    import subprocess
    import tempfile

    pcb_path = HERE / "oas.kicad_pcb"
    sch_path = HERE / "oas.kicad_sch"
    if not pcb_path.exists() or not sch_path.exists():
        return 0

    if kicad_cli is None:
        kicad_cli = os.environ.get("OAS_KICAD_CLI")
    if kicad_cli is None:
        for c in (
            r"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe",
            r"C:/Program Files/KiCad/9.0/bin/kicad-cli.exe",
        ):
            if Path(c).exists():
                kicad_cli = c
                break
    if kicad_cli is None:
        kicad_cli = shutil.which("kicad-cli")
    if kicad_cli is None:
        print("  [sync_pcb_nets] kicad-cli not found; skipping net sync")
        return 0

    with tempfile.TemporaryDirectory() as td:
        net_path = Path(td) / "oas.net"
        r = subprocess.run(
            [kicad_cli, "sch", "export", "netlist",
             "--output", str(net_path),
             "--format", "kicadsexpr",
             str(sch_path)],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        # kicad-cli prints "Ostrzeżenie: schemat posiada błędy numeracji"
        # (annotation warnings) on stderr even when the netlist file is
        # written successfully; treat exit code 0 as OK and warn on
        # anything else.
        if r.returncode != 0:
            print("  [sync_pcb_nets] kicad-cli netlist export failed:")
            print(r.stdout)
            print(r.stderr)
            return 0
        if not net_path.exists():
            print("  [sync_pcb_nets] netlist file not produced")
            return 0
        pad_nets, nets = parse_netlist_for_pad_nets(net_path)

    pcb_text = pcb_path.read_text(encoding="utf-8")
    new_text = apply_nets_to_pcb(pcb_text, pad_nets, nets)

    # Count assignments actually applied (= pad_nets entries whose ref has
    # a matching footprint on the PCB). A reference appears at least once
    # in the file iff `(property "Reference" "<R>"` is present.
    assigned = 0
    for (ref, _pin), _ in pad_nets.items():
        if f'(property "Reference" "{ref}"' in pcb_text:
            assigned += 1
    pcb_path.write_text(new_text, encoding="utf-8")
    return assigned


# -----------------------------------------------------------------------------
# Schematic Footprint property back-fill (v0.23 — closes review Mn3;
# v0.24 — lib-qualify the back-filled values to silence ERC footprint_link_issues)
# -----------------------------------------------------------------------------
# Every real component symbol in the sub-sheets is emitted with an EMPTY
# `(property "Footprint" "")` field by the `_sch_*` helpers (they don't know
# which footprint reference each symbol will end up wearing). The PCB-side
# footprint reference is authoritative for the JLCPCB BOM workflow that walks
# the PCB; however, running the schematic-driven netlist exporter or KiCad's
# "Update PCB from Schematic" path would surface a "no footprint assigned"
# warning per missing field. This post-process function back-fills the
# property by reading the PCB file (already written at this point in main())
# and copying each footprint's library reference into the matching schematic
# symbol's Footprint property.
#
# v0.23 BUG (caught in review iteration 2): the PCB-side `(property
# "Footprint" "...")` string is written without a library prefix by the
# `gen_*_pcb_footprint` helpers for inline (non-stock-library) footprints —
# e.g. `gen_capacitor_0402_pcb_footprint` writes the bare `"C_0402_1005Metric"`
# rather than `"Capacitor_SMD:C_0402_1005Metric"`. Naively copying that into
# the schematic produced 15 `footprint_link_issues` ERC warnings (parsed as
# library == "" which is not a registered footprint library).
#
# v0.24 fix: lib-qualify each bare footprint name via a hard-coded
# bare → library lookup table. The table is sourced from the stock KiCad
# library locations referenced by each `gen_*_pcb_footprint` helper (e.g.
# `R_0603_1608Metric` lives in `Resistor_SMD`, `D_SMA` lives in `Diode_SMD`,
# `SOT-23` lives in `Package_TO_SOT_SMD`, etc.). All entries are verified
# to exist in stock KiCad 9/10 installs. Project-local footprints (under
# `libraries/oas.pretty/`) and stock footprints emitted via
# `_emit_stock_lib_footprint` already carry the `Lib:Name` prefix in the
# PCB-side property, so they pass through unchanged.
#
# Note: power flags (#PWR*, #FLG*) intentionally retain the empty Footprint
# field — they are graphical / power-bus markers, not real parts and do not
# appear on the PCB.

# Bare-footprint-name → KiCad stock-library nickname. Used by
# `_build_pcb_ref_to_footprint` to lib-qualify any non-stock-library
# `(property "Footprint" "<bare>")` it encounters in the PCB so the
# schematic back-fill emits valid `<Lib>:<Name>` references. The library
# nicknames must match those declared in `fp-lib-table` and the entries
# must exist in the stock KiCad install.
BARE_FOOTPRINT_TO_LIB: dict[str, str] = {
    # 0402/0603/0805 chip caps + resistors — Capacitor_SMD / Resistor_SMD
    "C_0402_1005Metric": "Capacitor_SMD",
    "C_0603_1608Metric": "Capacitor_SMD",
    "C_0805_2012Metric": "Capacitor_SMD",
    "R_0603_1608Metric": "Resistor_SMD",
    # 2920 polyfuse footprint — uses Resistor_SMD library naming
    "R_2920_7351Metric": "Resistor_SMD",
    # Diode SMD packages — Diode_SMD library
    "D_SMA": "Diode_SMD",
    "D_SMB": "Diode_SMD",
    "D_SOD-323": "Diode_SMD",
    # SMD inductor (NR5040-class shielded power inductor)
    "L_NR5040": "Inductor_SMD",
    # Radial-lead electrolytic capacitors (through-hole)
    "CP_Radial_D6.3mm_P2.5mm": "Capacitor_THT",
    "CP_Radial_D8mm_P3.5mm": "Capacitor_THT",
    # SOT-23 small-signal transistors / diode packages
    "SOT-23": "Package_TO_SOT_SMD",
}


# -----------------------------------------------------------------------------
# v0.26 — Z-CLEARANCE GUARDRAIL
# -----------------------------------------------------------------------------
# The OAS PCB carries two daughterboards mounted on pin sockets/headers:
# ESP32-C6 DevKitM-1-N4 (MOD1, ~8.6 mm above PCB) and HLK-LD2410C
# (LDR1, ~7 mm above PCB).
# The daughterboard mech-ref footprints intentionally do NOT carry an
# F.CrtYd (see _emit_daughterboard_reference_pcb_footprint) so KiCad's
# DRC `courtyards_overlap` rule does not block legitimate SMD placement
# under their shadow. The trade-off: DRC has zero awareness of the third
# dimension, so a tall THT component placed under a daughterboard sails
# through DRC + ERC + visual review even when it would physically
# prevent the daughterboard from seating into its sockets.
#
# v0.25 clearance audit (kept inline below as the Z-clearance budget
# constants) found 3
# radial THT electrolytic caps (C1, C3, C4, all 11-12 mm tall) and one
# TO-263-5 buck (U1, 4.6 mm) under the ESP32 shadow that exceeded the
# ~5.5 mm under-daughterboard budget. v0.26 relocated them; this
# function backs the v0.26 fix with a programmatic invariant check that
# fires loudly on any future regression — the same pattern used by
# `BARE_FOOTPRINT_TO_LIB` to catch missing footprint-library mappings.
#
# How it works:
#   1. FOOTPRINT_HEIGHT — declares the maximum Z-extent (above PCB top
#      surface, mm) of every footprint emitted by boardgen. Keys are
#      the fully-qualified `(property "Footprint" "...")` strings as
#      written into oas.kicad_pcb. Missing entries -> hard assertion in
#      check_z_clearance_violations() (catches new generators that
#      forget to declare a height).
#   2. DAUGHTERBOARD_Z_CLEARANCE — per-daughterboard available clearance
#      between OAS PCB top surface and daughterboard PCB bottom surface.
#      Conservative values: socket plastic body height minus the typical
#      3 mm mating-pin tail that bottoms out inside the socket throat.
#   3. _DAUGHTERBOARD_BODY_SHADOWS — the PCB-frame XY rectangle each
#      daughterboard body covers (its mech-ref footprint's F.Fab body
#      outline, transformed by anchor + rotation). Computed lazily from
#      the source-of-truth `*_ANCHOR_*` / `*_BODY_*` constants at the
#      top of the file.
#   4. check_z_clearance_violations() — enumerates every placed
#      footprint (via _build_pcb_ref_to_footprint), looks up its height,
#      and tests whether its placement center falls inside any
#      daughterboard shadow. Returns the list of violations; main()
#      aborts with a formatted error message if non-empty.

# Footprint-property string → maximum component height above OAS PCB
# (mm, datasheet typical-max, conservative when a range exists).
#
# Sources (datasheet citations, originally gathered during the v0.25
# clearance audit):
#   - Chip resistors / capacitors 0402 / 0603 / 0805: Murata GRM /
#     Vishay CRCW datasheets — 0.5 / 0.95 / 1.25 mm respectively.
#   - SOT-23: Onsemi / Vishay generic — 1.1 mm.
#   - SMA / SMB diodes: Vishay — 2.3 mm (SMA), 2.6 mm (SMB).
#   - SOD-323 diodes: Vishay — 1.0 mm.
#   - SOT-583-8 / VSON-8 (TPS62933): TI SOT-583 — 0.85 mm.
#   - TO-263-5 / D2PAK-5 (LM2596S): TI — 4.83 mm max, 4.6 mm typ.
#   - 5×5 SMD shielded inductor (NR5040 / WE-PD-S): Wurth WE-PD-S 5045
#     = 4.5 mm worst-case body height.
#   - 1812 SMD PTC fuse (F1): Littelfuse 1812L075/33DR — ~1.1 mm.
#   - JST GH 6-pin horizontal SMD socket (J3): JST — 4.25 mm.
#   - JST SH 4-pin horizontal SMD socket (J9): JST — 1.5 mm.
#   - Phoenix MSTBA 5.08 mm 3-pin terminal block (J1): Phoenix
#     1988861 — 14.0 mm above PCB.
#   - PinHeader 2.54 mm vertical (J2, J10): plastic body 2.5 mm + pin
#     11.5 mm = 14.0 mm total above PCB.
#   - PinHeader 1.27 mm vertical (J4): plastic 2.0 mm + pin 8 mm =
#     ~10 mm above PCB.
#   - PinSocket 2.54 mm vertical (J5/J6): plastic body 8.5 mm.
#   - CP_Radial_D6.3mm_P2.5mm electrolytic: Panasonic ECA-1AM221 etc.
#     — 11.2 mm max.
#   - CP_Radial_D8.0mm_P3.50mm electrolytic: Panasonic ECA-1HM101 etc.
#     — 12.5 mm max.
#   - SK6812-SIDE side-emitting RGB LED: SK6812SIDE 3535 — 1.6 mm.
#   - Mounting hole / zip-tie hole / NPTH: 0 mm (no body).
#   - SEN66 mechanical reference (lays flat on PCB, body 21.5 mm tall):
#     SEN66 datasheet — 21.5 mm above PCB; the mech-ref carries its own
#     F.CrtYd so DRC catches XY collisions, but the body itself is the
#     daughterboard analogue — exempt from the under-daughterboard
#     check (handled via _IS_DAUGHTERBOARD_REF below).
#   - Daughterboard mech-refs themselves (ESP32-C6-DevKitM-1 /
#     LD2410): they ARE the daughterboards; never appear
#     "under" themselves. Excluded from the check via the same
#     _IS_DAUGHTERBOARD_REF predicate.
#
# UPDATE WHEN ADDING A NEW GENERATOR: add the new footprint's
# `(property "Footprint" "...")` string here with its datasheet-max
# height. If you forget, `check_z_clearance_violations()` asserts at
# build time with a clear error message.
FOOTPRINT_HEIGHT: dict[str, float] = {
    # ---- Chip passives ----
    "Capacitor_SMD:C_0402_1005Metric": 0.5,
    "Capacitor_SMD:C_0603_1608Metric": 0.95,
    "Capacitor_SMD:C_0805_2012Metric": 1.25,
    "Resistor_SMD:R_0603_1608Metric": 0.5,
    # ---- Discrete semi packages ----
    "Diode_SMD:D_SMA": 2.3,
    "Diode_SMD:D_SMB": 2.6,
    "Diode_SMD:D_SOD-323": 1.0,
    "Package_TO_SOT_SMD:SOT-23": 1.1,
    "Package_TO_SOT_SMD:SOT-583-8": 0.85,
    "oas:TO-263-5_LM2596": 4.83,
    # Note: the TPS62933 SOT-583 footprint property is written as
    # `Package_SO:VSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm` by gen_sot583_pcb_footprint
    "Package_SO:VSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm": 0.85,
    # ---- Inductors ----
    "Inductor_SMD:L_APV_ANR5040": 4.5,
    # v0.40 post-order: CENKER CKCS5040 is 5.0 × 5.0 × 4.0 mm.
    "Inductor_SMD:L_Cenker_CKCS5040": 4.0,
    # F1 polyfuse — see "oas:Fuse_1812L_4532Metric" in the OAS-internal
    # block below (v0.42 moved it off the KiCad stock Fuse_* land).
    # ---- Radial THT electrolytics (the v0.26 audit-driven entries) ----
    "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm": 11.2,
    "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm": 12.5,
    # ---- Connectors ----
    "Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal": 4.25,
    "Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal": 1.5,
    "Connector_Phoenix_MSTB:PhoenixContact_MSTBA_2,5_3-G-5,08_1x03_P5.08mm_Horizontal": 14.0,
    # J4 — 1x5 gold-pin header carrying the HLK-LD2410C. A standard 2.54 mm
    # male strip stands ~11.5 mm proud of the PCB (≈6 mm pin + 2.5 mm
    # spacer + the part of the tail left above the board); the module is
    # soldered part-way up it. v0.53 / issue #9 replaced the 1.27 mm entry.
    "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical": 11.5,
    "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical": 14.0,
    "Connector_PinSocket_2.54mm:PinSocket_1x08_P2.54mm_Vertical": 8.5,
    "Connector_PinSocket_2.54mm:PinSocket_1x15_P2.54mm_Vertical": 8.5,
    # ---- OAS-internal footprints ----
    "oas:SK6812-SIDE": 1.6,
    # F1 PTC fuse — Littelfuse 1812L075/33DR, 1812 body, datasheet max
    # thickness ~1.1 mm. Custom land (oas:Fuse_1812L_4532Metric); v0.42
    # replaced the generic KiCad stock 1812 fuse land — see Deviation budget.
    "oas:Fuse_1812L_4532Metric": 1.1,
    "oas:MountingHole_3.8mm_M3": 0.0,
    "oas:ZipTieHole_3mm_NPTH": 0.0,
    # Mechanical references — daughterboards / SEN66. Excluded from the
    # under-daughterboard check via _IS_DAUGHTERBOARD_REF below, so this
    # value is informational only (the body Z of the part itself above
    # the PCB).
    "oas:SEN66_Mechanical_Reference": 21.5,
    # Sourced from the single geometry constant so the two cannot drift.
    "oas:LD2410_Mechanical_Reference": LD2410_BODY_Z,
    "oas:ESP32-C6-DevKitM-1_Reference": 8.6,
}


# Component-clearance budget under each daughterboard, in mm. The budget
# is the worst-case-realistic vertical distance between the OAS PCB top
# surface and the daughterboard's PCB bottom surface (after the mating
# pin tails bottom out inside the socket throat). Per the v0.25
# clearance audit (rationale captured inline):
#   - ESP32 daughterboard on 2× PinSocket_1x15_P2.54mm_Vertical (8.5 mm
#     plastic body): conservative 5.5 mm budget. Top of the socket plastic
#     less ~3 mm of male pin tail protrusion from the DevKitM-1.
#   - HLK-LD2410C on a 1×5 vertical 2.54 mm gold-pin header (J4): the
#     module PCB rests on the ~2.5 mm header spacer, and its UNDERSIDE
#     carries the LDO, two crystals and an inductor (~1.5 mm). Net budget
#     ~1 mm — tighter than the -B's 2 mm, so v0.53 / issue #9 placed
#     NOTHING under the shadow at all (C11, the module's own decoupling
#     cap, sits just north of the pin row). The guardrail flags anything
#     that creeps in. Both the header spacer height and the underside
#     component height are estimates: Hi-Link publishes no thickness for
#     the -C — CONFIRM WITH CALIPERS on the delivered module.
DAUGHTERBOARD_Z_CLEARANCE: dict[str, float] = {
    "MOD1": 5.5,   # ESP32-C6 DevKitM-1-N4
    "LDR1": 1.0,   # HLK-LD2410C (2.54 mm header, components on its underside)
}


# References that ARE daughterboards (or other tall mechanical refs that
# are themselves the obstacle). These are skipped when iterating OAS
# components, so a daughterboard never triggers the guardrail "against
# itself" or against another tall mech-ref.
_DAUGHTERBOARD_REFS: frozenset[str] = frozenset({"MOD1", "LDR1", "SENS1"})

# Per-daughterboard intentional mounting sockets — these are the female
# pin sockets (J5/J6 for ESP32) and the LD2410C's
# 2.54 mm gold-pin header (J4) that the daughterboards PLUG INTO. They live
# under the daughterboard shadow by design — their "height" is the
# daughterboard's standoff, not an obstruction. Excluded per-shadow so
# the J5 socket (mounting MOD1) doesn't trigger a violation for MOD1,
# but would still trigger for another daughterboard's shadow.
_DAUGHTERBOARD_MOUNTING_SOCKETS: dict[str, frozenset[str]] = {
    "MOD1": frozenset({"J5", "J6"}),       # ESP32 pin sockets
    "LDR1": frozenset({"J4"}),             # LD2410 1.27 mm pin header
}


def _daughterboard_body_shadows() -> dict[str, tuple[float, float, float, float]]:
    """Compute the PCB-frame XY bounding box of each daughterboard body
    shadow. Returns a dict ref → (x_min, x_max, y_min, y_max).

    Shadows are computed from the source-of-truth `*_ANCHOR_*` and
    `*_BODY_*` constants at the top of the file (NOT parsed back out of
    the .kicad_pcb file) so this function works correctly even before
    the PCB has been written for the first time. The body extents match
    what `_emit_daughterboard_reference_pcb_footprint` writes onto
    F.Fab — see that function's docstring for the local-to-PCB
    coordinate transform under each rotation.
    """
    shadows: dict[str, tuple[float, float, float, float]] = {}

    # ESP32-C6 DevKitM-1-N4 (MOD1): helper rotation 90, LIB +X → PCB -Y,
    # LIB +Y → PCB +X. Body LIB rect (0,0) → (body_w, body_l). After
    # rotation the body covers PCB X = [anchor_x, anchor_x + body_l] and
    # PCB Y = [anchor_y - body_w, anchor_y].
    # v0.53 (issue #3): extend the shadow WEST by the antenna-tab protrusion
    # (the ESP32-C6-MINI-1 PCB antenna overhangs the antenna short edge at PCB
    # -X). The tab is only ~13.2 mm wide (a sub-band of the 25.4 mm body), but
    # this AABB widens the whole west edge — a CONSERVATIVE over-approximation
    # (the corners it adds are empty of tall parts). With the -7.5 mm move, U1
    # (TO-263, 4.83 mm) now sits under the tab; extending the shadow makes the
    # Z-guardrail actually check it against the 5.5 mm MOD1 budget (it passes).
    esp_xmin = ESP32_ANCHOR_X - ESP32_ANTENNA_TAB_PROTRUSION
    esp_xmax = ESP32_ANCHOR_X + ESP32_BODY_L
    esp_ymin = ESP32_ANCHOR_Y - ESP32_BODY_W
    esp_ymax = ESP32_ANCHOR_Y
    shadows["MOD1"] = (esp_xmin, esp_xmax, esp_ymin, esp_ymax)

    # HLK-LD2410C (LDR1): rotation 0 since v0.53 / issue #9 (the -B stood
    # its 35 mm strip on end at 270°), so the LIB rect (0,0) →
    # (LD2410_BODY_W, LD2410_BODY_H) maps straight onto PCB X in
    # [anchor_x, anchor_x + LD2410_BODY_W] and Y in
    # [anchor_y, anchor_y + LD2410_BODY_H]. The anchor is the body corner
    # that is NORTH-WEST on the board and is itself DERIVED from the J4
    # pin-1 datum — see the LD2410C block in _project.py.
    ld_xmin = LD2410_ANCHOR_X
    ld_xmax = LD2410_ANCHOR_X + LD2410_BODY_W
    ld_ymin = LD2410_ANCHOR_Y
    ld_ymax = LD2410_ANCHOR_Y + LD2410_BODY_H
    shadows["LDR1"] = (ld_xmin, ld_xmax, ld_ymin, ld_ymax)

    return shadows


def _parse_footprint_placements() -> list[tuple[str, str, float, float, float]]:
    """Read oas.kicad_pcb and return (reference, footprint_property,
    pcb_x, pcb_y, rotation_deg) for every placed footprint. The
    placement (x, y) is the footprint's anchor in PCB-frame mm
    (note: KiCad stores PCB Y with the +Y-down screen convention,
    but `fy(y)` in this codebase negates the sign so the value in
    the file is mirrored — the `_invert_pcb_y` constant below
    handles that). The footprint property string is canonicalized
    via `BARE_FOOTPRINT_TO_LIB`. Rotation is 0 when absent in the
    `(at x y rot)` clause.
    """
    import re

    text = (HERE / "oas.kicad_pcb").read_text(encoding="utf-8")
    placements: list[tuple[str, str, float, float, float]] = []
    fp_starts = [m.start() for m in re.finditer(r'(?m)^\s*\(footprint "([^"]+)"', text)]
    fp_starts.append(len(text))
    for i in range(len(fp_starts) - 1):
        block = text[fp_starts[i]:fp_starts[i + 1]]
        m_name = re.search(r'\(footprint "([^"]+)"', block)
        if not m_name:
            continue
        fp_name_header = m_name.group(1)
        # Match (at <x> <y>) or (at <x> <y> <rot>). x / y are signed
        # floats. The `at` clause is the second-occurring property in
        # the block (after the (layer ...) clause) and IS the placement.
        m_at = re.search(
            r'\(at\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)(?:\s+(-?\d+(?:\.\d+)?))?\)',
            block,
        )
        if not m_at:
            continue
        # NB: `fx(x)` / `fy(y)` add PAGE_CENTRE_X / PAGE_CENTRE_Y
        # (148.5 / 105.0 mm) to recentre PCB coordinates onto an A4
        # page. Reverse that here so placements are in the same
        # PCB frame the daughterboard shadows live in.
        pcb_x = float(m_at.group(1)) - PAGE_CENTRE_X
        pcb_y = float(m_at.group(2)) - PAGE_CENTRE_Y
        rotation = float(m_at.group(3)) if m_at.group(3) is not None else 0.0
        m_ref = re.search(r'\(property "Reference" "([^"]+)"', block)
        if not m_ref:
            continue
        ref = m_ref.group(1)
        m_fp_prop = re.search(r'\(property "Footprint" "([^"]*)"', block)
        raw = m_fp_prop.group(1) if (m_fp_prop and m_fp_prop.group(1)) else fp_name_header
        if ":" in raw:
            canonical = raw
        else:
            lib = BARE_FOOTPRINT_TO_LIB.get(raw)
            assert lib is not None, (
                f"BARE_FOOTPRINT_TO_LIB missing entry for {raw!r} "
                f"(used by reference {ref!r})."
            )
            canonical = f"{lib}:{raw}"
        placements.append((ref, canonical, pcb_x, pcb_y, rotation))
    return placements


# Approximate planar (XY) body half-extent above the OAS PCB for each
# footprint property. Used by the Z-clearance guardrail to test whether
# a footprint's body (not just its anchor) intrudes into a daughterboard
# shadow. Each entry is a (half_x, half_y) tuple — half-extent of the
# component's BODY (not pads, not courtyard) along PCB X and Y at the
# rotation the OAS PCB uses for that footprint.
#
# Notes:
#   - For ROTATION-VARIABLE footprints (used at multiple rotations
#     across the OAS PCB) we'd need a different model. As of v0.26 every
#     footprint in `_FOOTPRINT_HALF_EXTENT` is used at exactly the
#     rotation listed here (e.g. all PinSocket_1x15 are placed with
#     rotation 90 — long axis along PCB X). If you ever place one at
#     rotation 0 too, swap the (half_x, half_y) values for that
#     instance or split the dict by (footprint, rotation).
#   - SMD/THT body half-extents from datasheets / KiCad footprint
#     library geometry. For circular radial-cap bodies, both half-X and
#     half-Y equal the body radius.
#   - Sockets (long axis) declared with the long axis along PCB X
#     (rotation 90 places the socket's LIB +Y along PCB +X — see the
#     mounting-socket placement comments around the `gen_pinsocket_*`
#     calls). Pad extent ±0.85 mm and crty extent ±1.77 mm in the short
#     axis; long axis follows pin count × 2.54 mm + 2× 1.77 mm crty.
_FOOTPRINT_HALF_EXTENT: dict[str, tuple[float, float]] = {
    "Capacitor_SMD:C_0402_1005Metric": (0.7, 0.7),
    "Capacitor_SMD:C_0603_1608Metric": (1.0, 0.9),
    "Capacitor_SMD:C_0805_2012Metric": (1.4, 1.0),
    "Resistor_SMD:R_0603_1608Metric": (1.0, 0.9),
    "Diode_SMD:D_SMA": (2.5, 1.4),
    "Diode_SMD:D_SMB": (3.0, 1.8),
    "Diode_SMD:D_SOD-323": (1.0, 0.7),
    "Package_TO_SOT_SMD:SOT-23": (1.5, 1.5),
    "Package_TO_SOT_SMD:SOT-583-8": (1.0, 1.0),
    "oas:TO-263-5_LM2596": (5.3, 5.3),
    "Package_SO:VSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm": (1.0, 1.0),
    "Inductor_SMD:L_APV_ANR5040": (2.6, 2.6),
    # v0.40 post-order: CENKER CKCS5040 body half-extent (5.0 / 2 + ~0.3 mm
    # for end-terminals = 2.8).
    "Inductor_SMD:L_Cenker_CKCS5040": (2.8, 2.6),
    # F1 polyfuse half-extent — see "oas:Fuse_1812L_4532Metric" below.
    # Radial caps — cylindrical body, radius = half-extent both axes
    "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm": (3.2, 3.2),
    "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm": (4.0, 4.0),
    # Connectors — placed at varying rotations, see per-call comments
    # in gen_*_pcb_footprint helpers. The (half_x, half_y) here assumes
    # the rotation actually used on the OAS PCB.
    # J3 — JST GH 6-pin horizontal SMD, rotation 90 (mouth -X / west;
    # v0.53 issue #2). Body half-extent swapped from the rotation-0
    # (4.6, 2.5) — the 6-pin row (~9.2 mm) now runs along PCB Y.
    "Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal": (2.5, 4.6),
    # J9 — JST SH 4-pin horizontal SMD, rotation 180 (mouth toward chord)
    "Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal": (2.7, 1.5),
    # J1 — Phoenix MSTBA 3-pin terminal block, rotation 180
    "Connector_Phoenix_MSTB:PhoenixContact_MSTBA_2,5_3-G-5,08_1x03_P5.08mm_Horizontal": (8.5, 6.5),
    # J4 — LD2410C 2.54 mm gold-pin header, rotation 90 (pad row along
    # PCB +X). Courtyard 3.54 x 13.70 mm about the row, i.e. half-extent
    # (10.16/2 + 1.77, 1.77) = (6.85, 1.77) measured from the ROW CENTRE.
    # Pin headers are anchored at PAD 1, not the row centre, so the check
    # re-centres the test point first (see the row-centre shift in
    # check_z_clearance_violations) — the same treatment radial caps get.
    "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical": (6.85, 1.77),
    # J2, J10 — 6-pin 2.54 mm vertical pin header, rotation 0/180. Row
    # 5 x 2.54 = 12.70 mm + 2 x 1.77 courtyard -> half 8.12 along the row;
    # the historical 7.6 predates the row-centre shift and is kept because
    # it is the tighter (non-conservative direction is now handled by the
    # re-centring, and both refs are far from every daughterboard shadow).
    "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical": (1.5, 7.6),
    # J5/J6 — 15-pin ESP32 sockets, rotation 90 (long axis along PCB +X)
    "Connector_PinSocket_2.54mm:PinSocket_1x15_P2.54mm_Vertical": (19.6, 1.8),
    "oas:SK6812-SIDE": (2.0, 1.0),
    # F1 PTC fuse — courtyard 5.51 × 3.90 mm (pads at ±2.557 mm X outer
    # edge, 0.20 mm margin) -> half-extent (2.76, 1.95).
    "oas:Fuse_1812L_4532Metric": (2.76, 1.95),
    "oas:MountingHole_3.8mm_M3": (1.9, 1.9),
    "oas:ZipTieHole_3mm_NPTH": (1.5, 1.5),
    # Mechanical references (daughterboards / SEN66) — these refs are
    # in _DAUGHTERBOARD_REFS so the guardrail skips them; values are
    # informational only.
    "oas:SEN66_Mechanical_Reference": (12.8, 27.6),
    "oas:LD2410_Mechanical_Reference": (11.0, 8.0),
    "oas:ESP32-C6-DevKitM-1_Reference": (24.13, 12.7),
}


# Per-reference half-extent overrides — used when a single footprint
# entry above is placed at multiple rotations across the OAS PCB and
# the default (rotation-calibrated) value is wrong for one of the
# placements. Each entry pins down the SPECIFIC (half_x, half_y) for
# that reference, overriding the per-footprint lookup.
_FOOTPRINT_HALF_EXTENT_OVERRIDES: dict[str, tuple[float, float]] = {
    # J2 / J10 — PinHeader_1x06_P2.54mm_Vertical, both placed at rotation
    # 90 (horizontal pad row along PCB +X) as of v0.43. The
    # _FOOTPRINT_HALF_EXTENT default (1.5, 7.6) is the un-rotated extent;
    # rotation 90 swaps it to (7.6, 1.5).
    "J2":  (7.6, 1.5),
    "J10": (7.6, 1.5),
}


def check_z_clearance_violations() -> list[str]:
    """Programmatic invariant check: every footprint placed inside a
    daughterboard's body shadow must have a component height ≤ that
    daughterboard's under-board Z-clearance budget.

    Returns a list of human-readable violation strings (empty when the
    PCB is clean). Calls `assert` if any placed footprint references a
    footprint-property string not declared in `FOOTPRINT_HEIGHT` — this
    catches new generators that forget to declare a height (mirrors the
    `BARE_FOOTPRINT_TO_LIB` regression-prevention pattern from v0.24).

    The check tests footprint EXTENT (anchor ± per-footprint planar
    half-extent from `_FOOTPRINT_HALF_EXTENT`) rather than just anchor,
    so a 12 mm-tall radial cap anchored 2 mm outside a daughterboard
    shadow still triggers the guardrail when its body pokes ~2 mm into
    the shadow.

    Daughterboards themselves (MOD1/LDR1/SENS1) and their mating
    sockets (J5/J6/J4) are exempt from the check — those are the
    daughterboard's own support feet and live under its shadow by
    design.
    """
    import math
    import re

    placements = _parse_footprint_placements()
    shadows = _daughterboard_body_shadows()
    violations: list[str] = []
    for ref, fp_prop, px, py, rotation in placements:
        if ref in _DAUGHTERBOARD_REFS:
            # Skip the daughterboard mech-refs themselves and the SEN66
            # body (handled by its own F.CrtYd).
            continue
        height = FOOTPRINT_HEIGHT.get(fp_prop)
        assert height is not None, (
            f"FOOTPRINT_HEIGHT missing entry for {fp_prop!r} "
            f"(used by reference {ref!r}). Add the appropriate "
            f"datasheet-max height to FOOTPRINT_HEIGHT in boardgen/_postprocess.py."
        )
        # Per-reference override takes precedence over the per-footprint
        # default — used when a single footprint is placed at multiple
        # rotations across the OAS PCB and the default dict value is
        # only calibrated for one of them. Currently J10 (PinHeader_1x06
        # at rotation 90) overrides the J2 default (rotation 0).
        half = _FOOTPRINT_HALF_EXTENT_OVERRIDES.get(ref)
        if half is None:
            half = _FOOTPRINT_HALF_EXTENT.get(fp_prop)
        assert half is not None, (
            f"_FOOTPRINT_HALF_EXTENT missing entry for {fp_prop!r} "
            f"(used by reference {ref!r}). Add a planar half-extent to "
            f"_FOOTPRINT_HALF_EXTENT in boardgen/_postprocess.py."
        )
        half_x, half_y = half
        # Radial caps: the footprint (at) anchor is at PIN 1, not the body
        # centre — the body sits +pitch/2 along local +X (see
        # gen_capacitor_polarized_radial_pcb_footprint). Shift the test
        # point to the body centre so the AABB uses the real body, not a
        # pitch/2-displaced phantom.
        m_radial = re.search(r"CP_Radial_D[\d.]+mm_P([\d.]+)mm", fp_prop)
        if m_radial:
            hp = float(m_radial.group(1)) / 2.0
            th = math.radians(rotation)
            px = px + hp * math.cos(th)
            py = py + hp * math.sin(th)
        # Pin headers / sockets: the (at) anchor is PAD 1 at one END of the
        # row, but the half-extents above are measured from the ROW CENTRE.
        # Shift the test point to that centre, else the AABB is displaced by
        # half the row length — it would model empty laminate on one side
        # and miss real header body on the other (a silent false negative
        # for anything parked off the far end). Stock KiCad 1xN headers lay
        # their pads along footprint-local +Y, which the OAS rotation
        # convention maps to (sin, cos) on the PCB.
        m_row = re.search(r"Pin(?:Header|Socket)_1x(\d+)_P([\d.]+)mm", fp_prop)
        if m_row:
            span = (int(m_row.group(1)) - 1) * float(m_row.group(2)) / 2.0
            th = math.radians(rotation)
            px = px + span * math.sin(th)
            py = py + span * math.cos(th)
        # Footprint body AABB (axis-aligned bounding box) on the PCB.
        body_xmin, body_xmax = px - half_x, px + half_x
        body_ymin, body_ymax = py - half_y, py + half_y
        for db_ref, (x_min, x_max, y_min, y_max) in shadows.items():
            # Exempt the daughterboard's own mounting sockets.
            if ref in _DAUGHTERBOARD_MOUNTING_SOCKETS.get(db_ref, frozenset()):
                continue
            # AABB-vs-AABB intersection test.
            if (body_xmax < x_min or body_xmin > x_max
                    or body_ymax < y_min or body_ymin > y_max):
                continue
            budget = DAUGHTERBOARD_Z_CLEARANCE[db_ref]
            if height > budget:
                margin = budget - height
                violations.append(
                    f"  {ref:>6}  {fp_prop:<60}  at ({px:+7.2f}, {py:+7.2f}) "
                    f"height={height:5.2f} mm  under {db_ref} (budget {budget:.2f} mm)  "
                    f"margin={margin:+5.2f} mm"
                )
    return violations


def _build_pcb_ref_to_footprint() -> dict[str, str]:
    """Parse the freshly-written oas.kicad_pcb and return a mapping of
    `Reference` (e.g. "R5") → fully-qualified footprint string
    (e.g. "Resistor_SMD:R_0603_1608Metric").

    Reads each `(footprint ...)` block (each at the start of a line, with
    optional leading whitespace — KiCad pretty-prints nested blocks with
    tab/space indentation, so the regex must tolerate that to capture all
    76 placed footprints rather than only the 45 written at column 0).
    For each block, extracts its inner `(property "Footprint" "...")`
    clause (which is the canonical source-of-truth — `_emit_stock_lib_footprint`
    writes a fully-qualified `Lib:Name` string, and
    `_emit_two_pad_smd_footprint` / inline helpers write a bare `Name`
    that we lib-qualify via `BARE_FOOTPRINT_TO_LIB`). The fallback (no
    `(property "Footprint" ...)` at all) uses the footprint block header
    name, also lib-qualified via the table.

    Every value in the returned dict is GUARANTEED to contain `:` (a real
    library prefix). If any bare name escaped the lookup table, this
    function `assert`-fails so the missing entry is caught at generate time
    rather than as a downstream ERC warning.

    Note on the regex: `(?m)^\\s*\\(footprint "..."` requires the
    `(footprint` token to be the first non-whitespace content on its line.
    Verified (v0.25) that the file contains no nested `(footprint "..."`
    references — every match in `oas.kicad_pcb` is a real top-level
    placed-footprint instance. Match count is exactly 76, equal to the
    kiutils enumeration of placed footprints.
    """
    import re

    text = (HERE / "oas.kicad_pcb").read_text(encoding="utf-8")
    mapping: dict[str, str] = {}

    # Walk every `(footprint "<libname>:<fpname>" ...)` block. For each,
    # extract its `(property "Reference" "<R>" ...)` and use the footprint
    # name from its header as the Footprint property value.
    # The regex allows optional leading whitespace because gen_pcb() emits
    # some footprint blocks with tab/space indentation (KiCad-style nested
    # block pretty-printing). v0.24's column-0-only regex silently skipped
    # 31 of 76 placed footprints, leaving 27 schematic-side empty Footprint
    # properties; v0.25 closes that gap.
    fp_starts = [m.start() for m in re.finditer(r'(?m)^\s*\(footprint "([^"]+)"', text)]
    # Append end of file to bound the last block.
    fp_starts.append(len(text))
    for i in range(len(fp_starts) - 1):
        block = text[fp_starts[i]:fp_starts[i + 1]]
        # Block may begin with the leading whitespace captured by `\s*` —
        # use search rather than match so we don't depend on column-0 here.
        m_name = re.search(r'\(footprint "([^"]+)"', block)
        if not m_name:
            continue
        fp_name_header = m_name.group(1)
        # Inside this block, the FIRST `(property "Reference" "..."` line is
        # the reference designator for the placed footprint. The
        # `(property "Footprint" "..."` clause is the authoritative
        # library-path string (may be bare for inline footprints, qualified
        # for stock-library footprints).
        m_ref = re.search(r'\(property "Reference" "([^"]+)"', block)
        if not m_ref:
            continue
        ref = m_ref.group(1)
        m_fp_prop = re.search(r'\(property "Footprint" "([^"]*)"', block)
        raw = m_fp_prop.group(1) if (m_fp_prop and m_fp_prop.group(1)) else fp_name_header
        if ":" in raw:
            canonical = raw
        else:
            # Bare name — lib-qualify via the lookup table.
            lib = BARE_FOOTPRINT_TO_LIB.get(raw)
            assert lib is not None, (
                f"BARE_FOOTPRINT_TO_LIB missing entry for {raw!r} "
                f"(used by footprint reference {ref!r}). Add the appropriate "
                f"library nickname to BARE_FOOTPRINT_TO_LIB in boardgen/_postprocess.py."
            )
            canonical = f"{lib}:{raw}"
        mapping[ref] = canonical

    # Sanity check: every mapped value must be lib-qualified. This catches
    # any regression where a new bare-name generator is added without a
    # matching BARE_FOOTPRINT_TO_LIB entry.
    for ref, fp in mapping.items():
        assert ":" in fp, f"Footprint mapping for {ref!r} is not lib-qualified: {fp!r}"
    return mapping


def _build_lcsc_metadata_map() -> dict[tuple[str, str], tuple[str, str, str]]:
    """Return `(Value, Footprint)` -> `(Manufacturer, MPN, LCSC)` from the
    canonical Python dict in `lcsc_mapping.py`.

    Used by `_apply_schematic_lcsc_metadata` to inject supply-chain sourcing
    metadata into every schematic symbol instance, so the same data that
    drives the BOM is visible inside the schematic editor (and exportable
    via `kicad-cli sch export bom --fields`).

    Skips DEPRECATED rows (LCSC starts with "DEPRECATED-") — those are
    sentinel entries kept only to detect pre-v0.36 regenerated schematics
    and have no matching schematic symbol.
    """
    import sys as _sys
    _sys.path.insert(0, str(HERE))
    from lcsc_mapping import LCSC_MAPPING  # noqa: E402

    result: dict[tuple[str, str], tuple[str, str, str]] = {}
    for (value, footprint), entry in LCSC_MAPPING.items():
        lcsc = entry.get("lcsc", "").strip()
        if lcsc.startswith("DEPRECATED-"):
            continue
        mfr = entry.get("manufacturer", "").strip()
        mpn = entry.get("mpn", "").strip()
        result[(value, footprint)] = (mfr, mpn, lcsc)
    return result


def _apply_schematic_lcsc_metadata(
    content: str,
    lcsc_map: dict[tuple[str, str], tuple[str, str, str]],
) -> str:
    """Post-process a sub-sheet schematic string, injecting three new
    properties on every real-component symbol instance whose
    `(Value, Footprint)` pair appears in `lcsc-mapping.csv`:

      - `(property "Manufacturer" "...")`
      - `(property "MPN" "...")`
      - `(property "LCSC" "...")`

    All three are emitted as HIDDEN properties at position (0, 0) so
    they don't clutter the schematic rendering, but they become part
    of the symbol's data and are picked up by `kicad-cli sch export
    bom --fields "Value,Reference,Footprint,Manufacturer,MPN,LCSC,..."`.

    This closes the v0.37 user concern "projekt sobie, BOM sobie": the
    schematic is now self-sufficient for BOM generation. The
    `lcsc-mapping.csv` post-process in `export_production.py` still
    runs as a defensive cross-check, but a kicad-cli BOM export that
    skips the post-process will still carry full sourcing metadata.

    Walks each top-level `(symbol ...)` block. For each block whose
    `Reference` is non-`#`-prefixed (i.e. a real component, not a
    power flag) AND whose `(Value, Footprint)` pair has a mapping
    entry, inserts the three new properties immediately after the
    last existing `(property ...)` block (right before the first
    `(pin ` or `(instances ` clause).

    Deterministic UUIDs derived from the symbol's Reference so the
    schematic file stays bit-identical across regenerations.
    """
    import re

    out_parts: list[str] = []
    i = 0
    n = len(content)
    while i < n:
        idx = content.find("(symbol", i)
        if idx == -1:
            out_parts.append(content[i:])
            break
        out_parts.append(content[i:idx])
        # Find matching close paren of the (symbol ...) block.
        depth = 0
        j = idx
        while j < n:
            ch = content[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = content[idx:j]

        # Extract Reference; skip power flags / virtual symbols.
        m_ref = re.search(r'\(property "Reference" "([^"]+)"', block)
        if m_ref and not m_ref.group(1).startswith("#"):
            ref = m_ref.group(1)
            m_val = re.search(r'\(property "Value" "([^"]+)"', block)
            m_fp = re.search(r'\(property "Footprint" "([^"]*)"', block)
            if m_val and m_fp:
                value = m_val.group(1)
                footprint = m_fp.group(1)
                metadata = lcsc_map.get((value, footprint))
                if metadata:
                    mfr, mpn, lcsc = metadata
                    # Find the END of the last `(property ...)` block inside
                    # this symbol. Properties appear sequentially before the
                    # first `(pin ` clause; we walk depth-counting to locate
                    # each property's close paren and take the last one.
                    last_prop_end = _find_last_property_end(block)
                    if last_prop_end is not None:
                        new_props = _emit_schematic_metadata_properties(
                            ref, mfr, mpn, lcsc,
                        )
                        block = block[:last_prop_end] + new_props + block[last_prop_end:]
        out_parts.append(block)
        i = j
    return "".join(out_parts)


def _find_last_property_end(block: str) -> int | None:
    """Return the position (offset within `block`) immediately AFTER the
    closing `)` of the LAST top-level `(property "..." ...)` clause
    inside the symbol block. Returns None if no property is found."""
    last_end: int | None = None
    pos = 0
    while True:
        idx = block.find('(property "', pos)
        if idx == -1:
            break
        # Walk depth to find matching close.
        depth = 0
        k = idx
        while k < len(block):
            ch = block[k]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    k += 1
                    last_end = k
                    pos = k
                    break
            k += 1
        else:
            break
    return last_end


def _emit_schematic_metadata_properties(
    reference: str, manufacturer: str, mpn: str, lcsc: str,
) -> str:
    """Render three hidden schematic properties (Manufacturer, MPN, LCSC)
    matching the standard KiCad schematic property block format used by
    Reference/Value/Footprint/Datasheet/Description (no `(uuid ...)`
    clause — schematic symbol-instance properties don't carry UUIDs;
    only the symbol itself has a UUID). Hidden at position (0, 0)
    — they exist for BOM export only, never rendered."""
    # `reference` accepted for API symmetry with _apply_schematic_lcsc_metadata
    # but unused — schematic property blocks are not UUID-stamped.
    _ = reference

    def _prop(name: str, value: str) -> str:
        # Escape any embedded quotes in the value.
        safe = value.replace('"', '\\"')
        return (
            f'\n\t\t(property "{name}" "{safe}"\n'
            f'\t\t\t(at 0 0 0)\n'
            f'\t\t\t(effects\n'
            f'\t\t\t\t(font\n'
            f'\t\t\t\t\t(size 1.27 1.27)\n'
            f'\t\t\t\t)\n'
            f'\t\t\t\t(hide yes)\n'
            f'\t\t\t)\n'
            f'\t\t)'
        )

    return (
        _prop("Manufacturer", manufacturer)
        + _prop("MPN", mpn)
        + _prop("LCSC", lcsc)
    )


def _apply_schematic_footprints(content: str, ref_to_fp: dict[str, str]) -> str:
    """Post-process a sub-sheet schematic string, replacing every
    `(property "Footprint" "")` field of a real-component symbol instance
    with `(property "Footprint" "<libname>:<fpname>")` looked up from the
    PCB-side mapping. Symbols whose Reference begins with `#` (power /
    flag markers) are left untouched because they have no physical
    footprint on the PCB.

    Walks each top-level `(symbol ...)` block, reads its Reference, and
    if a non-#-prefixed Reference has a mapped footprint, rewrites the
    block's first `(property "Footprint" "")` occurrence.
    """
    import re

    # Find each (symbol ...) block at the top level. Use a depth-counter.
    out_parts: list[str] = []
    i = 0
    n = len(content)
    while i < n:
        idx = content.find("(symbol", i)
        if idx == -1:
            out_parts.append(content[i:])
            break
        # Copy text before the block as-is.
        out_parts.append(content[i:idx])
        # Find matching close paren.
        depth = 0
        j = idx
        while j < n:
            ch = content[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = content[idx:j]
        # Extract Reference. The first `(property "Reference" "..."` inside
        # the block is the designator.
        m_ref = re.search(r'\(property "Reference" "([^"]+)"', block)
        if m_ref:
            ref = m_ref.group(1)
            fp_value = ref_to_fp.get(ref)
            if fp_value and not ref.startswith("#"):
                # Rewrite first `(property "Footprint" "")` -> `("Footprint" "<fp>")`.
                # Use count=1 so only the schematic-symbol-instance Footprint
                # property is touched (lib_symbol templates handled in the
                # `(symbol ...)` library section at top of file have their
                # own `(property "Footprint" "")` which stays untouched
                # because library-template symbols live INSIDE the
                # `(lib_symbols ...)` block, not at top level — but defensive
                # count=1 keeps the behavior deterministic regardless).
                block = block.replace(
                    '(property "Footprint" ""',
                    f'(property "Footprint" "{fp_value}"',
                    1,
                )
        out_parts.append(block)
        i = j
    return "".join(out_parts)
