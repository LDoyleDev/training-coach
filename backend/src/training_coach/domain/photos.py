"""Progress photos (2-B, #143, ADR-0039). Pure logic, no I/O.

Only JPEG is accepted, and every photo is cleaned before it is stored: the metadata segments
(EXIF with the camera's GPS position and time, XMP, comments, ...) are dropped and only what is
needed to show the picture is kept. The browser re-encodes photos before upload, which drops
them too; this is the check that doesn't trust it.
"""

from enum import StrEnum

MAX_BYTES = 3 * 1024 * 1024  # a 1600 px JPEG from the browser is well under 1 MB


class Pose(StrEnum):
    FRONT = "front"
    SIDE = "side"
    BACK = "back"


SOI = b"\xff\xd8"
EOI = b"\xff\xd9"
SOS = 0xDA
APP0 = 0xE0  # JFIF: density and version, nothing personal
APP14 = 0xEE  # Adobe: the colour transform some decoders need
KEEP_APP = frozenset({APP0, APP14})
COM = 0xFE
STANDALONE = frozenset({0x01, *range(0xD0, 0xD8)})  # TEM, RST0-7: no length field


def _scan_end(data: bytes, at: int) -> int:
    """Where the entropy-coded image data starting at ``at`` ends: the next real marker.
    0xFF 0x00 is a stuffed byte and 0xFF 0xD0-0xD7 restart markers, both part of the data."""
    while True:
        at = data.find(0xFF, at)
        if at == -1 or at + 1 >= len(data):
            return -1
        following = data[at + 1]
        if following == 0x00 or 0xD0 <= following <= 0xD7 or following == 0xFF:
            at += 1
            continue
        return at


def clean_jpeg(data: bytes) -> bytes | str:
    """The JPEG without its metadata segments, or why it isn't a JPEG that can be stored.

    Walks every segment, through the image data of each scan, so metadata placed between
    scans is dropped too; stops at the first end-of-image marker and drops anything after it
    (a camera's trailer, a second picture)."""
    if len(data) > MAX_BYTES:
        return f"the photo is over {MAX_BYTES // (1024 * 1024)} MB"
    if not data.startswith(SOI):
        return "the photo isn't a JPEG"
    kept = bytearray(SOI)
    at = len(SOI)
    scanned = False
    while True:
        if at + 2 > len(data) or data[at] != 0xFF:
            return "the photo is damaged"
        marker = data[at + 1]
        if marker == 0xFF:  # fill byte before a marker
            at += 1
            continue
        if marker == EOI[1]:
            if not scanned:
                return "the photo is damaged"
            kept += EOI
            return bytes(kept)  # anything after the end is dropped
        if marker in STANDALONE:
            kept += data[at : at + 2]
            at += 2
            continue
        if at + 4 > len(data):
            return "the photo is damaged"
        length = int.from_bytes(data[at + 2 : at + 4], "big")
        end = at + 2 + length
        if length < 2 or end > len(data):
            return "the photo is damaged"
        metadata = (0xE0 <= marker <= 0xEF and marker not in KEEP_APP) or marker == COM
        if not metadata:
            kept += data[at:end]
        at = end
        if marker == SOS:
            stop = _scan_end(data, at)
            if stop == -1:
                return "the photo is damaged"
            kept += data[at:stop]  # the image data of this scan
            at = stop
            scanned = True
