from bs4 import BeautifulSoup
from typing import List, Dict


def parse_languages(html: str) -> List[Dict[str, str]]:
    """
    Extract language name and proficiency from a LinkedIn /details/languages/ page.
    Returns a list of dicts: [{"name": "...", "proficiency": "..."}, ...]
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1. Find the heading that says "Languages"
    heading = None
    for h in soup.find_all(["h2", "h3"]):
        if h.get_text(strip=True) == "Languages":
            heading = h
            break

    if not heading:
        return []  # no languages section found

    # 2. Look for the next <ul> or <div> that contains the list items
    #    (we avoid hardcoded class names by traversing siblings)
    container = heading.find_next_sibling()
    while container and container.name not in ("ul", "div"):
        container = container.find_next_sibling()

    if not container:
        return []

    # 3. Extract each language item
    languages = []
    for item in container.find_all("li", recursive=False):   # direct children only
        # Each item likely contains two spans: name and proficiency
        spans = item.find_all("span")
        if len(spans) >= 2:
            name = spans[0].get_text(strip=True)
            proficiency = spans[1].get_text(strip=True)
            languages.append({"name": name, "proficiency": proficiency})
        else:
            # fallback: split by newline or other delimiters
            text = item.get_text(separator="\n", strip=True)
            parts = text.split("\n")
            if len(parts) >= 2:
                languages.append({"name": parts[0].strip(), "proficiency": parts[1].strip()})

    return languages