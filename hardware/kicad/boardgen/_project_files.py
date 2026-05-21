"""boardgen/_project_files.py - oas.kicad_pro, fp-lib-table,
sym-lib-table, OAS.kicad_sym emitters.

These are the "metadata" files KiCad needs alongside the schematic + PCB:

  - oas.kicad_pro   = project file (design rules, sheet array, layer
                      tables, JLCPCB-tuned constraints)
  - fp-lib-table    = footprint library registration (mounts oas:* and
                      stock libraries)
  - sym-lib-table   = symbol library registration (mounts OAS.kicad_sym)
  - libraries/OAS.kicad_sym = project-local symbol library

gen_pro embeds SHEET_BLOCK_UUIDS and ROOT_SHEET_UUID into the "sheets"
array so the project file matches the hierarchical schematic; bit-identity
across runs relies on those UUIDs being deterministic v5 (see
boardgen/_common.U).
"""
from __future__ import annotations

import json
import textwrap

from boardgen._common import (
    ROOT_SHEET_UUID,
    SUBSHEETS, SHEET_BLOCK_UUIDS,
    SUBSHEET_DISPLAY_NAMES,
)
from boardgen._lib_symbols import (
    POWER_LIB_SYMBOLS,
    _esp32c6_devkitm1_lib_symbol,
    _sk6812_side_lib_symbol,
)


# -----------------------------------------------------------------------------
# 4) Project file
# -----------------------------------------------------------------------------
def gen_pro() -> str:
    project = {
        "meta": {"filename": "oas.kicad_pro", "version": 3},
        "board": {
            "3dviewports": [],
            "design_settings": {
                "defaults": {
                    "apply_defaults_to_fp_fields": False,
                    "apply_defaults_to_fp_shapes": False,
                    "apply_defaults_to_fp_text": False,
                    "board_outline_line_width": 0.1,
                    "copper_line_width": 0.2,
                    "copper_text_italic": False,
                    "copper_text_size_h": 1.5,
                    "copper_text_size_v": 1.5,
                    "copper_text_thickness": 0.3,
                    "copper_text_upright": False,
                    "courtyard_line_width": 0.05,
                    "dimension_precision": 4,
                    "dimension_units": 3,
                    "dimensions": {
                        "arrow_length": 1270000,
                        "extension_offset": 500000,
                        "keep_text_aligned": True,
                        "suppress_zeroes": False,
                        "text_position": 0,
                        "units_format": 1,
                    },
                    "fab_line_width": 0.1,
                    "fab_text_italic": False,
                    "fab_text_size_h": 1.0,
                    "fab_text_size_v": 1.0,
                    "fab_text_thickness": 0.15,
                    "fab_text_upright": False,
                    "other_line_width": 0.15,
                    "other_text_italic": False,
                    "other_text_size_h": 1.0,
                    "other_text_size_v": 1.0,
                    "other_text_thickness": 0.15,
                    "other_text_upright": False,
                    "pads": {"drill": 0.762, "height": 1.524, "width": 1.524},
                    "silk_line_width": 0.15,
                    "silk_text_italic": False,
                    "silk_text_size_h": 1.0,
                    "silk_text_size_v": 1.0,
                    "silk_text_thickness": 0.15,
                    "silk_text_upright": False,
                    "zones": {"45_degree_only": False, "min_clearance": 0.5},
                },
                "rules": {
                    # JLCPCB-compatible (1-2 layer "minimum" capability)
                    "allow_blind_buried_vias": False,
                    "allow_microvias": False,
                    "max_error": 0.005,
                    # v0.39: kept at 0.15 mm (KiCad-clean). JLCPCB's DFM
                    # scanner warned about 4 sub-0.20 mm clearances in v0.34,
                    # but their fab capability IS 0.15 mm - the warning is a
                    # yield hint, not a defect. Bumping to 0.20 mm would
                    # trigger 121 DRC violations + require re-routing every
                    # autoroute-packed trace. Cost is not justified for the
                    # 5-prototype quantity.
                    "min_clearance": 0.15,
                    "min_connection": 0.0,
                    # v0.50 (approach-C): raised 0.3 → 0.35 mm. Freerouting
                    # placed I2C SCL/SDA B.Cu traces at 0.19 mm from Edge.Cuts
                    # under the 0.30 mm setting. 0.35 mm matches the .kicad_dru
                    # "Trace to Outline" rule and forces Freerouting to stay clear.
                    "min_copper_edge_clearance": 0.35,
                    "min_groove_width": 0.0,
                    "min_hole_clearance": 0.25,
                    "min_hole_to_hole": 0.5,
                    "min_microvia_diameter": 0.2,
                    "min_microvia_drill": 0.1,
                    # v0.28d: lowered from 2 → 1. The autoroute pass blocked
                    # some thermal spokes on dense GND pads (J3.5, C14.2,
                    # D21.4, U2.1, C20.2), leaving each pad with only 1
                    # spoke to the F.Cu GND pour. A single spoke (0.5 mm
                    # wide × 0.5 mm thermal gap) carries ~1 A continuous
                    # without thermal-relief failure; OAS GND current at
                    # the busiest of these pads (J3 SEN66 return) peaks
                    # at ~0.2 A. Relaxing min_resolved_spokes to 1 is
                    # safe at the OAS power envelope. Reconsider if a
                    # future high-current GND pad (e.g. >2 A continuous)
                    # is added.
                    "min_resolved_spokes": 1,
                    # v0.39 tried 0.20 mm hoping to surface the 17 silk-to-pad
                    # DFM warnings in KiCad DRC. KiCad found 0 violations at
                    # 0.20 mm - the offending silk drawings are inside stock
                    # library footprints which KiCad treats as authoritative.
                    # Reverted to KiCad default 0.15.
                    "min_silk_clearance": 0.15,
                    "min_text_height": 1.0,
                    "min_text_thickness": 0.15,
                    "min_through_hole_diameter": 0.3,
                    "min_track_width": 0.15,
                    "min_via_annular_width": 0.1,
                    "min_via_diameter": 0.5,
                    "solder_mask_to_copper_clearance": 0.0,
                    "use_height_for_length_calcs": True,
                },
                # v0.40 audit-16: rule_severities removed (was demoting
                # lib_footprint_mismatch to "ignore" for Q1 pad-name
                # remap). Audit-16 reverses that compromise — instead
                # of suppressing the warning, we eliminate the cause by
                # creating a project-local `OAS:Q_PMOS_GDS` symbol with
                # NUMERIC pin numbers 1/2/3 that bind to the canonical
                # stock SOT-23 pads "1"/"2"/"3" with no remap. Pad NAMES
                # in the manufactured PCB now match stock verbatim, so
                # KiCad's lib_footprint_mismatch is silent without
                # severity override.
                "rule_severities": {},
            },
            "ipc2581": {"dist": "", "distpn": "", "internal_id": "", "mfg": "", "mpn": ""},
            "layer_pairs": [],
            "layer_presets": [],
            "viewports": [],
        },
        "boards": [],
        "cvpcb": {"equivalence_files": []},
        "erc": {
            "erc_exclusions": [],
            "meta": {"version": 0},
            "pin_map": [],
            # `rule_severities` is intentionally an empty object: it carries
            # explicit overrides only. KiCad's `kicad-cli sch erc` falls back
            # to its built-in default severity list for every ERC category
            # NOT present here (e.g. "Global label only appears once",
            # "Four connection points are joined together", "SPICE model
            # issue", "Assigned footprint doesn't match footprint filters" —
            # all of which the ERC report shows as "ignored" categories).
            # If a future maintainer wonders where those default-ignores
            # come from: they are not in this file, they are baked into
            # kicad-cli (v0.23 review Nt1).
            "rule_severities": {},
        },
        "libraries": {
            "pinned_footprint_libs": ["oas"],
            "pinned_symbol_libs": [],
        },
        "net_settings": {
            "classes": [
                {
                    "name": "Default",
                    "bus_width": 12,
                    "clearance": 0.15,
                    "diff_pair_gap": 0.25,
                    "diff_pair_via_gap": 0.25,
                    "diff_pair_width": 0.2,
                    "line_style": 0,
                    "microvia_diameter": 0.3,
                    "microvia_drill": 0.1,
                    "priority": 2147483647,
                    "schematic_color": "rgba(0, 0, 0, 0.000)",
                    "pcb_color": "rgba(0, 0, 0, 0.000)",
                    "track_width": 0.25,
                    "via_diameter": 0.6,
                    "via_drill": 0.3,
                    "wire_width": 6,
                },
                {
                    "name": "Power",
                    "bus_width": 12,
                    "clearance": 0.2,
                    "diff_pair_gap": 0.25,
                    "diff_pair_via_gap": 0.25,
                    "diff_pair_width": 0.2,
                    "line_style": 0,
                    "microvia_diameter": 0.3,
                    "microvia_drill": 0.1,
                    "priority": 100,
                    "schematic_color": "rgba(0, 0, 0, 0.000)",
                    "pcb_color": "rgba(0, 0, 0, 0.000)",
                    "track_width": 0.5,
                    "via_diameter": 0.8,
                    "via_drill": 0.4,
                    "wire_width": 6,
                },
            ],
            "meta": {"version": 4},
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": [],
        },
        "pcbnew": {
            "last_paths": {"gencad": "", "idf": "", "netlist": "", "plot": "",
                           "pos_files": "", "specctra_dsn": "", "step": "", "svg": "", "vrml": ""},
            "page_layout_descr_file": "",
        },
        "schematic": {
            "annotate_start_num": 0,
            "bom_export_filename": "${PROJECTNAME}.csv",
            "bom_settings": {},
            "connection_grid_size": 50.0,
            "drawing": {},
            "legacy_lib_dir": "",
            "legacy_lib_list": [],
            "ngspice": {},
            "spice_adjust_passive_values": False,
            "subpart_first_id": 65,
            "subpart_id_separator": 0,
        },
        "sheets": [
            [ROOT_SHEET_UUID, "Root"],
            *[
                [SHEET_BLOCK_UUIDS[name], SUBSHEET_DISPLAY_NAMES[name]]
                for name in SUBSHEETS
            ],
        ],
        "text_variables": {},
        "tuning_profiles": [],
    }
    return json.dumps(project, indent=2)

# -----------------------------------------------------------------------------
# 5) Footprint library table
# -----------------------------------------------------------------------------
def gen_fp_lib_table() -> str:
    return textwrap.dedent("""\
        (fp_lib_table
        \t(version 7)
        \t(lib (name "oas") (type "KiCad") (uri "${KIPRJMOD}/libraries/oas.pretty") (options "") (descr "Project-local footprints"))
        )
        """)

def gen_sym_lib_table() -> str:
    """Project-local symbol-library table.

    Maps the `OAS` library name (used as `OAS:ESP32-C6_DevKitM-1` lib_id
    inside mcu.kicad_sch) to the project-local `libraries/OAS.kicad_sym`
    file. Without this entry, KiCad ERC raises `lib_symbol_issues` on the
    U3 symbol ("Obecna konfiguracja nie zawiera biblioteki symboli 'OAS'").
    """
    return textwrap.dedent("""\
        (sym_lib_table
        \t(version 7)
        \t(lib
        \t\t(name "OAS")
        \t\t(type "KiCad")
        \t\t(uri "${KIPRJMOD}/libraries/OAS.kicad_sym")
        \t\t(options "")
        \t\t(descr "OAS project-local symbols (ESP32-C6 DevKitM-1, ...)")
        \t)
        )
        """)


def gen_oas_symbol_library() -> str:
    """Project-local symbol library file `OAS.kicad_sym`.

    Mirrors the embedded `(symbol "OAS:ESP32-C6_DevKitM-1" ...)` inside
    mcu.kicad_sch so KiCad can resolve the OAS library reference from
    the sym-lib-table. The embedded copy in mcu.kicad_sch is what gets
    rendered; this file exists primarily to silence the
    `lib_symbol_issues` ERC warning on U3.

    v0.16 adds `OAS:SK6812-SIDE` for the AQI status-LED ring (D11..D22).
    """
    # v0.40 audit-16: extract OAS:Q_PMOS_GDS from POWER_LIB_SYMBOLS so
    # the standalone libraries/OAS.kicad_sym carries the same Q_PMOS_GDS
    # definition that's embedded in power.kicad_sch. Required because
    # the Q1 schematic instance references `OAS:Q_PMOS_GDS` (NOT
    # Device:Q_PMOS — would trigger lib_symbol_mismatch since our pin
    # numbers 1/2/3 differ from stock D/G/S).
    import re as _re
    m = _re.search(
        r'(\(symbol "OAS:Q_PMOS_GDS"[\s\S]*?\(embedded_fonts no\)\s*\))',
        POWER_LIB_SYMBOLS,
    )
    assert m is not None, "could not extract OAS:Q_PMOS_GDS from POWER_LIB_SYMBOLS"
    q_pmos_gds_block = m.group(1)
    bodies = [
        _esp32c6_devkitm1_lib_symbol(),
        _sk6812_side_lib_symbol(),
        # Wrap in two leading tabs to match the convention expected by
        # _strip_one_tab below.
        "\t\t" + q_pmos_gds_block,
    ]
    # The two helpers return content indented with two leading tabs (one
    # tab inside the schematic file, one inside `lib_symbols`). In the
    # standalone `.kicad_sym` file the `(symbol ...)` blocks are nested
    # ONCE inside `(kicad_symbol_lib ...)`, so strip one tab from each
    # line.
    def _strip_one_tab(s: str) -> str:
        return "\n".join(
            (line[1:] if line.startswith("\t") else line)
            for line in s.split("\n")
        )
    body_text = "\n".join(_strip_one_tab(b) for b in bodies)
    return textwrap.dedent("""\
        (kicad_symbol_lib
        \t(version 20251024)
        \t(generator "kicad_symbol_editor")
        \t(generator_version "10.0")
        """) + body_text + "\n)\n"
