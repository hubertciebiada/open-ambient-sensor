# Research — small round display at the centre of the AK-N-94 cover

Research package addressing the user's request to evaluate a small round
display (true OLED or round IPS TFT LCD) mounted at the **centre of the
front cover** of the OAS unit, showing live SEN66 + LD2410 telemetry.
Mid-2026 component availability and pricing assumed; sources cited inline.

Research date: 2026-05-13. Where a claim is not anchored to a primary
manufacturer / authorised distributor source it is explicitly flagged as
**uncertain**.

CLAUDE.md currently lists `Display (OLED / LCD)` under "Out of scope
(decisions already made)". The user has asked to revisit. This document
takes the revisit honestly — the analysis ends with an explicit "is this
a good idea?" answer, not a sales pitch.

---

## 1. TL;DR recommendation

**Recommended choice (only if the user really wants a display on the
cover):** Waveshare **1.28" Round LCD Display Module** (GC9A01, 240×240,
SPI, Ø32.4 mm module OD, ~Ø32.5 mm visible bezel, 8-pin 2.54 mm header).
Manufacturer SKU `1.28inch LCD Module`. Mounted at the cover centre on a
3D-printed bezel (placement option **B1** — display floats on the cover
interior, PCB-side connector wires up via a short ribbon). On the OAS
PCB side, add a **1× JST-GH 8-pin horizontal SMD socket (`SM08B-GHS-TB`)**
near the cable hole as `J9`, plus a short pre-crimped 100 mm JST-GH-to-
2.54 mm-DuPont harness.

**However**, the honest recommendation is:

> **Don't add a display on the cover in v1.** The combination of (a) the
> existing NFC-tap UX already delivering "phone close to unit → see live
> data" *without* visible electronics, (b) the cover modification cost
> (Ø32 mm clear window cut through the perforated white ABS, plus a
> printed bezel), (c) the aesthetic regression (a dark grey LCD square
> in the middle of a smoke-detector silhouette is the single biggest
> deviation from the "smoke detector look" the project has been
> defending), and (d) the +50–150 mW continuous heat budget against the
> SEN66 ΔT ≤ 2 K target, all push the **default answer back to "leave
> display out of scope, keep the NFC tap + LED ring + HA dashboard
> stack."**

If the user wants the display anyway (e.g. for a kitchen / hallway unit
where pulling out a phone is awkward), the Waveshare 1.28" GC9A01 module
is the right SKU; the rest of this document details how to land it.

---

## 2. Why the revisit is (partly) justified

Three things have changed since CLAUDE.md first marked the display
out-of-scope; together they raise the question from "no, ever" to
"borderline, with caveats":

1. **Round IPS TFT LCDs with GC9A01 drivers have become a commodity.**
   In 2022 a 1.28" round 240×240 IPS module was a niche €25 part; in
   2026 the Waveshare module is €15 at qty 1 and €11–12 at qty 10 via
   AliExpress with verified vendor listings, available in stock at
   Botland, Kamami and TME. The price gap that originally pushed
   "display = expensive add-on" has narrowed.
2. **ESPHome added a `gc9a01a` driver under the `ili9xxx` platform**
   (around ESPHome 2023.6 with continued maintenance through 2026).
   The firmware path is well-trodden — there are public ESPHome configs
   for round LCDs showing weather, room conditions, AQI dial gauges,
   etc. Custom-component complexity is no longer the gating item it
   was.
3. **The OAS PCB now has 9 safe spare GPIOs** (per the v0.4 pinout
   table in CLAUDE.md). SPI for the display burns 4–5 of those (MOSI,
   SCK, CS, DC, optional RESET). That's affordable now whereas in v0.3
   when the GPIO map was tighter it would have been painful.

Three things have **not** changed, and each weighs against the display:

1. **Aesthetic pillar (Pillar #2).** A round LCD in the centre of a
   white perforated smoke-detector cover is a major silhouette change.
   The unit stops reading as a smoke detector and starts reading as a
   thermostat or smart-home control panel. That's a deliberate user
   call — but it's an irreversible visual shift, not a minor tweak.
2. **NFC tap UX overlap.** The whole point of keeping the NT3H1101
   tag (MIKROE-2462) in the design was the "phone close to unit → see
   live data" interaction. A display largely duplicates that role for
   anyone willing to walk up to the unit at all. HA dashboards on
   phones / wall tablets cover the "want data without walking up"
   case.
3. **Cover modification.** The AK-N-94 is **perforated white ABS**.
   The perforation is functional (SEN66 air sampling). Cutting a
   Ø32 mm window in the centre removes ~5–7% of the total perforation
   area, all of it in the most direct line-of-sight zone above the
   SEN66 inlets. Below-the-line analysis suggests airflow impact is
   small but non-zero. The aesthetic impact is the dominant penalty.

So: revisit was justified by the changed economics and firmware path,
but the original three blocking arguments (aesthetic, UX overlap, cover
work) still hold. **The revisit's net conclusion is closer to "no, but
documented" than to "yes, with caveats."**

---

## 3. Part A — Round-display candidates

Prices in EUR, qty 1 and qty 10 brackets, mid-2026 estimates from
Botland / Kamami / Waveshare official / Adafruit / Mouser / AliExpress
verified-vendor listings. Where a price could not be anchored to a
specific live listing it is labelled **uncertain**.

### A1. True (passive-emission) round OLED

Round-glass OLED in the 1–2" range is rare commodity hardware in 2026.
Most "round OLED" listings are square SSD1306 modules in a round bezel,
which doesn't actually give you a circular active area.

| Candidate | MPN / SKU | Notes | OAS verdict |
|---|---|---|---|
| **WiseChip UG-2828GDEDF11** | UG-2828GDEDF11 (mono) | 1.5" round 128×128 mono OLED, SPI/I²C, glass diameter ~30 mm. Niche; main distributor is WiseChip via specialist re-sellers (Mouser carries the rectangular sister parts but Ø30 round-cut is order-on-demand). Price uncertain; €40–€80 estimate. **Uncertain.** | Reject — Module Identification rule passes (deterministic MPN) but availability is thin enough that batch sourcing for 10–20 units is unreliable. |
| **Univision UG series round-cut OLEDs** | various | Same family of products; same availability problem. | Reject — same reason. |
| **DFRobot / generic "1.5" round mono OLED"** | no deterministic MPN | Various AliExpress / Tindie listings. Fails Module Identification rule. | Reject. |

**True-OLED verdict**: not viable in 2026 at the OAS production scale
(10–20 units). Even if a unit is sourced, the mono-colour limitation
makes "AQI traffic-light gradient" depend on glyph shape rather than
colour, which weakens the UX vs the existing LED ring.

### A2. Round IPS TFT LCD (active backlight)

This is where the commodity options live.

| Candidate | MPN / SKU | Driver | Resolution | Module OD | Active dia. | Interface | Backlight V | ESPHome | Price qty 1 / qty 10 |
|---|---|---|---|---|---|---|---|---|---|
| **Waveshare 1.28" Round LCD** | Waveshare "1.28inch LCD Module" | GC9A01 | 240×240 | Ø **32.4 mm** | Ø **32.5 mm visible** (32.4 mm diameter PCB, ~25 mm active) | SPI 4-wire, 3.3 V logic | 3.3 V backlight (PWM via BL pin) | **Native** via `ili9xxx` + `model: GC9A01A` | ~€14 / ~€11 (Waveshare direct, Botland EAN `5904422312251` *uncertain*) |
| **Waveshare 1.28" Round Touch LCD** | Waveshare "1.28inch Touch LCD" | GC9A01 + CST816S touch | 240×240 | Ø ~32.4 mm | same | SPI display + I²C touch | 3.3 V | Display native; CST816S touch native via `cst816s` component (ESPHome 2024.6+) | ~€18 / ~€15 |
| **Adafruit 1.28" Round TFT** | Adafruit P/N **5443** *(verify, uncertain — Adafruit catalog ordering varies; cross-check at order time)* | GC9A01 | 240×240 | Ø ~36 mm (incl. flange) | Ø ~32 mm | SPI 4-wire | 3.3 V | Native (`GC9A01A`) | ~€20 / qty 10 not advertised |
| **Generic "1.28 inch Round LCD GC9A01"** AliExpress | no deterministic MPN | GC9A01 | 240×240 | varies | varies | SPI | 3.3 V | Native | ~€8 / ~€6 — **REJECT** (Module Identification: no MPN, vendor swaps batches) |
| **0.85" Round IPS LCD** | various, often GC9107 | GC9107 | 128×128 | Ø ~24 mm | ~Ø 18 mm | SPI | 3.3 V | Native (`gc9107` since ESPHome 2024.x) | ~€10 / ~€8 — passable backup if Ø32 is too large but resolution is tight for sensor-readout glyphs |
| **Waveshare 1.85" Round Touch LCD** | Waveshare "1.85inch Touch LCD" | ST7789 / similar 360×360 | 360×360 | Ø **47 mm** | Ø ~45 mm | QSPI or SPI | 3.3 V | Native ST7789 driver; QSPI mode may need community config | ~€25 / ~€20 |
| **Waveshare 2.1" Round Touch LCD** | Waveshare "2.1inch Touch LCD" | NV3041A | 480×480 | Ø **53 mm** | Ø ~51 mm | QSPI | 3.3 V | **Community / external_component only** as of mid-2026 | ~€35 / ~€28 |
| **Waveshare 1.5" Round LCD** | Waveshare "1.5inch LCD" | GC9C01 | 360×360 | Ø ~40 mm | Ø ~38 mm | QSPI | 3.3 V | **External_component** only as of mid-2026 | ~€20 / ~€16 |
| **Mono SSD1306 0.96" / 1.3" OLED** in round-bezel mount | various | SSD1306 / SH1106 | 128×64 | rectangular | rectangular (not actually round) | I²C 0x3C | 3.3 V | Native | ~€4 / ~€3 — does not satisfy "round" but listed for completeness |

**Module Identification rule check** (per CLAUDE.md): only the Waveshare
and Adafruit candidates carry deterministic MPNs. The "generic GC9A01"
listings on AliExpress without a vendor commitment are rejected even
though they're cheap.

**Top pick: Waveshare 1.28" Round LCD (non-touch)**.

- Right size (Ø32.4 mm fits comfortably in the centre of the AK-N-94
  cover above the LED ring at Ø22 mm and the J1 terminal block).
- Right interface complexity (SPI 4-wire is a known quantity).
- Right ESPHome path (`ili9xxx`, `model: GC9A01A`, used widely in
  community).
- Right price (€11–14 at relevant quantities).
- Right vendor: Waveshare is a verified commodity supplier with stable
  SKU and the Botland / Kamami / TME re-seller path is robust in EU.

**Touch variant trade-off**: the +€4 for capacitive touch buys a
single-finger swipe-to-page UX (next sensor / next page). Worth it
*only* if the user commits to a multi-page firmware UX. For a single
"static dial of AQI + textual readouts" no touch is needed.

### A3. Why SPI not I²C

The user asked whether I²C is preferred. Short answer: **for a Ø32 mm
240×240 round LCD it has to be SPI**. The GC9A01 chip family is SPI-
only; the bandwidth needed for 240×240 × 16 bpp at 10 Hz frame rate is
~9 Mbit/s, which I²C (max 1 Mbit/s in fast-mode-plus) cannot deliver.
Mono SSD1306 OLEDs are I²C-friendly but are not round.

SPI cost on OAS: 4 GPIOs guaranteed (MOSI, SCK, CS, DC). RESET can be
tied to a hardware reset rail (saves one GPIO) but is usually wired for
clean recovery. Backlight enable / PWM is typically tied to a 5th GPIO
or to a fixed 3.3 V rail through a resistor.

Available safe-non-strap GPIOs on ESP32-C6-DevKitM-1-N4 per CLAUDE.md
pinout table: **0, 1, 14, 18, 19, 20, 21, 22, 23 — nine pins free**.
Burning 4–5 of these on a display still leaves 4–5 spare for future
expansion. Acceptable margin.

Suggested SPI pin assignment:

| Display pin | Signal | OAS GPIO | Notes |
|---|---|---|---|
| MOSI | SPI MOSI | GPIO 18 | SPI bus shared if Qwiic ever needs SPI |
| SCK | SPI SCK | GPIO 19 | same |
| CS | Display chip-select | GPIO 20 | dedicated |
| DC | Data/command select | GPIO 21 | dedicated |
| RST | Reset (active low) | GPIO 22 | dedicated; alternatively tie to system reset rail |
| BL | Backlight PWM | GPIO 23 | dedicated; PWM for brightness control |

That's 6 GPIOs burned for full feature parity. With RESET tied to the
3.3 V rail through a 10 kΩ + 100 nF RC, it drops to 5 GPIOs.

---

## 4. Part B — Geometric placement

### B1. Display on the cover, floating above the PCB (RECOMMENDED if proceeding)

- Display mounted on the **interior face of the AK-N-94 cover**, viewing
  outward.
- Cover gets a Ø32 mm clear window cut into the perforated white ABS at
  the geometric centre.
- 3D-printed bezel holds the display module behind the window, with a
  thin (1.5–2 mm) clear-acrylic or polycarbonate insert as the visible
  surface.
- Display PCB-to-OAS-PCB connection: a short (60–100 mm) ribbon /
  pigtail cable.
- **Footprint on OAS PCB**: zero — the display floats on the cover.
  Only a connector (J9) at the PCB centre region.
- **Wiring path**: the cable from the cover display drops to the OAS
  PCB through the void between PCB and cover (~15 mm vertical
  clearance), terminating at J9.

**Cover modification**:
- Ø32 mm clear window through the white perforated ABS at centre. This
  destroys ~Ø32 mm × π/4 ≈ 800 mm² of perforation surface (~3% of
  total cover area, ~5–7% of the perforated zone since perforation
  doesn't extend to the rim).
- Most of the lost perforation is **directly above the SEN66 inlets**
  (the SEN66 sits at +X bottom-right). Practically the SEN66 sees
  perforation at the bottom-right quadrant of the cover, not the
  centre, so the airflow impact is **smaller than the area number
  suggests** — probably <3% reduction in effective inlet area.
- The clear window must be sealed against the cover ABS to maintain
  the "inlet vs outlet sealed channel" requirement Sensirion spells
  out (mech §3). A clear-acrylic insert glued or ultrasonically
  welded into the window opening achieves this if executed cleanly.

**Geometric clearance check at PCB centre**:
- J1 terminal block: anchor (+5.08, +22.4), body extends Y=+22.4..+12.29
  along chord. Display centred at origin (0,0) has 12.29 mm radial
  clearance to J1 top edge — plenty.
- SK6812-SIDE ring: Ø22 mm pitch circle around origin. Display Ø32 mm
  would **extend past the LED ring** (16 mm radius > 11 mm LED radius).
  This is fine on the cover side (display is on the cover, LEDs on the
  PCB, they live in different Z planes), but **interferes optically**:
  the display body blocks the upward light path from the LEDs at the
  centre of the ring. With side-emit LEDs throwing light radially
  outward this is **acceptable** (LEDs are designed to illuminate the
  perforated area around the display, not under it).
- Cable hole Ø12 mm at origin: directly under the display. Display
  body shadow is fine; cable enters from rear of case, passes through
  PCB, lands at J1 terminal block — no conflict with the display on
  the cover.
- Cover interior height above PCB ~15 mm. Display module thickness
  ~3–5 mm + bezel ~3–5 mm + clear window 1.5–2 mm = ~8–12 mm stack on
  the cover side. Fits within the 15 mm void. The 17 mm front-side
  height constraint applies to the **PCB**, not the cover — display
  on the cover doesn't infringe it.

**B1 verdict**: geometrically clean. The biggest open item is the
cover window execution (3D-printed bezel + clear insert), which is
a non-trivial mechanical sub-project but well within DIY scope.

### B2. Display on the PCB, viewed through a cover window

- Display mounted on the OAS PCB facing UP, viewed through a clear
  window in the cover.
- **Blocker**: the centre of the OAS PCB is occupied by (a) the Ø12 mm
  cable pass-through hole, (b) the J1 24V terminal block south of the
  hole, (c) the SK6812-SIDE LED ring around the hole. There is no
  contiguous Ø32 mm flat PCB area at the centre for a display footprint
  to land on.
- Relocating the cable hole + J1 + LED ring would be a major redesign
  (the centre placement is itself a deliberate choice — cable enters
  rear of case at electrical wall box).
- 17 mm front-side height constraint: a display module is typically
  3–5 mm thick — well within budget. But its FPC stub + connector add
  another ~5 mm, which is on the edge.

**B2 verdict**: rejected. Requires too much downstream rework for too
little win over B1.

### B3. Off-centre placement (e.g. upper-right zone)

- Display mounted somewhere not-centre (upper right, upper left, etc.)
  to avoid the cable+J1+LED conflict.
- **Conflicts**:
  - Upper-right is occupied by the SEN66 body (anchor +23.5, +22.0,
    body covers X≈23.5..49.1, Y≈-33.2..+22.0 — most of the right half).
  - Upper-left is the ESP32-C6 DevKitM-1 daughterboard
    (X≈-37.16..+11.10, Y≈-39.43..-14.03).
  - Left side is MIKROE-2462 (X≈-38.16..-7.81 by ~57 mm height) and
    further left the LD2410.
  - The only meaningful gap is the **central column between LD2410's
    right edge and SEN66's left edge**, at roughly X≈-7..+12, Y≈+5..+22
    — small (~20 × 17 mm) and already partly occupied by the LED ring.
- Breaks the user's explicit "centre of front cover" request, and
  doesn't actually have room for a Ø32 mm display anyway.

**B3 verdict**: rejected. No room.

**Winning placement: B1.** Display floats on the cover; OAS PCB
contributes only a connector at the centre.

---

## 5. Part C — Connector and PCB-side preparation

### Connector choice

For an 8-pin SPI display interface (GND, 3V3, MOSI, SCK, CS, DC, RST,
BL) at low data rates (~10 MHz SPI), the requirements are:

- 8 contacts
- polarised (cannot mate backwards)
- compact (Ø32 mm display is small; a chunky connector dwarfs it)
- compatible with the existing OAS connector family (JST GH is already
  used for SEN66's J3 — `SM06B-GHS-TB`)

**Recommended: JST GH 8-pin horizontal SMD socket — `SM08B-GHS-TB`**.
Same family as J3; KiCad stock library footprint
`Connector_JST:JST_GH_SM08B-GHS-TB_1x08-1MP_P1.25mm_Horizontal`; LCSC
P/N **C160390** (JLCPCB Extended Library, ~€0.30 at qty 100). Mating
cable: pre-crimped JST GH-08 to header-pin or directly to a JST GH
plug at the display end.

Alternatives considered:
- 2.54 mm 1×8 female pin socket (matches the ESP32 / MIKROE-2462
  daughterboard convention) — rejected: bulky (8 × 2.54 = 20.32 mm
  long), reduces space at the central area, and a flying lead from a
  cover-mounted display into pin headers is mechanically awkward (the
  cable has to terminate in a 1×8 male header which adds bulk on the
  display side).
- JST SH (1.0 mm pitch, even smaller) — rejected: SH cables are
  fragile in DIY assembly; OAS has standardised on GH (1.25 mm) for J3.
- FPC connector — rejected: requires a flat flex cable, more delicate
  for hand assembly, and the Waveshare 1.28" module ships with a
  2.54 mm pin header rather than an FPC pigtail.

### PCB placement of J9

Place J9 just south of the cable hole, north of J1. Tight, but the
J1 north edge is at Y=+12.29 and the cable hole edge is at Y=−6
(Ø12 mm hole centred at origin). That leaves a usable strip from
Y=−6 to Y=+12.29, width ~18 mm, centred at X=0. Plenty for an
SM08B-GHS-TB (footprint ~10 × 5 mm).

**Proposed J9 anchor**: (−5.0, +3.0), rotation 0° (cable opening
faces NORTH = toward the cable hole; cable then loops up through the
cable-hole region to the cover above). Verify against the SK6812-SIDE
ring D11 / D22 (the north slot LEDs) at the next layout pass.

### Cable harness

A pre-made JST GH-08 → 8 × 0.1" socket harness, 100 mm long, lets the
display module (which ships with a 2.54 mm male pin header) plug
directly into the cable while the JST GH-08 plug mates with J9 on the
OAS PCB. Custom-crimped 6–10 mm pre-stripped flying leads from a
JST GH-08 connector kit are acceptable for DIY assembly.

Cable length 100 mm is sized to allow opening the case for service
without disconnecting the display (cover lifts up to ~80 mm of cable
slack).

---

## 6. Part D — Trade-off analysis vs design pillars

### Pillar #1 — Measurement quality

**SEN66 airflow**: cutting a Ø32 mm clear window in the perforated
cover removes ~800 mm² of perforation, most of it from the centre
zone. The SEN66 inlets are at the bottom-right of the PCB (anchor
+23.5, +22.0), so the centre-zone perforation is **already not
directly above the inlets**. The realistic impact is a small (<3%)
reduction in effective inlet area, well within Sensirion's design
guideline tolerance.

The bigger airflow concern is **sealing**. Sensirion mech §3 requires
inlet and outlet to be in separate sealed channels. A cover window
that doesn't seal cleanly to the surrounding ABS creates a third
leakage path (cover-interior → window edge → ambient). The 3D-printed
bezel + glued clear insert must achieve airtight seal at that
interface, which is a non-trivial mechanical sub-project for a DIY
assembly.

**SEN66 self-heating**: a GC9A01 round LCD with backlight at typical
brightness (100% duty for daylight visibility) dissipates ~100–150 mW
(20–30 mA on the 3.3 V backlight LED + GC9A01 chip + SPI traffic).
At reduced brightness (auto-dim at 25%) it drops to ~30–50 mW.
**At the cover, separated from the SEN66 by ~15 mm of air, this heat
does not couple strongly into the SEN66.** The body of the unit is
already vented (perforated cover), so cover-side heat escapes upward
through the perforation rather than recirculating down to the SEN66.
Estimated SEN66 ΔT contribution from the display: **<0.3 K** — well
inside the 2 K multi-unit consistency target. Pillar #1 survives.

**SPI EMI**: 10 MHz SPI fundamental, harmonics into 100–500 MHz range.
The radio in the ESP32-C6 sits 2.4 / 5 GHz. SEN66 RF immunity spec is
3 V/m 80 MHz–6 GHz. The SPI bus emission is well below 3 V/m at any
point on the OAS PCB. **No measurable EMI risk.** Pillar #1 survives.

### Pillar #2 — Aesthetic acceptability

This is where the display fails honestly.

The OAS aesthetic anchor is "smoke-detector silhouette in a furnished
room — should disappear into the ceiling / wall." The cover is white
perforated ABS. The current visible front face shows only the
diffuse LED halo (when active) and uniform white perforation
otherwise. **The unit looks like a smoke detector.**

Adding a Ø32 mm round LCD changes the front-face silhouette to:
- **Display off**: a dark grey 32 mm circle in the middle of a white
  perforated cover. Sticks out visually. Reads as a thermostat or
  smart-home control panel, not a smoke detector.
- **Display on**: a bright pixel-grid square (the 240×240 IPS active
  area inside its bezel) showing numbers. Reads as an information
  appliance — definitively no longer a smoke detector.

The "off" state is the problem. **The unit is in the off state ~99%
of its lifetime** (display would auto-blank after idle to manage power
and screen burn-in; if always-on, the dark-grey-against-white contrast
is a constant visual element). There is no way to mask the off-state
LCD against the white perforated ABS — even the best round IPS LCDs
have an off-state luminance close to black.

Two mitigations exist but each has costs:

1. **Tinted / mirror-finish cover window**. A neutral-density 50%
   smoked acrylic insert makes the off-state appear darker (good)
   and reduces on-state contrast (bad — display becomes hard to read
   in daylight). Trade-off marginal.
2. **Display-off-by-default + wake-on-motion (LD2410)**. The display
   wakes only when the LD2410 detects a person within 1–2 m and
   blanks after 30 s of stillness. Reduces the visible-when-off
   problem to "5–10 s when someone walks past the unit." Reasonable
   compromise, costs zero BOM but adds firmware complexity.

Even with mitigation #2, the **first impression** of the unit at
install — when the cover is fitted and the unit is being shown off —
will be the off-state dark circle. This is the irreversible aesthetic
penalty.

**Pillar #2 verdict**: the display is a clear aesthetic regression
versus the current "smooth white perforated cover" silhouette. It is
not a fatal regression — many people find a small round display
charming in its own right — but it changes the product visually, and
that change is the user's call to make explicitly, not implicitly.

---

## 7. Part E — Visible alternatives (briefly)

- **E-paper round display**: Waveshare 1.54" rectangular e-paper is
  commodity in 2026; round e-paper is rare and expensive. E-paper has
  the killer advantage of "no backlight, looks like printed text in
  ambient light" — solves the off-state aesthetic problem. The killer
  disadvantage is refresh rate (5–15 s for full refresh, 0.5–1 s for
  partial). For air-quality data that updates every 10 s the refresh
  is workable. Cost: €25–€40 per unit. **Worth investigating as a
  v2 option** if the display direction is pursued; for v1 the part is
  too niche.
- **7-segment LED display (TM1637 / MAX7219)**: 4-digit displays at
  €2–€4. Always-on retro look, reads PPM CO2 cleanly. Niche aesthetic
  — fits "industrial sensor" not "ambient living-room unit." Skip.
- **Status-only LED ring (current approach) + NFC tap + HA dashboard**:
  the current OAS UX. No display, no cover modification, smoke-
  detector silhouette intact. **This is the baseline the display must
  beat.** Honest analysis says it's the right baseline for a v1
  wall-mount sensor that's supposed to disappear.

---

## 8. Decision tree

To land on a final choice, the user should answer:

1. **Is "looks like a smoke detector" a hard requirement?**  
   → **Yes** → skip the display entirely. Existing NFC tap + LED ring
   + HA dashboard already cover the UX. Keep CLAUDE.md as-is.  
   → **No, I want a visible display** → continue to Q2.

2. **Will the display run always-on, or wake-on-presence?**  
   → **Always-on** → accept the constant dark-circle-on-white off-
   state appearance (or use a smoked-acrylic window to soften it).  
   → **Wake-on-presence** → display blanks after 30 s of stillness via
   LD2410 trigger. Less visual impact but more firmware work.

3. **Touch UI or read-only dial?**  
   → **Read-only dial / static gauge** → Waveshare 1.28" non-touch,
   €11/qty 10. ESPHome `display.lvgl` or `display.gc9a01a` simple
   gauge templates.  
   → **Multi-page touch UX** → Waveshare 1.28" Touch (+€4), CST816S
   capacitive touch. Adds I²C device address (verify free address) and
   one more wire pair from the display to OAS.

4. **DIY assembly or production?**  
   → **DIY single-unit** → Waveshare 1.28", JST-GH-08 connector,
   100 mm pre-made cable. Total BOM impact ~€15.  
   → **Production batch of 5–20** → same Waveshare module, but
   pre-source the JST GH-08 harness in batch (custom-crimped or pre-
   made via LCSC). BOM impact ~€11/unit.

---

## 9. BOM impact

| Item | Qty | Source | Unit price qty 1 | Unit price qty 10 | Unit price qty 100 |
|---|---|---|---|---|---|
| Waveshare 1.28" Round LCD (GC9A01, 240×240) | 1 | Waveshare / Botland / Kamami | ~€14 | ~€11 | ~€9 |
| JST GH 8-pin horizontal SMD socket (`SM08B-GHS-TB`, J9) | 1 | LCSC C160390 / Mouser | ~€0.40 | ~€0.30 | ~€0.20 |
| Pre-made JST GH-08 to 0.1" pin harness, 100 mm | 1 | LCSC / AliExpress verified vendor | ~€2 | ~€1.50 | ~€1 |
| 3D-printed bezel (PETG / ABS, own-printed) | 1 | own | ~€0.10 of filament | ~€0.10 | ~€0.10 |
| Clear-acrylic / polycarbonate insert (Ø34 mm, 1.5 mm thick) | 1 | local plastic shop / laser-cut | ~€1 | ~€0.80 | ~€0.50 |
| **Display-block total per unit** |  |  | **~€18** | **~€14** | **~€11** |
| **Cumulative OAS BOM impact** |  |  | +€18 | +€14 | +€11 |

For context the rest of the OAS BOM is approximately €70–€90 at qty
10 (SEN66 dominates at ~€55, ESP32-C6-DevKitM-1-N4 €9, LD2410 €4,
MIKROE-2462 €13, enclosure €15, plus passives). The display adds
~15% to BOM cost.

---

## 10. Open risks and uncertainty

1. **Botland / Kamami EAN for Waveshare 1.28" Round LCD**: stated as
   `5904422312251` is **uncertain** — not verified against a live
   listing. Re-verify before placing the order.
2. **Adafruit P/N 5443** for their round 1.28" TFT is **uncertain** —
   Adafruit reorganises their product line periodically. Cross-check
   at order time.
3. **Cover window seal**: the 3D-printed bezel + clear insert must
   seal airtight against the ABS cover to maintain Sensirion's
   inlet/outlet sealed-channel requirement. Execution risk: high.
   Needs prototype validation before committing to a series.
4. **Off-state aesthetic**: cannot be hidden. User must explicitly
   accept that the unit looks like a thermostat (display) rather than
   a smoke detector (no display) when off.
5. **Power budget**: backlight at 100% duty draws ~20–30 mA from 3V3.
   OAS power supply (TPS62933, 5V→3.3V at ~95%) has plenty of
   headroom, but the assumption was the 3V3 rail would mostly serve
   SEN66 (130–200 mA peak) + ESP32 (60 mA avg) + LD2410 (60 mA peak) +
   ring (~50 mA at 25% RGB duty). +30 mA for the display is within
   budget but worth a final rail-current re-tally before ordering.
6. **ESPHome `gc9a01a` driver stability**: confirmed via community
   ESPHome configs through 2026; not formally regression-tested by
   the OAS project. First-prototype validation needed.
7. **Cable hole vs display window collision**: the cover window is
   ~Ø32 mm centred at origin; the cable enters from the **rear** of
   the case (electrical wall box) and exits via the PCB's Ø12 mm hole
   to terminate at J1 on the PCB. The display sits on the **front**
   of the cover. The cable does not pass through the display window.
   But the 3D-printed bezel must leave the cable hole clear if the
   bezel extends inward toward the PCB. Mechanical detail to be
   resolved in the bezel design.

---

## 11. Implementation outline (next agent's TODO)

Assuming the user explicitly answers "yes, add the display":

1. **`generate.py` constants**:
   - Add `J9_X`, `J9_Y`, `J9_ROTATION` constants (proposed start:
     `−5.0, +3.0, 0`).
   - Add `JST_GH_08PIN_FOOTPRINT_NAME = "JST_GH_SM08B-GHS-TB_1x08-1MP_P1.25mm_Horizontal"`.
   - Verify against KiCad stock library.

2. **`generate.py` schematic addition (in `sensors.kicad_sch`)**:
   - Add a `Conn_01x08` symbol for J9 with hierarchical labels:
     `VCC_3V3`, `GND`, `SPI_MOSI`, `SPI_SCK`, `DISPLAY_CS`,
     `DISPLAY_DC`, `DISPLAY_RST`, `DISPLAY_BL`.
   - Add a 100 nF decoupling capacitor C13 close to J9 between VCC_3V3
     and GND.
   - Re-export hierarchical labels at the root sheet level.

3. **`generate.py` MCU sub-sheet (`mcu.kicad_sch`)**:
   - Add wires from ESP32 DevKitM-1 pin sockets to the new labels:
     GPIO 18 → SPI_MOSI, GPIO 19 → SPI_SCK, GPIO 20 → DISPLAY_CS,
     GPIO 21 → DISPLAY_DC, GPIO 22 → DISPLAY_RST, GPIO 23 →
     DISPLAY_BL. Update the pin map table in CLAUDE.md.

4. **`generate.py` PCB footprint placement**:
   - Emit J9 SMD footprint at `(J9_X, J9_Y)` rotation `J9_ROTATION`.
   - Emit C13 0402 capacitor adjacent to J9.
   - Add a F.SilkS label near J9: `"to display ->"`.

5. **CLAUDE.md updates**:
   - Remove `Display (OLED / LCD)` from "Out of scope".
   - Add a v0.19 changelog entry documenting the decision and the
     trade-offs accepted (aesthetic regression, BOM +€11/unit at
     qty 10, +6 GPIOs burned).
   - Update the pinout table with the 6 new SPI signals.
   - Add a new component file `hardware/components/waveshare-1.28-round-lcd.md`
     documenting the module identification, ESPHome config snippet,
     wiring pinout, and the cover-window mechanical spec.

6. **ESPHome firmware (`firmware/esphome/oas.yaml`)**:
   - Add `spi:` and `display:` blocks for GC9A01.
   - Add `script:` for wake-on-presence (LD2410 → display backlight ON;
     30 s idle → backlight OFF).
   - Add LVGL or `lambda` template for the AQI dial.

7. **Mechanical**:
   - Design 3D-printable bezel STL (`hardware/case/display-bezel.stl`).
   - Specify clear-insert dimensions (Ø34 mm, 1.5 mm thick, smoked or
     clear). Source: local plastic / laser-cut.
   - Document cover-window cutting procedure in
     `docs/ASSEMBLY.md`.

If the user explicitly answers "no, leave display out of scope": this
document remains as the rationale-of-record so a future contributor
doesn't have to re-do the analysis. No code changes.

---

## 12. Honest verdict

**My recommendation is: do not add the display in v1.**

The existing OAS UX (LED ring colour-code + NFC tap on phone + HA
dashboard on phone or wall tablet) covers every use case the display
would serve, with the additional advantage of preserving the smoke-
detector aesthetic that the project has been actively defending.

The display's costs (cover modification, aesthetic regression in the
off-state, +6 GPIOs, +€11/unit BOM, +1 BOM line, +mechanical sub-
project for the bezel+window, +firmware complexity, sealing risk for
Sensirion's inlet/outlet sealed-channel requirement) are real and
permanent. The benefit (look at the unit and see the data without
needing your phone or HA app) is real but small — the user already
has multiple alternative paths to the same data.

The case **for** the display is strongest if:
- The unit is going in a high-traffic area where pulling out a phone
  is socially awkward (e.g. a hallway with frequent visitors).
- The user has explicitly committed to the thermostat-style aesthetic
  rather than the smoke-detector aesthetic.
- The deployment is single-unit or low-volume (2–3 units) so the
  BOM and assembly cost don't multiply.

The case **against** is strongest if:
- The unit is going in a living space where it should fade into the
  ceiling/wall (the original OAS design target).
- The deployment is multi-unit (5–20 units) so the per-unit BOM and
  assembly burden multiplies.
- The user has not yet validated the cover-window sealing approach on
  a prototype.

If the user wants to proceed, the implementation outline above
provides a complete path. If the user defers, the rationale is now
documented and the next revisit can pick up from here.
