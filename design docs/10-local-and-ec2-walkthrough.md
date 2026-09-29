# Run SunLena locally, then deploy it to EC2

This is the beginner-friendly runbook for the code that exists in this repository today. It does not assume the future CloudFront, ECS, or worker-queue architecture.

## What is implemented today

The current app is a Compose stack: a React/Vite web app, one modular FastAPI API, PostgreSQL, and a separate one-at-a-time media worker. Caddy is added only in the EC2 stack and handles public HTTP/HTTPS. Google sign-in uses Firebase in the browser; the API verifies Firebase ID tokens using a Firebase Admin service-account JSON file. PostgreSQL stores playlists, reviews, and durable download-job state; a private named volume stores media files.

This is not yet full SunLeo feature parity. The core yt-dlp/FFmpeg media workflow and pydub/FFmpeg editor are present; Last.fm enrichment, chatbot/recommendation services, and several old provider integrations are not yet wired into SunLena. The legacy environment keys have been retained locally for reference, but copying a key does not implement its old feature. Quick download searches by the selected song's title and artist and uses the first YouTube result; inspect the source title shown in Downloads because a title match is not a guarantee of the exact recording.

## Credential migration already done

SunLeo's root `.env`, `frontend2/.env`, `frontend2/.env.example`, `backend/recommendation_service/.env`, and root `.env.example` were inspected without displaying values. Their environment entries were merged into SunLena's ignored `.env`; SunLeo's `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`, and `FIREBASE_APP_ID` were mapped to the matching `VITE_FIREBASE_*` variables. SunLeo's Firebase Admin JSON was copied to `.secrets/firebase-admin.json` and its project ID matches the web configuration. Both target paths are ignored by Git.

The old values were not validated against live third-party services. A copied value can be revoked, restricted, or expired. Some old entries (for example Spotify, Last.fm, LLM, EmailJS, and Discord settings) are unused in SunLena. The production EC2 `.env` should contain only the keys listed in `env.ec2.example`, plus the new database password; do not transfer every old secret to a public server.

The Firebase web API key is browser configuration and will be visible in the built site; restrict it in Google Cloud if appropriate. The Admin JSON is privileged. Never paste it into chat, commit it, include it in an image, or put it in a browser variable. Since the source file is outside this repository, it was not possible to determine whether that credential existed in earlier SunLeo Git history. If it was ever committed or exposed, revoke it and create a replacement in Firebase/Google Cloud.

## A. Run locally on Windows

### 1. Start Docker and check the tools

Install and start Docker Desktop, then open a new PowerShell window. Docker Desktop includes Docker Engine, CLI, and Compose on Windows. [Docker Desktop / Compose installation](https://docs.docker.com/compose/install/)

```powershell
Set-Location 'C:\Users\shour\Desktop\SunLena\SunLena'
docker --version
docker compose version
docker info
```

`docker info` must connect to the Docker Engine. If it reports a named-pipe permission error, start Docker Desktop, wait until it says the engine is running, and retry. Do not diagnose or remove containers while the engine is unavailable.

### 2. Confirm local-only settings and start the stack

The API and worker images install Python dependencies during the Docker image build from `apps/api/pyproject.toml`. `yt-dlp` has a minimum version and no upper bound, so a fresh dependency install resolves the newest published version satisfying that requirement. Starting an already-built container does not run pip again, and Docker may reuse its cached dependency layer. This is intentional: changing dependencies on every container start makes deployments unpredictable. When you specifically want to refresh yt-dlp and the Python packages, rebuild those images without cache, then start the stack:

```powershell
docker compose build --no-cache api worker
docker compose up -d
```

The first build takes longer because it refreshes the base OS package index, installs FFmpeg, and resolves Python dependencies again. Review dependency changes before deploying them to EC2.

The `.env` and Firebase JSON have already been copied into this checkout. Check their presence without printing their contents:

```powershell
Test-Path .env
Test-Path .secrets\firebase-admin.json
git check-ignore .env .secrets\firebase-admin.json
```

Then build and start the development stack:

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Compose builds the web/API/worker images and starts PostgreSQL. The API container runs database migrations before it starts serving; the worker waits for the API health check. PostgreSQL data and media files use separate named volumes, so normal container replacement preserves both.

Open <http://localhost:5173>. Check the API at <http://localhost:8000/health/live>, readiness at <http://localhost:8000/health/ready>, and interactive API docs at <http://localhost:8000/docs>.

```powershell
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
docker compose logs --tail 100 api web database
```

### 3. Verify Google sign-in

In Firebase Console, use the same project identified in the copied client config:

1. Under Authentication, enable Google as a sign-in provider.
2. In Authentication settings, add `localhost` to Authorized domains if it is absent. Recent Firebase projects may not add it automatically. [Firebase Google sign-in setup](https://firebase.google.com/docs/auth/web/google-signin)
3. Confirm that the Admin service-account JSON belongs to that same project (the migration script compared the project IDs, but did not prove the account remains valid).
4. Sign in from the local site. Try creating a playlist and review, then refresh and confirm the data persists.

Google login creates a Firebase identity; SunLena's API validates the resulting ID token. Firebase is external to AWS, so EC2 does not replace it. Its free usage and quotas depend on Firebase plan and current terms; do not assume every Firebase feature or level of traffic is free.

### 4. Stop and restart safely

```powershell
docker compose stop
docker compose start
```

To stop and remove the containers and project network while preserving Postgres data:

```powershell
docker compose down
```

Only when you explicitly want to erase the local database too, use `docker compose down -v`. This deletes playlist/review records stored in the local volume. It is not a routine update command.

## B. What to do with the existing frontend-only container

You do **not** need to manually delete a Docker image to switch to this code. `docker compose up --build` builds the images for this repository and creates/recreates its `web`, `api`, and `database` services. Images can remain on disk; old unreferenced images do not serve traffic on their own.

First identify what owns port 5173 after Docker Desktop is running:

```powershell
docker ps -a --filter 'publish=5173' --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker compose ls
```

Then choose based on the result:

- **It is the old SunLeo Compose project:** in another PowerShell window, change to the old SunLeo folder and run `docker compose ps` to confirm. If you are ready to stop the old site, run `docker compose down` from that old folder. This removes that Compose project's containers and network, but not its named volumes. Do not add `-v` if there may be data you want to keep.
- **It is an individually started container:** use its exact name from `docker ps`; inspect it with `docker inspect <name>` before stopping it. If it is definitely the old frontend and you no longer need it, stop it with `docker stop <name>`. Removal with `docker rm <name>` is optional and affects only that named container.
- **It is already the SunLena `web` service:** do not stop it separately; run `docker compose up -d --build` from SunLena to update this stack.

If port 5173 is occupied by the old site, the new web service cannot bind it. Stop the confirmed old frontend, then start SunLena. Keep the old project/volume until you have verified whether it contains anything you need. Do not use `docker system prune`, `docker volume prune`, or `docker compose down -v` as a shortcut.

## C. Deploy the current app to one EC2 VM

This is one EC2 Ubuntu server running all containers. Before creating resources, read the [EC2/VPC/Name.com runbook](08-ec2-domain-runbook.md): `m7i-flex.large` is Free Tier eligible only for certain account cohorts, credits expire, and public IPv4/EBS/data transfer can add charges. AWS billing alerts warn you but do not cap spending.

### 1. Prepare the project and production settings

Before connecting the server, make sure the current SunLena code is in a Git remote you can clone from EC2. Do not commit `.env` or `.secrets`. The production stack is `compose.ec2.yaml`, not the local `compose.yaml`.

Have these ready:

- A Firebase project with Google provider enabled and the matching Admin JSON.
- The chosen full hostname, for example `sunlena.shouryaaswal.dev` (only if that domain is in your Name.com account).
- A strong, unique PostgreSQL password. Generate one on a trusted machine with `openssl rand -base64 32 | tr '+/' '-_' | tr -d '='`; store it in a password manager.
- A playback-link signing key: `openssl rand -hex 32`. Keep it in the server's ignored `.env`; API instances must share this secret.
- A backup plan for the database. A Docker volume survives container rebuilds, but not loss of the VM/disk.

### 2. Create the EC2 network and instance

Follow the exact subnet, route table, Internet Gateway, security-group, and SSM checklist in [the EC2 runbook](08-ec2-domain-runbook.md). In brief, create one custom VPC (`10.20.0.0/16`), one public subnet (`10.20.1.0/24`) in one Mumbai AZ, attach an Internet Gateway, and route `0.0.0.0/0` to it. Do not create a NAT Gateway. Use the default network ACL and one security group.

In EC2 Launch Instance:

1. Region: Mumbai (`ap-south-1`). AMI: Ubuntu Server LTS x86_64 with no Marketplace software charge. Check the console's Free Tier/credit indication for your account.
2. Instance type: `m7i-flex.large` only after checking eligibility and estimating the full bill. It has 2 vCPU and 8 GiB RAM. Keep the media worker concurrency at one and build Docker images locally where practical.
3. Network settings: choose the custom VPC/subnet and the security group from the runbook. Assign a public IPv4. Attach an instance profile with `AmazonSSMManagedInstanceCore`; do not add inbound SSH. If using SSH as a fallback, restrict TCP 22 to your current public IP `/32` and remove the rule after use.
4. Storage: encrypted gp3 root EBS, start around 30 GB. Database, media and Caddy volumes all live on this disk; monitor disk and plan off-host backups. Storage remains billable when an EC2 instance is stopped.
5. Launch and wait for both EC2 status checks to pass. Prefer Systems Manager → Session Manager to open a shell. If SSM is not online, check the instance role, SSM Agent, and outbound HTTPS 443 before falling back to SSH.

For a stable Name.com A record, allocate and associate an Elastic IP, understanding the public IPv4 hourly charge. Otherwise use the auto-assigned IP and update DNS whenever it changes after stop/start. The detailed tradeoffs and setup are in the runbook.
### 3. Install Docker Engine and Compose on Ubuntu

Run on the EC2 server. These commands configure Docker's official Ubuntu package repository and install Engine, Buildx, and the Compose plugin. [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/) [Docker Compose plugin](https://docs.docker.com/compose/install/linux/)

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo \"$VERSION_CODENAME\")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc" | sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
```

Use `sudo docker ...` in this guide. Adding a user to the `docker` group effectively grants root-equivalent control; avoid that convenience change until you understand the implication.

### 4. Clone the code and transfer only required secrets

On the instance:

```bash
sudo mkdir -p /opt/sunlena
sudo chown "$USER":"$USER" /opt/sunlena
git clone <YOUR_GIT_REMOTE> /opt/sunlena
cd /opt/sunlena
cp env.ec2.example .env
mkdir -p .secrets
chmod 700 .secrets
```

Edit the production file using `nano .env`. Set `SUNLENA_HOST`, all five Firebase settings (`FIREBASE_PROJECT_ID` plus the four `VITE_FIREBASE_*` keys), a newly generated `POSTGRES_PASSWORD`, and `SUNLENA_MEDIA_SIGNING_SECRET`. Use no surrounding `<` or `>` placeholders. Keep the Firebase project IDs identical. This production file is separate from the local `.env` and should have only the production variables shown in `env.ec2.example`.

For a short secret-file transfer, temporarily add the security-group SSH rule from your current IPv4 `/32` as described in the runbook, and use an EC2 key pair. Replace `<EC2_PUBLIC_IP>` with the current EC2 public address (Elastic IP if associated). Close TCP 22 again after the copy:

```powershell
scp .secrets\firebase-admin.json ubuntu@<EC2_PUBLIC_IP>:/opt/sunlena/.secrets/firebase-admin.json
```

Back on the instance:

```bash
chmod 600 .env .secrets/firebase-admin.json
sudo docker compose -f compose.ec2.yaml config --quiet
```

If the config check reports a missing variable or secret path, fix that before starting. Do not run plain `docker compose config` in a shared terminal: rendered Compose configuration may include resolved environment values.

### 5. Point Name.com DNS at the EC2 public IP

In Name.com, open **My Domains → `shouryaaswal.dev` → DNS Records**. DNS editing through Name.com requires the domain to use Name.com's nameservers; if the DNS page says nameservers are elsewhere, make changes at the active DNS provider instead. Add an A record:

| Name.com field | Value |
|---|---|
| Type | `A` |
| Host | `sunlena` |
| Answer | EC2 Elastic IP (stable; billable) or current auto-assigned public IPv4 |
| TTL | Default (or a short value while first configuring) |

The result is `sunlena.shouryaaswal.dev`. Leave unrelated root-domain records alone. [Name.com: add an A record](https://www.name.com/support/articles/115004893508-adding-an-a-record) [Name.com: adding DNS records](https://www.name.com/support/articles/206127137-adding-dns-records-and-templates)

From PowerShell, query the record and confirm that it resolves to the EC2 public IPv4:

```powershell
Resolve-DnsName sunlena.shouryaaswal.dev -Type A
```

Wait and retry if DNS has not propagated. Confirm the hostname in `.env` is the exact same name. Caddy can only request its HTTPS certificate after the public hostname resolves to this server and inbound ports 80/443 reach it.

### 6. Enable production Google sign-in and start the site

In Firebase Console, enable Google sign-in and add `sunlena.shouryaaswal.dev` under Authentication → Settings → Authorized domains. Firebase documents the provider and authorized-domain setup [here](https://firebase.google.com/docs/auth/web/google-signin). Keep the Firebase project ID aligned with the copied Admin JSON and the web config.

On EC2:

```bash
cd /opt/sunlena
sudo docker compose -f compose.ec2.yaml up -d --build
sudo docker compose -f compose.ec2.yaml ps
sudo docker compose -f compose.ec2.yaml logs --tail 100 api caddy
```

Caddy serves the built web app, proxies `/api/*` internally to FastAPI, and obtains/renews TLS certificates. Only Caddy publishes host ports. The API and PostgreSQL are reachable only on the private Compose network. Wait for Caddy to finish certificate issuance, then browse to `https://sunlena.shouryaaswal.dev`.

Verify:

```bash
curl -fsS https://sunlena.shouryaaswal.dev/health/live
curl -fsS https://sunlena.shouryaaswal.dev/health/ready
sudo docker compose -f compose.ec2.yaml ps
```

Use the site to sign in, search, create a playlist, create a review, and refresh. Rebooting/recreating containers should preserve Postgres records because the Compose database uses a named volume. Also verify the HTTP URL redirects to HTTPS and browser login returns to the correct hostname.

### 7. Updating the deployed version

Back up the database first if users have data. Then, on the VM:

```bash
cd /opt/sunlena
git pull --ff-only
sudo docker compose -f compose.ec2.yaml up -d --build
sudo docker compose -f compose.ec2.yaml ps
sudo docker compose -f compose.ec2.yaml logs --tail 100 api caddy
```

This rebuilds/replaces containers whose definitions or images changed. It keeps the named database and Caddy volumes. It does not require deleting old images manually. Never add `down -v` during a routine release; that would remove persistent named volumes and can destroy the database and certificate state.

## Common failure checks

| Symptom | First checks |
|---|---|
| Browser cannot load site | EC2 TCP 80/443 firewall, A record/public IP, `docker compose ... ps`, Caddy logs |
| Caddy has no certificate | DNS points to the current EC2 public IPv4; hostname matches exactly; inbound 80/443 open; check Caddy logs |
| API container exits | API logs, Firebase project ID, valid JSON secret file and file path, Postgres health, migration error |
| Google sign-in fails | Google provider enabled; domain authorized in Firebase; Vite Firebase values match project; rebuild web after changing build-time Vite config |
| Local site cannot bind port 5173 | Identify the current port owner using `docker ps -a`; stop only the confirmed old frontend container/project |
| Site works but saved data vanishes | Confirm the database uses the named volume; check you did not use `down -v` or create a different Compose project name |

## Cost and safety reminders

The goal can be a very low-cost setup, but a public EC2 deployment is not guaranteed to cost zero. The server plan, storage, traffic, snapshots/backups, domain renewal, and Firebase usage can have charges. Check the current AWS pricing page for the selected region and your account before provisioning. Start with one instance and no CloudFront/load balancer; add services only when measured need or a learning milestone justifies the extra cost and operations.

This one-machine setup is a single point of failure. It is not a backup. Schedule database backups, test restoring one, update Ubuntu/Docker, watch disk space/log growth, restrict SSH, and keep private credentials out of Git and images. Avoid storing downloaded media on the VM until retention, licensing, abuse limits, and disk cleanup are designed.
