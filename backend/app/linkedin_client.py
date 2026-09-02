import re

import httpx

from app.cookies import make_session_payload

LINKEDIN_ORIGIN = "https://www.linkedin.com"
BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}


class LinkedInClient:
    """Stateful httpx client for one pipeline run.

    The cookie jar carries Set-Cookie updates from each upstream response
    into the next request automatically.
    """

    def __init__(self, session_payload: dict, session_id: str):
        self._session_id = session_id
        cookies = httpx.Cookies()
        for cookie in session_payload.get("cookies", []):
            if not cookie.get("name") or not cookie.get("value"):
                continue
            cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
            )
        self._client = httpx.AsyncClient(
            cookies=cookies,
            headers=BROWSER_HEADERS,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
        )

    async def get(self, path_or_url: str) -> httpx.Response:
        url = path_or_url if path_or_url.startswith("https://") else f"{LINKEDIN_ORIGIN}{path_or_url}"
        response = await self._client.get(url)
        response.raise_for_status()
        return response

    async def fetch_image_bytes(self, image_url: str) -> tuple[bytes, str] | None:
        try:
            response = await self.get(image_url)
        except httpx.HTTPError:
            return None
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("image/"):
            return response.content, content_type.split(";")[0].strip()
        return None

    def _csrf_token_for_url(self, url: str) -> str | None:
        """Use the JSESSIONID that httpx will actually send to this URL.

        A browser jar can contain multiple JSESSIONID variants. Selecting the
        first jar entry can pair the CSRF header with the wrong session cookie.
        """
        prepared = self._client.build_request("POST", url)
        cookie_header = prepared.headers.get("cookie", "")
        match = re.search(r'(?:^|;\s*)JSESSIONID=(?:"([^"]+)"|([^;\s]+))', cookie_header)
        return (match.group(1) or match.group(2)) if match else None

    async def get_rsc_pagination(self, pagination_path: str, referer_path: str, request_body: dict, page_headers: dict[str, str]) -> httpx.Response:
        """Fetch a React Flight pagination response using the live cookie jar."""
        url = f"{LINKEDIN_ORIGIN}{pagination_path}"
        csrf_token = self._csrf_token_for_url(url)
        if not csrf_token:
            raise httpx.RequestError("JSESSIONID is unavailable; cannot set csrf-token.")
        response = await self._client.post(
            url,
            json=request_body,
            headers={
                "Accept": "*/*",
                "Content-Type": "application/json",
                "csrf-token": csrf_token,
                "Origin": LINKEDIN_ORIGIN,
                "Referer": f"{LINKEDIN_ORIGIN}{referer_path}",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                **page_headers,
            },
        )
        response.raise_for_status()
        return response

    def session_payload(self) -> dict:
        """Serialize the live httpx cookie jar back into the storage format."""
        jar = self._client.cookies.jar
        cookies = []
        for cookie in jar:
            cookies.append(
                {
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                    "expires": cookie.expires,
                    "secure": bool(cookie.secure),
                    "httpOnly": "HttpOnly" in getattr(cookie, "_rest", {}),
                }
            )
        return make_session_payload(cookies, self._session_id)

    async def close(self) -> None:
        await self._client.aclose()
