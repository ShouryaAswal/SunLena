# 6. Security and operations

## Security baseline
- Verify token signature, issuer, audience, expiry and subject; use stable provider subject, not email.
- Enforce authorization in backend use cases; test cross-account playlist/job access.
- Bound inputs, review lengths, job duration/output, URL types and rates; parameterize DB queries.
- EC2 security group inbound: TCP 80 and 443 from the internet; no 5173/8000/5432/Redis/worker ports. Prefer SSM Session Manager with an EC2 instance profile granting `AmazonSSMManagedInstanceCore`, so there is no inbound SSH rule. If SSH is a temporary fallback, allow TCP 22 only from the administrator's current public IPv4 `/32`, then remove it. Keep outbound HTTPS/DNS available for OS updates, image pulls, Firebase, providers and certificate renewal.
- Place the host in a public subnet with an Internet Gateway route; do not add a NAT Gateway for this one-host design. The instance needs a public IPv4 for inbound HTTPS and outbound updates. An Elastic IP gives stable Name.com DNS but has a separate hourly public-IPv4 charge; a dynamic address is cheaper operationally but changes after stop/start.
- One EC2 instance, one subnet/AZ and one EBS root/data disk are a single failure domain. Encrypt EBS, use least-privilege IAM, keep PostgreSQL/media in Docker volumes not public buckets, and create an off-host backup plan before inviting users.
- Non-root containers, pinned deps/images, patch cadence, no Docker socket.
- Secrets never in Git/images/build args/frontend/logs/shell history; rotate exposure.
- Restrictive CORS (not auth), CSP/HSTS/frame/content-type headers; CSRF controls for cookie sessions.
- High-entropy share links, hashed when revocation/privacy matter; never sequential secret IDs.
- Provider keys server-side; restrict browser keys by origin where possible.

## Worker isolation (highest risk)
Separate non-root worker container with no Docker socket or Firebase Admin credential; only the DB and private media volume are mounted. The browser supplies a catalog track ID, not a URL; yt-dlp receives a constructed YouTube search query. Direct URL fetching is excluded: arbitrary URLs create SSRF and rights/terms risks. Cap each result at 30 minutes/150 MB, two active jobs per owner, one worker concurrency, and 500 MB stored media per owner. Editor inputs cap at 50 MB and every transform/format/bitrate is bounded. File endpoints verify the Firebase owner against the job row, sanitize filenames and ensure the resolved path remains below the media root. Native player streams use one-hour HMAC-signed capabilities scoped to a job; protect the shared signing key and rotate it deliberately. Keep the output volume private; add OS/container memory and CPU limits before increasing concurrency.

## Privacy/family-safe operation
Collect only needed data; no selling/sharing usage data. Playlists private by default with disclosed/revocable public links. Explain provider data received. Provide deletion/export and backup-retention explanation. Avoid logs with email/tokens/full URLs/review text. Provide reporting and designate a reviewer before inviting users. No analytics before privacy/consent decision.

## One-host observability
Structured logs: time/severity/service/request ID/route template/duration/status/safe error. Separate liveness/readiness. Track search/provider latency/errors, auth failures, job outcomes/age, disk and DB health. Rotate logs. Alert/check for disk and bill; budget alerts notify, not cap. Write steps for outage, leaked credential, full disk, failed backup and abuse report.

## Backup/recovery and release
Automate encrypted PostgreSQL backup to separate storage; restrict access, set retention. Decide separately whether the user's media library is backed up; otherwise explain that downloaded files may be lost on VM/disk failure even if job history survives. Monitor the media volume and database. Restore onto a clean host and record recovery time/data loss. Backups cost storage/transfer. Before upgrades, backup DB and retain prior image. Initially deploy tagged images, run migration once, restart, verify flows and retain rollback version; avoid building on tiny VM; never rely only on `latest`. Later CI checks formatting/types/dependencies/security and CD deploys approved releases. Keep migrations rolling-compatible.

## Before inviting real users
HTTPS; no public DB/debug/admin; login/logout/expiry and ownership verified; partial provider errors clear; playlist privacy/revocation works; worker runs non-root with quotas and private files; cross-account media access is denied; restore and rollback rehearsed; privacy/contact/report/deletion processes exist; budget/disk/media-volume alerts configured.
