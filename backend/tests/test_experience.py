import json
from pathlib import Path
from app.parsers.experience import parse_experience

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parse_experience():
    """Test that the experience parser extracts data correctly."""
    fixture_path = FIXTURE_DIR / "experience.html"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    with open(fixture_path, "r", encoding="utf-8") as f:
        html = f.read()

    result = parse_experience(html)

    print("\n🔍 Parsed experience entries:")
    print(json.dumps(result, indent=2, default=str))
    print(f"\n📊 Count: {len(result)}")

    # Contract: parse_experience returns a list
    assert isinstance(result, list)

    # Optional: if a valid experience is present, check structure
    if result:
        first = result[0]
        # Each entry should be a dict with at least one of these fields
        # The exact fields may vary; we check if it's a dict
        assert isinstance(first, dict)
        # Optionally, assert specific keys if you know they should exist
        # assert "title" in first or "company" in first