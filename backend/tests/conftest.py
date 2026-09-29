from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from training_coach.api.app import create_app
from training_coach.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test", database_url="sqlite:///:memory:")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
