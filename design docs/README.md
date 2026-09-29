# SunLena design docs

This folder is the product, architecture, and deployment blueprint for rebuilding SunLeo as SunLena. Implementation status is recorded below; these plans distinguish the current single-host setup from future scaling stages.

## Read in this order

1. [Product and scope](01-product-and-scope.md)
2. [Architecture and decisions](02-architecture-and-decisions.md)
3. [Repository structure](03-repository-structure.md)
4. [Frontend experience](04-frontend-experience.md)
5. [Data, APIs, and integrations](05-data-apis-and-integrations.md)
6. [Security and operations](06-security-and-operations.md)
7. [Stages and deployment](07-stages-and-deployment.md)
8. [EC2 VPC, security group, and Name.com runbook](08-ec2-domain-runbook.md)
9. [Decision log](09-decision-log.md)
10. [Run locally and deploy to EC2](10-local-and-ec2-walkthrough.md)

The referenced SunLeo work and source repository informed this rebuild: React, FastAPI, Firebase auth/playlists, iTunes/Last.fm/YouTube metadata and thumbnails, and an in-memory conversion workflow. SunLena keeps clear backend module boundaries while deploying as one API plus a separate media worker on one EC2 host for the first AWS release. Lightsail is no longer the recommended first host because its fixed bundles do not match the user's price expectation.

Start with a modular monolith plus a separate worker process, not deployed microservices. This keeps clear domain boundaries without multiplying deployment, networking, security and monitoring work for a small learning project and roughly 100 known users.

## Implemented foundation

The repository now includes Apple catalog search/previews, Firebase token verification, PostgreSQL migrations, private playlists with unlisted share links, reviews, editorial mood discovery, persistent yt-dlp/FFmpeg download jobs, a private media volume, playlist-aware audio playback, and an audio editor. Google sign-in requires local Firebase web settings plus an Admin service-account file described in the root README. This is an early working foundation, not yet complete SunLeo feature parity; inspect the original SunLeo repo before declaring parity.

SunLeo's local environment values have been copied into the ignored SunLena `.env`, with its Firebase client names mapped to SunLena's Vite variables. The Firebase Admin JSON is in ignored `.secrets/firebase-admin.json`. Legacy provider keys are preserved locally, but they are not automatically wired into SunLena or required by the EC2 deployment.

Zero operating cost cannot be promised. `m7i-flex.large` is listed as Free Tier eligible only for accounts created on/after July 15, 2025 under AWS's newer credit program; eligibility lasts at most six months or until credits run out. Earlier accounts have different instance eligibility. Confirm account creation date, plan, credits, region/AMI eligibility and estimated monthly bill before provisioning. Public IPv4, EBS, data transfer, snapshots, and other resources can cost extra; alerts do not cap spend. The EC2 plan uses one public instance and deliberately avoids NAT gateways, load balancers, RDS and CloudFront at first. A current indexed Mumbai on-demand estimate is about $73.55/month for 730 compute hours alone, so $100 credit would cover around 1.36 months of compute; validate before provisioning. See [AWS Free Tier rules](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html), [AWS Pricing Calculator](https://calculator.aws/), [indicative regional price index](https://cloudparity.io/pricing/aws/m7i-flex.large?os=linux&price_model=ondemand&region=ap-south-1), and [public IPv4 pricing](https://aws.amazon.com/vpc/pricing/). YouTube media has provider terms and copyright implications; technical capability is not permission. Use the media workflow only for content you are authorized to download, keep the worker private, and provide an easy way to delete stored files.
