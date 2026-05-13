# OAS PCB v0.23 — Review Iteration #2 (independent verification)

- **Date**: 2026-05-13
- **Reviewer**: Opus 4.7 (independent agent, fresh session)
- **Scope**: `C:\Git\open-ambient-sensor\` at commit `abccb472a173e18a8be6456fd4ceb1fdc15cb0b6` (v0.23 — "close all Minor + Nits from review iteration 1")
- **Purpose**: independent verification that the fix agent's v0.23 work closed the iter-1 findings without introducing regressions, so the fix-review loop can terminate.
- **kiutils version**: **1.4.8** (`pip install --user kiutils`)
- **KiCad CLI**: `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`
- **Working dir**: `C:\Git\open-ambient-sensor\hardware\kicad`

---

## TL;DR — the loop does NOT terminate at v0.23

The v0.23 commit ships an inconsistent state: the **source-of-truth Python (`generate.py`) has been updated**, but the **derived KiCad files were NEVER regenerated** before commit. As a result:

1. At HEAD, ERC = 0 / 0 only because the committed `*.kicad_sch` files are STALE — they still reflect the v0.22 schematic state without the Mn3 back-fill.
2. The committed `oas.kicad_pcb` lacks the Mn4 J2/J10 `dnp` flags entirely — those exist only in Python.
3. Running `python regenerate.py` (the canonical workflow per CLAUDE.md "PCB design workflow") REBUILDS the derived files and exposes a real regression: **ERC goes from 0/0 to 0 errors + 15 warnings.** The 15 warnings (`footprint_link_issues`) are caused directly by the Mn3 back-fill writing lib-less footprint strings (e.g. `"SOT-23"`, `"C_0402_1005Metric"`) into the schematic's `Footprint` property — KiCad ERC then complains that "current configuration does not contain footprint library ''" (empty library prefix).

CLAUDE.md "PCB design workflow" §3 says: *"runs `kicad-cli pcb drc` and `kicad-cli sch erc` and aborts on any error or warning."* The v0.23 commit's regenerate.py does not abort on ERC warnings (only DRC does, via `--severity-warning`). So 15 schematic warnings sailed through without alarm.

Additionally, **CLAUDE.md has no v0.23 changelog entry**: the fix agent's brief required "verify the v0.23 entry exists and is honest" — the entry does not exist.

---

## Verification of v0.23 claimed fixes (V1..V8)

### V1 — Mn1 closure: zip-tie X positions doc fix **— PASS**

CLAUDE.md line 149 now reads:

> Realized (v0.7+): **Pair 1 at X = 22, Pair 2 at X = 30** — both inside the strict safe corridor, no outlet overlap. (Earlier draft suggested X ≈ 50 as a second pair, but X=50 sits inside the outlet circle X=32..53 and would block ~8% of outlet area; rejected.)

The speculative "X ≈ 25 / X ≈ 50" text is gone. `generate.py` `SEN66_ZIPTIE_LOCAL` confirmed to hold these realized values. **PASS**.

### V2 — Mn2 closure: v0.6 "<40 mm" historical retraction **— PASS**

CLAUDE.md line 480 now ends with:

> **[Retracted in v0.15.8 / v0.22 — see Architectural decisions §"Shared I²C bus" for the honest realized value of ~140 mm PCB MST + ~80 mm cable = ~220 mm total. The "<40 mm" target was never met by the realized geometry.]**

In-place historical-retraction annotation present. **PASS**.

### V3 — Mn3 closure: empty `Footprint` property back-fill **— FAIL (regression introduced)**

Implementation present (`generate.py` lines 16771–16871 `_build_pcb_ref_to_footprint` + `_apply_schematic_footprints`, called from `main()` at line 16955). However:

a) **The committed `.kicad_sch` files are STALE.** A direct check of the v0.23 commit shows NO `.kicad_sch` changes (`git log --name-only abccb47`). Only `generate.py` / `regenerate.py` / `CLAUDE.md` / renders were committed. So at HEAD, the schematic still has `(property "Footprint" "")` for all 51 affected symbols — exactly as in v0.22. The fix is in Python but not in the derived artefacts.

b) **Running `regenerate.py` to apply the fix exposes a regression.** kiutils enumeration after a fresh `python regenerate.py` invocation shows the schematic now contains lib-less footprint strings like `"SOT-23"`, `"CP_Radial_D8mm_P3.5mm"`, `"C_0402_1005Metric"`. KiCad ERC then emits 15 `footprint_link_issues` warnings of the form:

```
[footprint_link_issues]: Obecna konfiguracja nie zawiera biblioteki footprintów ''
    ; warning
    @(82.55 mm, 78.74 mm): Symbol Q1 [Q_PMOS]
```

The 15 affected symbols are: Q1, C1, C3, C4, C20, C21, C22, C24, C25, C26, C27, C28, C29, C30, C31. (Power-section radial-CP polarized caps + decoupling 0402 caps + Q1 SOT-23.)

**Root cause**: the v0.22 PCB footprint generators emit `(property "Footprint" "<bare_name>")` for many footprints — e.g. `gen_c_0402_pcb_footprint` writes literally `"C_0402_1005Metric"` (no `Capacitor_SMD:` prefix); `gen_q_sot23_pcb_footprint` writes `"SOT-23"` (no `Package_TO_SOT_SMD:` prefix). The Mn3 post-process treats the PCB-side Footprint property as the canonical lib path (`canonical = m_fp_prop.group(1) if m_fp_prop else fp_name`), but for these 15 footprints that property is itself bare. The schematic ends up with `(property "Footprint" "SOT-23")` etc., and ERC parses `""` as the lib name → footprint_link_issues warning.

**Why the fix agent's commit didn't catch this**: the fix agent did not regenerate-and-recheck before commit, and `regenerate.py` does not abort on ERC warnings. The v0.22 baseline had `(property "Footprint" "")` which ERC accepts as "footprint not assigned (silent — no error)". The v0.23 Mn3 attempt to be more helpful introduces a *malformed* footprint reference, which ERC objects to.

**Possible fixes** (for the next iteration):
- Pre-normalize the PCB-side Footprint property to always include the proper lib prefix at footprint-generator time (touches ~10 helper functions). Then the Mn3 post-process produces valid schematic references and ERC stays silent.
- Only back-fill when the PCB Footprint string contains a `:` (skip lib-less ones). Then those 15 symbols stay with `(property "Footprint" "")` — same baseline as v0.22. Cheaper but partial.
- Hardcode a bare-name → lib-prefixed-name map in `_build_pcb_ref_to_footprint` for the 15 known bare cases.

**Disposition: FAIL — introduces 15 ERC warnings.** Combined with the stale-derived-artefact problem (a), Mn3 needs another iteration.

### V4 — Mn4 closure: PCB-side DNP attribute on J2 + J10 **— FAIL at HEAD, PASS after regenerate**

`generate.py` correctly emits `(attr through_hole exclude_from_pos_files exclude_from_bom dnp)` for J10 (via `_emit_stock_lib_footprint(dnp=True)` at line 3211–3213) and J2 (via literal in `gen_pinheader_6_recovery_pcb_footprint` at line 4220).

But at HEAD, `oas.kicad_pcb` still has `(attr through_hole)` for both J2 and J10 (verified by raw text scan). After `regenerate.py`, both blocks show `(attr through_hole exclude_from_pos_files exclude_from_bom dnp)` — confirmed.

**Disposition**: the Python is correct; the committed PCB file does not reflect it. Same stale-derived-artefact problem as Mn3.

### V5 — Mn5 closure: explanatory courtyard comment **— PASS**

`generate.py:4477–4488` carries the multi-line docstring contrasting MOD1/MOD2/LDR1 (no F.CrtYd, daughterboard standoff allows SMD underneath) with SENS1 (F.CrtYd present, zero standoff). Exactly the rationale iter-1 requested. **PASS**.

### V6 — Nt1 closure: rule_severities comment **— PASS**

`generate.py:16116–16125` contains an 8-line comment immediately before `"rule_severities": {}` explaining that the empty dict means kicad-cli defaults are inherited and listing the four default-ignored ERC categories. **PASS**.

### V7 — Nt2 closure: regenerate.py determinism self-check **— PASS (and verified by running)**

`regenerate.py:80–105` defines `_kicad_source_files()` (17 files: pcb, root sch, 4 sub-sheet sch, pro, fp-lib-table, sym-lib-table, kicad_mod×7, kicad_sym×1) and `_hash_file()` (sha256). `main()` step 1b/4 (lines 117–143) snapshots hashes, re-runs `generate.py`, compares, and `sys.exit("ERROR: ...")` on any drift.

I ran `python regenerate.py` end-to-end. Output:

```
=== 1b/4  Determinism self-check (re-run generate.py) ===
  OK � generate.py output is bit-identical across consecutive runs (17 files checked).
```

17 files checked, zero drift. **PASS**.

### V8 — no regressions **— MIXED**

- **Footprint count**: v0.22 had 76 footprints (kiutils count). v0.23-regenerated has 76. Reference set identical (`set(v0.22_refs) == set(v0.23_refs)`). ✓
- **Net coverage**: 230 pads, 219 with `(net N "name")` clauses, 0 pads with `net 0`, 24 `unconnected-*` autonet pads, 195 pads with valid electrical nets. Matches iter-1's count of 195 valid + 24 unconnected = 219. Net assignments same as v0.22. ✓
- **DRC**: 0 violations, 160 unconnected ratlines (same as v0.22). ✓
- **ERC**: **REGRESSION — went from 0/0 to 0 errors + 15 warnings** (see V3). ✗
- **Visual placement**: SEN66 anchor (23.50, 22.00) rot 90; ESP32 MOD1 anchor (-27.76, -24.70) rot 90; NFC MOD2 anchor (-12.76, 40.64) rot 180; LD2410 LDR1 anchor (-43.47, -16.51) rot 270. All match v0.22 anchors per iter-1 report. ✓
- **DRC ignores**: unchanged from v0.22. No new ignores added in v0.23. ✓
- **Stale derived artefacts**: HEAD's `oas.kicad_pcb` + 4 sub-sheet `*.kicad_sch` do NOT match the committed `generate.py` source. Running `regenerate.py` produces a 15-line dirty diff. ✗

**Disposition: MIXED** — placement/net/DRC consistent, but ERC regressed and derived artefacts are out of sync with source.

---

## Full re-pass findings

### Critical (blocks routing or fab)

**C1. v0.23 commit ships inconsistent state: `generate.py` updated, derived `.kicad_pcb` / `.kicad_sch` NOT regenerated.**
- The CLAUDE.md "PCB design workflow" §3 mandates: *"runs `python regenerate.py`. That one command: calls `generate.py` to rebuild every KiCad source file, ..."* — i.e. regenerate before commit is the workflow contract.
- `git log --name-only abccb47` shows the v0.23 commit includes `generate.py` + `regenerate.py` + `CLAUDE.md` + 8 render SVG/PNG, but NOT `oas.kicad_pcb`, `power.kicad_sch`, `mcu.kicad_sch`, `sensors.kicad_sch`, `io.kicad_sch`. Renders changed (because they were re-rendered before commit), but the .kicad_pcb / .kicad_sch sources weren't.
- Consequence A: the J2/J10 PCB-side `dnp` attribute (Mn4) is NOT present at HEAD — the fix is in Python but not in the file that fab pick-and-place reads. If the user generates pos files from HEAD's `oas.kicad_pcb` today, J2 and J10 will be included in the pick-and-place run (i.e., the Mn4 fix is INVISIBLE at HEAD).
- Consequence B: the schematic Footprint property back-fill (Mn3) is NOT present at HEAD — schematic still has 51× `(property "Footprint" "")`.
- Consequence C: the bit-identical determinism self-check passes ONLY because the test snapshots hashes AFTER the first generate.py run, then re-runs and compares — so it can't detect that the on-disk files entering the workflow disagreed with the Python.
- Routing on a stale .kicad_pcb is technically possible (routing only cares about geometry, not the Footprint property), but PRs / reviews of the routed result will be confusing because the schematic-PCB property values won't match.
- **Recommended fix**: run `python regenerate.py` and commit the resulting .kicad_pcb + .kicad_sch diff in v0.24. This will also surface C2 below.

**C2. Mn3 fix introduces 15 ERC `footprint_link_issues` warnings on regenerated schematic.**
- After `regenerate.py`, ERC = 0 errors + **15 warnings** (Q1, C1, C3, C4, C20–C31). All same error class: `Obecna konfiguracja nie zawiera biblioteki footprintów ''` (= "current config does not contain footprint library ''").
- Root cause documented under V3 above: the 15 PCB-side `(property "Footprint" "<bare_name>")` strings lack the `Lib:` prefix; the post-process blindly copies them into the schematic.
- CLAUDE.md "PCB design workflow" rule §3 states ERC warnings must abort. The fix agent's `regenerate.py` only aborts on DRC warnings (via `--severity-warning` flag), not ERC. So 15 silent regressions slipped through.
- **Recommended fix**: pick one of the three remediation paths listed in V3. Plus: add `--exit-code-violations` to the `kicad-cli sch erc` invocation in `regenerate.py` so future ERC warnings cause CI failure.

### Major (should fix before tagging "ready to route")

**Mj1. CLAUDE.md is missing a v0.23 changelog entry.**
- Every prior version v0.1 through v0.22 has its own changelog entry under the `## Changelog` section. v0.23 has none.
- The fix agent's task brief explicitly required: *"verify the v0.23 entry exists and is honest."* That entry does not exist.
- The v0.23 commit message says what was changed, but the project's *source of truth for changes* is the in-repo `CLAUDE.md`. A future maintainer reading the file will see v0.22 then jump straight to whatever v0.24 looks like, missing the Mn1–Nt2 closures + the determinism self-check.
- Cosmetic-ish, but breaks the project's documented convention.

**Mj2. `regenerate.py` does not abort on `kicad-cli sch erc` warnings.**
- The DRC step uses `kicad-cli pcb drc ... --severity-error --severity-warning ...` which causes kicad-cli to exit non-zero on warnings.
- The ERC step omits these flags. `kicad-cli sch erc` exits 0 even with 15 warnings. The subprocess succeeds silently, leaving the warnings only in the report file that nobody reads automatically.
- This is why C2 (the 15 new warnings) was not caught by the fix agent's own end-to-end run.
- Two-line fix: add `"--exit-code-violations"` (or rely on `--severity-warning` equivalent if it exists for sch erc) to the `kcli sch erc` invocation around regenerate.py:155–159.

### Minor (cosmetic / deferrable)

**Mn1 (deferred from iter-1, still present).** Pairwise SMD pad-bbox gaps < 0.3 mm at `C15 ↔ C6` (0.20 mm) and four LED/cap pairs at 0.24 mm. All inside the 0.15 mm `min_clearance` rule; flagged for routing-time awareness only. iter-1 disposition stands.

**Mn2 (new).** The Mn3 fix's docstring (`generate.py:16812–16821`) says: *"Symbols whose Reference begins with `#` (power / flag markers) are left untouched because they have no physical footprint on the PCB."* Good design. But the same paragraph could mention the ERC regression risk for bare-name PCB Footprint properties — currently a maintainer would have no warning before introducing a new bare-name footprint generator and being surprised by new ERC warnings.

### Nits

**Nt1 (new).** The PCB-side `(property "Footprint" "...")` value should always be a fully-qualified `Lib:Footprint` string. Currently 49 of the 76 placed footprints (kiutils enumeration) use bare names. This is the underlying reason Mn3 misfires for 15 of them. Long-term cleanup: normalize all footprint generators to emit `<Lib>:<Name>` in the Footprint property. Not blocking, but eliminates an entire class of "schematic-PCB sync" bugs.

**Nt2 (deferred from iter-1, still present).** J5/J6/J7/J8 NC pads with `unconnected-(...)` autonets (24 such pads). Same iter-1 disposition: harmless, expected.

---

## Per-category status

| Category | Status | Notes |
|---|---|---|
| **A. Body-shadow + courtyard checks** | **PASS** | Daughterboard anchors / rotations match v0.22 exactly. SENS1 F.CrtYd present, MOD1/MOD2/LDR1 F.CrtYd absent by design (documented in v0.23 Mn5 comment). Body-shadow vs populated-SMD check: 0 partial overlaps, expected fully-inside counts unchanged. |
| **B. DRC + ERC strict zero verification** | **FAIL** | DRC = 0 / 0 violations, 160 unconnected ratlines (expected). **ERC = 0 errors / 15 warnings after regenerate** (C2 above). ERC at HEAD before regenerate = 0/0 but only because committed schematic files are stale. ERC ignores unchanged from v0.22 (no audit issue). |
| **C. Net coverage** | **PASS** | 195 pads on valid electrical nets, 24 on `unconnected-*` autonets, 11 on net 0 (mounting holes / zip-tie holes / JST MP pegs). Matches v0.22 baseline ≥ 195. |
| **D. Component placement sanity** | **PASS** | All 76 placed footprints' anchors match v0.22 byte-for-byte (PCB diff vs v0.22 commit = 0 bytes). F1 at (+54, +9), Q1 at (+27, +25), J3 SEN66 socket at (+36, +27) rot 0, J4 LD2410 header at (-44.74, +19.05) rot 270. Confirmed unchanged. |
| **E. Schematic sanity** | **WARN** | Refs + pin maps + DNP flags unchanged. Schematic Footprint property: 51 symbols had empty `""` at v0.22; after Mn3 post-process they get back-filled, but for 15 of them the back-fill produces an invalid lib-less reference (C2). At HEAD-as-committed, the back-fill hasn't been applied to the .kicad_sch files at all (C1). |
| **F. v0.22 + v0.23 specific verification** | **WARN** | iter-1's v0.22 verifications all still hold. v0.23-specific verification: V1, V2, V5, V6, V7 PASS; V3 FAIL (regression); V4 PASS in Python / FAIL at HEAD; V8 MIXED. |
| **G. Routing readiness** | **WARN** | Geometry is fine (PCB byte-identical to v0.22). I²C MST ~140 mm, 4.7 kΩ pull-ups, R7 boot-strap, all unchanged. But the schematic-PCB property sync is in a known-broken state that should be resolved before routing-then-re-export, otherwise the post-routing schematic-to-PCB diff will surface this exact mess at the worst time. |
| **H. Documentation** | **WARN** | Mn1 (zip-tie X) + Mn2 (cable-length retraction) inline doc fixes correctly applied. But CLAUDE.md is **missing the v0.23 changelog entry entirely** (Mj1). Module Identification rule unchanged. "Open work / TODO" unchanged. |

---

## Bottom line — verdict: **FIX REQUIRED — at least 2 issues (C1 + C2 + Mj1 + Mj2) before next pass**

The fix-review loop does NOT terminate at v0.23. Two of the v0.23 closures (Mn3, Mn4) suffer from the same root cause: the fix agent updated `generate.py` but never ran `regenerate.py` and committed the resulting .kicad_pcb / .kicad_sch diff. Worse, the act of running regenerate.py to bring the derived files into sync *exposes a real regression* in Mn3 (15 new ERC warnings) which the fix agent's `regenerate.py` doesn't surface because it doesn't abort on ERC warnings.

**For v0.24 (the next fix iteration), the agent should:**

1. Fix the Mn3 implementation so the back-filled Footprint property is a valid `Lib:Footprint` reference — easiest path is "skip bare names" (Variant B in V3 above), preserving v0.22's empty-string baseline for the 15 problem symbols.
2. Run `python regenerate.py` and verify ERC = 0/0 + DRC = 0/0 AFTER regen.
3. Commit the resulting .kicad_pcb + 4 .kicad_sch diff (so HEAD matches the Python source-of-truth).
4. Add a v0.23 changelog entry to CLAUDE.md (and a v0.24 entry for these new fixes).
5. Patch `regenerate.py` to call `kicad-cli sch erc` with `--exit-code-violations` so future ERC warnings cause subprocess failure (matches the DRC step's strictness).

Confidence: **HIGH** that v0.23 is not ready to route as-is. The Mn3 ERC regression is reproducible 100% by running `python regenerate.py`.

---

## Independent verification scripts (run snippets)

### Footprint count + net coverage (kiutils)

```python
from kiutils.utils.sexpr import parse_sexp
from kiutils.board import Board

text = open('oas.kicad_pcb', encoding='utf-8').read()
board = Board.from_sexpr(parse_sexp(text))
print(f'Total footprints: {len(board.footprints)}')        # 76
nolib = [fp for fp in board.footprints if not fp.libraryNickname]
print(f'WITHOUT lib prefix: {len(nolib)}')                  # 49
```

### Schematic Footprint property check

```python
import re
for sheet in ['power', 'mcu', 'sensors', 'io']:
    text = open(f'{sheet}.kicad_sch', encoding='utf-8').read()
    # After regenerate, Q1's Footprint should be 'SOT-23' (lib-less, causes ERC warning)
    for ref in ['Q1', 'C20', 'C1']:
        m = re.search(r'\(property "Reference" "' + ref + '"', text)
        if not m: continue
        tail = text[m.start():m.start()+2000]
        mfp = re.search(r'\(property "Footprint" "([^"]*)"', tail)
        print(f'{sheet}/{ref} Footprint={mfp.group(1)!r}')
```

### Determinism self-check (run end-to-end)

```bash
cd hardware/kicad && python regenerate.py
# Expected output:
#   === 1b/4  Determinism self-check (re-run generate.py) ===
#     OK ... generate.py output is bit-identical across consecutive runs (17 files checked).
```

### ERC verification

```bash
# Run AFTER regenerate.py to see the 15 warnings
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch erc \
    --output /tmp/erc.rpt oas.kicad_sch
# Look for: " ** ERC messages: 15  Errors 0  Warnings 15"
# All 15 should be [footprint_link_issues]: "current config does not contain footprint library ''"
```

### v0.22 vs v0.23 placement diff (must be empty)

```bash
git diff 291de30..abccb47 -- hardware/kicad/oas.kicad_pcb     # empty
git diff 291de30..abccb47 -- hardware/kicad/power.kicad_sch   # empty
# (All KiCad source files are unchanged between v0.22 and v0.23 in the committed tree.
# This is the C1 problem — Python advanced but artefacts did not.)
```
