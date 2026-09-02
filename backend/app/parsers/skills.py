from bs4 import BeautifulSoup

def parse_skills(html: str) -> list[str]:
    """
    Extract skill names from the /details/skills/ page HTML.

    Strategy:
      - Find all <p> tags that have a <span> child.
      - Extract the first text node inside that <span> (or just get the text).
      - Skip any <p> that is inside a <nav> (the filter pills).
      - Skip the heading "Skills" (it has no <span> anyway).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Find all <p> tags that contain a <span> as a direct or nested child
    all_ps = soup.find_all("p")
    skills = []

    for p in all_ps:
        # Skip if this <p> is inside a <nav> (filter pills)
        if p.find_parent("nav"):
            continue

        # Check if this <p> has a <span> child
        span = p.find("span")
        if span:
            # Get the text of the span, but strip any extra whitespace
            text = span.get_text(strip=True)
            if text and text != "Skills":
                skills.append(text)

    return skills