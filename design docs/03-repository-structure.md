# 3. Repository structure

Start small; add layers only when they hold real responsibilities.

```text
sunlena/
├── design docs/
├── apps/
│   ├── web/                           # React + TypeScript + Vite
│   │   └── src/{app,pages,features,components,lib,styles}
│   └── api/                           # FastAPI modular monolith
│       ├── app/main.py
│       ├── app/core/                  # settings, logging, errors, security
│       ├── app/db/                    # engine/session/migration integration
│       ├── app/modules/{identity,catalog,search,playlists,discovery,reviews,media,admin}/
│       ├── app/shared/                # cross-cutting primitives only
│       ├── migrations/                # Alembic revisions
│       ├── tests/
│       ├── Dockerfile
│       └── pyproject.toml
├── packages/api-client/               # optional generated typed client
├── infra/{compose,lightsail,terraform}/
├── ops/{caddy,scripts,runbooks}/
├── .github/workflows/                 # CI/CD after releases are repeatable
├── compose.yaml, compose.lightsail.yaml, .env.example, env.lightsail.example
├── .dockerignore, .gitignore
├── README.md
└── SECURITY.md
```

Frontend feature folders own search, playlists, auth, media jobs, audio player/editor, reviews and discovery. `components/ui` has reusable primitives; `components/music` has track/artwork/player parts. Keep remote state in a query/cache layer and API calls in one client; avoid generic `utils.ts` and rules embedded in JSX. The always-available player uses iTunes preview samples or owner-authorized local downloads; playlist queues prefer a completed private download over the short preview.

Backend modules may use `router.py`, `schemas.py`, `service.py`, `models.py`, `repository.py` and tests where each layer has a real job. `media/` owns persistent job records, authenticated file/editor routes, the yt-dlp/FFmpeg pipeline, pydub transforms and a separately invokable DB-polling worker module. Router maps HTTP; service holds use cases/permissions; repository owns queries. Worker does not import FastAPI routers.

Container rules: one Dockerfile per deployable process (share a base later), multi-stage frontend, non-root production user, `.dockerignore` excludes secrets/env/credentials/media/build caches/dependencies, Compose owns local wiring/health, production injects secrets. `.env.example` contains placeholders only. Persist DB/media; containers/code are replaceable. Include migration and backup/restore scripts. Use opaque public IDs; provider DTOs remain within adapters. Never commit secrets, DB files, user media or generated output.
