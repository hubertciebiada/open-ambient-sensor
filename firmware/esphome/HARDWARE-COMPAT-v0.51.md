# ⚠ This firmware targets OAS hardware **v0.51** — read before flashing

`project_version` is set to `v0.51` (shown in the boot log and Home Assistant).
This firmware contains a **board-revision-specific workaround** that will BREAK
the air-quality sensor if flashed onto a corrected board. Do not "tidy it up".

## v0.51-specific behaviour

### 1. I²C SDA/SCL are intentionally SWAPPED (`packages/air-quality.yaml`)
The bus is declared `sda: GPIO7 / scl: GPIO6` — the **opposite** of the schematic
(GPIO6 = SDA, GPIO7 = SCL). On the v0.51 board the SEN66's SDA/SCL reach the
opposite ESP GPIOs — a **J3 pinout error on the board**. The JST-GH lead is a
straight 1:1 cable (the crossing is NOT in the cable). The firmware swap cancels
the board error so the SEN66 ACKs at 0x6B and reports real readings with a
**straight cable** (no cable surgery).

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

### 2. NFC removed entirely (issue #7 — resolved)
The dynamic NFC tag feature is **gone**: `packages/nfc.yaml` is deleted from the
firmware and the MIKROE-2462 / NT3H1101 hardware (MOD2, J7, J8, C12, the NFC_FD
net) is removed from the next board revision. NFC RF coupling was unusable
through the AK-N-94 cover (antenna over the ground plane + distance), and the
only workable fix would have broken the enclosure aesthetics. On the five v0.51
prototype boards the J7/J8 footprints + MOD2 silk remain physically present but
unpopulated and unused. This is also why the SDA/SCL swap above is safe (NFC
was the only other I²C consumer).

### 3. LED ring `num_leds: 7`
Matches the actual board (D11..D18, D13 skipped). Earlier firmware said 11.

## Summary of which firmware goes on which board
| Board | J3 pinout | SEN66 cable | I²C pins in firmware |
|---|---|---|---|
| **v0.51 (this)** | SDA/SCL swapped (error) | straight 1:1 | `sda: GPIO7 / scl: GPIO6` (swapped) |
| Fixed rev (issue #6) | corrected | straight 1:1 | `sda: GPIO6 / scl: GPIO7` (schematic) |
