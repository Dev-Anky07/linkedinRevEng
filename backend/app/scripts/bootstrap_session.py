import argparse
import json
from pathlib import Path

from app.config import get_settings
from app.cookies import make_session_payload, normalize_cookie_export
from app.security import SessionCipher
from app.session_repository import RedisSessionRepository

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Encrypt a local LinkedIn cookie export and store it in Redis.")
    parser.add_argument("--cookies-file", type=Path, required=True, help="Path to an untracked JSON browser-cookie export.")
    parser.add_argument("--force", action="store_true", help="Replace an existing Redis session record.")
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    if not args.cookies_file.is_file():
        raise SystemExit(f"Cookie file not found: {args.cookies_file}")
    settings = get_settings()
    repository = RedisSessionRepository(settings.redis_url, SessionCipher(settings.session_encryption_key), settings.linkedin_session_id)
    try:
        cookies = normalize_cookie_export(json.loads(args.cookies_file.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"Unable to read a valid LinkedIn cookie export: {error}") from error
    try:
        repository.ping()
        if repository.exists() and not args.force:
            raise SystemExit("A Redis session already exists. Re-run with --force only when intentionally rotating it.")
        repository.save(make_session_payload(cookies, settings.linkedin_session_id))
    except Exception as error:
        raise SystemExit(f"Unable to store the encrypted session in Redis: {error}") from error
    print(f"Stored {len(cookies)} encrypted LinkedIn cookies at {repository.key}.")
    print("Cookie values were not printed.")

if __name__ == "__main__":
    main()
