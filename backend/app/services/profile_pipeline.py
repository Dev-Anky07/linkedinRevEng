import httpx

from app.linkedin_client import LinkedInClient
from app.parsers import parse_certifications, parse_experience, parse_languages_rsc, parse_profile_page, parse_skills
from app.rsc import LANGUAGES_PAGER_ID, build_languages_request_body, build_languages_rsc_headers, build_pagination_path
from app.session_repository import RedisSessionRepository


class ProfilePipeline:
    """Run the authenticated LinkedIn requests in their required order.

    A single LinkedInClient and its in-memory cookie jar live for the whole
    pipeline. The encrypted jar is checkpointed after every upstream response.
    """

    def __init__(self, client: LinkedInClient, repository: RedisSessionRepository):
        self._client = client
        self._repository = repository

    async def run(self, username: str) -> dict:
        result: dict = {
            "profileUrl": f"https://www.linkedin.com/in/{username}/",
            "profile": {},
            "experience": [],
            "certifications": [],
            "skills": [],
            "languages": [],
            "meta": {"sections": {}, "warnings": []},
        }

        # Mandatory: this establishes/refreshes the session state used by all
        # later requests.
        profile_response = await self._client.get(f"/in/{username}/")
        result["profile"] = parse_profile_page(profile_response.text)
        result["meta"]["sections"]["profile"] = "parsed"
        await self._checkpoint()

        # Confirm that the complete source URL works. Return URL + media
        # metadata instead of a large base64 image in the API response.
        image_url = result["profile"].get("profileImageUrl")
        if image_url:
            image = await self._client.fetch_image_bytes(image_url)
            if image:
                image_bytes, content_type = image
                result["profile"]["profileImage"] = {
                    "url": image_url,
                    "contentType": content_type,
                    "sizeBytes": len(image_bytes),
                }
                result["meta"]["sections"]["profileImage"] = "fetched"
            else:
                result["meta"]["sections"]["profileImage"] = "unavailable"
                result["meta"]["warnings"].append("Profile image could not be fetched.")
            await self._checkpoint()

        await self._fetch_optional_section(result, "experience", f"/in/{username}/details/experience/", parse_experience)
        await self._fetch_optional_section(result, "certifications", f"/in/{username}/details/certifications/", parse_certifications)
        await self._fetch_optional_section(result, "skills", f"/in/{username}/details/skills/", parse_skills)
        await self._fetch_languages(result, username)
        return result

    async def _fetch_optional_section(self, result: dict, section: str, path: str, parser) -> None:
        try:
            response = await self._client.get(path)
            result[section] = parser(response.text)
            result["meta"]["sections"][section] = "parsed" if result[section] else "fetched_no_data"
        except httpx.HTTPError as error:
            result["meta"]["sections"][section] = "unavailable"
            status = error.response.status_code if getattr(error, "response", None) else "network error"
            result["meta"]["warnings"].append(f"{section.title()} could not be fetched ({status}).")
        finally:
            # Persist cookie changes even if a payload later proves unusable.
            await self._checkpoint()

    async def _checkpoint(self) -> None:
        self._repository.save(self._client.session_payload())

    async def _fetch_languages(self, result: dict, username: str) -> None:
        section = "languages"
        details_path = f"/in/{username}/details/languages/"
        try:
            # The HTML establishes the current trace context and contains the
            # per-section pager id. The actual language rows live in the RSC
            # pagination response.
            details_response = await self._client.get(details_path)
            await self._checkpoint()

            pagination_path = build_pagination_path(details_response.text, LANGUAGES_PAGER_ID)
            request_body = build_languages_request_body(details_response.text, username)
            page_headers = build_languages_rsc_headers(details_response.text)
            if not pagination_path or not request_body or not page_headers:
                result["meta"]["sections"][section] = "rsc_request_unresolved"
                result["meta"]["warnings"].append("Languages pagination metadata was not found in the details response.")
                return

            rsc_response = await self._client.get_rsc_pagination(pagination_path, details_path, request_body, page_headers)
            result[section] = parse_languages_rsc(rsc_response.text)
            result["meta"]["sections"][section] = "parsed" if result[section] else "rsc_fetched_no_data"
        except httpx.HTTPError as error:
            status = error.response.status_code if getattr(error, "response", None) else "network error"
            result["meta"]["sections"][section] = "unavailable"
            result["meta"]["warnings"].append(f"Languages could not be fetched ({status}).")
        finally:
            await self._checkpoint()
