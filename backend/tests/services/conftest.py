"""
Fixtures for the service-layer unit tests.

`tests/conftest.py` opens a database session for every test via an autouse
fixture, which the API tests need. The tests in this package don't: they
exercise pure domain logic over in-memory objects. Overriding `db` here
keeps that true, so these tests run with no database at all — and stay fast.
"""

from collections.abc import Generator

import pytest


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[None]:
    yield None
