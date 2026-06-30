# ⚠ This firmware targets OAS hardware **v0.51** — read before flashing

`project_version` is set to `v0.51` (shown in the boot log and Home Assistant).
This firmware contains a **board-revision-specific workaround** that will BREAK
the air-quality sensor if flashed onto a corrected board. Do not "tidy it up".

## v0.51-specific behaviour

### 1. I²C SDA/SCL are intentionally SWAPPED (`packages/air-quality.yaml`)
The bus is declared `sda: GPIO7 / scl: GPIO6` — the **opposite** of the schematic
(GPIO6 = SDA, GPIO7 = SCL). The SEN66 JST-GH cable shipped with the v0.51
prototypes has SDA/SCL crossed; the firmware swap cancels that so the SEN66 ACKs
at 0x6B and reports real readings with the **as-shipped cable** (no cable surgery).

This is only safe because the SEN66 is the **only** device left on the I²C bus
(NFC was dropped — see below; the LD2410 is on UART). Caveat: it also swaps the
J9 Qwiic port, so a standard Qwiic device on a v0.51 board + this firmware would
need a crossed cable.

**Proper fix = GitHub issue #6** (correct J3's pinout so a straight cable works).
When that board revision exists:
- revert `air-quality.yaml` to `sda: GPIO6 / scl: GPIO7`,
- bump `project_version` in `oas.yaml`,
- delete or rewrite this file.

➡ **Never flash this firmware onto a board whose J3 pinout has been fixed** — the
double-swap would leave the SEN66 dead.

### 2. NFC package disabled (`oas.yaml`)
The `nfc:` include is commented out. NFC RF coupling is unusable through the
AK-N-94 cover (antenna over the ground plane + distance). Full removal is tracked
in **issue #7**. This is also why the SDA/SCL swap above is safe (NFC was the only
other I²C consumer).

### 3. LED ring `num_leds: 7`
Matches the actual board (D11..D18, D13 skipped). Earlier firmware said 11.

## Summary of which firmware goes on which board
| Board | SEN66 cable | I²C pins in firmware |
|---|---|---|
| **v0.51 (this)** | crossed (as shipped) | `sda: GPIO7 / scl: GPIO6` (swapped) |
| Fixed rev (issue #6) | straight | `sda: GPIO6 / scl: GPIO7` (schematic) |
