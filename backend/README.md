# Profilely backend

This service stores one mutable authenticated session as an encrypted Redis record and exposes the profile pipeline at `POST /api/v1/profiles`.

## Local setup

1. Copy the repository `.env.example` to `.env.local` and fill in `REDIS_URL`, `SESSION_ENCRYPTION_KEY`, and `LINKEDIN_SESSION_ID`.
2. Keep the browser-cookie export in `secrets/linkedin-cookies.json`; it must never be committed.
3. Bootstrap or rotate the encrypted Redis session:

   ```bash
   PYTHONPATH=backend python3 -m app.scripts.bootstrap_session \
     --cookies-file secrets/linkedin-cookies.json --force
   ```

4. Run the API:

   ```bash
   PYTHONPATH=backend python3 -m uvicorn app.main:app --reload --port 8000
   ```

5. Verify it:

   ```bash
   curl http://127.0.0.1:8000/health
   curl -X POST http://127.0.0.1:8000/api/v1/profiles \
     -H 'Content-Type: application/json' \
     --data '{"linkedinUrl":"https://www.linkedin.com/in/example/"}'
   ```

The profile pipeline serializes profile, image, experience, certifications, skills, and language requests under one Redis lock. The authentication cookie jar is checkpointed after every request. Sections that are fetched but not yet parseable return empty data with a section status in `data.meta.sections`.

## Vercel deployment

Deploy this `backend/` directory as its own Vercel project. `pyproject.toml` identifies `app.main:app` as the FastAPI entrypoint and `vercel.json` allows each profile pipeline request up to 90 seconds.

Create the following **Production** environment variables in Vercel. Mark the first two as **Sensitive**:

| Variable | Purpose |
| --- | --- |
| `REDIS_URL` | TLS Redis connection URL for the persistent encrypted cookie jar. |
| `SESSION_ENCRYPTION_KEY` | The same base64-encoded 32-byte AES key used when bootstrapping the production Redis record. |
| `LINKEDIN_SESSION_ID` | The Redis session name, normally `primary`. |
| `CORS_ORIGINS` | The deployed frontend origin, for example `https://your-web.vercel.app`. |

Do not add the browser-cookie export to Vercel environment variables or the repository. Instead, create the encrypted production session record once with the bootstrap script, using the production `REDIS_URL` and `SESSION_ENCRYPTION_KEY`. The service then loads and updates that Redis record after every upstream request.

Deploy the Vite repository root as a separate frontend Vercel project. Set its build command to `npm run build`, its output directory to `dist`, and set `VITE_API_BASE_URL` to the public URL of this backend, for example `https://your-api.vercel.app`. Because Vite exposes `VITE_*` values to the browser, that variable must contain only a public API URL—never a secret.
