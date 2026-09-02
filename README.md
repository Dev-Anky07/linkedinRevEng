# Profilely

Profilely is a small full-stack LinkedIn profile lookup tool. It accepts a public LinkedIn profile URL, runs a server-side sequential retrieval pipeline using a stored authenticated browser session, and returns structured profile data.

The repository contains two deployable applications:

- `src/` — Vite + React frontend.
- `backend/` — FastAPI API and encrypted Redis session management.

## Current response coverage

The API currently returns data that has been verified against captured profile responses:

- Name, headline, location, and profile image metadata
- Experience
- Languages

Certifications and skills are fetched by the pipeline but are intentionally not displayed until their parsers are reliable.

## Local setup

### 1. Configure secrets

Copy `.env.example` to `.env.local` and fill in the values:

```bash
cp .env.example .env.local
```

Required server-side values:

```text
REDIS_URL=rediss://...
SESSION_ENCRYPTION_KEY=base64-encoded-32-byte-key
LINKEDIN_SESSION_ID=primary
```

Keep the browser-cookie export at `secrets/linkedin-cookies.json`. It is ignored by Git and must never be committed.

### 2. Bootstrap the encrypted cookie jar

```bash
PYTHONPATH=backend python3 -m app.scripts.bootstrap_session \
  --cookies-file secrets/linkedin-cookies.json --force
```

This encrypts the cookie jar and stores it in Redis. The API reads and updates the same record after each upstream request.

### 3. Run the API

```bash
PYTHONPATH=backend python3 -m uvicorn app.main:app --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

### 4. Run the frontend

```bash
npm install
npm run dev
```

Open the URL Vite prints, normally `http://127.0.0.1:5173/`.

## API

### `POST /api/v1/profiles`

Request body:

```json
{
  "linkedinUrl": "https://www.linkedin.com/in/example-profile/"
}
```

Example response shape:

```json
{
  "data": {
    "profileUrl": "https://www.linkedin.com/in/example-profile/",
    "profile": {
      "name": "Example Person",
      "headline": "Example headline",
      "location": "City, Region, Country",
      "profileImage": {
        "url": "https://...",
        "contentType": "image/jpeg",
        "sizeBytes": 12345
      }
    },
    "experience": [],
    "languages": [],
    "certifications": [],
    "skills": [],
    "meta": {
      "sections": {
        "profile": "parsed",
        "profileImage": "fetched",
        "experience": "parsed",
        "languages": "parsed"
      },
      "warnings": []
    }
  }
}
```

Interactive local API documentation is available at `http://127.0.0.1:8000/docs`.

## Architecture

1. The frontend posts a LinkedIn `/in/{username}` URL to FastAPI.
2. The API validates the URL and extracts the username.
3. A Redis lock serializes access to the shared LinkedIn session.
4. The API loads the AES-GCM encrypted cookie jar from Redis.
5. Sequential upstream requests are made; the latest cookies are persisted after each checkpoint.
6. Parsers return structured data to the frontend.

## Deploying to Vercel

Deploy the same GitHub repository as **two Vercel projects**.

### Backend project

- Root Directory: `backend`
- FastAPI entrypoint: `app.main:app` (configured in `backend/pyproject.toml`)
- Production variables:
  - `REDIS_URL` — Sensitive
  - `SESSION_ENCRYPTION_KEY` — Sensitive
  - `LINKEDIN_SESSION_ID=primary`
  - `CORS_ORIGINS=https://your-frontend.vercel.app`

### Frontend project

- Root Directory: repository root
- Framework: Vite
- Build Command: `npm run build`
- Output Directory: `dist`
- Production variable:
  - `VITE_API_BASE_URL=https://your-api.vercel.app`

`VITE_*` variables are embedded in the browser build. Never place credentials, cookie JSON, Redis URLs, or encryption keys in a `VITE_*` variable.

If production uses a new Redis database, session ID, or encryption key, run the bootstrap script once with the production values before making API requests.

## Limitations

- LinkedIn’s response structure can change; parsers should be maintained alongside new fixtures.
- A single stored session is serialized with a Redis lock, so concurrent lookups wait rather than sharing cookie updates unsafely.
- The tool only returns fields visible to the authenticated session and currently exposes only the parser-verified fields in the UI.
- Use must comply with LinkedIn’s applicable terms, privacy obligations, and the laws relevant to your users and deployment.

## Security

- Browser cookies are not stored in the repository or sent to the frontend.
- Redis stores the cookie jar as an AES-GCM encrypted record.
- Rotate the encryption key deliberately: existing session records must be re-bootstrapped after a key rotation.
