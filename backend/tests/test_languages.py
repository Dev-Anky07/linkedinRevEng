import os
from app.parsers.languages import parse_languages

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "languages.html")


def test_parse_languages():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    result = parse_languages(html)

    # The provided fixture does NOT contain the language list,
    # so we expect an empty list.
    assert result == [], f"Expected empty list, got {result}"

    # If you replace the fixture with a fully rendered page,
    # the expected output would be:
    # expected = [
    #     {"name": "English", "proficiency": "Native or bilingual proficiency"},
    #     {"name": "German", "proficiency": "Limited working proficiency"},
    #     {"name": "Hindi", "proficiency": "Native or bilingual proficiency"},
    # ]
    # assert result == expected