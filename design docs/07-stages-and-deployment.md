# 7. Stages and deployment

One major concept per stage. Check current regional pricing before provisioning; do not invent estimates.

**Progress:** The repository now has a local Compose stack and a first media workflow: Apple previews, Firebase-protected yt-dlp/FFmpeg downloads, persistent progress jobs, private files, playlist/player controls, and a bounded audio editor. Search submits the selected advanced field and routes results to Discover from every section. Stage 2 still needs live runtime validation, parity review, report/moderation and account lifecycle work. See the local-to-EC2 walkthrough for commands.

## Stage 0 — Requirements/local foundation
**Learn:** requirements, repo boundaries, contracts, design tokens. Inspect SunLeo and make parity matrix; build React shell, FastAPI skeleton/health, typed client, config validation. **Done:** shell works against stub API; no production secrets. **Cloud:** $0.

## Stage 1 — Docker Compose
**Learn:** images, networks, volumes, health. Add web/API/worker images, PostgreSQL, migrations, non-root users, `.dockerignore`, fake providers. **Done:** one command starts; data survives container recreation; components rebuild independently. **Cloud:** $0.

## Stage 2 — Local MVP
**Learn:** auth, schema, adapters, async jobs, UX states. Google sign-in is verified server-side; the web now exposes Apple preview samples, playlist selection on save, music playback, durable media jobs, recent downloads/progress, and an editor using pydub/FFmpeg. The yt-dlp worker uses a one-result title/artist search, one job at a time, 30-minute/150MB per-file limits, two active jobs per user, and 500MB stored per user. **Remaining:** run migrations/builds under Docker, verify real playback/Google auth/download handling, add cancellation/report/account deletion, and rehearse restoring both DB and media. **Done:** progress survives API restart; cross-user file reads are denied; playlist queue plays own completed file or catalog preview. Provider quotas and VM/media storage may cost.

## Stage 3 — Single EC2 VM (first AWS target)
**Learn:** VPCs, subnets, Internet Gateways, route tables, security groups, IAM instance profiles, SSM, DNS, Compose operations, TLS, backup/rollback. Deploy reverse proxy, React, FastAPI, PostgreSQL and worker on one `m7i-flex.large` host in `ap-south-1`; Name.com A record to an Elastic IP; Caddy/Let's Encrypt.

**Code/ops:** production config, secure headers/CORS, health/restart, pinned images, migration-on-release, DB backup/restore, disk caps/cleanup, request limits, structured logs, deploy/rollback scripts. Host secrets restricted and uncommitted; move to managed secrets later.

**Scaffold provided:** `compose.ec2.yaml` runs PostgreSQL, API, one separate yt-dlp/FFmpeg worker, production web container, and Caddy. Postgres, private media files, and Caddy state use named volumes. The API/worker share a 500MB per-user media quota by policy; verify free disk and monitoring. `env.ec2.example` lists required values. Off-host database/media backups, alert setup, and restore rehearsal remain operator tasks before inviting real users.

**Done:** HTTPS hostname, intended ports only, reboot recovery, persistent DB/media, backup/restore test, repeatable deploy/rollback, billing and disk alerts. **Capacity:** 2 vCPU/8 GiB is a reasonable starting point for a small private audience with one conversion at a time; it is not HA, autoscaling or sustained full-CPU capacity. Measure RAM/CPU/disk under real conversion before inviting users. **Cost gate:** `m7i-flex.large` Free Tier eligibility depends on account creation date (new program from July 15, 2025), credits last no more than six months or until spent; older accounts have different eligible sizes. Public IPv4, EBS, backups/snapshots and transfer may bill separately. Verify the Billing console and regional estimate first. No zero-cost guarantee.

## Stage 4 — S3/CloudFront frontend (optional)
**Learn:** object storage, CDN/cache, CORS/invalidation. Private S3 + CloudFront OAC; API stays EC2 initially. **Changes:** API base/path, SPA fallback, cache headers, CI upload/invalidation, origins/auth/CORS. **Done:** private origin, HTTPS, auth works, versions compatible. Adds request/transfer costs; optional for ~100 users.

## Stage 5 — Durable jobs
**Learn:** queues, at-least-once, idempotency, DLQ, object storage. Replace the current Postgres-polling worker queue and VM volume with SQS, durable job state and private S3 outputs/short-lived URLs. **Changes:** queue interface, leases, retry classes, cancellation, S3 lifecycle/cleanup, signed media playback and limits. **Done:** worker can scale without shared local disk, restart/duplicates are safe, failures go to DLQ, expiry cleans, costs visible. Transfer may dominate.

## Stage 6 — Split hosting
**Learn:** independent deployment/scaling, ECR, IAM, health. Options: ECS on EC2 or Fargate; choose from evidence/budget. **Changes:** stateless API, shared durable DB/queue/media, scoped IAM/config, graceful shutdown and compatible releases. **Done:** API restart does not lose jobs; worker scales by queue; no host-local dependency.

## Stage 7 — IaC/hardening
**Learn:** reproducible infrastructure, CI/CD, least privilege, SLOs, recovery. Terraform/CDK, GitHub OIDC, ECR, CloudWatch, secrets, managed DB if justified, restore drills, runbooks, security/patch cadence, privacy/moderation. WAF only with rationale. **Done:** recreate environment; audited rollback; tested recovery; monthly cost review.

## Lambda and learning checkpoint
Lambda is not the initial host and is a poor default for variable media conversion due to runtime/ephemeral constraints. Short cleanup/notification jobs may fit after checking current limits/cost. SQS-driven container worker fits media better. At each stage write an ADR (problem, alternatives, cost/ops, rollback, evidence to change) and record CPU/memory, job duration, provider errors, disk, users and bill.
