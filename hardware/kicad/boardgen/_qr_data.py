"""boardgen/_qr_data.py — vendored QR-code module matrix for the silkscreen.

QR code linking to the public project repository, printed on F.SilkS in
the west pocket freed by the NFC removal (GitHub issue #7). The matrix
is VENDORED (not generated at build time) so boardgen stays free of
third-party dependencies and bit-deterministic (Lesson 9).

Provenance
----------
Generated 2026-07-17 with python `qrcode` 8.2:

    import qrcode
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                       border=0)
    qr.add_data(QR_URL)
    qr.make(fit=True)          # -> version 4 (33x33), EC level M

Regenerate with the same snippet if QR_URL ever changes, then paste the
new rows below ('1' = dark module, '0' = light module) and re-run the
structural unit tests (tests/test_qr_data.py: size, finder patterns,
timing pattern). EC level M survives ~15 % module damage — chosen over
L for silkscreen print robustness. The quiet zone is NOT part of this
matrix; the emitter adds it (QR_SILK_QUIET_MODULES in _project.py).
"""

QR_URL = "https://github.com/hubertciebiada/open-ambient-sensor"

# 33 rows x 33 cols, row 0 = top (PCB north), col 0 = west. '1' = dark.
QR_MATRIX = [
    "111111100101100010111001001111111",
    "100000100011000101101010001000001",
    "101110101111101000101100001011101",
    "101110101100000100101010101011101",
    "101110101110011110111111001011101",
    "100000101111100001101000001000001",
    "111111101010101010101010101111111",
    "000000001110101010111100000000000",
    "101111100010011001011000001111100",
    "010111000010010011111101001101101",
    "001111110000011111000110111010100",
    "000110010100110111100100110011110",
    "011100101111001110010001110111000",
    "001110010010000100111001001101011",
    "111100110001011110001010011111010",
    "100011011000000100010100111011100",
    "100101100101001101000011110110001",
    "110111001110010010011001001101101",
    "110010100110101110101110100110110",
    "010011001011010100011110010111100",
    "100110100110101000111010110111010",
    "100110000110001110011111001001001",
    "100000111011011001100000110001010",
    "100011000000100010111111111001110",
    "101101101001100001010010111111010",
    "000000001111110011010101100010101",
    "111111100111110111001001101010110",
    "100000101011111001101111100011110",
    "101110101101111110010010111111000",
    "101110101101100100111001110010111",
    "101110101011010110001010001100100",
    "100000100110000100101110011011100",
    "111111101010010101000011110100010",
]
