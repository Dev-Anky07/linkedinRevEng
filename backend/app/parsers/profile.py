import re

from bs4 import BeautifulSoup


PRONOUN_WORDS = {
    "he", "him", "his", "she", "her", "hers", "they", "them", "their", "theirs",
    "xe", "xem", "xyr", "ze", "zir", "hir", "ey", "em", "eir", "ve", "ver", "per",
}


def _text(element) -> str:
    return element.get_text(" ", strip=True)


def _is_pronouns(text: str) -> bool:
    """Return true for compact pronoun labels such as ``He/Him`` or ``They/Them``."""
    parts = [part.strip().lower() for part in text.split("/") if part.strip()]
    return len(parts) >= 2 and all(part in PRONOUN_WORDS for part in parts)


def _top_card_content_block(h2):
    """Find the first ancestor whose direct paragraphs contain profile metadata.

    LinkedIn nests the name and optional pronouns inside a separate child element.
    The headline and education line are direct paragraphs of the next content block.
    """
    for ancestor in h2.parents:
        if not getattr(ancestor, "name", None):
            continue
        direct_paragraphs = ancestor.find_all("p", recursive=False)
        if any(_text(paragraph) and not _is_pronouns(_text(paragraph)) for paragraph in direct_paragraphs):
            return ancestor
    return None


def parse_profile_page(raw_html: str) -> dict:
    """Parse the LinkedIn profile page HTML.

    Returns a dict with profileImageUrl, name, headline, and location.
    Missing fields are returned as None (lenient, never raises).
    """
    soup = BeautifulSoup(raw_html, "html.parser")

    # 1. Profile image URL from the preload link
    profile_image_url = None
    for link in soup.find_all("link", {"rel": "preload", "as": "image"}):
        srcset = link.get("imagesrcset", link.get("imageSrcSet"))
        if srcset and "profile-displayphoto" in srcset:
            candidates = []
            for part in srcset.split(","):
                part = part.strip()
                if not part:
                    continue
                tokens = part.rsplit(maxsplit=1)
                if len(tokens) == 2:
                    url, desc = tokens
                    if desc.endswith("w"):
                        candidates.append((int(desc[:-1]), url))
            if candidates:
                _, best_url = max(candidates, key=lambda x: x[0])
                profile_image_url = best_url.replace("&amp;", "&")
            break

    # 2. Name from <title>
    name = None
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.text.strip()
        if " | LinkedIn" in title_text:
            name = title_text.split(" | LinkedIn")[0].strip()

    # 3. Headline and location using stable structural anchors
    headline = None
    location = None
    if name:
        primary_section = soup.find("section", {"aria-label": "Primary content"})
        if primary_section:
            lazy_col = primary_section.find("div", {"data-testid": "lazy-column"})
            if lazy_col:
                top_card_section = lazy_col.find("section")
                if top_card_section:
                    h2 = top_card_section.find("h2", string=re.compile(r"^" + re.escape(name) + r"$"))
                    if h2:
                        content_block = _top_card_content_block(h2)
                        if content_block:
                            direct_paragraphs = content_block.find_all("p", recursive=False)
                            for paragraph in direct_paragraphs:
                                text = _text(paragraph)
                                if text and not _is_pronouns(text):
                                    headline = text
                                    break

                            # Location is rendered in a direct child row, after the headline and
                            # education paragraphs. Avoid using the education line as a location.
                            for row in content_block.find_all("div", recursive=False):
                                for paragraph in row.find_all("p"):
                                    text = _text(paragraph)
                                    if text and text != "·" and "," in text and "Contact info" not in text:
                                        location = text
                                        break
                                if location:
                                    break

    return {
        "profileImageUrl": profile_image_url,
        "name": name,
        "headline": headline,
        "location": location,
    }
