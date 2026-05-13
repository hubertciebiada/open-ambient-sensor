# OAS PCB v0.24 — Review Iteration #3 (independent verification)

- **Date**: 2026-05-13
- **Reviewer**: Opus 4.7 (independent agent, fresh session)
- **Scope**: `C:\Git\open-ambient-sensor\` at commit `c4589a5` on `main` (v0.24 — "fix v0.23 regressions: lib-qualify footprints + ERC strict + derived-file resync")
- **Purpose**: independent verification that the v0.24 fix agent's work closed iter-2's findings (C1, C2, Mj1, Mj2) without re-introducing regressions, so the fix-review loop can terminate.
- **kiutils version**: 1.4.8
- **KiCad CLI**: `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`
- **Working dir**: `C:\Git\open-ambient-sensor\hardware\kicad`
- **Working tree at review start**: clean (`git status` shows two untracked items only: `.playwright-mcp/` and `botland-devkitm-screenshot.png` — both pre-existing and unrelated to the review).

---

## TL;DR — the loop TERMINATES at v0.24 with one residual cosmetic finding

The v0.24 commit honestly fixes all four iter-2 issues:
- **C1** (stale derived artefacts): RESOLVED — the v0.24 commit ships freshly regenerated `.kicad_pcb` + 4 `.kicad_sch` files alongside `generate.py`; a fresh end-to-end `regenerate.py` run produces byte-identical output to HEAD (all 7 source files hash-match HEAD).
- **C2** (15 ERC `footprint_link_issues` warnings): RESOLVED — `kicad-cli sch erc` now reports `ERC messages: 0  Errors 0  Warnings 0`, zero `footprint_link_issues` occurrences anywhere in `renders/_erc.rpt`.
- **Mj1** (CLAUDE.md missing v0.23 entry): RESOLVED — both v0.23 and v0.24 entries are present, honest, and complete.
- **Mj2** (`regenerate.py` not strict on ERC warnings): RESOLVED — the ERC subprocess invocation now carries `--severity-error --severity-warning --exit-code-violations`.

**One residual cosmetic finding survives v0.24** (already silent — does NOT produce ERC warnings, does NOT block routing):
- **Mn3-residual.** 27 schematic real-component symbols still have `(property "Footprint" "")` (empty) in the sub-sheets — R1–R7, F1, L1–L2, D1–D3, C2, C5–C17. These are the schematic symbols whose corresponding PCB footprints are written with indented `(footprint ` tokens (tab/space prefixed) in `oas.kicad_pcb`. The Mn3 back-fill regex `(?m)^\(footprint "..."` requires the token at column 0 and silently skips these 31 indented PCB blocks; the back-fill therefore covers only 45 of the 76 placed footprints. Empty Footprint properties are ERC-silent (KiCad treats them as "footprint not assigned — silent"), so no ERC warning fires. The previous-iter regression (C2) only surfaced because v0.23 *wrote* a malformed lib-less reference; v0.24 doesn't write anything to these 27 symbols at all (regex miss → no rewrite), so the field stays empty and ERC stays silent. **Functional impact on routing: zero.** Functional impact on schematic-driven netlist export: identical to v0.22 baseline. This is a Minor — flagged so the fix agent can decide whether to widen the regex in v0.25.

Verdict: **ONE MINOR ISSUE REMAINING (cosmetic, ERC-silent) — the fix-review loop is effectively TERMINATED.** A user who declares "loop terminates at any ERC-silent state" can stop here. A user who reads CLAUDE.md "PCB design workflow" §3 literally ("aborts on any error or warning") gets that enforcement at v0.24 — there are zero ERC warnings to abort on. Mn3-residual is not technically a regression vs v0.23 (it's a partial improvement on v0.22: 51 empty → 27 empty; v0.23 made it WORSE by writing 15 invalid strings; v0.24 fully recovers Q1 / C1 / C3 / C4 / C20–C31 to valid lib-qualified strings AND keeps everything else ERC-silent).

---

## Verification of v0.24 claimed fixes (V9..V15)

### V9 — Mn3 lib-qualified back-fill **— PASS**

- `_build_pcb_ref_to_footprint()` (generate.py:16856–16923) now prefers the PCB-side `(property "Footprint" "...")` clause (line 16903–16904) and routes any bare name through `BARE_FOOTPRINT_TO_LIB` with an `assert` for missing entries (line 16910). Final sanity loop (line 16921–16922) asserts every returned value contains `:`.
- I ran `_build_pcb_ref_to_footprint()` directly from a Python shell against the freshly written `oas.kicad_pcb`. The function returned 45 entries; every entry value contains a `:`. Spot checks: `Q1 → 'Package_TO_SOT_SMD:SOT-23'`, `C1 → 'Capacitor_THT:CP_Radial_D8.0mm_P3.50mm'`, `C20 → 'Capacitor_SMD:C_0402_1005Metric'`, `U2 → 'Package_TO_SOT_SMD:SOT-583-8'`.
- KiCad ERC against the regenerated schematic: **0 errors / 0 warnings**, zero `footprint_link_issues` strings in `renders/_erc.rpt` (independent grep).
- **Caveat (Mn3-residual)**: see Minor finding below — 27 schematic symbols still have empty Footprint properties because the back-fill regex misses 31 indented PCB footprint blocks. ERC stays silent (empty is fine), so V9 still PASSes the original ERC-zero contract.

### V10 — `BARE_FOOTPRINT_TO_LIB` table coverage **— PASS**

- Table at generate.py:16834–16853. 12 entries covering: C_0402/0603/0805_*Metric → `Capacitor_SMD`, R_0603/2920_*Metric → `Resistor_SMD` / (Fuse via fixed generator), D_SMA/D_SMB/D_SOD-323 → `Diode_SMD`, `L_NR5040` → `Inductor_SMD`, `CP_Radial_D6.3mm_P2.5mm` / `D8mm_P3.5mm` → `Capacitor_THT`, `SOT-23` → `Package_TO_SOT_SMD`.
- Defensive `assert` at line 16910 raises if `_build_pcb_ref_to_footprint()` encounters a bare name not in the table. I verified by reading the code; the message text guides the maintainer to add the missing entry. (Did NOT live-test by intentionally corrupting — to avoid touching the working tree.)
- Independent enumeration of PCB-side `(property "Footprint" "...")` values via `kiutils.utils.sexpr.parse_sexp`: every one of the 76 placed footprints now has a `Footprint` property containing `:`. Zero bare names, zero missing properties.
- Note: this changes the v0.23 "PCB has 49 bare-name Footprint properties" finding from iter-2 V8 to zero — v0.24 also normalized the PCB-side strings (per the v0.24 changelog "Issue 1" second paragraph). The table is now strictly defensive: it doesn't get exercised in current generation because every PCB Footprint string is already qualified. The assertion guards against future regressions.

### V11 — `regenerate.py` ERC strict mode **— PASS**

- Lines 164–170 of regenerate.py:
  ```python
  run([
      kcli, "sch", "erc",
      "--output", str(erc_report),
      "--severity-error", "--severity-warning",
      "--exit-code-violations",
      str(SCH),
  ])
  ```
- All three strictness flags present, mirroring the DRC step (lines 149–154). The fix agent reports having verified it aborts when a Footprint is corrupted (returns kicad-cli exit 5); I did not re-test by intentional corruption to avoid touching the tree, but the flags are syntactically correct per `kicad-cli sch erc --help` (verified in my own session against the same KiCad 10.0 install).

### V12 — CLAUDE.md v0.23 + v0.24 entries **— PASS**

- v0.23 entry: CLAUDE.md lines 729–737. Documents Mn1, Mn2, Mn3 (including the malformed back-fill bug + acknowledgement that V3/V4 didn't land at HEAD), Mn4, Mn5, Nt1, Nt2 closures. Honest "Why this iteration regressed" subsection (line 737) ascribes blame to (a) no regenerate.py end-to-end before commit and (b) regenerate.py not aborting on ERC warnings. Both consequences explicitly listed.
- v0.24 entry: CLAUDE.md lines 739–746. Five "Issue N" subsections cover (1) lib-qualified back-fill + BARE_FOOTPRINT_TO_LIB + assertions + inline generator name normalization with specific `L_NR5040 → L_APV_ANR5040`, `R_2920_7351Metric → Fuse_2920_7451Metric`, `CP_Radial_D8mm → CP_Radial_D8.0mm_P3.50mm` corrections; (2) ERC strict flags; (3) derived-file resync; (4) CLAUDE.md changelog hygiene; (5) review file committed. Includes a "Reusable lesson" reflection at line 746.
- Both entries are honest about prior mistakes (no whitewashing) and concrete about fixes (specific line numbers / file paths / API names).

### V13 — Review file `_review-iteration-2-v0.23.md` committed **— PASS**

- `git log --name-only c4589a5 | grep iteration-2` → `hardware/components/_review-iteration-2-v0.23.md`. Confirmed present in the v0.24 commit's file list.

### V14 — Full re-run determinism + DRC + ERC **— PASS**

- Captured HEAD hashes for 7 KiCad source files (`oas.kicad_pcb`, `oas.kicad_sch`, `oas.kicad_pro`, 4 sub-sheet `.kicad_sch`).
- Ran `python regenerate.py` end-to-end (~78 s, 5 stages including 3D renders).
- Determinism self-check inside regenerate.py: `OK — generate.py output is bit-identical across consecutive runs (17 files checked)`.
- After the full run, all 7 source files hash-match HEAD bit-for-bit (verified via sha256 comparison; output: `ALL MATCH HEAD`).
- `renders/_drc.rpt` final line block: `** Found 0 DRC violations **`, `** Found 0 unconnected items **` is NOT asserted (160 unconnected ratlines are listed but classified as `Local override; error` and reported separately — this is the same pre-routing baseline as iter-1/iter-2; routing will close them).
- `renders/_erc.rpt`: `** ERC messages: 0  Errors 0  Warnings 0 **`. Zero `footprint_link_issues` strings (independent grep).
- Renders/ outputs regenerated cleanly; PNG/SVG diffs vs HEAD (not byte-compared, but the renders are visual previews — geometry is unchanged per source-file hash identity).

### V15 — Mn6, Nt3 status (deferred from iter-1) **— PASS (unchanged)**

- Mn6 (tight pad-pair clearances, 5 pairs at C15↔C6 = 0.20 mm + four LED/cap pairs at 0.24 mm): iter-1 disposition stands. No new pairs introduced in v0.23/v0.24. Still inside DRC `min_clearance` = 0.15 mm; flagged for routing-time awareness only.
- Nt3 (J5/J6/J7/J8 NC pads on `unconnected-(JN-Pin_N-PadN)` autonets, 24 pads): unchanged. Net coverage check confirms 24 pads on `unconnected-*` autonets — same baseline as v0.22/v0.23.

---

## Full re-pass findings

### Critical (blocks routing or fab)

None.

### Major (should fix before tagging "ready to route")

None.

### Minor (cosmetic / deferrable)

**Mn3-residual. 27 schematic real-component symbols still have empty `(property "Footprint" "")`.** The Mn3 back-fill in `_build_pcb_ref_to_footprint()` uses the regex `(?m)^\(footprint "([^"]+)"` (generate.py:16885). This requires the `(footprint` token to start at column 0. But `gen_pcb()` writes the placed footprints inside the root `(kicad_pcb ...)` block with indentation (mostly tabs / 8-space prefixes for the SEN66 region — see `oas.kicad_pcb` lines 16251 and onward). Concretely:
- Total `(footprint ` occurrences in `oas.kicad_pcb`: **76**.
- Matched by `(?m)^\(footprint`: **45**. These are the (mostly later-added) generators that emit a leading newline before `(footprint`.
- Missed by the regex: **31** — refs `C2`, `C5`–`C17`, `D1`–`D3`, `F1`, `L1`–`L2`, `R1`–`R7`, plus `ZT1`–`ZT4` (no schematic counterpart for ziptie holes).
- Schematic symbols affected: 27 (the four ZT refs have no schematic instance).
- The fix agent's `_apply_schematic_footprints()` post-process can only back-fill refs that appear in the `ref_to_fp` map. The 27 missed refs are silently skipped — the schematic literal `(property "Footprint" "")` stays in place.
- ERC consequence: zero. KiCad treats empty Footprint as "footprint not assigned (silent)". This is the same baseline as v0.22 for these 27 symbols.
- Recommended one-line fix for v0.25: change the regex to `r'\s*\(footprint "([^"]+)"'` and use `re.finditer` without the multiline flag (or add a leading-whitespace alternation: `(?m)^[\s\t]*\(footprint "..."`). Re-run regenerate.py and verify the 27 schematic instances pick up lib-qualified Footprint values. ERC should remain 0/0 because the values that would be back-filled are now all lib-qualified PCB-side.
- Alternatively: leave Mn3-residual deferred. Empty Footprint properties are ERC-acceptable and don't impair routing. The only practical concern is netlist export from the schematic — but the current OAS workflow drives the PCB from Python, not from "Update PCB from Schematic", so the empty-Footprint impact is theoretical.

This is a Minor finding (cosmetic, ERC-silent, no routing impact). Not enough to re-open the fix-review loop unless the user wants a clean schematic-side BOM export.

### Nits

**Nt-doc-comment. `_build_pcb_ref_to_footprint()` docstring overstates coverage.** Line 16859–16872 implies the function captures every footprint in the PCB: *"Reads each top-level `(footprint ...)` block ..."*. In practice it captures only the 45 truly-column-0 blocks (see Mn3-residual). The docstring should either disclose the regex limitation or be updated alongside the regex fix.

---

## Per-category status

| Category | Status | Notes |
|---|---|---|
| **A. Body-shadow + courtyard checks** | **PASS** | Daughterboard anchors / rotations unchanged from v0.22/v0.23: SENS1 (SEN66) at (23.50, 22.00) rot 90; MOD1 (ESP32) at (-27.76, -24.70) rot 90; MOD2 (NFC) at (-12.76, 40.64) rot 180; LDR1 (LD2410) at (-43.47, -16.51) rot 270. SENS1 F.CrtYd present; MOD1/MOD2/LDR1 F.CrtYd absent by design per the v0.23 Mn5 docstring. PCB-source hashes match HEAD → geometry is bit-identical to commit. |
| **B. DRC + ERC strict-zero verification + ignore audit** | **PASS** | DRC = **0 violations**, 160 unconnected ratlines (same as v0.22 → routing will close). ERC = **0 errors / 0 warnings** after full regenerate. ERC strict flags (`--severity-error --severity-warning --exit-code-violations`) verified in `regenerate.py:164–170`. Ignored DRC checks (Footprint has no courtyard / Track endpoint not centered on via / Tuning profile / Footprint mismatch / Component type mismatch) are unchanged from v0.22 and still appropriate (3 of 5 are pre-routing-only, 2 are intentional design choices documented in `gen_pro()`). Ignored ERC categories (4) documented in the v0.23 Nt1 comment immediately above `"rule_severities": {}` in `gen_pro()`. No new ignores were added in v0.24 (audit reads `rule_severities` is still `{}`). |
| **C. Net coverage** | **PASS** | 278 net declarations in `oas.kicad_pcb`. 219 pads with `(net N "name")` clauses. 24 pads on `unconnected-*` autonets (the J5/J6/J7/J8 NC pins per Nt3). Baseline matches iter-1/iter-2. The 11 net-0 pads (mounting holes, zip-tie holes, JST MP pegs) baseline also matches. v0.24's Footprint-property changes do NOT touch pad net assignments — net sync runs from schematic NET declarations, not from Footprint properties. |
| **D. Component placement sanity** | **PASS** | 76 placed footprints. All inside PCB outline (verified via re-run; `regenerate.py` runs `kicad-cli pcb drc` which would flag outside-board). Pairwise clearances unchanged. Mn6 pad-pair tight clearances still 5 pairs (C15↔C6 = 0.20 mm + 4 LED/cap pairs at 0.24 mm) — no new tight pairs introduced. |
| **E. Schematic sanity** | **PASS-with-Mn3-residual** | 65 real-component schematic instances across 4 sub-sheets. All have a `Reference`, `Value`, and Footprint property. 38 of 65 have a fully-qualified `Lib:Name` Footprint string after v0.24 back-fill; 27 still have empty `""` (see Mn3-residual). DNP flags consistent: J2 + J10 both carry `(dnp yes)` on the schematic side AND `(attr through_hole exclude_from_pos_files exclude_from_bom dnp)` on the PCB side (v0.23 Mn4 + v0.24 resync). J5/J6 pin maps: not re-verified individually this iteration; iter-2 V8 confirmed J5/J6 pin-by-pin spec match against Espressif dimensions PDF and the geometry is byte-identical at v0.24. |
| **F. v0.22 + v0.23 + v0.24 specific verification** | **PASS** | iter-1/iter-2 v0.22-specific verifications all still hold (geometry hash-match). v0.23 specific: V1–V8 from iter-2 — V1, V2, V5, V6, V7 still PASS; V3 (Mn3 lib-qualified back-fill) now PASS at HEAD with Mn3-residual caveat; V4 (J2/J10 DNP) now PASS at HEAD (PCB regenerated). v0.24 specific: V9–V15 all PASS per section above. |
| **G. Routing readiness** | **PASS** | Geometry is hash-identical to v0.23 + v0.22 commits — those previous iter-1/iter-2 readiness assessments transfer unchanged. I²C MST geometry, 4.7 kΩ pull-ups, R7 boot-strap, all preserved. The empty-Footprint Mn3-residual does NOT affect routing — KiCad's PCB router consumes pad coordinates + nets, not schematic-side Footprint properties. The schematic-to-PCB diff (e.g. via Eeschema's Update-PCB-from-Schematic) is now a known-clean operation (every PCB Footprint property is lib-qualified, every schematic Footprint that gets back-filled is lib-qualified, the 27 empty ones are ERC-silent on both sides). |
| **H. Documentation** | **PASS** | v0.23 + v0.24 changelog entries present, honest, complete. Hard constraint #1 (17 mm / SEN66-zone 22 mm) unchanged. Module Identification rule unchanged. "Open work / TODO" unchanged. The v0.24 entry includes a "Reusable lesson" reflection about derived-file commit hygiene. |

---

## Bottom line — verdict

**ONE MINOR ISSUE REMAINING — but the fix-review loop is functionally TERMINATED.**

The loop terminates in the practical sense:
- DRC = 0/0, ERC = 0/0, both **enforced** by `regenerate.py` strict flags (not just measured).
- Determinism self-check passes (17 files bit-identical across two consecutive runs).
- All four iter-2 issues (C1, C2, Mj1, Mj2) are resolved at HEAD, not just in Python.
- Geometry is unchanged from v0.22/v0.23 (PCB source hash-stable across all three iterations).

The one residual finding (**Mn3-residual** — 27 schematic symbols with empty Footprint property due to a regex column-0 limitation in `_build_pcb_ref_to_footprint()`) is:
- ERC-silent (KiCad treats empty Footprint as "footprint not assigned — silent").
- Not a regression vs v0.23 (v0.23's regression wrote 15 *invalid* values; v0.24 correctly skips those refs entirely — net improvement).
- Improvement over v0.22 baseline (v0.22 had 51 empty Footprint properties; v0.24 has 27).
- Cosmetic: zero impact on routing or fab; only matters if a user runs a schematic-side netlist export and expects BOM-grade Footprint metadata in the netlist.

Recommendation:
- **If the user's bar is "ERC = 0/0 strict-enforced + routing-ready"**: loop terminates at v0.24. Proceed to routing.
- **If the user's bar is "every schematic real-component symbol has a populated Lib:Name Footprint property"**: one more iteration (v0.25) to fix the regex column-0 bug in `_build_pcb_ref_to_footprint()`. Expected diff: ~1 line in the regex, plus re-run + commit the resulting `.kicad_sch` diff. No PCB / DRC / ERC changes expected.

**Confidence: HIGH.** All claims verified by direct file inspection + end-to-end `regenerate.py` execution. The Mn3-residual finding is independently reproducible (paste the regex into a Python REPL and count matches).

---

## Independent verification scripts (run snippets)

### V14 end-to-end determinism + hash match against HEAD

```python
import hashlib, subprocess, sys
from pathlib import Path

files = ['oas.kicad_pcb', 'oas.kicad_sch', 'oas.kicad_pro',
         'power.kicad_sch', 'mcu.kicad_sch', 'sensors.kicad_sch', 'io.kicad_sch']

# Pre-run hashes (HEAD state at review start)
pre = {f: hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in files}

# Run regenerate.py end-to-end (~78 s with renders)
subprocess.check_call([sys.executable, 'regenerate.py'])

# Post-run hashes
post = {f: hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in files}

for f in files:
    assert pre[f] == post[f], f'{f}: HASH DRIFTED'
print('OK — all 7 KiCad source files hash-match HEAD after regenerate')
```

### V10 + Mn3-residual: enumerate every PCB Footprint property + back-fill coverage

```python
from kiutils.utils.sexpr import parse_sexp
import re

text = open('oas.kicad_pcb', encoding='utf-8').read()
parsed = parse_sexp(text)
fps = [it for it in parsed if isinstance(it, list) and it and it[0] == 'footprint']

def prop(fp, key):
    for s in fp:
        if isinstance(s, list) and len(s) >= 3 and s[0] == 'property' and s[1] == key:
            return s[2]
    return None

bare = []
qualified = 0
for fp in fps:
    val = prop(fp, 'Footprint')
    if val is None or val == '':
        bare.append((prop(fp, 'Reference'), 'EMPTY'))
    elif ':' not in val:
        bare.append((prop(fp, 'Reference'), val))
    else:
        qualified += 1

print(f'Total PCB footprints: {len(fps)}')
print(f'Fully lib-qualified: {qualified}')
print(f'Bare or empty: {len(bare)}')
# Expected: 76, 76, 0 (V10 PASS)

# Mn3-residual demo: regex column-0 vs all
top = len(re.findall(r'(?m)^\(footprint "', text))   # 45
all_ = len(re.findall(r'\(footprint "', text))       # 76
print(f'Multiline-^ regex: {top} / {all_} total → {all_-top} indented PCB blocks missed')
```

### Mn3-residual: count empty Footprint in schematic instances

```python
import re
issues = 0
for sheet in ['power', 'mcu', 'sensors', 'io']:
    text = open(f'{sheet}.kicad_sch', encoding='utf-8').read()
    # Strip (lib_symbols ...) block
    m = re.search(r'\(lib_symbols', text)
    if m:
        s = m.start(); d = 0; j = s
        while j < len(text):
            d += (1 if text[j]=='(' else (-1 if text[j]==')' else 0))
            if text[j] == ')' and d == 0:
                j += 1; break
            j += 1
        text = text[:s] + text[j:]
    # Walk top-level (symbol ...) instances
    i = 0
    while True:
        idx = text.find('(symbol', i)
        if idx == -1: break
        d = 0; j = idx
        while j < len(text):
            d += (1 if text[j]=='(' else (-1 if text[j]==')' else 0))
            if text[j] == ')' and d == 0:
                j += 1; break
            j += 1
        blk = text[idx:j]
        r = re.search(r'\(property "Reference" "([^"]+)"', blk)
        f = re.search(r'\(property "Footprint" "([^"]*)"', blk)
        if r and f and not r.group(1).startswith('#') and f.group(1) == '':
            issues += 1
        i = j
print(f'Schematic symbols with empty Footprint: {issues}')
# Expected: 27
```

### V13 — review file tracked

```bash
git log --name-only c4589a5 | grep iteration-2
# Expected: hardware/components/_review-iteration-2-v0.23.md
```
