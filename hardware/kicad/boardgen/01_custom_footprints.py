"""boardgen stage 01: write the 8 custom .kicad_mod files.

These project-local footprints live under libraries/oas.pretty/ and
cover mechanical references + the 4020 side-emit SK6812 LED + the
Littelfuse-1812L PTC fuse land — none have a usable KiCad stock
equivalent (the SK6812 SIDE package and the 1812L termination geometry
are both absent from / mismatched by the stock libraries).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from boardgen._common import HERE
from boardgen._footprints import (
    gen_mounting_hole_footprint,
    gen_sen66_mechanical_footprint,
    gen_ziptie_hole_footprint,
    gen_ld2410_mechanical_footprint,
    gen_sk6812_side_footprint,
    gen_fuse_1812l_footprint,
    gen_daughterboard_mech_lib_file,
)
from boardgen._project import (
    ESP32_BODY_W, ESP32_BODY_L, ESP32_PIN_ROW_INSET, ESP32_PIN_PITCH,
    ESP32_PIN_COUNT_PER_ROW, ESP32_PIN_START_OFFSET,
    MIKROE2462_BODY_W, MIKROE2462_BODY_L,
    MIKROE2462_PIN_ROW_INSET, MIKROE2462_PIN_PITCH,
    MIKROE2462_PIN_COUNT_PER_ROW, MIKROE2462_PIN_START_OFFSET,
)


def run(ctx) -> None:
    (HERE / "libraries" / "oas.pretty").mkdir(parents=True, exist_ok=True)

    (HERE / "libraries" / "oas.pretty" / "MountingHole_3.8mm_M3.kicad_mod").write_text(
        gen_mounting_hole_footprint(), encoding="utf-8"
    )
    (HERE / "libraries" / "oas.pretty" / "SEN66_Mechanical_Reference.kicad_mod").write_text(
        gen_sen66_mechanical_footprint(), encoding="utf-8"
    )
    (HERE / "libraries" / "oas.pretty" / "ZipTieHole_3mm_NPTH.kicad_mod").write_text(
        gen_ziptie_hole_footprint(), encoding="utf-8"
    )
    (HERE / "libraries" / "oas.pretty" / "LD2410_Mechanical_Reference.kicad_mod").write_text(
        gen_ld2410_mechanical_footprint(), encoding="utf-8"
    )
    (HERE / "libraries" / "oas.pretty" / "ESP32-C6-DevKitM-1_Reference.kicad_mod").write_text(
        gen_daughterboard_mech_lib_file(
            name="ESP32-C6-DevKitM-1_Reference",
            descr="Espressif ESP32-C6-DevKitM-1-N4 daughterboard mechanical reference (no pads). EAN 5904422385651. Body 25.4×48.26×8.6 mm. Mounts on 2× 1x15 P2.54 mm female pin sockets; antenna at one short edge, dual USB-C at the other. Pin block offset 0.98 mm toward antenna end per Espressif dimensions PDF.",
            body_w=ESP32_BODY_W, body_l=ESP32_BODY_L,
            pin_row_inset=ESP32_PIN_ROW_INSET,
            pin_pitch=ESP32_PIN_PITCH,
            pin_count_per_row=ESP32_PIN_COUNT_PER_ROW,
            body_label="ESP32-C6 DevKitM-1",
            antenna_label="ant",
            usb_label="USB",
            uuid_tag="esp32-devkitm1",
            pin_start_offset=ESP32_PIN_START_OFFSET,
        ),
        encoding="utf-8",
    )
    (HERE / "libraries" / "oas.pretty" / "MIKROE-2462_Reference.kicad_mod").write_text(
        gen_daughterboard_mech_lib_file(
            name="MIKROE-2462_Reference",
            descr="MikroElektronika NFC Tag 2 Click (NT3H1101 NTAG I²C plus + onboard PCB antenna) daughterboard mechanical reference (no pads). Body 25.4×57.15×7 mm per mikroBUS size L spec. Pin block offset 2.54 mm toward pin-1 short edge; NFC antenna spiral on the ~36.83 mm strip past pin 8.",
            body_w=MIKROE2462_BODY_W, body_l=MIKROE2462_BODY_L,
            pin_row_inset=MIKROE2462_PIN_ROW_INSET,
            pin_pitch=MIKROE2462_PIN_PITCH,
            pin_count_per_row=MIKROE2462_PIN_COUNT_PER_ROW,
            body_label="MIKROE-2462",
            antenna_label=None,
            usb_label=None,
            uuid_tag="mikroe2462",
            pin_start_offset=MIKROE2462_PIN_START_OFFSET,
        ),
        encoding="utf-8",
    )
    (HERE / "libraries" / "oas.pretty" / "SK6812-SIDE.kicad_mod").write_text(
        gen_sk6812_side_footprint(), encoding="utf-8",
    )
    (HERE / "libraries" / "oas.pretty" / "Fuse_1812L_4532Metric.kicad_mod").write_text(
        gen_fuse_1812l_footprint(), encoding="utf-8",
    )


if __name__ == "__main__":
    from boardgen._common import Context
    run(Context())
