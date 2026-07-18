"""
Regression tests for tools/extract_routes.py (Lesson 12).

Covers the two historical failure modes:
  - boardgen-emitted boards write `(net N)` (integer code only) inside
    segment/via blocks — the pre-fix regex matched only the KiCad
    interactive-save format `(net N "name")`, so extraction silently
    yielded 0 records and OVERWROTE oas_routes.py with an empty snapshot.
  - the zero-record guard: main() must exit non-zero WITHOUT writing
    when extraction yields nothing.

The round-trip test treats the committed oas_routes.py as ground truth:
parsing the committed (boardgen-emitted) oas.kicad_pcb and rendering the
result must reproduce the committed file byte-for-byte.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools import extract_routes
from boardgen._routing import ROUTING_CHUNKS

# The round-trip test below reads the COMMITTED oas.kicad_pcb. While signal
# routing is deferred to GitHub issue #8 (ROUTING_CHUNKS has no "autoroute"
# chunk) the board carries GND pours only, so it no longer round-trips to the
# frozen oas_routes.py snapshot — skip that one test. The pure-function
# extractor tests (synthetic PCB text) run regardless.
_routing_deferred = pytest.mark.skipif(
    "autoroute" not in ROUTING_CHUNKS,
    reason="signal routing deferred to issue #8",
)


@_routing_deferred
def test_round_trip_boardgen_format_byte_identical() -> None:
    """Committed oas.kicad_pcb (boardgen `(net N)` format) round-trips.

    Counts match the committed snapshot header ("Source snapshot: 390
    segments, 45 vias.") — the GitHub issue #8 full re-route on the
    widened-buck-corridor placement (Freerouting 2.2.4, 0 unrouted) plus
    the GND island-to-plane stitch vias.
    """
    text = extract_routes.PCB.read_text(encoding="utf-8")
    segments, vias = extract_routes.extract(text)
    assert len(segments) == 390
    assert len(vias) == 45

    rendered = extract_routes.render(segments, vias)
    committed = extract_routes.OUT.read_text(encoding="utf-8")
    # render() ends with exactly one trailing newline (the final "" line
    # joined by "\n"), matching write_text of the committed file — so a
    # plain string comparison IS the byte-for-byte check.
    assert rendered == committed


def test_extract_kicad_save_format_inline_name() -> None:
    """KiCad interactive-save format `(net 1 "GND")` parses directly."""
    pcb_text = (
        '(kicad_pcb\n'
        '\t(net 0 "")\n'
        '\t(net 1 "GND")\n'
        '\t(segment\n'
        '\t\t(start 100 50)\n'
        '\t\t(end 101 50)\n'
        '\t\t(width 0.25)\n'
        '\t\t(layer "F.Cu")\n'
        '\t\t(net 1 "GND")\n'
        '\t\t(uuid "00000000-0000-0000-0000-000000000000")\n'
        '\t)\n'
        ')\n'
    )
    segments, vias = extract_routes.extract(pcb_text)
    assert vias == []
    assert len(segments) == 1
    assert segments[0]["net_name"] == "GND"
    assert segments[0]["layer"] == "F.Cu"
    assert segments[0]["start"] == (100 - extract_routes.PAGE_CENTRE_X,
                                    50 - extract_routes.PAGE_CENTRE_Y)


def test_extract_boardgen_format_code_lookup() -> None:
    """boardgen format `(net 1)` resolves through the declaration table."""
    pcb_text = (
        '(kicad_pcb\n'
        '\t(net 0 "")\n'
        '\t(net 1 "GND")\n'
        '\t(via\n'
        '\t\t(at 120 90)\n'
        '\t\t(size 0.7)\n'
        '\t\t(drill 0.3)\n'
        '\t\t(layers "F.Cu" "B.Cu")\n'
        '\t\t(net 1)\n'
        '\t\t(uuid "00000000-0000-0000-0000-000000000000")\n'
        '\t)\n'
        ')\n'
    )
    segments, vias = extract_routes.extract(pcb_text)
    assert segments == []
    assert len(vias) == 1
    assert vias[0]["net_name"] == "GND"
    assert vias[0]["layers"] == ("F.Cu", "B.Cu")


def test_unknown_net_code_fails_loudly() -> None:
    """An integer net code absent from the declaration table is an error."""
    pcb_text = (
        '(kicad_pcb\n'
        '\t(net 0 "")\n'
        '\t(segment\n'
        '\t\t(start 100 50)\n'
        '\t\t(end 101 50)\n'
        '\t\t(width 0.25)\n'
        '\t\t(layer "F.Cu")\n'
        '\t\t(net 99)\n'
        '\t)\n'
        ')\n'
    )
    with pytest.raises(ValueError, match="net code 99"):
        extract_routes.extract(pcb_text)


def test_extract_zero_routes_returns_empty() -> None:
    """Pure-function path: a routeless board extracts to two empty lists."""
    pcb_text = '(kicad_pcb\n\t(net 0 "")\n)\n'
    segments, vias = extract_routes.extract(pcb_text)
    assert segments == []
    assert vias == []


def test_main_guard_refuses_to_write_empty_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """main() exits non-zero and writes NOTHING on a 0-segment 0-via board.

    PCB and OUT are monkeypatched into tmp_path so the test can never
    touch the real oas.kicad_pcb / oas_routes.py.
    """
    fake_pcb = tmp_path / "board.kicad_pcb"
    fake_pcb.write_text('(kicad_pcb\n\t(net 0 "")\n)\n', encoding="utf-8")
    fake_out = tmp_path / "oas_routes.py"

    monkeypatch.setattr(extract_routes, "PCB", fake_pcb)
    monkeypatch.setattr(extract_routes, "OUT", fake_out)

    with pytest.raises(SystemExit) as excinfo:
        extract_routes.main()
    assert excinfo.value.code == 1
    assert not fake_out.exists()
    captured = capsys.readouterr()
    assert "refusing to overwrite" in captured.err
