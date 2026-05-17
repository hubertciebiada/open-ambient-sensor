# Miscellaneous BOM — locally-sourced items

Items that are not ordered through JLCPCB or Mouser and need to be sourced separately. **Draft.**

| Item | Quantity per unit | Source | Notes |
|---|---|---|---|
| SZOMK AK-N-94 enclosure | 1 | <https://www.chinaenclosure.com> | Ø128 mm perforated white ABS |
| Sensirion SEN66 module | 1 | Sensirion / Mouser / Digi-Key | Combo air-quality sensor; PCB-mount face-up (lies flat on its back face, openings face up toward AK-N-94 cover perforations — v0.6 reversed the earlier cover-mount plan) |
| HiLink HLK-LD2410B module | 1 | AliExpress / HiLink direct | mmWave presence radar (specifically the -B variant, NOT -C — pin order and body dimensions differ between variants per HLK datasheets) |
| JST GH 6-pin cable (50 cm) | 1 | Sensirion accessory or generic AWG26 6-pin JST GH | Connects SEN66 module to PCB-mounted J3 socket. 50 cm reference length (Sensirion accessory) — actual run length inside AK-N-94 is < 100 mm. |
| 24 V DC PSU | 1 (shared across deployment) | generic | Bus power for multi-unit installations |

## Open items

- [ ] Validate enclosure pricing and lead time at batch quantity (typical: 5–20 units)
- [ ] Confirm SEN66 distributor with the best stock for European delivery
- [ ] Decide whether to ship the JST GH cable pre-crimped or provide a crimp instruction
