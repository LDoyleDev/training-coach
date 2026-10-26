"""Every measurement kind reaches every place that lists kinds (ADR-0076): a new Kind that one
list misses fails here, not in front of the person."""

import io
import json
import zipfile
from datetime import UTC, date, datetime
from typing import get_args

from sqlalchemy.orm import Session

from training_coach.api.body import KindName
from training_coach.domain.measurements import REMEASURE, SPECS, Kind
from training_coach.services import ai_summary, export, measurements, proposals

# Kinds a connected AI can't propose, and why: resting heart rate comes from the band or the
# Body page (ADR-0058).
NOT_PROPOSABLE = {Kind.RESTING_HR}
ON = date(2026, 10, 10)


def test_every_kind_is_in_every_list() -> None:
    every = {k.value for k in Kind}
    assert set(get_args(KindName)) == every
    assert set(SPECS) == set(REMEASURE) == set(Kind)
    proposable = every - {k.value for k in NOT_PROPOSABLE}
    assert set(get_args(proposals.BodyKind)) == proposable
    schema = proposals.INPUT_SCHEMA["properties"]["measurements"]["properties"]
    assert set(schema) == proposable


def test_every_kind_is_stored_summarised_and_exported(session: Session) -> None:
    values = {k: SPECS[k].low for k in Kind}  # the database's check takes each kind
    assert measurements.save(session, ON, ON, values) is None
    session.flush()
    text = ai_summary.body(session, None)
    for kind in Kind:
        assert f"{ON.isoformat()} {SPECS[kind].label}:" in text, kind
    archive = export.archive(session, datetime.now(UTC))
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        rows = json.loads(zipped.read("data.json"))["tables"]["measurements"]
    assert {r["kind"] for r in rows} == {k.value for k in Kind}
