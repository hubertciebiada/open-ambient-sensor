# ⚠ Hardware ↔ firmware compatibility — v0.51 boards need pin overrides

The firmware DEFAULTS in `oas.yaml` target boards with the **corrected J3
pinout** (GitHub issue #6 fixed): `i2c_sda_pin: GPIO6` / `i2c_scl_pin: GPIO7`
— the schematic mapping. The five **v0.51** prototype boards (2026-05 run)
have **SDA/SCL crossed at J3** (the SEN66 socket) and MUST be flashed with a
substitution override that swaps the two pins.

They need a **second** override as well: v0.51 routes the LD2410 UART to
GPIO 16/17, which later boards vacated (`ld2410_tx_pin: GPIO1` /
`ld2410_rx_pin: GPIO0` are now the defaults). See "LD2410 UART pins" below.

➡ **Flashing the wrong mapping bricks the SEN66 either way** — the sensor is
powered but never ACKs at 0x6B (`[E][sen6x] Communication failed`, all
channels NA). Match the firmware to the board revision (check the silkscreen
version marking) before flashing.

## Which firmware goes on which board

| Board | J3 pinout | SEN66 cable | I²C substitutions | LD2410 UART substitutions |
|---|---|---|---|---|
| **v0.51** (five 2026-05 protos) | SDA/SCL crossed (error) | straight 1:1 | `i2c_sda_pin: GPIO7` / `i2c_scl_pin: GPIO6` — override, see below | `ld2410_tx_pin: GPIO16` / `ld2410_rx_pin: GPIO17` — override |
| Fixed rev (issue #6 landed) | mirror of SEN6x Table 16 (correct) | straight 1:1 | defaults (`GPIO6` / `GPIO7`) — no override | defaults (`GPIO1` / `GPIO0`) — no override |

## v0.51 override (exact snippet)

Create a per-device config that includes `oas.yaml` as a package and swaps
the pins (complete template: [`examples/v0.51-board.yaml`](examples/v0.51-board.yaml)):

```yaml
substitutions:
  device_id: room-a
  friendly_name: "Room A"
  i2c_sda_pin: GPIO7      # v0.51 board: J3 SDA/SCL crossed (issue #6)
  i2c_scl_pin: GPIO6
  ld2410_tx_pin: GPIO16   # v0.51 board: radar UART still on the console pins
  ld2410_rx_pin: GPIO17
  project_version: "v0.51"

packages:
  oas: !include ../oas.yaml
```

`!secret` resolution: ESPHome searches for `secrets.yaml` next to the file
that uses the tag (`packages/`) or next to the main config (`examples/`) —
NOT next to the packaged `oas.yaml`. Create a one-line uncommitted proxy
`examples/secrets.yaml` (the `**/secrets.yaml` gitignore covers it):

```yaml
<<: !include ../secrets.yaml
```

## Why v0.51 needs the swap (root cause — issue #6, bench-confirmed 2026-06-30)

The v0.51 J3 copied the SEN6x datasheet **Table 16** pinout (v0.92 Dec 2025,
p. 15 — 1=VDD, 2=GND, 3=SDA, 4=SCL, 5=GND, 6=VDD) pin-for-pin onto the
board-side socket. Table 16 is the **module side**. Both cable ends are
polarized JST GH-family connectors (the latch/shroud keying means housing
position N always mates header pin N), and a standard flat parallel-wire GH
lead has both housings crimped on the same face of the wire row — between
two face-to-face headers that maps position k to position 7−k, a full
positional mirror (1↔6, 2↔5, 3↔4). Sensirion's pinout is power-symmetric
(pins 1/6 and 2/5 internally tied), so the mirror is invisible on the power
pins and manifests ONLY as an SDA↔SCL swap: the SEN66 was powered but never
ACKed. Swapping the I²C pins in firmware cancels the board error — bring-up
confirmed the SEN66 then ACKs at 0x6B and reports real readings with a
straight cable (no cable surgery).

The corrected board (issue #6 fix) wires J3 as the MIRROR of Table 16
(1=VDD, 2=GND, **3=SCL, 4=SDA**, 5=GND, 6=VDD) so a straight flat lead lands
SDA→SDA / SCL→SCL and the defaults are correct. See CLAUDE.md **Lesson 21**;
enforced in CI by pipeline stage 19 check E.

Cable caveat (both revisions): the design standardizes on the **flat
parallel-wire** GH lead style — the style verified on the bench. An
opposite-crimp lead (housings on opposite faces of the wire row,
electrically position-1:1 — the Qwiic-cable style) would re-cross SDA/SCL.
Do NOT reuse a hand-crossed cable from the early v0.51 workaround era on a
corrected board (double-cross).

## LD2410 UART pins (v0.51 = GPIO 16/17, later boards = GPIO 1/0)

v0.51 wires J4's UART pair to the ESP32-C6's **U0TXD/U0RXD** (GPIO 16/17).
On the ESP32-C6-DevKitM-1 those two pads are also hard-wired, through
**populated 0 Ω links** (R9 → bridge RXD, R7 → bridge TXD), to the onboard
**CP2102N** USB-UART bridge — and that bridge's VDD/REGIN sit on `VCC_3V3`,
the board 3.3 V rail OAS feeds at J5.1, **not** on USB VBUS. The bridge is
therefore powered and driving whenever the unit is on, cable or no cable:
bench-probed on a v0.51 board (2026-07-22, radar unpowered, bridge USB port
empty) GPIO 17 read **DRIVEN HIGH** while GPIO 2 and GPIO 16 read floating.
The radar's Tx output and the bridge's TXD output share that node.

Later boards move the pair to **GPIO 1 (TX) / GPIO 0 (RX)** — free, adjacent
pads on the socket row nearest J4. See CLAUDE.md **Lesson 23**; enforced in
CI by the console-pin checks in pipeline stage 06.

On a v0.51 board the override restores communication with the module, but
the contention is physical and cannot be fixed in firmware — the presence
`binary_sensor` fed by the radar's **OUT** pin (GPIO 2) is unaffected and
stays the reliable signal there.

## Bus-wide side effect: J9 Qwiic port

The I²C mapping is bus-wide, so it also affects the J9 Qwiic port:

- corrected board + defaults → J9 is a **standard** Qwiic port;
- v0.51 board + override → a standard Qwiic device on J9 needs a
  **crossed** Qwiic cable.

## Applies to every revision (kept here for history)

- **NFC removed entirely** (issue #7): `packages/nfc.yaml` is gone and the
  MIKROE-2462 / NT3H1101 hardware (MOD2, J7, J8, C12, the NFC_FD net) is
  removed from the corrected board revision. On the five v0.51 boards the
  J7/J8 footprints + MOD2 silk remain physically present but unpopulated.
  With NFC gone the SEN66 is the only fixed I²C device (LD2410 is UART),
  which is why the v0.51 pin-swap override is safe on the shared bus.
- **LED ring `num_leds: 7`** matches every board (D11..D18, D13 skipped).
