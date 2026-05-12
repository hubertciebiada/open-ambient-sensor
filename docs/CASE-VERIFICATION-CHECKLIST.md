# Enclosure verification checklist (post Aliexpress delivery)

Status: **PENDING** — verify each item against the physical AK-N-94 sample when it arrives.

Several decisions in the current schematic and PCB are based on the manufacturer DXF (annotated in Chinese, gitignored under `hardware/case/`). Some annotations are ambiguous or globally applied where they may have been region-specific. This checklist captures every assumption that needs a physical verification before locking in the PCB layout.

---

## 1. Front-side height limit (17 mm)

**Current assumption**: 17 mm maximum component height on the front side, derived from DXF annotation `正面限高 17mm` ("front-side height limit 17 mm").

**Open question**: is this limit **global** (entire PCB area) or **regional** (specific zone, e.g. SEN66 bracket area, mounting pillars)?

**To verify**:
- Open DXF and check whether the 17 mm annotation has a bounding region attached, or is a single dimension line tied to a specific feature
- Measure physical sample: from PCB mounting plane (where M3 bosses contact PCB) up to the nearest enclosure inside surface (cover, ribs, brackets) — note where the minimum occurs and where the maximum occurs
- Identify any cover-side features (SEN66 mounting bracket, LED light pipes, screw bosses) that may impose local minimums

**Implication if limit is larger**:
- Issue #3 from the second review (cap height violation) goes away
- Can use radial through-hole electrolytics (cheaper, more capacitance options) instead of SMD aluminum D-can
- Can use larger inductors with better thermal performance
- Possibly TO-220 with passive heatsink for LM2596 if dissipation becomes a concern

**Implication if limit is smaller (e.g. 15 mm)**:
- Re-evaluate all currently-tall components (SEN66 itself is 21.5 mm — already on cover, not PCB)
- C1, C3 (100 µF/50 V) might not fit even in SMD D-can — go to multi-layer ceramic or polymer

## 2. Back-side height limit (5 mm with washers, originally 3 mm)

**Current assumption**: 5 mm effective back-side clearance, achieved by adding **2 mm washers under the M3 mounting screws**. This lifts the PCB 2 mm off the enclosure's mounting bosses, gaining 2 mm extra back-side clearance over the DXF-annotated 3 mm baseline.

Originally the DXF annotation `背面焊脚限高 3mm` ("back-side solder-pin height limit 3 mm") was treated as a hard limit. The user opted to relax it to 5 mm via washers — back-side now tolerates standard through-hole pin-header bottoms (typically 2.5-3 mm protrusion after trimming) without requiring tight pin-trimming during assembly.

**To verify**:
- Confirm 3 mm is **solder-pin height** in the original DXF (through-hole protrusions on the back of the PCB), not "no component height of any kind"
- Verify the mounting bosses on the physical sample have enough thread depth to accommodate the 2 mm washer + M3 screw without bottoming out (M3 screw typically 6-8 mm thread engagement; bosses need to be at least 8 mm deep to support both)
- Verify the front-side clearance (17 mm assumption) is unaffected by the washer lift, or whether the 2 mm PCB lift reduces effective front clearance proportionally

**Implication**:
- Standard through-hole pin headers fit without aggressive pin trimming
- SMD components on back side are still discouraged (cleanliness), but if needed up to ~4 mm tall parts could be placed
- Slightly increased thermal pathway through PCB to the enclosure cover (PCB now 2 mm further from rear-cover heat sink, but rear cover is already minimal thermal-sink contribution)

## 3. Cable pass-through hole (Ø12 mm, PCB centre)

**Current assumption**: 24 V wires enter from rear of case through the centre of the PCB (Ø12 mm hole), terminate at J1 on the front.

**To verify**:
- Physical sample has a corresponding hole / cable gland on the rear cover? Or do we drill it ourselves?
- Does the rear cover have enough room for a strain-relief / cable gland fitting?
- Is the Ø12 mm sized correctly for 3× 1.5 mm² conductors (e.g. YDY 3×1.5 outer Ø ≈ 8–9 mm) with some bend radius margin?
- Distance from rear of enclosure to PCB back side — enough to accommodate cable bending?

## 4. Connector cutouts in the case wall (C1–C5)

**Current assumption**: 5 rectangular cutouts in the case wall at the chord position, with dimensions per `hardware/case/README.md`.

**To verify**:
- Each cutout is at the position we encoded (origin = PCB centre)
- Each cutout is the size we encoded (W × H per the README table)
- The "language tab" Ø3 mm semicircle above C4 — does it actually exist on the physical sample? Does it interfere with anything?
- C2 and C3 are encoded as "clipped at chord" (would extend beyond the flat edge of the PCB by 1-3 mm). Verify that the case wall behavior matches — does the enclosure indeed have cutouts going down to the chord plane?

## 5. Mounting holes (3× M3 on Ø110 mm pitch circle)

**Current assumption**: 3 M3 mounting holes on a Ø110 mm pitch circle, equilateral triangle, NPTH (screws go into plastic bosses).

**To verify**:
- Physical bosses present at the correct positions (within ±0.5 mm)
- Bosses are plastic (not metal inserts) — confirms NPTH choice
- M3 screws thread directly into plastic (typical depth ~6-8 mm) — no over-tightening required
- Distance from boss tops to PCB plane — confirms whether washers or standoffs are needed

## 6. SEN66 mounting on cover

**Current assumption**: SEN66 mounts on the inside of the front cover via a 3D-printed bracket (TBD), connected to the PCB via a 50 mm JST-GH cable.

**To verify**:
- Cover has enough internal clear area to mount the bracket — typical SEN66 module is ~28×30×21.5 mm; needs free space directly above the bracket location
- Bracket-to-PCB cable routing: clearance between the bracket and PCB components (specifically anything in the central area — Q1, D1, J1 are at the bottom but the cable runs centrally)
- Perforation pattern on the cover — is the SEN66 air inlet directly under perforated area? (Air must reach the sensor.)
- Bracket should hold the sensor such that the inlet pad faces the perforations, with no internal obstruction within ~5 mm

## 7. Perforation pattern on the cover

**Current assumption**: the AK-N-94 cover is perforated white ABS, "smoke-detector form factor" style — radial slots or hole array allowing airflow.

**To verify**:
- Pattern is dense enough for airflow to reach SEN66 inlet (the sensor expects no air-restricting features within ~5 mm)
- Perforations also help convective heat removal from the POWER sector (upper-left in PCB orientation)
- Light path for the front status LED (WS2812) — is there a clear (non-perforated) section over its planned location? Or do we accept the LED light coming out through perforations? (Aesthetic decision.)

## 8. PCB outline match

**Current assumption**: Ø120 mm D-shape (R=60 mm arc + 82.65 mm flat chord). Encoded into KiCad outline.

**To verify**:
- Place a test PCB (cardboard cutout of correct geometry would do for first pass) inside the enclosure — does it land within the mounting bosses with 0.5-1 mm clearance all around?
- Specifically check that the flat chord (82.65 mm) doesn't interfere with internal ribs / features
- Verify the orientation — which side of the PCB faces the cover, which faces the rear cover (the rear cover has the cable entry; the front cover has the perforations + SEN66 bracket)

## 9. Aesthetic acceptability (pillar #2)

**Current assumption**: the enclosure is the right form factor for a wall-mounted sensor in a living space.

**To verify subjectively**:
- Does the enclosure look acceptable on a wall? Mock-mount it temporarily and check from typical room viewing angles
- Does the ABS color match other wall fixtures (light switches, smoke detectors, etc.)?
- Does the perforation pattern look intentional / industrial-design-quality, or cheap / off-putting?
- Any visible mold lines, parting seams, or sink marks that affect perceived quality?

If the answer to any of the above is "no", **this is a critical issue** — pillar #2 cannot be compromised. Reject the enclosure and find an alternative before committing to PCB fab.

## 10. Cable entry strain relief

**Current assumption**: 24 V cable enters through PCB centre Ø12 mm hole. No explicit strain relief — relying on terminal block clamping + cable gland on the rear cover.

**To verify**:
- Does the rear cover come with a cable gland fitting, or is it a plain hole? (If plain, we add a third-party gland.)
- If a gland is included: thread spec (M12? PG7? metric?) — needed for cable selection
- Verify the cable bend radius inside the case — short bend at the hole exit might over-stress the insulation. May need to relocate J1 if bend radius is insufficient.

---

## Decisions to revisit AFTER verification

| Issue | Currently | After verification, possibly |
|---|---|---|
| Cap footprints (C1, C3, C4) | Pending — depends on actual height limit | SMD D-can OR radial through-hole |
| LM2596 thermal pad | DPAK with 2000 mm² copper pour | Add passive heatsink if more vertical space available |
| Connector strip positions (C1–C5) | Locked from DXF | Tweak ±0.5 mm if physical mismatch |
| SEN66 bracket geometry | TBD, will design after enclosure measurement | Print bracket, test fit, iterate |
| Cable gland thread | Unknown | Add to BOM once known |

---

## How to use this list

1. When the AK-N-94 sample arrives, work through each section in order
2. For each item, record findings in this file directly (commit changes — they go into the public repo as documentation)
3. Items that become "verified, no issue" can be removed from the list
4. Items that require schematic / PCB changes become new chunks in the regeneration workflow
5. Items that affect both pillars (measurement quality + aesthetic acceptability) take priority

When all items are verified or resolved, this file can be archived or kept as historical reference.
