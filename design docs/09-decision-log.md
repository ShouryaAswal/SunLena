# 9. Decision log

| Topic | Initial choice | Alternatives / revisit trigger |
|---|---|---|
| Deployment | Modular monolith + worker | Microservices add ops; split on measured scale/failure/team needs. |
| First host | One Lightsail VM + Compose | EC2/Lightsail containers/ECS; compare current regional cost and learning value. Not HA. |
| Database | PostgreSQL | SQLite local-only simplicity; DynamoDB for access pattern; RDS when ops burden justifies cost. |
| Login | Firebase Google, backend verifies | Cognito federation for AWS identity learning/reduced Firebase coupling. No casual password implementation. |
| Search | Adapters; test Apple/iTunes first | Last.fm/licensed provider; verify live terms/quotas. |
| Artwork | Source URL + fallback; cache only if allowed | Copy only if license/terms permit. |
| Jobs | DB-backed queue + worker initially | SQS when hosts/retries/reliability warrant; Redis adds ops. |
| Media | Private bounded local volume, short TTL | S3 when separation/recovery requires it. |
| Frontend | Same proxy initially | S3/CloudFront when scale/availability/learning merits. |
| TLS | Caddy on one host | Paid Lightsail LB managed TLS; CloudFront later. |
| Discovery | Explainable tags/heuristics | ML only with opt-in data and measurable value. |
| Motion | Purposeful, reduced-motion-aware | Heavy scroll storytelling may hurt usability/performance. |
| IaC | Manual Lightsail then Terraform/CDK | Earlier if multiple envs/frequent changes. |
| Zero-cost | Minimize/disclose spend | Never claim public AWS is $0; verify price before provisioning. |

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
