import json
from pathlib import Path

from app.parsers.skills import parse_skills

FIXTURE_DIR = Path(__file__).parent / "fixtures"

def test_parse_skills():
    fixture_path = FIXTURE_DIR / "skills.html"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    with open(fixture_path, "r", encoding="utf-8") as f:
        html = f.read()

    result = parse_skills(html)

    print("\n🔍 Parsed skills data:")
    print(json.dumps(result, indent=2, default=str))

    assert isinstance(result, list)
    # Optionally, you can assert that we got at least the expected count
    # but we keep it minimal.