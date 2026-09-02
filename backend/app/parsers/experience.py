import re

from bs4 import BeautifulSoup


def parse_experience(raw_html: str) -> list[dict]:
    """Parse the /details/experience/ page HTML into a list of experience dicts.

    Lenient: returns [] when no items are found, never raises.
    """
    soup = BeautifulSoup(raw_html, "html.parser")

    primary = soup.find("section", {"aria-label": "Primary content"})
    if not primary:
        return []

    lazy_col = primary.find("div", {"data-testid": "lazy-column"})
    if not lazy_col:
        return []

    items = lazy_col.find_all("div", componentkey=re.compile(r"^entity-collection-item-"))
    experiences = []

    month_pattern = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    date_pattern = re.compile(rf"{month_pattern}\s+\d{{4}}.*{month_pattern}\s+\d{{4}}")
    present_date_pattern = re.compile(rf"{month_pattern}\s+\d{{4}}\s*[-·]\s*Present", re.IGNORECASE)

    for item in items:
        paragraphs = item.find_all("p", recursive=True)

        title = None
        company = None
        employment_type = None
        date_range = None
        location = None
        description = None
        skills = None

        desc_p = item.find("p", {"data-testid": "expandable-text-box"})
        if desc_p:
            description = desc_p.get_text(strip=True)

        for p in paragraphs:
            text = p.get_text(strip=True)
            if text.startswith("Skills:"):
                raw_skills = text.replace("Skills:", "").strip()
                raw_skills = re.sub(r"\s*\+\s*\d+\s*skills$", "", raw_skills)
                skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
                break

        for p in paragraphs:
            text = p.get_text(strip=True)
            if not text:
                continue
            if (description and text == description) or (skills and text.startswith("Skills:")):
                continue

            if title is None:
                if "·" not in text and not date_pattern.search(text) and not present_date_pattern.search(text) and "," not in text:
                    title = text
                    continue

            if "·" in text and not date_pattern.search(text) and not present_date_pattern.search(text):
                parts = text.split("·")
                company = parts[0].strip()
                if len(parts) >= 2:
                    employment_type = parts[1].strip()
                continue

            if date_pattern.search(text) or present_date_pattern.search(text):
                date_range = text
                continue

            if "·" not in text and ("," in text or text.lower() in {"hybrid", "remote", "on-site", "onsite"}):
                location = text
                continue

            if title is None:
                title = text

        if title is None and paragraphs:
            title = paragraphs[0].get_text(strip=True)

        if title:
            experiences.append(
                {
                    "title": title,
                    "company": company,
                    "employmentType": employment_type,
                    "dateRange": date_range,
                    "location": location,
                    "description": description,
                    "skills": skills,
                }
            )

    return experiences
