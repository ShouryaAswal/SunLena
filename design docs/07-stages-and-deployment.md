# 7. Stages and deployment

One major concept per stage. Check current regional pricing before provisioning; do not invent estimates.

**Progress:** The repository now has a local Compose stack and a first media workflow: Apple previews, Firebase-protected yt-dlp/FFmpeg downloads, persistent progress jobs, private files, playlist/player controls, and a bounded audio editor. Search submits the selected advanced field and routes results to Discover from every section. Direct YouTube-link ingestion is excluded from this stage. Stage 2 still needs live runtime validation, parity review, report/moderation and account lifecycle work. See the local-to-Lightsail walkthrough for commands.

## Stage 0 — Requirements/local foundation
**Learn:** requirements, repo boundaries, contracts, design tokens. Inspect SunLeo and make parity matrix; build React shell, FastAPI skeleton/health, typed client, config validation. **Done:** shell works against stub API; no production secrets. **Cloud:** $0.

## Stage 1 — Docker Compose
**Learn:** images, networks, volumes, health. Add web/API/worker images, PostgreSQL, migrations, non-root users, `.dockerignore`, fake providers. **Done:** one command starts; data survives container recreation; components rebuild independently. **Cloud:** $0.

## Stage 2 — Local MVP
**Learn:** auth, schema, adapters, async jobs, UX states. Google sign-in is verified server-side; the web now exposes Apple preview samples, playlist selection on save, music playback, durable media jobs, recent downloads/progress, and an editor using pydub/FFmpeg. The yt-dlp worker uses a one-result title/artist search, one job at a time, 30-minute/150MB per-file limits, two active jobs per user, and 500MB stored per user. **Remaining:** run migrations/builds under Docker, verify real playback/Google auth/download handling, add cancellation/report/account deletion, and rehearse restoring both DB and media. **Done:** progress survives API restart; cross-user file reads are denied; playlist queue plays own completed file or catalog preview. Provider quotas and VM/media storage may cost.

## Stage 3 — Single Lightsail VM
**Learn:** Linux, DNS, firewall, SSH, Compose operations, TLS, backup/rollback. Deploy reverse proxy, React, FastAPI, PostgreSQL, worker on one VM; static IP; Name.com A record; Caddy/Let's Encrypt or paid Lightsail LB.

**Code/ops:** production config, secure headers/CORS, health/restart, pinned images, migration-on-release, DB backup/restore, disk caps/cleanup, request limits, structured logs, deploy/rollback scripts. Host secrets restricted and uncommitted; move to managed secrets later.

**Scaffold provided:** `compose.lightsail.yaml` runs PostgreSQL, API, one separate yt-dlp/FFmpeg worker, production web container, and Caddy. Postgres, private media files, and Caddy state use named volumes. The API/worker share a 500MB per-user media quota by policy; verify free disk and monitoring on the chosen plan. `env.lightsail.example` lists required values. Off-host database/media backups, alert setup, and restore rehearsal remain operator tasks before inviting real users.

**Done:** HTTPS hostname, intended ports only, reboot recovery, persistent DB/media, backup/restore test, repeatable deploy/rollback, billing and disk alerts. **Limits:** single failure domain; no HA/autoscale. Keep worker concurrency at one. 1 GiB VMs may run out of RAM/disk with DB/app/media; choose from measured usage. Swap is a cushion, not more RAM. Cost includes current plan, storage/snapshot/transfer and domain renewal; never assume free-tier.

## Stage 4 — S3/CloudFront frontend (optional)
**Learn:** object storage, CDN/cache, CORS/invalidation. Private S3 + CloudFront OAC; API stays Lightsail. **Changes:** API base/path, SPA fallback, cache headers, CI upload/invalidation, origins/auth/CORS. **Done:** private origin, HTTPS, auth works, versions compatible. Adds request/transfer costs; optional for ~100 users.

## Stage 5 — Durable jobs
**Learn:** queues, at-least-once, idempotency, DLQ, object storage. Replace the current Postgres-polling worker queue and VM volume with SQS, durable job state and private S3 outputs/short-lived URLs. **Changes:** queue interface, leases, retry classes, cancellation, S3 lifecycle/cleanup, signed media playback and limits. **Done:** worker can scale without shared local disk, restart/duplicates are safe, failures go to DLQ, expiry cleans, costs visible. Transfer may dominate.

## Stage 6 — Split hosting
**Learn:** independent deployment/scaling, ECR, IAM, health. Options: separate Lightsail, ECS/EC2, Fargate; choose from evidence/budget. **Changes:** stateless API, shared durable DB/queue/media, scoped IAM/config, graceful shutdown and compatible releases. **Done:** API restart does not lose jobs; worker scales by queue; no host-local dependency.

## Stage 7 — IaC/hardening
**Learn:** reproducible infrastructure, CI/CD, least privilege, SLOs, recovery. Terraform/CDK, GitHub OIDC, ECR, CloudWatch, secrets, managed DB if justified, restore drills, runbooks, security/patch cadence, privacy/moderation. WAF only with rationale. **Done:** recreate environment; audited rollback; tested recovery; monthly cost review.

## Lambda and learning checkpoint
Lambda is not the initial host and is a poor default for variable media conversion due to runtime/ephemeral constraints. Short cleanup/notification jobs may fit after checking current limits/cost. SQS-driven container worker fits media better. At each stage write an ADR (problem, alternatives, cost/ops, rollback, evidence to change) and record CPU/memory, job duration, provider errors, disk, users and bill.
