# SZOMK AK-N-94 enclosure

Verification of the OAS reference enclosure against publicly available
manufacturer and distributor sources. Where the public listing data was
ambiguous or thin, that fact is recorded honestly rather than papered over —
mechanical detail beyond the high-level dimensions sits behind a sales-contact
wall at SZOMK, and only the physical sample (CASE-VERIFICATION-CHECKLIST.md)
will settle the remaining unknowns.

Verification date: 2026-05-13.

---

## Identifiers

- **MPN**: `AK-N-94`
- **Manufacturer**: Shenzhen OMK Electronics Co., Ltd. ("SZOMK")
- **Manufacturer website**: <https://www.chinaenclosure.com>
- **Manufacturer contact** (per SZOMK product pages): email `ivy@szomk.com.cn`, tel `+86-755-83222882`
- **Product family**: AK-N series ("N" prefix used by SZOMK for various IoT / wall-mount / smoke-detector style enclosures; numeric suffix is sequential and not size-encoded)
- **Marketed application** (per SZOMK related-products listing): "ZigBee hub, WiFi controller" — i.e. a small smart-home / IoT hub-style round enclosure. The AK-N-94 has the smoke-detector form factor commonly used for both indoor air-quality sensors and ZigBee/WiFi hubs.

### Confirmation of the SKU's existence

Search across SZOMK's public catalogue does **not** return a dedicated AK-N-94
product page; the SKU surfaces only in the "related products / similar variants"
sidebar of other AK-N listings (e.g. the AK-N-23a alarm-smoke-sensor page,
<https://www.chinaenclosure.com/products/SZOMK-Plastic-Enclosures-for-Alarm-Smoke-Sensor-AK-N-23a-85x85x40mm.html>),
where it is listed as:

> **AK-N-94** — 128 × 40 mm — ZigBee hub, wifi controller

The two-dimensional "128 × 40 mm" form (vs the usual three-dimensional
W × L × H seen for rectangular AK-N variants in the same table) implies a
**round** outer geometry: Ø128 mm × 40 mm height. This matches the OAS
project's working description (Ø128 mm perforated white ABS, smoke-detector
form factor).

Detailed mechanical drawings (DXF, dimension PDFs, PCB pocket geometry) are
not publicly downloadable from SZOMK's website — they are supplied to
purchasers by SZOMK sales on request. The OAS project obtained the DXF from
SZOMK directly; that file is **not committed to this repo** (CLAUDE.md
Rule 6 — third-party IP). All mechanical figures below are either (a) the
public dimensions surfaced via the SZOMK / distributor listings, or (b)
**derived measurements** taken from the SZOMK DXF that are now our own work
(part of the OAS KiCad sources) and therefore committable.

---

## Mechanical

### Outer envelope (public listing data)

| Dimension | Value | Source |
|---|---|---|
| Outer diameter | **Ø128 mm** | SZOMK catalogue related-products listing on AK-N-23a page |
| Outer height (closed enclosure, cover + base stacked) | **40 mm** | same |
| Form factor | Round, two-piece (cover + base), smoke-detector / IoT-hub style | inferred from AK-N family product photos |
| Cover finish | Perforated (smoke-detector style hole array) — visible on SZOMK product photography for adjacent AK-N smoke-detector models | inferred from family photography |
| Material | ABS plastic | SZOMK material standard across AK-N family |
| Color | White (standard); custom colors available on order | SZOMK standard offering |
| IP rating | IP54 (typical for indoor AK-N family — not formally listed for AK-N-94 in the public data; treat as best-guess pending confirmation) | inferred from sister SKUs (AK-N-23a, AK-NW-47, AK-NW-60) which all list IP54 |
| UL94 V0 fire-retardant material option | Available on request | SZOMK family-wide customisation note |

### Derived PCB pocket geometry (OAS own work, from the manufacturer DXF)

These are measurements taken from the SZOMK-supplied DXF and re-expressed as
the OAS KiCad outline. Numbers are committed in `hardware/kicad/generate.py`
and `hardware/case/README.md`; this is **our own derivative work** and is the
authoritative repo-side reference.

| Feature | Value | Notes |
|---|---|---|
| PCB outline shape | D-shape (circle truncated by one chord) | one flat edge along the bottom |
| PCB arc radius | **R = 60 mm** (Ø 120 mm) | implies 4 mm radial gap from PCB edge to enclosure inner wall (128/2 − 120/2 = 4 mm), consistent with typical SZOMK PCB-to-wall clearance |
| Chord length | **82.6545 mm** | full DXF precision; used as 82.65 mm in documentation rounding |
| Chord position (Y from PCB origin) | **43.498 mm** | PCB origin = geometric centre of the un-truncated Ø120 circle |
| Mounting holes | 3 × M3 clearance | NPTH; bosses are plastic on the enclosure side |
| Hole diameter | **Ø 3.8 mm** | clearance for M3 screw with no copper pad |
| Mounting hole pitch circle | **Ø 110 mm** (R = 55 mm) | equilateral-triangle pattern, one hole at the pole opposite the chord |
| Hole positions (mm, PCB origin = centre) | H1 (+47.631, +27.500), H2 (−47.631, +27.500), H3 (0, −55.000) | H1/H2 near chord, H3 at top opposite chord |
| Cable pass-through hole | **Ø 12 mm** at PCB origin (0, 0) | sized for 3 × 1.5 mm² conductor cable bend |
| Component-height limit, front (per DXF annotation `正面限高 17mm`) | **17 mm** — see notes below | annotation interpretation is currently treated as **regional** (peripheral / near mounting bosses) not global; central area very likely allows ≥22 mm to accommodate the SEN66 body. Final answer pending physical sample (CASE-VERIFICATION-CHECKLIST §1). |
| Component-height limit, back (per DXF annotation `背面焊脚限高 3mm`) | **3 mm baseline → 5 mm effective** | 5 mm achieved by lifting the PCB 2 mm with washers under each M3 mounting screw |
| Case-wall cutouts at the chord | **5 rectangular openings** (C1..C5) for edge-mount connectors | original count; OAS uses C3 / C4 / C5 (C1, C2 dropped in OAS v0.15.6) — see `hardware/case/README.md` for individual cutout positions |

The 4 mm radial clearance between the Ø120 PCB outline and the Ø128 enclosure
outer diameter is consistent with SZOMK's typical PCB pocket design across the
AK-N family — the PCB sits inside a recessed boss-and-rib structure with a
small clearance ring for the case wall thickness and an assembly tolerance.

### Mounting boss + cover assembly

Not publicly documented; OAS assumes (to be verified against the physical
sample per CASE-VERIFICATION-CHECKLIST §5):

- 3 plastic mounting bosses (no metal threaded inserts), located on the
  Ø110 mm pitch circle, accepting M3 screws threaded directly into ABS.
- Boss height sufficient to seat the PCB and a 2 mm washer + M3 screw without
  bottoming out (≥ 8 mm thread engagement on each boss).
- Cover and base meet at a friction / snap fit (no top-side screws on AK-N
  family; rear-side screw access is typical for the AK-N IoT/smoke-detector
  models).
- 3 wall-mount screw holes on the back of the enclosure on a 60 mm pitch
  matching a standard wall-recessed electrical box (this is the OAS design
  intent; SZOMK's AK-N family typically targets this pitch but it is not
  publicly listed for AK-N-94 specifically — to be verified).

---

## Sourcing

| Channel | URL | Notes |
|---|---|---|
| Manufacturer direct | <https://www.chinaenclosure.com> | request a quote and the DXF / datasheet from SZOMK sales by SKU |
| Manufacturer Alibaba storefront | <https://szomk.en.alibaba.com/> | direct purchase; English support |
| Made-in-China storefront | <https://szomkbox.en.made-in-china.com/> | SZOMK's mirror listings |
| AliExpress (SZOMK official store and resellers) | search `szomk AK-N-94` on aliexpress.com | various resellers; verify SKU on product photo before purchase — generic "smoke detector enclosure" listings on AliExpress are often unbranded clones, not genuine SZOMK |
| DirectIndustry (catalog browsing only) | <https://www.directindustry.com/prod/szomk-electronics-236108.html> | SZOMK catalogue index; products do not ship from DirectIndustry — used for spec lookup only |
| EU distribution | not stocked at a major EU distributor as of verification date | TME, Farnell, Mouser, RS, Distrelec, Botland do not list SZOMK enclosures. EU buyers route via AliExpress or direct from SZOMK with the corresponding shipping lead time. |

### MOQ and lead time

- **MOQ**: 1 piece for stock items (per multiple SZOMK product pages including
  AK-NW-47). For custom drilling / silkscreen / logo / colour, MOQ rises to
  20–50 pieces.
- **Lead time**: 1–3 working days for stock items; 7–15 working days for
  custom production (per SZOMK AK-NW-60 listing).
- **Shipping (CN → EU)**: typical 1–3 weeks via AliExpress standard / SZOMK
  freight.

### Customisation services available

SZOMK offers (per AK-NW-47 page and AK-NW-60 page):

- Custom drilling / punching (for example, the OAS-specific connector cutouts
  in the case wall, the cable entry on the back, the SEN66 cover bracket)
- Custom silkscreen / laser engraving / stickers (branding)
- Custom colour (white is standard; black, gray, custom Pantone available)
- UL94 V0 fire-retardant ABS substitution (relevant if the unit ever lands in
  a fire-code-restricted indoor location)
- Powder coating (uncommon for ABS but offered for the aluminium AK-C family)

Custom services require a 20–50 piece MOQ and typically add 7–15 days lead
time.

---

## Caveats

### Cover removal / assembly access
The AK-N family is two-piece (cover + base). Cover removal during assembly
and field service is by friction / snap fit; no top-side screws are visible
on adjacent AK-N IoT and smoke-detector SKUs. **To be confirmed** against
the physical sample — if the AK-N-94 uses rear-cover screws or a bayonet
twist-lock, this changes the OAS service workflow (rear-side cable entry
becomes harder to detach without first removing the unit from the wall).

### Color options
White is the default for AK-N IoT / smoke-detector style models. Black and
gray are available as standard non-MOQ colors on many AK-N SKUs; AK-N-94's
specific stock-color list is not publicly listed but the family default
applies. Custom colors require a 20–50 piece MOQ. OAS uses white to match
typical indoor-wall fixtures (light switches, smoke alarms).

### IP rating
Not formally listed in the public data for AK-N-94 specifically. The
adjacent AK-N IoT / smoke-detector SKUs list IP54 (dust-protected and
splash-resistant). The perforated cover obviously **breaks** IP rating on
the SEN66 air-inlet path, so the "IP54" claim cannot apply to the
perforated face — at best it applies to the seam between cover and base.
OAS treats this enclosure as **indoor-only, non-IP-rated** in deployment
guidance regardless of the catalogue claim.

### Mains-rated / fire-retardant standard
The AK-N-94 ships in standard ABS. For a 24 V DC powered device (OAS),
standard ABS is acceptable per common indoor low-voltage device practice.
For installations where local fire code requires UL94 V0 housings, request
the UL94 V0 material substitution from SZOMK at order time (custom MOQ
applies).

### "AK-N-94" vs "AK-NW-94"
A separate SKU `AK-NW-94` also exists in the SZOMK catalogue — it is an
unrelated **100 × 100 × 51 mm rectangular** 2× AA battery temperature /
humidity sensor enclosure
(<https://www.chinaenclosure.com/products/SZOMK-2x-AA-Battery-Compartment-Plastic-Temperature-Humidity-Sensor-Enclosure-AK-NW-94-10010051mm.html>).
Make sure orders specify **AK-N-94** (no "W") and confirm the 128 mm
diameter on the supplier's order acknowledgement before shipping.

### Public spec data thinness
SZOMK does not publish a dedicated product page or full mechanical drawing
for AK-N-94 in the public web. The OAS project's mechanical figures all
derive from the manufacturer DXF supplied on request and validated against
the physical sample during the verification phase
(`docs/CASE-VERIFICATION-CHECKLIST.md`). Treat anything in this document
that is **not** in the "derived PCB pocket geometry" table as best-effort
inference from sister SKUs until the physical sample lands.

---

## Sources

- SZOMK manufacturer site: <https://www.chinaenclosure.com>
- SZOMK Alibaba storefront: <https://szomk.en.alibaba.com/>
- SZOMK Made-in-China storefront: <https://szomkbox.en.made-in-china.com/>
- AK-N-23a product page (related-products sidebar that confirms AK-N-94 = 128 × 40 mm, ZigBee hub / WiFi controller): <https://www.chinaenclosure.com/products/SZOMK-Plastic-Enclosures-for-Alarm-Smoke-Sensor-AK-N-23a-85x85x40mm.html>
- AK-NW-47 product page (sister SKU, used to confirm AK-N family customisation policy, IP54 typical, MOQ, lead time): <https://www.chinaenclosure.com/products/SZOMK-factory-supply-net-work-plastic-enclosure-for-electronics-round-box-110-36mm.html>
- AK-NW-60 product page (smoke-sensor white ABS housing, confirms IP54 + customisation services): <https://www.chinaenclosure.com/products/Smoke-sensor-plastic-housing-AK-NW-60.html>
- AK-NW-79 product page (121 × 25 mm smoke/gas detector housing, confirms IP54 + family naming): <https://www.chinaenclosure.com/products/plastic-enclosures-for-electronics-smoke-detector-shell-smart-home-kitchen-Gas-detector-housing-AK-N.html>
- AK-NW-94 product page (sister SKU — explicitly a different product, included here only to flag the confusable SKU): <https://www.chinaenclosure.com/products/SZOMK-2x-AA-Battery-Compartment-Plastic-Temperature-Humidity-Sensor-Enclosure-AK-NW-94-10010051mm.html>
- SZOMK catalogue index on DirectIndustry: <https://www.directindustry.com/prod/szomk-electronics-236108.html>
- SZOMK standard plastic enclosure catalogue (Scribd hosted): <https://www.scribd.com/document/744078613/SZOMK-Standard-plastic-enclosures-series-catalogue>
- OAS derived dimensions reference: `hardware/case/README.md`
- OAS physical-sample verification plan: `docs/CASE-VERIFICATION-CHECKLIST.md`
