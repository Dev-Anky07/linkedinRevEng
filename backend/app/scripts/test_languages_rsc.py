"""Exercise the live language RSC request without printing sensitive state."""

import argparse
import asyncio
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.config import get_settings
from app.linkedin_client import LinkedInClient
from app.rsc import LANGUAGES_PAGER_ID, build_languages_request_body, build_languages_rsc_headers, build_pagination_path, parse_languages_rsc
from app.security import SessionCipher
from app.session_lock import RedisSessionLock
from app.session_repository import RedisSessionRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test the derived languages RSC request.")
    parser.add_argument("username", help="Validated LinkedIn public-profile username")
    parser.add_argument("--without-parent-span", action="store_true", help="Omit parentSpanId while keeping the resolved pager id.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    settings = get_settings()
    repository = RedisSessionRepository(settings.redis_url, SessionCipher(settings.session_encryption_key), settings.linkedin_session_id)
    session_lock = RedisSessionLock(settings.redis_url, settings.linkedin_session_id)
    details_path = f"/in/{args.username}/details/languages/"

    with session_lock.hold():
        client = LinkedInClient(repository.load(), settings.linkedin_session_id)
        try:
            details = await client.get(details_path)
            pagination_path = build_pagination_path(details.text, LANGUAGES_PAGER_ID)
            request_body = build_languages_request_body(details.text, args.username)
            page_headers = build_languages_rsc_headers(details.text)
            if not pagination_path or not request_body or not page_headers:
                print({"rscPathResolved": bool(pagination_path), "requestBodyResolved": bool(request_body), "pageHeadersResolved": bool(page_headers)})
                return

            if args.without_parent_span:
                parts = urlsplit(pagination_path)
                query = [(key, value) for key, value in parse_qsl(parts.query) if key != "parentSpanId"]
                pagination_path = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

            try:
                rsc_response = await client.get_rsc_pagination(pagination_path, details_path, request_body, page_headers)
            except httpx.HTTPStatusError as error:
                print(
                    {
                        "rscPathResolved": True,
                        "requestBodyResolved": True,
                        "pageHeadersResolved": True,
                        "parentSpanIdIncluded": not args.without_parent_span,
                        "httpStatus": error.response.status_code,
                        "contentType": error.response.headers.get("content-type", ""),
                        "responseBytes": len(error.response.content),
                        "responseText": error.response.text[:200],
                        "parsedLanguages": [],
                    }
                )
                return

            print({"rscPathResolved": True, "requestBodyResolved": True, "pageHeadersResolved": True, "parentSpanIdIncluded": not args.without_parent_span, "httpStatus": rsc_response.status_code, "contentType": rsc_response.headers.get("content-type", ""), "parsedLanguages": parse_languages_rsc(rsc_response.text), "responseBytes": len(rsc_response.content)})
        finally:
            repository.save(client.session_payload())
            await client.close()


if __name__ == "__main__":
    asyncio.run(main())
