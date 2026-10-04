# 9. Decision log

| Topic | Initial choice | Alternatives / revisit trigger |
|---|---|---|
| Deployment | Modular monolith + worker | Microservices add ops; split on measured scale/failure/team needs. |
| First host | One EC2 `m7i-flex.large` + Compose in a single-AZ custom VPC | Revisit after measuring workload and account credits. This instance is Free Tier eligible only for certain account cohorts; always estimate EC2, EBS, public IPv4, backup and transfer costs. Not HA. |
| Database | PostgreSQL | SQLite local-only simplicity; DynamoDB for access pattern; RDS when ops burden justifies cost. |
| Login | Firebase Google, backend verifies | Cognito federation for AWS identity learning/reduced Firebase coupling. No casual password implementation. |
| Search | Adapters; test Apple/iTunes first | Last.fm/licensed provider; verify live terms/quotas. |
| Artwork | Source URL + fallback; cache only if allowed | Copy only if license/terms permit. |
| Jobs | DB-backed queue + worker initially | SQS when hosts/retries/reliability warrant; Redis adds ops. |
| Media | Private bounded local volume, short TTL | S3 when separation/recovery requires it. |
| Frontend | Same proxy initially | S3/CloudFront when scale/availability/learning merits. |
| TLS | Caddy on one host with Let's Encrypt | ALB/ACM or CloudFront later, if justified by availability, traffic or learning goals. |
| Discovery | Explainable tags/heuristics | ML only with opt-in data and measurable value. |
| Motion | Purposeful, reduced-motion-aware | Heavy scroll storytelling may hurt usability/performance. |
| IaC | Console-built EC2/VPC first for learning, then Terraform/CDK | Earlier if recreations or frequent changes; document every console choice now. |
| Zero-cost | Minimize/disclose spend | Never claim public AWS is $0; verify price before provisioning. |
| Media extraction | yt-dlp + bgutil PO tokens for YouTube and catalog jobs, even when Cobalt handles other hosts (`SUNLENA_YOUTUBE_EXTRACTOR`) | Cobalt returned empty YouTube tunnels for videos that need video-bound PO tokens (Oct 2026). Revisit if Cobalt gets a session server that fits the no-browser-automation constraint, or if yt-dlp is blocked on the host IP. |

## ADR template
```text
# ADR-NNN: Decision
Date / status:
Context and problem:
Constraints (users, budget, reliability, learning):
Options considered:
Decision:
Tradeoffs and operational burden:
Security/privacy/cost impact:
Rollback:
Evidence that would make us revisit:
```
