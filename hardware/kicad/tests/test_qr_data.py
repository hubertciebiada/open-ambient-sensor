"""Structural invariants of the vendored QR matrix (boardgen/_qr_data.py).

The matrix is vendored (not generated at build time — see the provenance
note in _qr_data.py), so these tests guard against hand-edit corruption:
a QR code with a broken finder or timing pattern silently stops scanning
while still looking plausible on the silkscreen. The checks below need
no QR library — they assert the fixed structural features every valid
QR symbol carries (ISO/IEC 18004): the three 7x7 finder patterns, their
separators, and the alternating timing patterns in row/column 6.
"""
from __future__ import annotations

from boardgen._qr_data import QR_MATRIX, QR_URL

# 7x7 finder pattern: dark ring, light inner ring, 3x3 dark core.
_FINDER = [
    "1111111",
    "1000001",
    "1011101",
    "1011101",
    "1011101",
    "1000001",
    "1111111",
]


def test_matrix_is_square_version_4() -> None:
    # Version 4 = 33x33 modules (chosen for the 53-byte URL at EC M).
    assert len(QR_MATRIX) == 33
    assert all(len(row) == 33 for row in QR_MATRIX)
    assert all(set(row) <= {"0", "1"} for row in QR_MATRIX)


def test_url_points_at_the_public_repo() -> None:
    assert QR_URL == "https://github.com/hubertciebiada/open-ambient-sensor"


def _block(r0: int, c0: int, h: int, w: int) -> list[str]:
    return [QR_MATRIX[r][c0:c0 + w] for r in range(r0, r0 + h)]


def test_finder_patterns_at_three_corners() -> None:
    n = len(QR_MATRIX)
    assert _block(0, 0, 7, 7) == _FINDER            # top-left
    assert _block(0, n - 7, 7, 7) == _FINDER        # top-right
    assert _block(n - 7, 0, 7, 7) == _FINDER        # bottom-left


def test_finder_separators_are_light() -> None:
    n = len(QR_MATRIX)
    assert all(QR_MATRIX[7][c] == "0" for c in range(8))            # TL south
    assert all(QR_MATRIX[r][7] == "0" for r in range(8))            # TL east
    assert all(QR_MATRIX[7][c] == "0" for c in range(n - 8, n))     # TR south
    assert all(QR_MATRIX[r][n - 8] == "0" for r in range(8))        # TR west
    assert all(QR_MATRIX[n - 8][c] == "0" for c in range(8))        # BL north
    assert all(QR_MATRIX[r][7] == "0" for r in range(n - 8, n))     # BL east


def test_timing_patterns_alternate() -> None:
    n = len(QR_MATRIX)
    for i in range(8, n - 8):
        expected = "1" if i % 2 == 0 else "0"
        assert QR_MATRIX[6][i] == expected, f"row-6 timing broken at col {i}"
        assert QR_MATRIX[i][6] == expected, f"col-6 timing broken at row {i}"
