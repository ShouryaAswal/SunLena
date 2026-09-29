# 8. Lightsail and Name.com runbook

Console labels, DNS controls and pricing change; verify live screens/rates. The referenced SunLeo task mentioned `shouryaaswal.dev`; use `sunlena.shouryaaswal.dev` only if that domain is in your Name.com account.

## DNS basics
Registrar and DNS hosting differ. A maps hostname to IPv4; CNAME maps subdomain to hostname. Attach Lightsail static IPv4 first because the default public IP can change after stop/start. DNS caches take time. If nameservers point elsewhere, manage records there.

## Instance + Caddy recommended
1. Select nearby region and Linux size based on measured memory/disk for API/DB/worker.
2. Attach Lightsail static IPv4.
3. Allow inbound 80/443; restrict SSH 22 to your IP where possible; do not open DB/app ports.
4. Install updates, Docker and Compose. Deploy versioned Compose with private DB/app network, persistent volume, logs/restart policy.
5. In active Name.com DNS add:

| Field | Value |
|---|---|
| Type | A |
| Host/Name | `sunlena` |
| Answer/Value | Lightsail static IPv4 |
| TTL | default or short while configuring |

Result: `sunlena.shouryaaswal.dev`. Do not change nameservers just to add this. PowerShell check:

```powershell
Resolve-DnsName sunlena.shouryaaswal.dev
```

Address should match static IP. If not, check active nameservers, host field, conflicting A/AAAA records and wait for TTL.

6. Configure Caddy hostname, proxy `/api/*` to FastAPI and serve React with SPA fallback. Only proxy binds public ports. Once DNS resolves and ports are open, start Caddy and inspect certificate logs. Confirm HTTP→HTTPS and matching certificate.
7. Add production hostname to Firebase Authorized domains and enable Google sign-in.
8. Verify search and Apple preview, Google auth, playlists, per-track save choice, downloads/progress, source-title match, playback, editing/export, cross-account media privacy, DB/media persistence after restart/reboot, backup restore, closed ports, logs/disk/alerts.

The repo's production Compose command is `docker compose -f compose.lightsail.yaml up -d --build`. Prepare `.env` from `env.lightsail.example` and `.secrets/firebase-admin.json` first. Caddy publishes only 80/443, routes API calls privately to FastAPI, serves the static production frontend, and stores certificate state in persistent volumes. A single non-root worker shares PostgreSQL and the private `media_data` volume with the API. Downloads and Caddy state are separate from the PostgreSQL volume; back up the database and decide whether to back up personal audio too. Keep one worker on a small VM, check free disk, and never mount media into the web container. Use `docker compose -f compose.lightsail.yaml logs -f api worker caddy` to inspect startup and certificate issues.

Caddy/Let's Encrypt is a low-cost single-host TLS option. Lightsail certificates are for Lightsail load balancers, not individual instances. A load balancer offers managed TLS/redirect and later balancing, but adds monthly cost and does not make one backend instance HA.

## Future CloudFront
1. S3 bucket with Block Public Access; upload built frontend.
2. CloudFront uses S3 REST endpoint + OAC; grant that distribution only.
3. Request/validate ACM certificate for hostname in `us-east-1`; attach and add alternate domain.
4. Change Name.com subdomain to CNAME targeting distribution hostname (or supported equivalent).
5. Configure SPA fallback, API origin/path, auth/cookie/header cache policy and exact CORS. Long cache hashed assets, short/revalidate `index.html`.
6. Confirm direct S3 read fails and CloudFront HTTPS works.

CloudFront custom-domain certificate is in `us-east-1`; OAC applies to S3 REST origin, not public website endpoint. Defer for ~100 known users absent evidence.

## Stop-cost checklist
Back up/export data, record DNS, remove DNS only when ready, then stop/delete instances and separately billable snapshots/storage/LBs/buckets/objects/databases/queues/container services/distributions. Some resources bill while app is stopped. Confirm billing console; alerts do not cap spend.

## Current references
- [Attach a Lightsail static IP](https://docs.aws.amazon.com/lightsail/latest/userguide/lightsail-create-static-ip.html)
- [Lightsail networking FAQ](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-networking.html)
- [Lightsail certificates FAQ](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-certificates.html)
- [Name.com: add an A record](https://www.name.com/support/articles/115004893508-adding-an-a-record)
- [Name.com: manage DNS records and active nameservers](https://www.name.com/support/articles/206127137-adding-dns-records-and-templates)
- [CloudFront: S3 origin and OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesOrigin.html)
- [CloudFront: custom domain and HTTPS requirements](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cnames-and-https-requirements.html)
