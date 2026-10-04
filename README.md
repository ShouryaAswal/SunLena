# SunLena

SunLena is a new, learning-first rebuild of SunLeo: a music discovery and playlist experience designed to start simply and grow only when real needs appear.

## Current status

The current flows include Apple catalog search/previews, Firebase Google sign-in, PostgreSQL playlists/reviews, editorial discovery, persistent yt-dlp/Cobalt download jobs, playback, and a bounded audio editor. Report/moderation and account deletion are not implemented. This remains a first feature-complete slice, not a verified feature-parity replacement for SunLeo.

## Start locally

SunLeo's environment entries have been carried into this checkout's ignored `.env`, with Firebase web keys mapped to SunLena's `VITE_FIREBASE_*` names. The Firebase Admin credential was copied to ignored `.secrets/firebase-admin.json`; its project ID matches the client config. Credential values are never included in this README. See the [full local-to-EC2 walkthrough](design%20docs/10-local-and-ec2-walkthrough.md) for setup, existing-container guidance, DNS, TLS, and deployment steps.

Requirements: Docker Desktop with Compose v2.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
New-Item -ItemType Directory -Force .secrets
docker compose -f compose.yaml -f compose.cobalt.yaml up --build -d
```

This starts local development with the Cobalt extractor enabled. To use the base yt-dlp pipeline instead, run `docker compose up --build -d`.

Open <http://localhost:5173>. API liveness is at <http://localhost:8000/health/live> and readiness at <http://localhost:8000/health/ready>.

### Enable Google sign-in and saved data

1. In Firebase Console, enable **Authentication → Sign-in method → Google** and register `localhost` as an authorized domain.
2. Copy the Firebase web app values into `.env`: `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, and `VITE_FIREBASE_APP_ID`. Also set `FIREBASE_PROJECT_ID` to the same project ID.
3. Create a Firebase Admin service-account key and save it as `.secrets/firebase-admin.json`. This key is privileged: do not commit or share it. In a deployed environment, use a managed secret store instead of copying it to the image.
4. Restart Compose after changing `.env` so Vite receives the browser config.

Search uses Apple's public iTunes Search endpoint and stores normalized track references and optional preview URLs in PostgreSQL. The homepage accepts either catalog search or a supported public media URL. Jobs use the existing persistent worker and private media volume; `SUNLENA_MEDIA_EXTRACTOR` selects `yt-dlp` (default) or Cobalt. With Cobalt selected, YouTube URLs and catalog downloads still go through yt-dlp with bgutil PO tokens (`SUNLENA_YOUTUBE_EXTRACTOR=yt-dlp`, the default), because Cobalt returns empty tunnels for YouTube videos that require video-bound PO tokens. Other URLs (Instagram, TikTok, …) go to Cobalt. The optional Cobalt deployment is in `compose.cobalt.yaml`; run it with `docker compose -f compose.yaml -f compose.cobalt.yaml up --build -d`. It adds a private Cobalt API with no host-published port. For details on formats, Cobalt API constraints, environment variables, tests, troubleshooting, and EC2 design, see [media extraction backends](design%20docs/11-media-extractors.md).

The yt-dlp pipeline remains installed and functional: the API/worker image pins yt-dlp and `bgutil-ytdlp-pot-provider`, uses yt-dlp's `default` extra (`yt-dlp-ejs`), Deno, and FFmpeg, and the base Compose stack starts its provider sidecar. The worker updates persistent PostgreSQL job status and stores owner-private files on the existing shared named volume. The API limits jobs to 30 minutes/150 MB each, two active jobs per user, and 500 MB of completed files per user. Cobalt handles requested extraction/conversion; SunLena's existing FFmpeg is used only when needed for output normalization and by the Studio editor.

To reproduce the complete media setup locally, use `docker compose up --build -d`; Compose builds the pinned API/worker image and starts the PO-token provider alongside the worker. For an EC2 rollout, rebuild and recreate the worker and provider with `sudo docker compose -f compose.ec2.yaml up -d --build worker bgutil-provider` (then inspect `ps` and logs). Do not use `down -v`; the media volume remains intact. To diagnose YouTube extraction, run this from the worker container, replacing the sample query with a permitted public video:

```bash
docker compose -f compose.ec2.yaml exec worker python -m yt_dlp --verbose --simulate \
  --extractor-args 'youtubepot-bgutilhttp:base_url=http://bgutil-provider:4416' \
  'ytsearch1:Rick Astley Never Gonna Give You Up'
```

Verbose output should list a `bgutil` PO Token Provider. If it does not, check that the worker image contains `bgutil-ytdlp-pot-provider==2.0.0`, the provider container is running, and the worker can reach `bgutil-provider:4416`. PO tokens can improve extraction on IPs receiving YouTube bot challenges, but do not guarantee downloads: YouTube may change enforcement or restrict an EC2 address. The Compose bridge makes the provider private to the stack and publishes no helper port; destination-level outbound filtering for YouTube/CDN endpoints must be enforced by the host/network firewall if required, since Compose does not provide domain-based egress filtering.

Without Firebase settings, catalog search and Apple preview playback work, while playlists, reviews and downloads require sign-in. In Compose, PostgreSQL is wired and the API applies schema migrations before it starts; the worker waits for API health before claiming jobs. Last.fm enrichment and the chatbot are not currently wired in.

Stop with `Ctrl+C`, then run `docker compose down`. Use `docker compose down -v` only when you intentionally want to delete the local PostgreSQL volume and its data.

## First EC2 deployment

The initial AWS target is one EC2 `m7i-flex.large` instance in Mumbai, running the production Compose stack behind Caddy. The host has 2 vCPU and 8 GiB RAM; keep media conversion concurrency at one and measure CPU, RAM and disk before inviting the full group. This is a single failure domain with no automatic failover. A current public price-list index puts on-demand compute around $73.55/month for 730 hours, before disk, public IPv4, transfer, snapshots and tax; verify with AWS Pricing Calculator. $100 of new-account credits would cover only about 1.36 months of compute at that estimate. So EC2 is a learning/flexibility choice while credits last, not the cheaper long-term option versus a $24 Lightsail plan.

**Free Tier eligibility is account-date dependent.** AWS currently lists `m7i-flex.large` as eligible for accounts created on/after July 15, 2025 under a credit-based program lasting at most six months or until credits run out. Older accounts have different eligible instance sizes. Confirm the account date, current credits, AMI/region eligibility and estimated bill in AWS Billing before provisioning. Public IPv4, EBS, snapshots, transfer and domain renewal can add costs; billing alerts do not cap charges. Read the [EC2, VPC, security-group, domain and cost runbook](design%20docs/08-ec2-domain-runbook.md) before launch.

The production files are `compose.ec2.yaml` and `env.ec2.example`. On the EC2 host:

```bash
cp env.ec2.example .env
mkdir -p .secrets
chmod 700 .secrets
# Fill in .env; copy the matching Firebase Admin JSON into .secrets/firebase-admin.json.
sudo docker compose -f compose.ec2.yaml config --quiet
sudo docker compose -f compose.ec2.yaml up -d --build
sudo docker compose -f compose.ec2.yaml ps
```

Set up one custom VPC/public subnet/Internet Gateway, allow inbound TCP 80/443 only, and prefer SSM Session Manager without an inbound SSH rule. Point a Name.com `A` record (for example host `sunlena`) at the EC2 Elastic IP, or update it when a dynamic IP changes. Caddy obtains HTTPS after DNS resolves. See the [full local-to-EC2 walkthrough](design%20docs/10-local-and-ec2-walkthrough.md) for every step.
## Documentation

Start with [design docs/README.md](design%20docs/README.md) for product scope, architecture, UI direction, data/API plan, security, staged deployment, and EC2/Name.com setup.

## Principles

- Start as a modular monolith plus a separate worker process, not a fleet of microservices.
- Do not commit secrets or user media.
- Public AWS hosting is not guaranteed to cost zero; check current pricing before provisioning.
- The homepage supports catalog search and validated public media URLs. Direct URL requests are restricted to an explicit platform-host allowlist; do not widen it without considering SSRF protections. Never expose the private media volume.
