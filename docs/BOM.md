# Bill of materials

**Status:** preliminary draft. Component selections are not final — see `CLAUDE.md` and `ARCHITECTURE.md` for the rationale.

The production BOM is split across three sources:

- [`hardware/bom/bom-jlcpcb.csv`](../hardware/bom/bom-jlcpcb.csv) — JLCPCB assembly (Basic + Extended Library parts) — **TODO**
- [`hardware/bom/bom-mouser.csv`](../hardware/bom/bom-mouser.csv) — Mouser parts not stocked at JLCPCB — **TODO**
- [`hardware/bom/bom-misc.md`](../hardware/bom/bom-misc.md) — locally-sourced items (enclosure, sensor modules, cables)

## Per-unit cost target

To be determined once the BOM is finalised. The project explicitly accepts a higher per-unit cost than the cheapest DIY alternatives in exchange for the two design pillars (measurement quality, aesthetic acceptability) — see [`CLAUDE.md`](../CLAUDE.md#design-philosophy).

## Sourcing notes

- Prefer **JLCPCB Basic Library** parts (free assembly) where they meet both design pillars
- Extended Library parts (~$3 setup fee) are acceptable when no Basic alternative qualifies
- Validate prices in **production quantity** (typical batch: 5–20 units), not single-piece pricing
- Do not propose parts that are known to be EOL or perpetually out of stock
- Cross-check stock against manufacturer the **same day** as ordering

## Open BOM items

- [ ] Buck 24 V → 5 V — final IC selection
- [ ] Buck 24 V → 3.3 V — final IC selection
- [ ] External I²C ESD protection — PESD3V3L4UG candidate
- [ ] NFC antenna matching capacitor — value derived from antenna geometry per NXP AN11203
- [ ] Decoupling and bulk capacitance review on each power rail
