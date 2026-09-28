# 7. Stages and deployment

One major concept per stage. Check current regional pricing before provisioning; do not invent estimates.

**Progress:** Stage 0 foundation, Stage 1 local Compose definitions, and part of Stage 2 are in the repo: frontend shell/search UI, iTunes search, Firebase token verification, PostgreSQL schema, playlists, reviews, and mood discovery. Firebase credentials and a running Docker daemon are required to use the full authenticated local stack. Stage 2 is not complete: report/moderation, account lifecycle, full SunLeo parity, and a reviewed media workflow remain outstanding.

## Stage 0 — Requirements/local foundation
**Learn:** requirements, repo boundaries, contracts, design tokens. Inspect SunLeo and make parity matrix; build React shell, FastAPI skeleton/health, typed client, config validation. **Done:** shell works against stub API; no production secrets. **Cloud:** $0.

## Stage 1 — Docker Compose
**Learn:** images, networks, volumes, health. Add web/API/worker images, PostgreSQL, migrations, non-root users, `.dockerignore`, fake providers. **Done:** one command starts; data survives container recreation; components rebuild independently. **Cloud:** $0.

## Stage 2 — Local MVP
**Learn:** auth, schema, adapters, async jobs, UX states. Add Google login + backend verification, search, playlists, reviews, explainable discovery, bounded job lifecycle, accessible responsive UI. Conversion remains off pending policy/security review. **Done:** core flows; cross-user access denied; provider failures partial; migrations/expiry work. Provider terms/quotas may cost.

## Stage 3 — Single Lightsail VM
**Learn:** Linux, DNS, firewall, SSH, Compose operations, TLS, backup/rollback. Deploy reverse proxy, React, FastAPI, PostgreSQL, worker on one VM; static IP; Name.com A record; Caddy/Let's Encrypt or paid Lightsail LB.

**Code/ops:** production config, secure headers/CORS, health/restart, pinned images, migration-on-release, DB backup/restore, disk caps/cleanup, request limits, structured logs, deploy/rollback scripts. Host secrets restricted and uncommitted; move to managed secrets later.

**Scaffold provided:** `compose.lightsail.yaml` runs PostgreSQL, API, production web container, and Caddy with persistent certificate/config volumes. `env.lightsail.example` lists required values. Database backups, alert setup, and a restore rehearsal remain operator tasks before inviting real users.

**Done:** HTTPS hostname, intended ports only, reboot recovery, persistent DB, restore test, repeatable deploy/rollback, billing alert. **Limits:** single failure domain; no HA/autoscale. Conversion off or concurrency one. 1 GiB VMs may run out of RAM/disk with DB/app/media; choose from measured usage. Swap is a cushion, not more RAM. Cost includes current plan, storage/snapshot/transfer and domain renewal; never assume free-tier.

## Stage 4 — S3/CloudFront frontend (optional)
**Learn:** object storage, CDN/cache, CORS/invalidation. Private S3 + CloudFront OAC; API stays Lightsail. **Changes:** API base/path, SPA fallback, cache headers, CI upload/invalidation, origins/auth/CORS. **Done:** private origin, HTTPS, auth works, versions compatible. Adds request/transfer costs; optional for ~100 users.

## Stage 5 — Durable jobs
**Learn:** queues, at-least-once, idempotency, DLQ, object storage. API intent → SQS → separate worker; DB/DynamoDB state; private S3 output and short URL. **Changes:** queue interface/local adapter, leases, retry classes, cancellation, states, S3/lifecycle/cleanup/limits. **Done:** restart and duplicates safe, failures to DLQ, expiry cleans, costs visible. Transfer may dominate.

## Stage 6 — Split hosting
**Learn:** independent deployment/scaling, ECR, IAM, health. Options: separate Lightsail, ECS/EC2, Fargate; choose from evidence/budget. **Changes:** stateless API, shared durable DB/queue/media, scoped IAM/config, graceful shutdown and compatible releases. **Done:** API restart does not lose jobs; worker scales by queue; no host-local dependency.

## Stage 7 — IaC/hardening
**Learn:** reproducible infrastructure, CI/CD, least privilege, SLOs, recovery. Terraform/CDK, GitHub OIDC, ECR, CloudWatch, secrets, managed DB if justified, restore drills, runbooks, security/patch cadence, privacy/moderation. WAF only with rationale. **Done:** recreate environment; audited rollback; tested recovery; monthly cost review.

## Lambda and learning checkpoint
Lambda is not the initial host and is a poor default for variable media conversion due to runtime/ephemeral constraints. Short cleanup/notification jobs may fit after checking current limits/cost. SQS-driven container worker fits media better. At each stage write an ADR (problem, alternatives, cost/ops, rollback, evidence to change) and record CPU/memory, job duration, provider errors, disk, users and bill.
