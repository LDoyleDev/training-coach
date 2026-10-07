"""What import-linter can't see (CLAUDE.md "Architecture rules"): adapters hold no models and
no query builders, however they got them. A model re-exported by a service, or ``select``
imported from sqlalchemy, is still the adapter querying the database itself."""

import importlib
import pkgutil
from types import ModuleType

import pytest
import sqlalchemy
from sqlalchemy import select

import training_coach.api
import training_coach.bot
from training_coach.db import models
from training_coach.db.models import Exercise

# The only parts of sqlalchemy an adapter may hold: session types for annotations, and
# exceptions to report a failed save.
ALLOWED_SQLALCHEMY = ("sqlalchemy.orm.session", "sqlalchemy.exc")


def _adapter_modules() -> list[ModuleType]:
    modules = []
    for package in (training_coach.api, training_coach.bot):
        for info in pkgutil.walk_packages(package.__path__, f"{package.__name__}."):
            modules.append(importlib.import_module(info.name))
    return modules


def _offences(module: ModuleType) -> list[str]:
    found = []
    for name, value in vars(module).items():
        # A module object (``import sqlalchemy``) counts as what it is; anything else by
        # where it was defined.
        origin = (
            value.__name__ if isinstance(value, ModuleType) else getattr(value, "__module__", None)
        )
        if not isinstance(origin, str) or name.startswith("__"):
            continue
        if origin == "training_coach.db.models":
            found.append(f"{name} (a model)")
        elif origin.split(".")[0] == "sqlalchemy" and not origin.startswith(ALLOWED_SQLALCHEMY):
            found.append(f"{name} (from {origin})")
    return found


@pytest.mark.parametrize("module", _adapter_modules(), ids=lambda m: m.__name__)
def test_adapters_hold_no_models_or_query_builders(module: ModuleType) -> None:
    assert _offences(module) == []


def test_the_check_catches_a_model_and_a_query_builder() -> None:
    probe = ModuleType("probe")
    probe.Exercise = Exercise  # type: ignore[attr-defined]  # a fake adapter module
    probe.select = select  # type: ignore[attr-defined]
    probe.sqlalchemy = sqlalchemy  # type: ignore[attr-defined]
    probe.models = models  # type: ignore[attr-defined]
    assert sorted(_offences(probe)) == [
        "Exercise (a model)",
        "models (a model)",
        "select (from sqlalchemy.sql._selectable_constructors)",
        "sqlalchemy (from sqlalchemy)",
    ]
