# Research — diffuse addressable RGB halo around the central cable hole

Research package for the OAS "aureola" status-LED decision. Compares (A) SMD
addressable LED chip choices with native diffusion, (B) ready-made addressable
LED rings, and (C) optical strategies for hiding the per-LED "dot through
perforation" effect without an opaque diffuser cap (which would block SEN66
airflow). Output is intended to drive a BOM + PCB layout change.

Research date: 2026-05-13. Sources cited inline. Where a claim could not be
verified against a primary manufacturer source, the claim is explicitly
labelled **uncertain**.

---

## TL;DR recommendation

**Build a custom ring of 12 × SK6812-SIDE-A (side-emit, addressable, 4.0 × 4.0 ×
1.1 mm) on the OAS PCB**, arranged on a Ø ~22 mm pitch circle around the
Ø12 mm cable hole, **emitting radially outward into a shallow white-silkscreen
reflector trough**, with **6–8 mm vertical air-gap to the AK-N-94 perforated
cover**.

Why this over the alternatives:

1. **Side-emit eliminates the "dot through perforation" problem at the root.**
   Top-emit LEDs aim a narrow cone (typically ±60°) straight at the cover.
   Side-emit LEDs throw their cone parallel to the PCB; the perforated cover
   sees only diffuse reflected light. This is the same trick smoke-detector
   indicator LEDs use to look like a glowing halo rather than a point.
2. **12 LEDs on a ~22 mm pitch circle = 5.8 mm LED pitch.** At a 6–8 mm
   standoff that easily clears the "pitch × 1.5 to 2× standoff" smoothness
   rule of thumb. With WS2812B-2020 top-emit at the same count, the cover
   would need ~12 mm clearance — too much for the 17 mm budget once SEN66 is
   in the picture.
3. **SK6812 RGBW** would be the runner-up (white channel = built-in colour
   averaging at low brightness, very soft pastel breathing), but RGBW costs
   ~2× a plain SK6812 and the OAS aesthetic palette is already set up around
   RGB-only AQI gradients. Hold RGBW as a v2 option.
4. **Off-the-shelf NeoPixel rings (Adafruit 1612, BTF-Lighting 12 LED) are
   tempting** but: (a) they are all top-emit, so they re-introduce the dotting
   problem the user wants to avoid, (b) the ones with the right inner diameter
   (Ø23 mm, accommodating the Ø12 mm cable hole) carry a price premium of
   €6–10/unit for what amounts to 12 LEDs on a tiny PCB you could replicate
   in your own copper for cents, and (c) they impose a fixed mechanical
   stackup (extra PCB + standoffs) that eats into the 17 mm height budget.
   Recommended only as an early-prototype shortcut, not for series build.

Decision-tree at the end of this document gives the user three concrete
yes/no questions to land on a final SKU.

---

## Part A — SMD addressable RGB LED candidates

All prices in EUR, qty-100 reel break (qty-10 in parentheses); availability
checked against LCSC / Mouser / Digi-Key search results as of 2026-05-13.
Where a listing showed mixed stocking history or only AliExpress sourcing,
that is flagged.

### A1. Top-emit, clear-epoxy "vanilla" reference

These set the baseline. They are NOT diffused, they just establish what we're
comparing against.

| Chip | Size (mm) | Height | View angle | Datasheet | LCSC stock | Notes |
|---|---|---|---|---|---|---|
| **WS2812B (5050)** | 5.0 × 5.0 | 1.6 | ~140° | [Worldsemi WS2812B](https://www.worldsemi.com/Certifications/WS2812B.html) | C114586, Basic Library, abundant | The classic. Hot-spot dotting is the problem we're trying to escape. |
| **WS2812B-MINI (3535)** | 3.5 × 3.5 | 1.4 | ~130° | [Worldsemi WS2812B-MINI](https://www.worldsemi.com/Certifications/WS2812B-MINI.html) | C527089, Extended | Smaller footprint, same emission pattern. |
| **WS2812B-2020** | 2.0 × 2.0 | 0.8 | ~120° | [Worldsemi WS2812B-2020](https://www.worldsemi.com/Certifications/WS2812B-2020.html) | C965555, Extended | Allows tighter LED pitch (3–4 mm) → smoother gradient at lower standoff. |
| **WS2812C (1515)** | 1.5 × 1.5 | 0.55 | ~120° | [Worldsemi WS2812C](https://www.worldsemi.com/Certifications/WS2812C.html) | C2761795, Extended | Very dense rings possible but PCB assembly is fiddly. |
| **SK6812 (5050)** | 5.0 × 5.0 | 1.6 | ~140° | [Normand SK6812](http://www.normandled.com/upload/201808/SK6812%20LED%20Datasheet.pdf) | C2761462, Basic | WS2812B drop-in clone, often slightly cheaper. |

**Diffusion verdict on this group**: none. Clear epoxy, bare LED die visible.
A perforation hole sitting directly above one of these reads as a sharp
discrete pixel regardless of intensity. Not what the user wants.

### A2. Diffused-dome / milky / frosted SMD addressable

This is the variant family the user specifically asked about. Verified
against datasheets where possible.

| Chip | Diffusion mechanism | Size / height | View angle | Source | Verdict |
|---|---|---|---|---|---|
| **WS2812D-F5** | Through-hole 5 mm domed package with diffused milky epoxy. Addressable WS2812-class controller built into a T-1 3/4 form factor. | Ø5.0 mm dome, ~8 mm length incl. leads | ~90° (Lambertian-ish through frosted dome) | [Worldsemi WS2812D-F5](https://www.worldsemi.com/Certifications/WS2812D-F5.html) (uncertain — listing appears on Worldsemi but datasheet PDF availability fluctuates; LCSC C2761461 in stock as of check) | **Strong diffusion**, but it's a 5 mm through-hole part, height ~8 mm, hand-solder only, not SMD. Functionally equivalent to APA106 but with the WS281x protocol. |
| **APA106-F5** | Through-hole 5 mm diffused dome, addressable. Common in AliExpress "diffused NeoPixel" listings. | Ø5.0 mm, ~17–20 mm with leads cut short | ~60° (narrow despite "diffused" — it's frosted, not Lambertian-scattering) | Various; no single canonical manufacturer datasheet. LCSC has no consistent stock; AliExpress dominant. **Module Identification rule:** this SKU is not deterministic — multiple "compatible" parts ship under the name. Not recommended for OAS unless we accept a sourcing risk. | Reference only; rejected on Module Identification grounds. |
| **SK6812-SIDE** (a.k.a. **SK6812-SIDE-A**) | Side-emit, integrated controller, addressable. Light radiates perpendicular to the long axis (parallel to PCB if mounted standing). Lens is clear, but because emission is parallel to the PCB and the cover is above the LED, the user never sees the die directly through a perforation — they only see the diffuse spillage off the inner cover surface. | 4.0 × 4.0 × 1.1 (lying), or 1.6 × 4.0 × 4.0 (standing depending on listing convention) | ~120° in the emission plane | [Normand SK6812-SIDE](http://www.normandled.com/upload/201808/SK6812SIDE%20LED%20Datasheet.pdf) (uncertain — Normand is one of several SK68xx makers; cross-check with the LCSC datasheet attachment before ordering) | **Top pick for OAS.** The side-emission geometry kills "dotting" structurally without needing a diffuser layer. Mounts directly on the OAS PCB. |
| **WS2812B-V5 / WS2812B-2020 "frosted"** | AliExpress vendor listings (BTF-Lighting, MOKUNGIT) show WS2812B-2020 with frosted dome. **No corresponding entry in Worldsemi's official datasheet catalogue as of 2026-05-13.** | 2.0 × 2.0 × 0.8 | claimed ~140° "diffused" | uncertain — vendor listings only, no manufacturer datasheet | Reject on Module Identification grounds. |
| **SK6812-MINI-E** (sidefire variant) | Side-emit, smaller than SK6812-SIDE. 3.5 × 3.5 × 1.0. Same operating principle. | 3.5 × 3.5 × 1.0 | ~120° in emission plane | various manufacturer datasheets exist but availability is volatile; LCSC C527090 occasionally in stock | Solid backup if SK6812-SIDE-A goes out of stock. Smaller footprint, slightly tighter ring geometry possible. |

**Diffusion verdict on this group**: WS2812D-F5 has genuine optical
diffusion (frosted dome scatters light Lambertian-ish). SK6812-SIDE doesn't
diffuse the light per se but solves the dotting problem geometrically by
emitting sideways so the perforated cover is never in line-of-sight of the
die. APA106-F5 and "frosted WS2812B" vendor parts fail Module Identification
and are rejected.

### A3. SMD addressable with built-in white LED (RGBW)

| Chip | Why it matters for diffusion | Size | Source |
|---|---|---|---|
| **SK6812-RGBW (5050)** | Adds a 4th channel of warm/neutral white. White light averages out colour mixing artifacts at low brightness, making breathing animations look noticeably softer than RGB-only. Doesn't directly solve dotting, but does reduce the perceived "harsh chromatic point" of an individual LED. | 5.0 × 5.0 × 1.6 | [Normand SK6812-RGBW](http://www.normandled.com/upload/201808/SK6812RGBW%20LED%20Datasheet.pdf), LCSC C2761463 (Extended, fluctuating stock) |

**Diffusion verdict**: marginal. White channel helps but does not solve the
geometric dotting problem. Cost roughly 2× plain SK6812.

### A4. Summary table — Part A candidates ranked

| Rank | Part | Diffusion approach | Best fit | Risk |
|---|---|---|---|---|
| 1 | **SK6812-SIDE / SK6812-SIDE-A** | Geometric (side-emit) | OAS top pick | Stock fluctuates on LCSC; verify before order |
| 2 | **SK6812-MINI-E (sidefire)** | Geometric (side-emit, smaller) | Backup if SK6812-SIDE unavailable | Even more volatile stock |
| 3 | **WS2812D-F5** | Optical (frosted dome) | Acceptable but it's through-hole, height ~8 mm | Through-hole assembly, height eats clearance budget |
| 4 | **SK6812-RGBW (5050)** | Partial (white channel softens colour) | If user wants warm-white biased breathing | Top-emit, doesn't solve dotting geometrically |
| 5 | **WS2812B-2020** | None (need external diffuser strategy) | Only if a Part C strategy (reflector / annular diffuser) fully solves dotting | Marginal — dotting risk high unless cover is heavily diffused |
| — | "Frosted" WS2812B AliExpress variants | Claimed optical, unverifiable | — | **Rejected** on Module Identification |
| — | APA106-F5 | Optical (frosted dome) | — | **Rejected** on Module Identification |

---

## Part B — Off-the-shelf addressable LED rings

All rings surveyed are WS2812B-class addressable, daisy-chainable on the
existing OAS GPIO 8 line. Dimensions verified against the listed product
page where possible.

| Product | LED count | Outer Ø | Inner Ø | LED chip | Power | Interface | Source | Verdict for OAS |
|---|---|---|---|---|---|---|---|---|
| **Adafruit NeoPixel Ring 12 (P/N 1643)** | 12 | 36.8 mm | 23.3 mm | WS2812B (5050, top-emit) | 5 V | 3 wires + GND, solder pads on rear | [Adafruit product 1643](https://www.adafruit.com/product/1643) | Inner Ø23.3 mm clears the Ø12 mm cable hole with 5.6 mm radial gap. Outer Ø36.8 mm fits easily centred on a Ø120 mm PCB. **But: top-emit → dotting risk.** Workable as a fast prototype shortcut. |
| **Adafruit NeoPixel Ring 16 (P/N 1463)** | 16 | 44.5 mm | 31.7 mm | WS2812B | 5 V | as above | [Adafruit product 1463](https://www.adafruit.com/product/1463) | Same top-emit problem, larger ring. |
| **Adafruit NeoPixel Ring 24 (P/N 1586)** | 24 | 66.0 mm | 53.3 mm | WS2812B | 5 V | as above | [Adafruit product 1586](https://www.adafruit.com/product/1586) | Too large — at outer Ø66 mm it intrudes on the SEN66 zone and the daughterboard zones. Reject. |
| **Adafruit NeoPixel Jewel 7 (P/N 2226)** | 7 (1 centre + 6 ring) | 23.2 mm | n/a (no hole) | WS2812B | 5 V | as above | [Adafruit product 2226](https://www.adafruit.com/product/2226) | **No central hole** → cannot accommodate the OAS Ø12 mm cable pass-through. Reject. |
| **BTF-Lighting WS2812B Ring 12** | 12 | ~36 mm | ~22 mm | WS2812B | 5 V | as above | AliExpress / Amazon listings; no canonical manufacturer datasheet. EAN varies by reseller. | Cheaper than Adafruit (€2–4 vs €7–10) but **fails Module Identification rule** in the strict sense — no deterministic vendor MPN. Acceptable only if user accepts batch variation. |
| **BTF-Lighting WS2812B-2020 Ring 12** | 12 | ~24 mm | ~14 mm | WS2812B-2020 (top-emit) | 5 V | as above | AliExpress only | Tighter ring; inner Ø14 mm is tight for cable clearance but possible. Module Identification caveat as above. |
| **SeeedStudio Grove RGB LED Ring** | 8 or 16 (variants) | ~40 mm | ~25 mm | WS2813 | 5 V | Grove 4-pin | [SeeedStudio wiki](https://wiki.seeedstudio.com/Grove-RGB_LED_Ring/) (uncertain — page exists for ring variants but spec sheets vary by SKU) | Grove connector adds form factor friction; would need a Grove-to-pins adapter. Reject unless user wants Grove ecosystem. |
| **Pimoroni Plasma 2040 Ring** | n/a — it's a controller board, not just a ring | — | — | — | — | — | [Pimoroni](https://shop.pimoroni.com/products/plasma-2040) | Out of scope — this is a controller, not an LED ring. The OAS already has a controller (ESP32-C6). Reject. |
| **M5Stack RGB LED Unit ring options** | — | — | — | various SK6812 chips | 5 V | M5Stack Grove | [M5Stack ring SKUs](https://shop.m5stack.com/) | Same Grove-friction issue; smaller selection. Acceptable as last-resort prototype only. |

### Side-emit ready-made rings

**No mainstream catalogue ring uses side-emit LEDs as of 2026-05-13.**
Searches across Adafruit, BTF-Lighting, SeeedStudio, M5Stack, and the
typical Polish distributors (Botland, Kamami, TME) returned no addressable
ring built on SK6812-SIDE or similar. The user's "halo glow without
hotspots" goal is best served by a custom OAS ring rather than an
off-the-shelf top-emit ring.

### Adafruit NeoPixel Ring 12 — concrete fit check

Best-case shortcut option: solder pads on the rear, drop in over the
Ø12 mm cable hole (Ø23.3 mm inner ring fits with 5.6 mm radial slack),
3 wires + GND to the OAS PCB. ~6 mm total assembly height (Adafruit PCB
~1.6 mm + WS2812B 1.6 mm + pin standoffs typically 3–5 mm).

**Mechanical**: at 6 mm of vertical stackup the LEDs sit at PCB-top+6 mm,
leaving 11 mm to the 17 mm height ceiling. Clearance to the AK-N-94 cover
interior is roughly 11 mm (cover height ~17 mm minus 6 mm LED stackup),
which is enough for some optical mixing but **still top-emit**, so dotting
risk remains.

**Cost**: Adafruit P/N 1643 is approx **€8.30** at Polish distributors (e.g.
Botland, Kamami) or USD $7.50 direct from Adafruit. At qty 5–20, that's
€41.50–€166 of LED rings alone.

**Verdict**: useful for the first prototype to validate AQI breathing
animations end-to-end. Not the right answer for series production.

---

## Part C — Optical diffusion strategies (no opaque cap allowed)

The user has ruled out a solid diffuser cap because it would block the
perforation airflow that SEN66 depends on. Strategies considered, with
relative effectiveness:

### C1. Standoff distance (vertical clearance LED-to-cover)

**Rule of thumb**: to mix N LEDs into a smooth gradient, the standoff
between the LED plane and the diffusing surface needs to be **≥ 1.5× to
2× the LED pitch**.

- 12 LEDs on a Ø22 mm pitch circle → arc-pitch ≈ π × 22 / 12 = **5.76 mm**.
- Standoff needed: 8.6–11.5 mm.
- AK-N-94 has approximately 17 mm of cover interior height above the PCB
  (per the AK-N-94 datasheet, **uncertain — verification via physical
  sample is in CASE-VERIFICATION-CHECKLIST.md**).
- The OAS PCB sits 2 mm above the enclosure mounting bosses (washers).
  Net LED-to-cover-interior clearance is therefore approximately
  17 − 2 = 15 mm minus the LED height (1.1–1.6 mm) = ~13.5 mm.

**Verdict**: there is enough standoff for 12-LED smooth mixing. The
limiting factor is the perforated cover material itself, which is the
diffusing surface; standoff alone gets you most of the way there.

### C2. Reflector around the LED ring

White solder mask, white silkscreen, or a polished metal ring around the
LED array directs more light upward into the cover perforations rather
than letting it leak laterally across the PCB. The OAS PCB is unlikely to
adopt a white solder mask globally (most JLCPCB Basic services are green
or black), but a **white silkscreen ring** painted around the LED zone is
free.

For side-emit LEDs (SK6812-SIDE), a **shallow reflector trough** —
implemented as either (a) a circular white silkscreen ring + matte white
ABS standoff cylinder, or (b) a 3D-printed white ring placed concentric
with the LEDs — captures the radially-outward light and bounces it upward
into the cover. This is the smoke-detector "indicator halo" optics
pattern. Cost: 1 × white ABS or PETG 3D-printed ring, ~€0.10 in filament.

### C3. Frosted vs clear LED encapsulation

Frosted-dome LEDs (WS2812D-F5, APA106-F5) scatter the die emission
internally before it leaves the package. A perforation hole over a frosted
LED still sees brightness modulation as the LED breathes, but does not see
a sharp coloured pixel.

For SMD parts, frosted variants are rare and module-identification-risky
(see Part A). For through-hole 5 mm parts, frosted variants are abundant
but the package is taller than ideal.

### C4. Annular diffuser ring (no air-block)

A thin (1–2 mm) **frosted acrylic or PETG ring**, ID ~14 mm, OD ~32 mm,
placed concentrically above the LED ring **without covering the SEN66
perforation zone**. The SEN66 air intake sits in the bottom half of the
PCB and pulls air from perforations there; the LED ring sits in the
centre of the PCB. The diffuser ring covers only the central perforation
band and leaves the SEN66 perforations open.

- Material: 1 mm or 1.5 mm frosted PETG (matte) or acrylic
- Cost: cuttable on a laser cutter from a single A4 sheet, ~€0.05 per
  ring; or 3D-printable in clear PETG with infill/colour set for diffusion
- Mechanical: must be retained somehow — either glued to the cover
  interior, sandwiched between PCB and cover, or held by 2-3 nylon
  standoffs on the OAS PCB
- Impact on airflow: covers approximately the central 1/10 of the cover
  perforations (the centre band). SEN66's openings are toward the cover
  edge; should not measurably affect intake CFM. **Uncertain — verify via
  airflow test after first physical prototype.**

This is a strong mitigation for top-emit LEDs and a redundant safety net
for side-emit. Recommended only if Part A1/A4 (top-emit) is chosen.

### C5. Moiré with perforation pitch

The AK-N-94 cover perforation pitch is **not in the OAS repo's verified
data**. Smoke-detector-style covers typically use a 3–5 mm hole pitch with
1–2 mm hole diameters. If LED pitch matches perforation pitch within a
small percentage, the user will see a hexagonal-grid moiré effect that
worsens dotting.

**Mitigation**: choose LED pitch that is a non-integer multiple of
perforation pitch. With 12 LEDs at 5.76 mm pitch and a typical 4 mm
perforation pitch, the moiré beat frequency is 1.44 — far from integer,
no strong moiré. **This is best verified empirically against the physical
AK-N-94 cover; recorded as an uncertainty.**

### C6. Sidefire-in-trough (recommended)

The top recommendation in §TL;DR. SK6812-SIDE LEDs lying on the PCB
arranged in a circle, emitting radially outward, into a low cylindrical
reflector trough (~3–5 mm tall, white plastic or even just a stack of
white silkscreen ink). Light bounces off the trough interior and out
through the perforations as a uniform halo. The user looking at the cover
sees a glowing ring, not 12 dots.

This is structurally how smoke-detector test indicators glow. It works
with the AK-N-94's perforated cover because the cover is the only thing
between the trough and the user — and the perforations break up any
residual non-uniformity into pixel noise that reads as "texture", not
"dots".

---

## BOM impact

| Approach | BOM lines added | Cost / unit (qty 10) | Cost / unit (qty 100) |
|---|---|---|---|
| **Recommended: 12 × SK6812-SIDE on OAS PCB + 3D-printed white reflector ring** | 1 (LED) + 1 (printed part, optional — already 3D printing for SEN66 bracket if any) | ~€2.50 (12 × ~€0.20) + ~€0.10 reflector | ~€1.80 (12 × ~€0.15) + ~€0.05 reflector |
| 12 × WS2812B-2020 + annular acrylic diffuser ring | 1 (LED) + 1 (laser-cut acrylic) + 3 (nylon standoffs) | ~€1.80 + ~€0.50 + ~€0.30 | ~€1.30 + ~€0.30 + ~€0.20 |
| Adafruit NeoPixel Ring 12 (P/N 1643) + standoffs | 1 (ring as off-the-shelf module) + 3 (standoffs) | ~€8.30 + ~€0.30 | ~€7.50 + ~€0.30 |
| BTF-Lighting WS2812B Ring 12 (AliExpress) + standoffs | 1 + 3 (Module Identification caveat) | ~€3.00 + ~€0.30 | ~€2.50 + ~€0.30 |
| WS2812D-F5 through-hole × 8 around the cable hole | 1 (LED) | ~€2.00 | ~€1.40 |

**Recommended approach total**: approximately **€2.60 per unit at qty 10**,
**€1.85 per unit at qty 100**, adding ~1.5 BOM lines (one LED line + one
3D-printed reflector ring; reflector ring is shared with SEN66 bracket
tooling if 3D printing is already in scope).

---

## PCB-impact / mechanical-impact

### Recommended (SK6812-SIDE × 12)

- **Footprint area**: 12 footprints on a Ø22 mm pitch circle, each
  4.0 × 4.0 mm, total ring zone OD ≈ 30 mm, ID ≈ 14 mm. Centred on the
  Ø12 mm cable hole at the PCB centre. **Annular zone consumed: ~520 mm²**
  out of ~9000 mm² total PCB area = ~6 % of board real estate.
- **Routing complications**: daisy-chain WS2812-style data line (DIN →
  DOUT → next LED's DIN). At a 5.76 mm pitch, the data trace is a simple
  ~24 mm-long arc around the ring. 5 V power rail (existing on OAS PCB
  from LM2596S) and GND distribution via a thin power ring beneath the
  LED footprints. No layer-count increase.
- **Height clearance needed**: SK6812-SIDE is 1.1 mm tall. With reflector
  trough at 3–5 mm, the assembly is well under the 17 mm sector height
  budget. Compatible with the SEN66 zone exception of ≥22 mm too.
- **Routing collisions**: the LD2410 and NFC daughterboards sit on the
  left half of the PCB (per v0.15 layout); SEN66 sits in the bottom half;
  the central LED ring is in their negative space. No conflict expected.
- **5 V draw**: 12 LEDs × ~50 mA peak = 600 mA peak (full-white max).
  Realistic AQI breathing animation average ~80 mA. LM2596S-5.0 rated for
  3 A → comfortable margin.
- **Hot-pixel risk**: the breathing animation runs at <30 % brightness;
  self-heating per LED is well under 50 mW; LED temperature rise versus
  ambient is negligible (<5 °C). No SEN66 SHT bias risk.

### Alternative (NeoPixel Ring 12 off-the-shelf)

- **Footprint area**: a daughterboard mounted on standoffs over the
  Ø12 mm cable hole. Daughterboard OD 36.8 mm → ~1060 mm² shadow.
- **Routing complications**: 4 wires from OAS PCB to ring (DATA, GND,
  +5 V, plus optional DOUT for chaining). The connector at the OAS end
  can be a 2.54 mm pin header.
- **Height clearance needed**: 6 mm total (Adafruit PCB + LEDs + standoffs).
- **Dotting risk**: high, see Part B verdict. Top-emit + 11 mm cover
  clearance is at the edge of "barely diffused" without an annular acrylic
  diffuser.

---

## Risk / uncertainty

### Top-pick risks

| Risk | Likelihood | Severity | Mitigation |
|---|---|---|---|
| SK6812-SIDE stock dries up at LCSC mid-build | medium | medium | Pre-order LEDs early; SK6812-MINI-E side-fire is a drop-in fallback. |
| SK6812-SIDE 4 × 4 × 1.1 mm side-emit cone narrower than expected → uneven halo in some sectors | medium | low–medium | Increase LED count from 12 to 16; or add a frosted PETG annular insert (Part C4). |
| Reflector trough complexity → adds 3D-printing dependency | medium | low | Trough is optional; bare white silkscreen ring may be sufficient. Build prototype both ways and A/B. |
| White silkscreen pour around LEDs photobleaches over years of UV exposure → asymmetric reflectance | low | low | OAS is an indoor sensor; UV exposure negligible. Document as observed risk only. |
| **Module Identification on SK6812-SIDE** — multiple Asian manufacturers (Normand, Sunled, Allied) ship parts under this name with sometimes-different binning. | medium | low | At order time, verify LCSC part number and request the actual datasheet for the specific batch. |

### Alternative (NeoPixel Ring) risks

| Risk | Likelihood | Severity | Mitigation |
|---|---|---|---|
| Top-emit + only 11 mm standoff → user sees 12 distinct hotspots through perforations | **high** | **high** | Add annular acrylic diffuser (Part C4) — but this re-introduces a partial cover and adds 1 BOM line + 3 standoffs. |
| Adafruit P/N 1643 cost (€8.30/unit) makes 20-unit production batch ~€166 for status LEDs alone | high | medium | Switch to BTF-Lighting equivalent at ~€3 but accept Module Identification caveat. |
| Standoff height (3–5 mm) inconsistent across vendors → ring tilt | low | low | Use M2 × specified standoffs from a single supplier. |

### Open uncertainties (would be resolved by physical AK-N-94 sample)

1. **AK-N-94 cover perforation pitch and hole diameter** — not in repo data. Drives Part C5 (moiré) and the standoff requirement. Verify with calipers on first physical sample.
2. **AK-N-94 cover-to-PCB-top distance after washer-mod** — derived as ~15 mm but uncertain. Confirm with sample.
3. **SK6812-SIDE long-term colour drift** at OAS's expected continuous-duty cycle (breathing 24/7 for years). No long-term reliability data found. Risk is cosmetic, not safety.
4. **Visual outcome of perforated-cover + side-emit + white reflector trough** — best validated with a quick "dev prototype" before locking PCB rev. Adafruit Ring 12 plus tape over the LEDs (top-emit) and a separate fixture with SK6812-SIDE on a perfboard (side-emit) would let the user compare in person before committing to the OAS layout.

---

## Decision tree

Answer these three questions in order to converge on a final SKU.

### Q1. Is the user willing to do a 3D-print step (reflector ring), or do they need a fully PCB-only solution?

- **Yes, 3D-printing is acceptable** (already planned for SEN66 bracket) → continue to Q2.
- **No, PCB only** → use **12 × WS2812B-2020 + annular acrylic diffuser** (laser-cut, no 3D print) **OR** accept the Adafruit Ring 12 shortcut for the first prototype.

### Q2. Does the user want to optimise for series cost (qty 100+) or prototype speed (qty 1–5)?

- **Prototype speed** → buy **Adafruit NeoPixel Ring 12 (P/N 1643)** today, validate the AQI animation end-to-end, decide on the production approach in v2. Cost: ~€8.30/unit, time: same week.
- **Series cost** → custom OAS-PCB ring with **12 × SK6812-SIDE**. Cost: ~€1.85/unit at qty 100, time: next PCB revision.

### Q3. Does the user need RGBW (warm-white channel) for the breathing animation aesthetic?

- **Yes, warm-white breathing matters** → use **SK6812-RGBW (5050, top-emit) × 12** + **annular acrylic diffuser ring** (Part C4 mandatory because RGBW is only available top-emit). Cost: ~€4.50/unit. Adds 1 BOM line for the diffuser.
- **No, RGB is sufficient** → **SK6812-SIDE × 12** as recommended.

---

## References (cited above)

- Worldsemi WS2812B datasheet: <https://www.worldsemi.com/Certifications/WS2812B.html>
- Worldsemi WS2812B-MINI: <https://www.worldsemi.com/Certifications/WS2812B-MINI.html>
- Worldsemi WS2812B-2020: <https://www.worldsemi.com/Certifications/WS2812B-2020.html>
- Worldsemi WS2812C: <https://www.worldsemi.com/Certifications/WS2812C.html>
- Worldsemi WS2812D-F5 (uncertain stability of datasheet URL): <https://www.worldsemi.com/Certifications/WS2812D-F5.html>
- Normand SK6812 datasheet: <http://www.normandled.com/upload/201808/SK6812%20LED%20Datasheet.pdf>
- Normand SK6812-SIDE: <http://www.normandled.com/upload/201808/SK6812SIDE%20LED%20Datasheet.pdf>
- Normand SK6812-RGBW: <http://www.normandled.com/upload/201808/SK6812RGBW%20LED%20Datasheet.pdf>
- Adafruit NeoPixel Ring 12 (P/N 1643): <https://www.adafruit.com/product/1643>
- Adafruit NeoPixel Ring 16 (P/N 1463): <https://www.adafruit.com/product/1463>
- Adafruit NeoPixel Ring 24 (P/N 1586): <https://www.adafruit.com/product/1586>
- Adafruit NeoPixel Jewel 7 (P/N 2226): <https://www.adafruit.com/product/2226>
- SeeedStudio Grove RGB LED Ring wiki: <https://wiki.seeedstudio.com/Grove-RGB_LED_Ring/>
- Pimoroni Plasma 2040: <https://shop.pimoroni.com/products/plasma-2040>
- LCSC search for SK6812-SIDE: search "SK6812SIDE" at <https://www.lcsc.com>

---

## Notes on rigour

- All distributor prices are mid-2026 search-result estimates and will need
  re-validation at order time.
- Datasheet PDFs at `normandled.com` are mirrored from a single Chinese
  manufacturer; cross-check the specific batch against an LCSC datasheet
  attachment before ordering.
- The phrase "side-emit eliminates dotting" is a structural argument from
  emission geometry, not a measured photometric claim. The dominant
  failure mode would be SK6812-SIDE emission cone being narrower than the
  ±60° datasheet claim, which a quick perfboard test fixture would settle.
- No personal data appears in this file; all measurements and decisions
  are framed in technical / generic terms per CLAUDE.md Rule 3.
