import json
from pathlib import Path

from app.rsc import parse_languages_rsc


def test_parse_languages_rsc() -> None:
    payload = (Path(__file__).parent / "fixtures" / "languages.rsc").read_text(encoding="utf-8")

    assert parse_languages_rsc(payload) == [
        {"name": "English", "proficiency": "Native or bilingual proficiency"},
        {"name": "German", "proficiency": "Limited working proficiency"},
        {"name": "Hindi", "proficiency": "Native or bilingual proficiency"},
    ]
