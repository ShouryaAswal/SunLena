# 5. Data, APIs, and integrations

## Google sign-in
Google login works with AWS compute: identity is separate from hosting. Initially use Firebase Authentication + Google, consistent with historical SunLeo direction. FastAPI verifies ID tokens server-side (signature, issuer, audience, expiry, subject); browser-decoded claims are untrusted. Store stable provider subject, not email. Keep an adapter for Cognito.

Alternative: Cognito User Pools federate Google and issue Cognito tokens. This reduces Firebase coupling/teaches AWS identity but adds setup. Cognito currently describes free tiers with plan/account conditions; verify live pricing, eligibility and region before relying on it. Neither auth provider makes hosting free. Do not implement passwords in MVP.

OAuth: separate dev/prod clients; exact origins/callbacks; authorized domain; runtime server credential; test linking, expiry, revocation, disabled user, logout and denied API calls.

## Provider adapters
- Apple/iTunes Search: candidate metadata/artwork search based on SunLeo; verify current terms, attribution, limits and caching.
- Apple `previewUrl`: short in-browser preview when one is returned; no full-catalog audio proxying.
- YouTube via yt-dlp: one title + artist `ytsearch1` lookup after an explicit Quick download action. Direct YouTube-link download is not supported. Do not accept arbitrary browser-provided URLs; any future authorized-source import needs an allowlist, rights safeguards and SSRF defenses. Show the actual matched source title in the user's download history.
- Last.fm: optional future enrichment/artwork/tags; legacy API keys remain unused unless an adapter is implemented.
- Discovery begins as transparent tags/curation, not an unsupported personalization claim.

Adapters require timeout, bounded retry/backoff, provider status, normalized DTO, provider-aware cache, rate protection, safe logs and config kill switch. Do not leak provider DTO throughout the app.

## Initial entities (relational)
- `users(id, identity_provider, provider_subject, email, display_name, avatar_url, created_at, updated_at, disabled_at)`; unique provider/subject.
- `tracks(id, title, normalized_title, duration_ms, artwork_url, metadata_json, created_at, updated_at)`; only permitted cached fields.
- `track_sources(id, track_id, provider, provider_track_id, canonical_url, fetched_at)`; unique provider identity.
- `playlists(id, owner_user_id, title, description, visibility, share_token_hash, created_at, updated_at)`.
- `playlist_items(id, playlist_id, track_id, position, added_at)`; deterministic ordering constraints.
- `reviews(id, track_id, author_user_id, rating, body, status, created_at, updated_at)`; unique track/author initially.
- `media_jobs(id, owner_id, track_id, status, stage, progress, output_format, bitrate, title, artist, source_title, file_name, file_path, file_size, error, created_at, started_at, finished_at)`; owner/track foreign keys and progress check. Keep audio files on a private filesystem volume, not in PostgreSQL.
- `reports(id, reporter_user_id, entity_type, entity_id, reason, status, created_at, resolved_at)`.
- `audit_events(id, actor_user_id, action, target_type, target_id, created_at, request_id)` for important admin/security actions.

Use opaque IDs, UTC timestamps and migrations. No media in DB. Minimize metadata and support deletion.

## API outline
All routes `/api/v1`; search public, writes/private data authenticated.

| Method/route | Purpose |
|---|---|
| `GET /health/live`, `/health/ready` | Liveness/readiness; readiness details private |
| `GET /search?q=&limit=&cursor=` | Provider search with partial results |
| `GET /tracks/{id}`, `GET /discover?mode=` | Details and explainable discovery |
| `GET /me`, `GET /me/playlists`, `POST /playlists` | Current user and playlist create/list |
| `GET/PATCH/DELETE /playlists/{id}` | Read/update/delete with owner/public check |
| `POST /playlists/{id}/items`, `PATCH /playlists/{id}/items/order`, `DELETE /playlists/{id}/items/{item_id}` | Manage contents |
| `GET /public/playlists/{token}` | Intentionally shared playlist |
| `PUT/DELETE /tracks/{id}/review`, `POST /reports` | Own review and abuse report |
| `GET /search?q=` | Upsert catalog metadata, including optional `preview_url` |
| `GET /media/jobs` | List only the signed-in user's recent downloads |
| `POST /media/jobs` | Enqueue `{track_id, output_format, bitrate}`; returns durable queued job |
| `GET /media/jobs/{id}` | Owner-only status/progress/details |
| `GET /media/jobs/{id}/file?inline=` | Owner-only audio/video playback or file download |
| `POST /media/jobs/{id}/playback` | Issue one-hour HMAC-signed, owner-scoped playback URL |
| `GET /media/play/{id}?expires=&signature=&inline=` | Stream using the short-lived signed capability (supports byte ranges) |
| `DELETE /media/jobs/{id}` | Remove an owned non-running job and its file |
| `POST /media/edit` | Owner-only bounded edit of a completed job, returns a new encoded file |

Use cursor pagination, size limits, stable errors and backend ownership checks. Never expose private email/playlists publicly.

## Search semantics
Search without login, with IP/provider abuse controls. Debounce/cancel stale requests. Song, artist and album filters map to the provider's corresponding search attribute and are passed explicitly on submit; the API also enforces the chosen field on normalized results if the provider ignores the attribute. Results always switch the app view to Discover. Dedupe by provider IDs and cautious title/artist/duration similarity; do not merge distinct recordings silently. Preserve source display values. Cache only within terms. Mood starts as curated tags/explicit filters, not psychological certainty. Personalization needs opt-in interaction data and measurable value.

## Media workflow and limits
The browser can only request a download for a catalog `track_id`; it cannot submit a URL for the worker to fetch. The worker constructs `ytsearch1:{title} {artist}`, limits the source to 30 minutes and 150 MB, and processes one job at a time on the initial EC2 host. An account may have at most two queued/running jobs. The temporary download is inside a per-user directory and is moved to a UUID-named private file; user-facing names are sanitized. A worker restart requeues rows left running. Keep media volume private and share it only with API/worker containers.

Audio editing is synchronous initially, with a 50 MB input cap and bounded trim, fade, bass/treble, volume, speed, format and bitrate values. Editing creates a new result and never mutates the original download. Supported editor exports are MP3 (128/192/320 kbps), AAC (128/192/256), OGG (128/192/320), MP4 (AAC audio, 128/192/256 kbps), WAV and FLAC. Quick download defaults to MP3 192 kbps; API formats also include M4A, Opus and MP4.

Playback URL issuance requires Firebase authentication and checks the job owner. It returns a one-hour HMAC-signed, job-specific capability so the browser's native audio element can seek/stream with byte-range requests without downloading a large file into memory. The media signing key is a server secret and must match across API replicas. Playlist playback prefers an owner's completed file for each track and falls back to the catalog sample. The app does not expose the media volume or permanent public URLs.

## Storage/operations follow-up
Temporary yt-dlp directories are removed when a job finishes/fails. Completed files currently remain until the owner deletes them; enforce a per-user storage quota and age-based cleanup before inviting a larger audience. Monitor media volume free space, failed/old jobs, worker health and database connectivity. Back up Postgres and media separately if both must survive host loss; never mistake a named Docker volume for an off-host backup.

## Current identity reference
[Amazon Cognito user-pool Google federation](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-identity-provider.html) and [Cognito pricing/free-tier conditions](https://aws.amazon.com/cognito/pricing/). Pricing/eligibility can change; check before choosing.

## Provider references
- [Firebase Google sign-in for web](https://firebase.google.com/docs/auth/web/google-signin)
- [Firebase Admin ID-token verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens)
- [Apple iTunes Search API](https://performance-partners.apple.com/search-api): approximately 20 requests/minute (subject to change); the implementation caches briefly and throttles upstream calls. Apple catalog promotional assets require an appropriate direct store link and must follow the current terms.
