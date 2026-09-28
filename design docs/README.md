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
8. [Lightsail and Name.com runbook](08-lightsail-domain-runbook.md)
9. [Decision log](09-decision-log.md)
10. [Run locally and deploy to Lightsail](10-local-and-lightsail-walkthrough.md)

The referenced SunLeo conversations describe React, several FastAPI services, Firebase auth/playlists, iTunes/Last.fm/YouTube metadata and thumbnails, and an in-memory conversion workflow. Treat this as historical context only; the old repository was not inspected here. Inspect it and create a feature parity matrix before deciding what to carry forward.

Start with a modular monolith plus a separate worker process, not deployed microservices. This keeps clear domain boundaries without multiplying deployment, networking, security and monitoring work for a small learning project and roughly 100 known users.

## Implemented foundation

The repository now includes Apple catalog search, Firebase token verification, PostgreSQL migrations, private playlists with unlisted share links, ratings/reviews, editorial mood discovery, and a responsive frontend that calls those APIs. Google sign-in requires local Firebase web settings plus an Admin service-account file described in the root README. This is an early working foundation, not yet a complete SunLeo feature-parity release; inspect the original SunLeo repo before declaring parity.

SunLeo's local environment values have been copied into the ignored SunLena `.env`, with its Firebase client names mapped to SunLena's Vite variables. The Firebase Admin JSON is in ignored `.secrets/firebase-admin.json`. Legacy provider keys are preserved locally, but they are not automatically wired into SunLena or required by the Lightsail deployment.

Zero operating cost cannot be promised for a public AWS deployment. Lightsail, storage, backups, transfer, domains and optional AWS services can be billable. Check current region pricing and account eligibility, set billing alerts (they do not cap spend), and write a teardown checklist before provisioning. Downloading YouTube media has provider terms and copyright implications; technical capability is not permission. Keep conversion disabled until policy, rights, abuse handling and security have been reviewed.
