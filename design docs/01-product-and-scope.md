# 1. Product and scope

## Product statement
SunLena is a polished music discovery and personal-library site for family and friends. People can search a catalog, preview short catalog samples, organize playlists, review songs, request a YouTube match for a searched song, keep the resulting media in their private library, play downloaded files, and make a personal edit/export.

## Audiences and outcomes
- Listener: find a track quickly, understand its source, save it, and return later.
- Listener: preview before deciding, download explicitly, see honest job progress, and play or edit files already in their library.
- Curator: create, edit, reorder, and intentionally share playlists.
- Family member: sign in with Google and use the site comfortably on a phone.
- Operator: deploy/update one small service, control spend, diagnose errors, and restore data.
- Learner: understand tradeoffs and explain why each boundary exists.

## Product principles
1. Search is the front door; focus the landing page on searching.
2. Distinguish metadata, artwork, thumbnails, reviews, and audio files.
3. Provider failure yields partial results and retry, not a blank screen.
4. Long work is an explicit job with states; do not hold an HTTP request open.
5. Private by default; playlist sharing is deliberate.
6. Motion adds feedback and hierarchy, never blocks use; respect reduced-motion settings.
7. Infrastructure follows evidence. Microservices are an option, not the product goal.

## Current product scope
- Responsive home/search with title/artist search, Apple preview samples, and clear catalog attribution.
- One-tap Quick download for a searched track. SunLena searches YouTube using title + artist, downloads one candidate via yt-dlp, and processes it with FFmpeg. The Downloads screen shows the found source title so the user can inspect the match.
- Private recent-download library with durable job state, progress, status/error, play, browser download and delete actions.
- Music player with play/pause, seek, previous/next, shuffle, sequential playlist playback, Apple preview fallback and downloaded-file playback.
- Audio Studio: select a private downloaded file; trim, fade, bass/treble, volume and speed; preview output; export MP3/AAC/OGG/MP4/WAV/FLAC with supported bitrates or lossless settings.
- Save action opens a per-track playlist picker; a first playlist can be created inline and the pending track is added.
- Track details: title, artist, album, duration where available, artwork and source.
- Google sign-in, profile/account settings, sign-out.
- Private playlists: create, rename, delete, add/remove tracks, reorder.
- Public/unlisted playlist links with revocation and clear visibility setting.
- Explainable provider-backed/curated discovery; no fake “personalized” claims.
- Track reviews/ratings with edit/delete and report controls.
- Advanced filters and mood exploration with honest semantics (“matches mellow tags”).
- Operator control to disable conversion, inspect failures and handle reports.

Later: durable per-user storage quotas and cleanup UI, source candidate chooser, job cancellation/retries, preview/download matching quality signals, collaborative playlists, follows, import/export, notifications, object storage/CDN and IaC/CI/CD.

Not initially: a public streaming catalog, arbitrary URL ingestion, public social graph/messaging, ads/subscriptions, Kubernetes/service mesh/multi-region, or immediate serverless conversion.

## Zero-cost constraint
Treat zero spend as a budget target with a stop condition. A domain may have renewal costs even if initially bundled; VM, snapshots, storage, transfer and optional services may be charged. Verify current pricing and terms. Before AWS resources, estimate region-specific monthly cost, set a budget alert, record a maximum acceptable spend, and know how to delete it. If the limit is literally ₹0, stay local or use a verified free offer with limits understood. AWS alerts notify; they do not enforce a hard cap.

## SunLeo parity discovery
Before implementation, inspect SunLeo and document every screen, endpoint, environment variable, integration, behavior and defect. Mark keep/redesign/defer/drop and ask before dropping product behavior. Referenced chat is not a source-code audit.
