import json
from pathlib import Path

import pytest

from umd_events.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str):
    return json.loads(fixture_text(name))


@pytest.fixture
def settings(tmp_path) -> Settings:
    s = Settings(data_dir=tmp_path)
    s.ensure_dirs()
    return s
