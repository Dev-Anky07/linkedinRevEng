from datetime import datetime, timezone
from typing import Any


def normalize_cookie_export(source: Any) -> list[dict[str, Any]]:
    """Accept common browser-export shapes and retain only LinkedIn-domain cookies."""
    raw_cookies = source.get("cookies", source) if isinstance(source, dict) else source
    if not isinstance(raw_cookies, list):
        raise ValueError("Cookie file must be a JSON array or an object containing a cookies array.")
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw_cookie in raw_cookies:
        if not isinstance(raw_cookie, dict):
            continue
        name = str(raw_cookie.get("name", "")).strip()
        value = str(raw_cookie.get("value", ""))
        domain = str(raw_cookie.get("domain", ".linkedin.com")).strip().lower()
        path = str(raw_cookie.get("path", "/")).strip() or "/"
        if not name or not value or not domain.lstrip(".").endswith("linkedin.com"):
            continue
        key = (name, domain, path)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"name": name, "value": value, "domain": domain, "path": path, "expires": raw_cookie.get("expires", raw_cookie.get("expirationDate")), "secure": bool(raw_cookie.get("secure", True)), "httpOnly": bool(raw_cookie.get("httpOnly", raw_cookie.get("http_only", False))), "sameSite": raw_cookie.get("sameSite", raw_cookie.get("same_site"))})
    if not normalized:
        raise ValueError("No LinkedIn-domain cookies were found in the supplied file.")
    return normalized


def make_session_payload(cookies: list[dict[str, Any]], session_id: str) -> dict[str, Any]:
    return {"schemaVersion": 1, "sessionId": session_id, "updatedAt": datetime.now(timezone.utc).isoformat(), "cookies": cookies}
