# backend/app/parsers/certifications.py
import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup


def parse_certifications(response_text: str) -> List[Dict[str, Any]]:
    """
    Parse certifications from the LinkedIn /details/certifications/ HTML.

    Returns:
        List of certifications, each with: name, issuer, date (optional).
        Returns empty list if no named certification is found.
    """
    if not response_text:
        return []

    soup = BeautifulSoup(response_text, "html.parser")

    # 1. Try to extract from the rehydrate-data script (most reliable)
    certs = _extract_from_rehydration_script(soup)
    if certs:
        return certs

    # 2. Fallback: look for the certifications container in HTML
    return _extract_from_html_container(soup)


def _extract_from_rehydration_script(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Attempt to parse certification data from the rehydrate-data script."""
    script = soup.find("script", id="rehydrate-data")
    if not script or not script.string:
        return []

    content = script.string
    # Find the CertificationDetailsLevel component block
    pattern = r'"componentKey":"[^"]*CertificationDetailsLevel"[^}]*"items":(\[.*?\])(?=,"cacheKey"|$)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return []

    import json
    try:
        items_json = match.group(1)
        items = json.loads(items_json)
        certs = []
        for item in items:
            # item may have an "item" key that is a React element list
            cert_data = _extract_from_react_item(item.get("item", []))
            if cert_data:
                certs.append(cert_data)
        return certs
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def _extract_from_react_item(item: Any) -> Dict[str, Any]:
    """Extract certification name, issuer, date from React element tree."""
    # This is a simplified walk; in practice you'd traverse the tree.
    # For now, we look for patterns in the string representation.
    item_str = str(item)
    cert = {}
    # Try to find a name (often in a text array)
    name_match = re.search(r'"text":\["([^"]+)"\]', item_str)
    if name_match:
        cert["name"] = name_match.group(1)
    # Try issuer
    issuer_match = re.search(r'"issuer":\{"name":"([^"]+)"\}', item_str)
    if issuer_match:
        cert["issuer"] = issuer_match.group(1)
    # Try date
    date_match = re.search(r'"date":\{"year":(\d+),"month":(\d+)\}', item_str)
    if date_match:
        cert["date"] = f"{date_match.group(2)}/{date_match.group(1)}"
    return cert


def _extract_from_html_container(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Fallback: look for the certifications container and extract any visible names.
    If no name is found, return empty list (don't guess).
    """
    # Find the container with the CertificationDetailsLevel component key
    container = soup.find("div", attrs={"componentkey": re.compile(r"CertificationDetailsLevel")})
    if not container:
        # Try a broader search for the lazy column
        container = soup.find("div", attrs={"data-testid": "lazy-column"})
    if not container:
        return []

    # Look for text that might be a certification name – typically a heading or strong text
    # We'll search for any text that isn't "In progress" and is relatively short
    names = []
    for elem in container.find_all(["h2", "h3", "p", "strong", "span"]):
        text = elem.get_text(strip=True)
        if text and len(text) < 100 and "progress" not in text.lower() and "ad" not in text.lower():
            # Likely a certification name
            names.append(text)

    # If we have exactly one name and also have an "In progress" indicator, return it
    if names and "In progress" in container.get_text():
        return [{"name": names[0], "status": "In progress"}]

    # Otherwise, no reliable name – return empty
    return []