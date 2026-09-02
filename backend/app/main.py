import re
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, HttpUrl

from app.config import get_settings
from app.linkedin_client import LinkedInClient
from app.security import SessionCipher
from app.services.profile_pipeline import ProfilePipeline
from app.session_lock import RedisSessionLock, SessionBusyError
from app.session_repository import RedisSessionRepository, SessionNotFoundError

settings = get_settings()
repository = RedisSessionRepository(settings.redis_url, SessionCipher(settings.session_encryption_key), settings.linkedin_session_id)
session_lock = RedisSessionLock(settings.redis_url, settings.linkedin_session_id)
app = FastAPI(title="Profilely API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=False, allow_methods=["POST", "GET"], allow_headers=["Content-Type"])
USERNAME_PATTERN = re.compile(r"^/in/([A-Za-z0-9_-]+)/?$")
LINKEDIN_MEDIA_HOST = "media.licdn.com"

class ProfileRequest(BaseModel):
    linkedinUrl: HttpUrl

def extract_username(linkedin_url: str) -> str:
    parsed = urlparse(linkedin_url)
    if parsed.hostname not in {"linkedin.com", "www.linkedin.com"}:
        raise ValueError("A linkedin.com public profile URL is required.")
    match = USERNAME_PATTERN.match(parsed.path)
    if not match:
        raise ValueError("A LinkedIn /in/{username} URL is required.")
    return match.group(1)


def is_linkedin_media_url(image_url: str) -> bool:
    """Only proxy HTTPS LinkedIn CDN media; never act as a general URL fetcher."""
    parsed = urlparse(image_url)
    return parsed.scheme == "https" and parsed.hostname == LINKEDIN_MEDIA_HOST and parsed.port is None


@app.get("/")
def api_landing() -> dict[str, object]:
    return {
        "name": "Profilely API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "demo": "https://linkedinrevengweb.vercel.app/",
        "profileLookup": {
            "method": "POST",
            "path": "/api/v1/profiles",
        },
    }

@app.get("/health")
def health() -> dict[str, str]:
    try:
        repository.ping()
    except Exception as error:
        raise HTTPException(status_code=503, detail="Redis is unavailable.") from error
    return {"status": "ok"}

@app.post("/api/v1/profiles")
async def fetch_profile(payload: ProfileRequest) -> dict[str, object]:
    try:
        username = extract_username(str(payload.linkedinUrl))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    try:
        with session_lock.hold():
            session = repository.load()
            client = LinkedInClient(session, settings.linkedin_session_id)
            try:
                pipeline = ProfilePipeline(client, repository)
                result = await pipeline.run(username)
            finally:
                repository.save(client.session_payload())
                await client.close()
    except SessionBusyError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except SessionNotFoundError as error:
        raise HTTPException(status_code=503, detail="LinkedIn session has not been bootstrapped.") from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="LinkedIn returned an upstream request error.") from error
    return {"data": result}


@app.get("/api/v1/profile-image")
async def proxy_profile_image(source: HttpUrl) -> Response:
    """Stream a previously discovered LinkedIn profile image through the API.

    LinkedIn media requests require the server-side session cookies, which the
    browser must never receive. The URL validation keeps this endpoint from
    being used as an arbitrary outbound-request proxy.
    """
    image_url = str(source)
    if not is_linkedin_media_url(image_url):
        raise HTTPException(status_code=400, detail="Only media.licdn.com image URLs are allowed.")

    try:
        with session_lock.hold():
            session = repository.load()
            client = LinkedInClient(session, settings.linkedin_session_id)
            try:
                image = await client.fetch_image_bytes(image_url)
            finally:
                repository.save(client.session_payload())
                await client.close()
    except SessionBusyError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except SessionNotFoundError as error:
        raise HTTPException(status_code=503, detail="LinkedIn session has not been bootstrapped.") from error

    if not image:
        raise HTTPException(status_code=404, detail="Profile image is unavailable.")

    image_bytes, content_type = image
    return Response(
        content=image_bytes,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )
