"""Fuzzing ``clean_jpeg`` with seeded random photos (security review 2026-10-10).

Seeded, so a failure reproduces; ``TC_FUZZ_ROUNDS`` runs more rounds locally
(``TC_FUZZ_ROUNDS=200000 uv run pytest tests/domain/test_photos_fuzz.py``).
"""

import os
import random

from training_coach.domain.photos import clean_jpeg

ROUNDS = int(os.environ.get("TC_FUZZ_ROUNDS", "2000"))
SECRET = b"GPS-52.5200N-13.4050E"  # long enough never to turn up by chance
KEPT = [*range(0xC0, 0xD0), 0xDB, 0xDD]  # frames, tables, DQT, DRI (SOS is added per scan)
# Every other marker that has a length: APPn, COM, JPG extensions and the unassigned ones.
DROPPED = [m for m in range(0x02, 0xFF) if m not in KEPT and m not in (0xD8, 0xD9, 0xDA, 0x01)]
DROPPED = [m for m in DROPPED if not 0xD0 <= m <= 0xD7]
ALPHABET = [b for b in range(256) if b != SECRET[0]]


def segment(marker: int, body: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(body) + 2).to_bytes(2, "big") + body


def noise(rng: random.Random, most: int) -> bytes:
    """Random bytes that can't hold the secret's first byte, so it can only come from us."""
    return bytes(rng.choices(ALPHABET, k=rng.randint(0, most)))


def scan_data(rng: random.Random) -> bytes:
    """Entropy-coded data as an encoder writes it: every 0xFF stuffed, restart markers between."""
    data = bytearray()
    for _ in range(rng.randint(1, 4)):
        data += noise(rng, 40).replace(b"\xff", b"\xff\x00")
        if rng.random() < 0.3:
            data += bytes([0xFF, rng.randint(0xD0, 0xD7)])
    return bytes(data)


def photo(rng: random.Random) -> bytes:
    """A well-formed JPEG with the secret in every metadata segment, mixed in anywhere."""
    parts: list[bytes] = []
    for _ in range(rng.randint(1, 3)):  # one or more scans, metadata possible between them
        for _ in range(rng.randint(0, 5)):
            roll = rng.random()
            if roll < 0.4:
                parts.append(segment(rng.choice(DROPPED), noise(rng, 20) + SECRET + noise(rng, 20)))
            elif roll < 0.5:  # an APP14 that isn't Adobe's
                parts.append(segment(0xEE, b"Other" + SECRET))
            elif roll < 0.6:
                parts.append(segment(0xEE, b"Adobe" + noise(rng, 7)))
            elif roll < 0.7:
                parts.append(b"\xff" * rng.randint(1, 3))  # fill bytes before a marker
            else:
                parts.append(segment(rng.choice(KEPT), noise(rng, 30)))
        parts.append(segment(0xDA, noise(rng, 10)) + scan_data(rng))
    trailer = SECRET if rng.random() < 0.3 else b""  # after the end: a camera's extra data
    return b"\xff\xd8" + b"".join(parts) + b"\xff\xd9" + trailer


def mutate(rng: random.Random, data: bytes) -> bytes:
    """Damage it the ways files get damaged: flipped, cut, inserted or deleted bytes."""
    damaged = bytearray(data)
    for _ in range(rng.randint(1, 4)):
        where = rng.randrange(len(damaged)) if damaged else 0
        kind = rng.randrange(4)
        if kind == 0 and damaged:
            damaged[where] = rng.randrange(256)
        elif kind == 1:
            del damaged[where:]
        elif kind == 2:
            damaged[where:where] = bytes(rng.randrange(256) for _ in range(rng.randint(1, 4)))
        elif damaged:
            del damaged[where : where + rng.randint(1, 4)]
    return bytes(damaged)


def test_no_metadata_survives_in_a_well_formed_photo() -> None:
    rng = random.Random(143)  # noqa: S311 - seeded to reproduce, not for secrets
    for round_ in range(ROUNDS):
        data = photo(rng)
        cleaned = clean_jpeg(data)
        assert isinstance(cleaned, bytes), (round_, cleaned)
        assert SECRET not in cleaned, round_
        assert cleaned.startswith(b"\xff\xd8"), round_
        assert cleaned.endswith(b"\xff\xd9"), round_


def test_a_damaged_photo_never_crashes_and_cleaning_settles() -> None:
    """Whatever the bytes: an answer (never an exception), never longer than what came in, and
    a cleaned photo comes through a second cleaning unchanged."""
    rng = random.Random(39)  # noqa: S311 - seeded to reproduce, not for secrets
    for round_ in range(ROUNDS):
        data = mutate(rng, photo(rng))
        cleaned = clean_jpeg(data)
        assert isinstance(cleaned, bytes | str), round_
        if isinstance(cleaned, bytes):
            assert len(cleaned) <= len(data), round_
            assert clean_jpeg(cleaned) == cleaned, round_


def test_random_bytes_are_refused_not_crashed_on() -> None:
    rng = random.Random(7)  # noqa: S311 - seeded to reproduce, not for secrets
    for round_ in range(ROUNDS):
        start = b"\xff\xd8" if rng.random() < 0.5 else b""
        data = start + bytes(rng.randrange(256) for _ in range(rng.randint(0, 200)))
        assert isinstance(clean_jpeg(data), bytes | str), round_
