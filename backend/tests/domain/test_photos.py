import pytest

from training_coach.domain.photos import MAX_BYTES, clean_jpeg


def segment(marker: int, body: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(body) + 2).to_bytes(2, "big") + body


JFIF = segment(0xE0, b"JFIF\x00\x01\x01")
EXIF = segment(0xE1, b"Exif\x00\x00GPS 52.52N 13.40E")
XMP = segment(0xE1, b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta/>")
ADOBE = segment(0xEE, b"Adobe\x00\x64")
COMMENT = segment(0xFE, b"taken at home")
TABLES = segment(0xDB, b"\x00" + bytes(64))
FRAME = segment(0xC0, b"\x08\x00\x10\x00\x10\x01\x01\x11\x00")
SCAN = segment(0xDA, b"\x01\x01\x00\x00\x3f\x00") + b"\x12\x34\xff\x00\x56" + b"\xff\xd9"


def jpeg(*segments: bytes) -> bytes:
    return b"\xff\xd8" + b"".join(segments)


def test_metadata_is_dropped_and_the_picture_kept() -> None:
    photo = jpeg(JFIF, EXIF, XMP, ADOBE, COMMENT, TABLES, FRAME, SCAN)
    cleaned = clean_jpeg(photo)
    assert cleaned == jpeg(JFIF, ADOBE, TABLES, FRAME, SCAN)
    assert isinstance(cleaned, bytes)
    assert b"GPS" not in cleaned
    assert b"xmpmeta" not in cleaned
    assert b"taken at home" not in cleaned


def test_fill_bytes_and_restart_markers_pass_through() -> None:
    photo = b"\xff\xd8" + b"\xff" + JFIF + b"\xff\xd0" + TABLES + FRAME + SCAN
    assert clean_jpeg(photo) == b"\xff\xd8" + JFIF + b"\xff\xd0" + TABLES + FRAME + SCAN


def test_trailing_padding_after_the_end_is_allowed() -> None:
    assert isinstance(clean_jpeg(jpeg(TABLES, FRAME, SCAN) + b"\x00\x00"), bytes)


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"\x89PNG\r\n\x1a\n", "isn't a JPEG"),
        (b"\xff\xd8" + b"\x00" * 10, "damaged"),  # no marker
        (b"\xff\xd8\xff", "damaged"),  # cut off at a marker
        (b"\xff\xd8\xff\xe0\x00", "damaged"),  # cut off in a length
        (b"\xff\xd8\xff\xe0\x00\x01", "damaged"),  # length below 2
        (b"\xff\xd8\xff\xe0\x00\x40abc", "damaged"),  # segment past the end
        (jpeg(TABLES, FRAME, SCAN[:-2]), "damaged"),  # no end of image
    ],
    ids=[
        "png",
        "no-marker",
        "cut-at-marker",
        "cut-in-length",
        "short-length",
        "past-end",
        "no-eoi",
    ],
)
def test_what_isnt_a_storable_jpeg_says_why(data: bytes, reason: str) -> None:
    result = clean_jpeg(data)
    assert isinstance(result, str)
    assert reason in result


def test_a_photo_over_the_limit_is_refused() -> None:
    assert clean_jpeg(bytes([0xFF, 0xD8]) + bytes(MAX_BYTES)) == "the photo is over 3 MB"
