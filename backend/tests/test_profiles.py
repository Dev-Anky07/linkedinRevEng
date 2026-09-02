import json
from pathlib import Path
from app.parsers.profile import parse_profile_page

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parse_profile():
    """Test that the profile parser extracts data correctly."""
    fixture_path = FIXTURE_DIR / "profile.html"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    with open(fixture_path, "r", encoding="utf-8") as f:
        html = f.read()

    result = parse_profile_page(html)

    print("\n🔍 Parsed profile data:")
    print(json.dumps(result, indent=2, default=str))

    # Contract: parse_profile_page returns a dict
    assert isinstance(result, dict)

    # Check for expected top-level keys (even if empty)
    assert result["headline"] == (
        "Ex Intern @ Tech Mahindra Makers Lab | Agentic AI | Generative AI | "
        "RAG Systems | Computer Vision | Ex-Maple & Moss Capital | Ex-Mishka Tech"
    )
    assert result["location"] == "Noida, Uttar Pradesh, India"
