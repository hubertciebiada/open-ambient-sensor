"""Unit tests for the pure-Python helpers in boardgen/_common.py.

Covers the two framework primitives whose silent regression would break
the whole project:

  - The deterministic UUID v5 system (`U` + `sheet_context`) — CLAUDE.md
    Lesson 9: boardgen output must be bit-identical across runs, which
    holds only if a given (sheet, tag) pair always maps to the same UUID
    and distinct pairs never collide.
  - `fmt()` — the KiCad coordinate formatter. Scientific notation or
    unstable trailing-zero handling would corrupt every emitted
    .kicad_pcb / .kicad_sch coordinate.

`U()` deliberately rejects tag reuse within one interpreter run (the
duplicate-tag guard), so the determinism tests snapshot and restore the
module-level `_seen_uuid_tags` registry instead of calling U() twice
naively.
"""
from __future__ import annotations

import uuid

import pytest

import boardgen._common as _common
from boardgen._common import U, fmt, sheet_context

# Tag prefix that no real boardgen stage uses — keeps these tests from
# ever colliding with tags registered by an imported boardgen module.
_T = "unittest-helpers"


@pytest.fixture(autouse=True)
def _restore_uuid_state():
    """Snapshot + restore the U() duplicate-tag registry and the active
    sheet context, so tests neither leak tags into each other nor into
    any other test module that imports boardgen."""
    saved_tags = set(_common._seen_uuid_tags)
    saved_sheet = _common._current_sheet
    yield
    _common._seen_uuid_tags.clear()
    _common._seen_uuid_tags.update(saved_tags)
    _common._current_sheet = saved_sheet


def _u_twice(tag: str) -> tuple[str, str]:
    """Call U(tag) twice, clearing the duplicate-tag guard in between,
    and return both results. This isolates the determinism property from
    the (separately tested) reuse guard."""
    first = U(tag)
    full = f"{_common._current_sheet}:{tag}" if _common._current_sheet else tag
    _common._seen_uuid_tags.discard(full)
    second = U(tag)
    return first, second


# ---------------------------------------------------------------------------
# U() / sheet_context
# ---------------------------------------------------------------------------

def test_u_same_tag_same_uuid() -> None:
    a, b = _u_twice(f"{_T}:wire-1")
    assert a == b


def test_u_same_tag_same_uuid_inside_sheet_context() -> None:
    with sheet_context("power"):
        a, b = _u_twice(f"{_T}:wire-1")
    assert a == b


def test_u_different_tags_differ() -> None:
    assert U(f"{_T}:wire-1") != U(f"{_T}:wire-2")


def test_u_sheet_context_namespaces_the_tag() -> None:
    tag = f"{_T}:3v3-bus"
    bare = U(tag)
    with sheet_context("power"):
        in_power = U(tag)
    with sheet_context("mcu"):
        in_mcu = U(tag)
    # Same logical tag in three scopes -> three distinct UUIDs.
    assert len({bare, in_power, in_mcu}) == 3


def test_u_emits_valid_version5_uuid() -> None:
    parsed = uuid.UUID(U(f"{_T}:format-check"))
    assert parsed.version == 5


def test_u_rejects_duplicate_tag_within_run() -> None:
    tag = f"{_T}:dup"
    U(tag)
    with pytest.raises(ValueError, match="duplicate tag"):
        U(tag)


def test_u_rejects_empty_tag() -> None:
    with pytest.raises(ValueError):
        U("")


def test_sheet_context_restores_previous_scope_on_exit() -> None:
    assert _common._current_sheet == ""
    with sheet_context("power"):
        assert _common._current_sheet == "power"
        with sheet_context("mcu"):
            assert _common._current_sheet == "mcu"
        assert _common._current_sheet == "power"
    assert _common._current_sheet == ""


# ---------------------------------------------------------------------------
# fmt()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, "0"),
        (13.0, "13"),          # integral float -> no decimal point
        (-55.0, "-55"),
        (2.50, "2.5"),          # trailing zeros stripped
        (27.5, "27.5"),
        (0.25, "0.25"),
        (47.6314, "47.6314"),
        (0.000001, "0.000001"),  # smallest representable at 6 decimals
        (148.5, "148.5"),
    ],
)
def test_fmt_known_values(value: float, expected: str) -> None:
    assert fmt(value) == expected


def test_fmt_rounds_to_six_decimals() -> None:
    assert fmt(1.0 / 3.0) == "0.333333"
    # Below the 6-decimal resolution -> collapses to "0", not "1e-07".
    assert fmt(1e-7) == "0"


@pytest.mark.parametrize(
    "value", [0.0, 1e-6, 1e-7, 0.25, -47.6314, 123456.789, 1e6, -1e6]
)
def test_fmt_never_emits_scientific_notation(value: float) -> None:
    out = fmt(value)
    assert "e" not in out.lower()
    float(out)  # must round-trip as a plain decimal literal
