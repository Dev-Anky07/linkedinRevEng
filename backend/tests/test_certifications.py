# backend/tests/test_certifications.py
import os
import json
from pathlib import Path
from app.parsers.certifications import parse_certifications

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parse_certifications():
    fixture_path = FIXTURE_DIR / "certifications.html"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    with open(fixture_path, "r", encoding="utf-8") as f:
        html = f.read()

    result = parse_certifications(html)

    # Always print the result for inspection
    print("\n🔍 Parsed certifications:")
    print(json.dumps(result, indent=2, default=str))
    print(f"\n📊 Count: {len(result)}")

    # The parser must always return a list
    assert isinstance(result, list)

    # Optional: If you know how many certifications to expect, add:
    # expected_count = 0  # adjust based on the fixture
    # assert len(result) == expected_count, f"Expected {expected_count}, got {len(result)}"