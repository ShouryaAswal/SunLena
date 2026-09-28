# 5. Data, APIs, and integrations

## Google sign-in
Google login works with AWS compute: identity is separate from hosting. Initially use Firebase Authentication + Google, consistent with historical SunLeo direction. FastAPI verifies ID tokens server-side (signature, issuer, audience, expiry, subject); browser-decoded claims are untrusted. Store stable provider subject, not email. Keep an adapter for Cognito.

Alternative: Cognito User Pools federate Google and issue Cognito tokens. This reduces Firebase coupling/teaches AWS identity but adds setup. Cognito currently describes free tiers with plan/account conditions; verify live pricing, eligibility and region before relying on it. Neither auth provider makes hosting free. Do not implement passwords in MVP.

OAuth: separate dev/prod clients; exact origins/callbacks; authorized domain; runtime server credential; test linking, expiry, revocation, disabled user, logout and denied API calls.

## Provider adapters
- Apple/iTunes Search: candidate metadata/artwork search based on SunLeo; verify current terms, attribution, limits and caching.
- Last.fm: optional enrichment/artwork/tags; key server-side, quotas/terms/attribution respected.
- YouTube metadata/thumbnail: only under current terms. Thumbnail is not a media license; URLs/images can vanish or have use constraints.
- Discovery begins as transparent tags/curation, not an unsupported personalization claim.

Adapters require timeout, bounded retry/backoff, provider status, normalized DTO, provider-aware cache, rate protection, safe logs and config kill switch. Do not leak provider DTO throughout the app.

## Initial entities (relational)
- `users(id, identity_provider, provider_subject, email, display_name, avatar_url, created_at, updated_at, disabled_at)`; unique provider/subject.
- `tracks(id, title, normalized_title, duration_ms, artwork_url, metadata_json, created_at, updated_at)`; only permitted cached fields.
- `track_sources(id, track_id, provider, provider_track_id, canonical_url, fetched_at)`; unique provider identity.
- `playlists(id, owner_user_id, title, description, visibility, share_token_hash, created_at, updated_at)`.
- `playlist_items(id, playlist_id, track_id, position, added_at)`; deterministic ordering constraints.
- `reviews(id, track_id, author_user_id, rating, body, status, created_at, updated_at)`; unique track/author initially.
- `conversion_jobs(id, owner_user_id, source_url, state, idempotency_key, requested_at, started_at, finished_at, expires_at, output_key, failure_code, attempts, lease_until)`.
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
| `POST /conversion-jobs` | Submit supported URL; rate-limited/idempotent |
| `GET /conversion-jobs/{id}`, `POST /conversion-jobs/{id}/cancel` | Owner status/cancel |
| `GET /conversion-jobs/{id}/download` | Short-lived owner-authorized download |

Use cursor pagination, size limits, stable errors and backend ownership checks. Never expose private email/playlists publicly.

## Search semantics
Search without login, with IP/provider abuse controls. Debounce/cancel stale requests. Dedupe by provider IDs and cautious title/artist/duration similarity; do not merge distinct recordings silently. Preserve source display values. Cache only within terms. Mood starts as curated tags/explicit filters, not psychological certainty. Personalization needs opt-in interaction data and measurable value.

## Media policy/security
Technical availability does not grant permission. Review current YouTube terms, copyright laws and provider restrictions before public enablement. Conversion off by default until reviewed; do not promise arbitrary URL support. Validate URLs/redirects and block loopback/private/link-local/metadata destinations (SSRF); subprocess argument arrays, timeout, resource caps, non-root worker, quotas, expiry and report handling. If disallowed, retain metadata/playlists and disable extraction.

## Retention proposals
Generated files expire in 24 hours; clean temp/failed files promptly; retain a disclosed small job audit after output expiry; no full search history by default. Support playlist/review/account deletion; explain backup retention. Confirm policy before implementation.

## Current identity reference
[Amazon Cognito user-pool Google federation](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-identity-provider.html) and [Cognito pricing/free-tier conditions](https://aws.amazon.com/cognito/pricing/). Pricing/eligibility can change; check before choosing.

## Provider references
- [Firebase Google sign-in for web](https://firebase.google.com/docs/auth/web/google-signin)
- [Firebase Admin ID-token verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens)
- [Apple iTunes Search API](https://performance-partners.apple.com/search-api): approximately 20 requests/minute (subject to change); the implementation caches briefly and throttles upstream calls. Apple catalog promotional assets require an appropriate direct store link and must follow the current terms.
