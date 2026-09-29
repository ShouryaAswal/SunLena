# 8. EC2, VPC, security group, and Name.com runbook

This is the recommended first AWS deployment: one EC2 host running the existing production Compose stack. It is intentionally a single failure domain to control complexity and cost. AWS prices and console labels change; check current account credits and regional pricing before clicking **Launch**.

## First check: will the instance actually use Free Tier credits?

AWS's newer Free Tier program applies to accounts created on or after July 15, 2025. In that cohort AWS currently lists `m7i-flex.large` as an eligible type, with up to $100 signup credits and the possibility of earning up to $100 additional credits. The free plan runs for at most six months or until credits run out. Older accounts follow the earlier program; the EC2 eligible list there is `t2.micro`/`t3.micro`, not `m7i-flex.large`. Even on a qualifying account, check AWS Billing → Free Tier/Credits and the selected AMI/region. Eligibility means credits/plan treatment, not an indefinitely free server. [AWS EC2 Free Tier rules](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html) · [AWS Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/)

`m7i-flex.large` has 2 x86-64 vCPUs and 8 GiB RAM, which is a reasonable initial size for this app and around 100 occasional users if downloads/conversion remain one-at-a-time. It is not a capacity guarantee: the family is EBS-only and Flex targets 40% baseline per vCPU while allowing higher performance for most periods. Watch CPU, memory, queue age and disk during real use. [M7i specifications](https://aws.amazon.com/ec2/instance-types/m7i/)

A current public price-list index gives an indicative Mumbai Linux on-demand rate of about `$0.1008/hour` for `m7i-flex.large`, or about `$73.55` for 730 running hours/month, before EBS, IPv4, data transfer, snapshots, tax or domain renewal. Treat that only as a planning estimate and verify the official AWS Pricing Calculator immediately before launch. At that run rate, $100 in credits covers roughly 1.36 instance-months alone, not the full six-month window; any other AWS use spends from the same pool. EC2 is a better hands-on VPC/IAM learning path and may be temporarily covered by credits, but it is not inherently cheaper than a $24 Lightsail bundle after credits. [Indicative Mumbai list-price index](https://cloudparity.io/pricing/aws/m7i-flex.large?os=linux&price_model=ondemand&region=ap-south-1).

Budget the full setup: EC2 runtime, EBS root disk, public IPv4, outbound data, snapshots/backups, logs, Firebase quotas and domain renewal. A public IPv4 currently lists at $0.005/address-hour (about $3.65 for 730 hours before taxes/credits); this applies to an in-use address too. EBS is billed per provisioned GB-month; AWS lists up to 30 GB EBS storage in Free Tier terms, but check which account program and credits apply. Use the [AWS Pricing Calculator](https://calculator.aws/) for `ap-south-1` and set a budget alert; alerts warn but do not stop charges. [Public IPv4 pricing](https://aws.amazon.com/vpc/pricing/) · [EBS pricing](https://aws.amazon.com/ebs/pricing/)

If the acceptable spend is literally ₹0, do not launch a public always-on instance until the account console confirms the credit coverage and you accept the expiry/overage behavior.

## Target network layout

For learning, create a small custom VPC (rather than relying on an opaque default VPC) while keeping the network single-subnet and inexpensive:

```text
Internet
   │ TCP 80/443 (HTTPS site) · TCP 443 outbound (updates/SSM/providers)
Internet Gateway
   │ route 0.0.0.0/0
Public subnet 10.20.1.0/24 (one selected Mumbai AZ)
   │
EC2 m7i-flex.large + encrypted gp3 EBS + public IPv4 / optional Elastic IP
   └── Docker Compose private bridge network
       ├── Caddy :80/:443 (only public container ports)
       ├── React web
       ├── FastAPI API
       ├── PostgreSQL (no host port)
       └── one yt-dlp/FFmpeg worker + private media volume
```

Create VPC `10.20.0.0/16`, one public subnet `10.20.1.0/24` in any single Mumbai AZ, an Internet Gateway attached to the VPC, and a route table associated with the subnet containing local VPC routing and `0.0.0.0/0 → Internet Gateway`. Assign a public IPv4 to the instance. No NAT Gateway, ALB, RDS, Redis, S3, ECS, or CloudFront for Stage 3; these add cost and are not needed for one Compose host. AWS internet-gateway routing and public-subnet behavior are documented [here](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Internet_Gateway.html).

Leave the default network ACL in place initially. Security groups are the instance firewall; they are stateful. Do not edit NACLs until you have a specific network requirement and understand return traffic/ephemeral ports.

## Security group

Create a security group associated with this VPC and attach it to the EC2 instance:

| Direction | Protocol/port | Source/destination | Purpose |
|---|---|---|---|
| Inbound | TCP 80 | `0.0.0.0/0` | HTTP redirect / ACME validation |
| Inbound | TCP 443 | `0.0.0.0/0` | HTTPS site |
| Inbound | UDP 443 | `0.0.0.0/0` | Optional HTTP/3 (Caddy publishes this) |
| Inbound | TCP 22 | **No rule** | Prefer SSM Session Manager |
| Outbound | Default all | `0.0.0.0/0` | OS/Docker updates, providers, DNS, Firebase and Let's Encrypt |

Do not create inbound rules for 5173, 8000, 5432, 6379, worker, or Docker remote API. Only Caddy publishes host ports. If SSM cannot be made available and you temporarily use SSH, add TCP 22 from your current public IP as a `/32`, use a key pair, and remove the rule when done. Never use `0.0.0.0/0` for SSH.

For SSM, attach an EC2 instance profile/role with AWS managed policy `AmazonSSMManagedInstanceCore`; keep the SSM Agent installed/running and allow outbound HTTPS 443 to Systems Manager endpoints. Session Manager provides shell access with no open inbound management port or SSH key. [Session Manager overview](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)

## EC2 launch choices

1. In EC2, select **Launch instance** in Mumbai (`ap-south-1`). Choose an x86_64 Amazon Linux 2023 or Ubuntu LTS AMI marked eligible for your account. Avoid Marketplace images with a software charge.
2. Select `m7i-flex.large` only after the billing eligibility check above. It is x86-64, 2 vCPU, 8 GiB RAM. Keep worker concurrency at one; do image builds locally or use swap only as emergency headroom, not as a substitute for RAM.
3. Choose the custom VPC, the one public subnet and the security group above. Enable auto-assign public IPv4.
4. Attach the SSM instance profile. Create/download a key pair only if you need the restricted SSH fallback.
5. Configure encrypted gp3 root EBS (start around 30 GB; media files share this host disk through a Docker volume, so size based on retention and monitor it). No extra IOPS/throughput provisioning is expected initially. Set instance termination protection only if you want that additional guardrail.
6. Launch and verify EC2 status checks pass. Record the instance ID, VPC/subnet/security group, AMI, AZ, EBS size and selected public-IP choice in your deployment notes.

### Stable IP decision

An Elastic IP is the simplest target for a durable Name.com A record, but it is a public IPv4 address and incurs the listed hourly charge. A regular auto-assigned public IP avoids allocating a static address, but changes after stop/start; every change means updating Name.com DNS and waiting for TTL. For a family site expected to stay online, use an Elastic IP if its cost is acceptable; for learning/testing, use the dynamic IP and accept DNS updates. Do not leave an unattached Elastic IP allocated.

## Name.com DNS and Caddy HTTPS

Registrar (Name.com) and DNS hosting can be different. Check the domain's active nameservers; edit records at the provider those nameservers identify. Do not change nameservers merely to add this subdomain. In Name.com DNS, create:

| Field | Value |
|---|---|
| Type | `A` |
| Host | `sunlena` |
| Answer | EC2 Elastic IP (or current auto-assigned public IPv4) |
| TTL | Default; lower temporarily if the panel allows and you expect IP changes |

The full hostname becomes `sunlena.shouryaaswal.dev` only if that domain is in your Name.com account. Leave root-domain and unrelated records alone. Remove conflicting A/AAAA records for this hostname. Check from PowerShell:

```powershell
Resolve-DnsName sunlena.shouryaaswal.dev -Type A
```

The answer must match the EC2 public address. Add that exact hostname in Firebase Authentication → Authorized domains. Set `SUNLENA_HOST` to the same name. Once DNS resolves and inbound 80/443 work, Caddy in the production Compose file obtains and renews Let's Encrypt HTTPS automatically. Only Caddy should publish 80/443; EC2 must be reachable on both during certificate issuance.

## Compose deployment on the host

Use the production stack already in the repo; Compose networking keeps API, DB and worker private. The production name is now provider-neutral EC2:

```bash
cp env.ec2.example .env
mkdir -p .secrets && chmod 700 .secrets
# Fill .env with domain, Firebase settings, new DB password, and media signing secret.
# Copy the matching Firebase Admin JSON into .secrets/firebase-admin.json; chmod 600 both secret files.
sudo docker compose -f compose.ec2.yaml config --quiet
sudo docker compose -f compose.ec2.yaml up -d --build
sudo docker compose -f compose.ec2.yaml ps
sudo docker compose -f compose.ec2.yaml logs --tail 100 api worker caddy
```

Never print a resolved Compose config in a shared terminal; it may reveal environment values. Keep `.env` and the Admin JSON out of Git and images. The Compose volumes persist Postgres, private audio and Caddy state across container replacement, but remain tied to this host/disk. Back up the DB off-host; decide whether the audio needs a separate backup. `docker compose down -v` deletes named volumes and is not a routine deploy command.

## Validate before inviting users

Check `https://sunlena.shouryaaswal.dev/health/live` and `/health/ready`; sign in; search/preview; save into a playlist; download one permitted track; play/edit/export it; verify a different user cannot read its file; restart containers and reboot once; confirm data survives; perform a database restore drill; check disk, memory, CPU, logs, billing and that only 80/443 are publicly reachable. Document the rollback image/tag and secrets recovery path.

## Future CloudFront (not part of initial bill/architecture)

When measured traffic or a learning milestone justifies it: move only static frontend assets to a private S3 bucket, serve through CloudFront with Origin Access Control, use an ACM certificate in `us-east-1`, and configure API/cache/CORS behavior carefully. Keep EC2 as API origin initially. This adds billable resources and does not make the single EC2 backend highly available. See [CloudFront S3/OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesOrigin.html) and [custom domain requirements](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cnames-and-https-requirements.html).

## Stop and cost review

First back up/export data and record DNS. Stop the instance when unused, understanding attached EBS and allocated public IPv4 can continue to incur charges. To end charges, delete/release each separately billable resource only after preserving data: EC2 instance, EBS volumes, snapshots, Elastic IP, load balancers, NAT gateways, buckets/objects, databases, queues and distributions. Verify Billing/Cost Explorer afterward. Billing alerts are not hard caps.

## References

- [AWS EC2 Free Tier usage and eligible instance types](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html)
- [AWS M7i/M7i-flex specifications](https://aws.amazon.com/ec2/instance-types/m7i/)
- [AWS VPC Internet Gateway routing](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Internet_Gateway.html)
- [AWS Systems Manager Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)
- [AWS public IPv4 pricing](https://aws.amazon.com/vpc/pricing/)
- [AWS EBS pricing](https://aws.amazon.com/ebs/pricing/)
- [Name.com: add an A record](https://www.name.com/support/articles/115004893508-adding-an-a-record)
- [Name.com: manage DNS records and active nameservers](https://www.name.com/support/articles/206127137-adding-dns-records-and-templates)
