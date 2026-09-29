# SunLena

SunLena is a new, learning-first rebuild of SunLeo: a music discovery and playlist experience designed to start simply and grow only when real needs appear.

## Current status

The current flows include Apple catalog search/previews, Firebase Google sign-in, PostgreSQL playlists/reviews, editorial discovery, persistent yt-dlp/FFmpeg download jobs, playback, and a bounded audio editor. Report/moderation and account deletion are not implemented. This remains a first feature-complete slice, not a verified feature-parity replacement for SunLeo.

## Start locally

SunLeo's environment entries have been carried into this checkout's ignored `.env`, with Firebase web keys mapped to SunLena's `VITE_FIREBASE_*` names. The Firebase Admin credential was copied to ignored `.secrets/firebase-admin.json`; its project ID matches the client config. Credential values are never included in this README. See the [full local-to-Lightsail walkthrough](design%20docs/10-local-and-lightsail-walkthrough.md) for setup, existing-container guidance, DNS, TLS, and deployment steps.

Requirements: Docker Desktop with Compose v2.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
New-Item -ItemType Directory -Force .secrets
docker compose up --build -d
```

Open <http://localhost:5173>. API liveness is at <http://localhost:8000/health/live> and readiness at <http://localhost:8000/health/ready>.

### Enable Google sign-in and saved data

1. In Firebase Console, enable **Authentication → Sign-in method → Google** and register `localhost` as an authorized domain.
2. Copy the Firebase web app values into `.env`: `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, and `VITE_FIREBASE_APP_ID`. Also set `FIREBASE_PROJECT_ID` to the same project ID.
3. Create a Firebase Admin service-account key and save it as `.secrets/firebase-admin.json`. This key is privileged: do not commit or share it. In a deployed environment, use a managed secret store instead of copying it to the image.
4. Restart Compose after changing `.env` so Vite receives the browser config.

Search uses Apple's public iTunes Search endpoint and stores normalized track references and optional preview URLs in PostgreSQL. Quick download queues a title/artist search using yt-dlp, then FFmpeg extracts the selected format. A separate single-concurrency worker updates persistent PostgreSQL job status and stores owner-private files on a shared named volume. The API limits jobs to 30 minutes/150 MB each, two active jobs per user, and 500 MB of completed files per user. The Studio editor trims and applies fades/EQ/volume/speed, then exports a new file without replacing the original.

Without Firebase settings, catalog search and Apple preview playback work, while playlists, reviews and downloads require sign-in. In Compose, PostgreSQL is wired and the API applies schema migrations before it starts; the worker waits for API health before claiming jobs. Last.fm enrichment and the chatbot are not currently wired in.

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

Caddy obtains and renews HTTPS certificates after DNS resolves. Verify `https://sunlena.your-domain`. The API, database, and worker do not publish host ports. This is still one VM: monitor disk and AWS spend, and plan separate PostgreSQL/media backups. AWS runtime and domain renewal can be billable; billing alerts do not cap spend. See [the Lightsail runbook](design%20docs/08-lightsail-domain-runbook.md) for the detailed DNS and TLS steps.

## Documentation

Start with [design docs/README.md](design%20docs/README.md) for product scope, architecture, UI direction, data/API plan, security, staged deployment, and Lightsail/Name.com setup.

## Principles

- Start as a modular monolith plus a separate worker process, not a fleet of microservices.
- Do not commit secrets or user media.
- Public AWS hosting is not guaranteed to cost zero; check current pricing before provisioning.
- The media worker only searches by a catalog track's title/artist; direct YouTube-link downloading and arbitrary URL routes are not supported. Do not expose arbitrary URL download routes or the private media volume.
