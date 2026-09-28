# 6. Security and operations

## Security baseline
- Verify token signature, issuer, audience, expiry and subject; use stable provider subject, not email.
- Enforce authorization in backend use cases; test cross-account playlist/job access.
- Bound inputs, review lengths, job duration/output, URL types and rates; parameterize DB queries.
- Public firewall only 80/443; restrict SSH; DB/app ports private.
- Non-root containers, pinned deps/images, patch cadence, no Docker socket.
- Secrets never in Git/images/build args/frontend/logs/shell history; rotate exposure.
- Restrictive CORS (not auth), CSP/HSTS/frame/content-type headers; CSRF controls for cookie sessions.
- High-entropy share links, hashed when revocation/privacy matter; never sequential secret IDs.
- Provider keys server-side; restrict browser keys by origin where possible.

## Worker isolation (highest risk)
Separate non-root container with bounded temp volume; no Docker socket/admin credentials; minimal DB role; CPU/memory/process/disk/time/concurrency caps; safe subprocess arrays; strict redirect/IP validation; block private/loopback/link-local/metadata targets; idempotent retry and cleanup. Do not serve output until ownership/processing checks pass. Lightsail egress controls are less flexible than a VPC design; defer public conversion until secure enough.

## Privacy/family-safe operation
Collect only needed data; no selling/sharing usage data. Playlists private by default with disclosed/revocable public links. Explain provider data received. Provide deletion/export and backup-retention explanation. Avoid logs with email/tokens/full URLs/review text. Provide reporting and designate a reviewer before inviting users. No analytics before privacy/consent decision.

## One-host observability
Structured logs: time/severity/service/request ID/route template/duration/status/safe error. Separate liveness/readiness. Track search/provider latency/errors, auth failures, job outcomes/age, disk and DB health. Rotate logs. Alert/check for disk and bill; budget alerts notify, not cap. Write steps for outage, leaked credential, full disk, failed backup and abuse report.

## Backup/recovery and release
Automate encrypted PostgreSQL backup to separate storage; restrict access, set retention. Keep config but not secrets. Generated media usually need not be backed up. Restore onto a clean DB and record recovery time/data loss. Backups cost storage/transfer. Before upgrades, backup DB and retain prior image. Initially deploy tagged image, run migration once, restart, verify flows and retain rollback version; avoid building on tiny VM; never rely only on `latest`. Later CI checks formatting/types/dependencies/security and CD deploys approved releases. Keep migrations rolling-compatible.

## Before inviting real users
HTTPS; no public DB/debug/admin; login/logout/expiry and ownership verified; partial provider errors clear; playlist privacy/revocation works; conversion disabled or reviewed/isolated/limited/expiring; restore and rollback rehearsed; privacy/acceptable-use/contact/report/deletion processes exist; budget/disk alerts configured.
