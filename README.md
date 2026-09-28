# SunLena

SunLena is a new, learning-first rebuild of SunLeo: a music discovery and playlist experience designed to start simply and grow only when real needs appear.

## Current status

The initial application flows are implemented: Apple catalog search, Firebase Google sign-in, PostgreSQL-backed playlists, reviews, and editorial mood discovery. Media extraction, reports/moderation, and account deletion are not implemented. This is an early foundation, not yet a verified feature-parity replacement for SunLeo; inspect the old source before calling parity complete.

## Start locally

SunLeo's environment entries have been carried into this checkout's ignored `.env`, with Firebase web keys mapped to SunLena's `VITE_FIREBASE_*` names. The Firebase Admin credential was copied to ignored `.secrets/firebase-admin.json`; its project ID matches the client config. Credential values are never included in this README. See the [full local-to-Lightsail walkthrough](design%20docs/10-local-and-lightsail-walkthrough.md) for setup, existing-container guidance, DNS, TLS, and deployment steps.

Requirements: Docker Desktop with Compose v2.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
New-Item -ItemType Directory -Force .secrets
docker compose up --build
```

Open <http://localhost:5173>. API liveness is at <http://localhost:8000/health/live> and readiness at <http://localhost:8000/health/ready>.

### Enable Google sign-in and saved data

1. In Firebase Console, enable **Authentication → Sign-in method → Google** and register `localhost` as an authorized domain.
2. Copy the Firebase web app values into `.env`: `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, and `VITE_FIREBASE_APP_ID`. Also set `FIREBASE_PROJECT_ID` to the same project ID.
3. Create a Firebase Admin service-account key and save it as `.secrets/firebase-admin.json`. This key is privileged: do not commit or share it. In a deployed environment, use a managed secret store instead of copying it to the image.
4. Restart Compose after changing `.env` so Vite receives the browser config.

Search uses Apple's public iTunes Search endpoint and stores normalized track references in PostgreSQL so playlists can refer to tracks. Results link back to Apple Music; artwork is displayed alongside the corresponding catalog link. The API caches search requests briefly and limits upstream calls. Provider rules and rate limits can change, so review them before opening the service publicly.

Without Firebase settings, catalog search works, while playlist/review writes correctly require sign-in. In Compose, PostgreSQL is wired and the API applies schema migrations before it starts. Last.fm enrichment and media extraction are not currently enabled.

Stop with `Ctrl+C`, then run `docker compose down`. Use `docker compose down -v` only when you intentionally want to delete the local PostgreSQL volume and its data.

## First Lightsail deployment

A production Compose file and Caddy HTTPS configuration are included. On the Lightsail VM, copy the repo, then:

```bash
cp env.lightsail.example .env
mkdir -p .secrets
```

Edit `.env` with your Name.com hostname, Firebase web config, Firebase project ID, and a strong base64url PostgreSQL password. Put the Firebase Admin service-account JSON at `.secrets/firebase-admin.json` with read-only permissions. In Name.com DNS, create an **A** record with host `sunlena` (or your chosen subdomain) and answer equal to the Lightsail static IPv4. In Firebase Authentication, add the public hostname as an authorized domain and enable Google sign-in.

Allow only TCP 80 and 443 publicly, plus SSH restricted to your IP. Then run:

```bash
docker compose -f compose.lightsail.yaml up -d --build
docker compose -f compose.lightsail.yaml ps
docker compose -f compose.lightsail.yaml logs -f api caddy
```

Caddy obtains and renews HTTPS certificates after DNS resolves. Verify `https://sunlena.your-domain`. The API and database do not publish host ports. This is still one VM: back up PostgreSQL, monitor disk and AWS spend, and keep media extraction disabled. AWS runtime and domain renewal can be billable; billing alerts do not cap spend. See [the Lightsail runbook](design%20docs/08-lightsail-domain-runbook.md) for the detailed DNS and TLS steps.

## Documentation

Start with [design docs/README.md](design%20docs/README.md) for product scope, architecture, UI direction, data/API plan, security, staged deployment, and Lightsail/Name.com setup.

## Principles

- Start as a modular monolith plus a separate worker process, not a fleet of microservices.
- Do not commit secrets or user media.
- Public AWS hosting is not guaranteed to cost zero; check current pricing before provisioning.
- Media extraction/downloading is not implemented. Do not enable an arbitrary-URL downloader without a rights basis and a safe source policy.
