# Post-fix review — v0.15.8 → v0.15.9 cleanup log

Brief log of what the independent code review of v0.15.8 found, what the
intermediate fix-agent pass addressed, and what this commit pass (today)
mopped up. Kept short on purpose; the canonical narrative is in
`CLAUDE.md` and the v0.15.8 / v0.15.9 commit messages.

Date: 2026-05-13.

---

## What the review found in v0.15.8

After the v0.15.8 chunk-of-three (LD2410 body shrink 15.24→7.62 mm, J3
flip, body labels moved to board-level `gr_text`), an independent review
flagged a set of residual items:

1. **LD2410 silkscreen vanished from the physical PCB.** The shrink to
   body_h = 7.62 mm made the J4 stock-footprint silk frame wider than
   the body itself in the short axis, so any closed silk rect at body
   extents would either overlap J4 silk or sit useless inside the body.
   v0.15.8 set `LD2410_EMIT_SILK_OUTLINE = False` as the only safe
   short-term option, leaving the body without a visible silhouette on
   F.SilkS — only the board-level "HLK-LD2410B" gr_text remained.
   User reported this as a regression and asked for the silhouette to
   come back.

2. **Stale pin-order comment block** at `generate.py` ~ line 11865-11885
   still listed the OLD wrong order ("Pin 1: VCC ... Pin 5: OUT").
   The corrected order ("Pin 1: OUT ... Pin 5: VCC") lived ~20 lines
   further down at line 11911-11918 and in the `J4_PIN_Y` dict — two
   sources of truth, one stale.

3. **Three stale "enclosure cover" mentions** in `generate.py`:
   - `gen_sen66_mechanical_footprint` docstring (line ~755) still said
     "the SEN66 doesn't bolt to the PCB; it lives on the enclosure cover".
   - `gen_cutouts` comment (line ~1316) said "the SEN66 itself lives on
     the cover, not on the PCB".
   - `gen_ziptie_hole_footprint` `descr` (line ~2680) said the zip-ties
     "retain the SEN66 module against the enclosure cover". This one
     flows into the production footprint metadata.
   All three predate the v0.6 cover→PCB migration.

4. **MIKROE-2462 descr mismatch** at `generate.py` ~ line 12492 still
   said "mikroBUS size S, 25.4×28.6×7 mm" — the v0.15.5 fix corrected
   `MIKROE2462_BODY_L` from 28.6 to 57.15 (size L) but missed the
   `descr` string. Plus the leading comment block at line 427-434
   ("size S — 25.4 × 28.6 mm, NOT the 42.9 mm size M") was the
   pre-v0.15.5 narrative.

5. **`_ld2410_local_to_pcb` docstring** (line ~335) claimed
   "Currently LD2410_ROTATION = 0 so this is just a translation"
   — actual is 270 (v0.11+) so the rotation matrix is actively used.

6. **CLAUDE.md line 154** still claimed I²C bus length of "<40 mm total"
   from the v0.6 assumption. v0.15.8 changelog acknowledges realized
   length is ~60 mm.

---

## What the intermediate fix-agent pass addressed (commits before today)

- v0.15.8 commit `1fd9bde` itself shipped the LD2410 body_h shrink,
  J3 flip, and the move of body labels to board-level `gr_text`. It
  is the commit that *introduced* the silkscreen regression for
  LD2410 — the body silk rect was intentionally dropped, with
  `LD2410_EMIT_SILK_OUTLINE = False` and a comment explaining the
  constraint, awaiting a better approach.

- v0.15.8.1 / commits `85d8a7a`, `74df170`, `ec0d250`: J4 pin-order
  end-for-end swap (Task #1 of the original review) was applied; the
  J4_PIN_Y dict at line 11925 now reflects the datasheet order.
  CLAUDE.md changelog updated for v0.15.7 / v0.15.8 narrative.
  The comment block at line 11865+ explaining J4 was NOT updated at
  the same time → became the stale text this pass cleans up.
  CLAUDE.md line 154 was not updated either.

---

## What this pass (v0.15.9) addressed

**Commit 1 — `kicad: v0.15.9 - restore LD2410 silkscreen ...`**
   Implements Approach B (U-shaped silk, 3 fp_line, no closed rect)
   in `gen_ld2410_mechanical_footprint` AND
   `gen_ld2410_reference_pcb_footprint`. The U opens on the connector
   short edge so the J4 stock-footprint silk frame handles that side;
   both long edges stop at `LD2410_SILK_INSET_CONN = 1.8 mm` (was
   0.2 mm) so they clear J4 silk-frame Y zone with 0.25 mm gap.

   Side effect: the existing board-level "HLK-LD2410B" and "antenna ^"
   gr_text labels had a horizontal bbox exceeding the new internal
   silk-U width and triggered silk_overlap DRC. Rotated those two
   labels 90° so they run along the body's long axis, comfortably
   inside the 35.56 mm span. DRC=0, ERC=0.

**Commit 2 — `docs+kicad: cleanup leftover stale comments from v0.15.8 review`**
   Items #2-#6 above:
   - Pin-order comment block updated to OUT/Tx/Rx/GND/VCC matching the
     code and the datasheet (citing HLK-LD2410B Datasheet V1.04 Table 1
     page 7).
   - Three "enclosure cover" mentions rewritten to reflect PCB-mount.
     The zip-tie footprint `descr` now says "retain the SEN66 module
     flat against the PCB (v0.6+ face-up PCB-mount)".
   - MIKROE-2462 `descr` and the comment block at line 427 updated to
     "size L, 25.4×57.15 mm" with the antenna spiral on the ~36.83 mm
     strip past pin 8.
   - `_ld2410_local_to_pcb` docstring updated to mention
     `LD2410_ROTATION = 270` (v0.11+) and that the rotation matrix is
     actively used, not vestigial.
   - CLAUDE.md line 154: replaced the "<40 mm total" claim with
     "~60 mm realized, still well within Sensirion's <100 mm hard
     limit, much shorter than the previous 80 mm off-PCB JST-GH cable
     run". Aligns the body text with the v0.15.8 changelog narrative.

---

## Status now

- LD2410 silhouette is visible on F.SilkS in the 3D-top and 2D-top
  renders. DRC=0, ERC=0.
- All five doc-hygiene findings from the post-v0.15.8 review have
  been addressed.
- No remaining work flagged by the review.

Open items unrelated to this review pass:
- SEN66 airflow sealing decision (foam shroud vs cover baffle) is
  still deferred until the physical AK-N-94 sample arrives.
- Post-prototype LED desolder on the DevKitM-1 (v0.5 plan) still
  pending first-prototype assembly.
- Hard constraint #1 verification (≥22 mm clearance in SEN66 zone of
  AK-N-94) still pending physical sample.
