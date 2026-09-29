# 4. Frontend experience

## Direction and foundation
Aim for premium music-editorial restraint: space, excellent typography, small palette, rich artwork, clear hierarchy and fast feedback. “Apple-like” means polished clarity, not copied branding/layout/assets. Use React + TypeScript + Vite, router, CSS variables/tokens with CSS Modules or equivalent, a remote-state query cache, and small local-state tool only if needed. CSS for simple transitions; Motion One/Framer Motion for selected transitions. Keep dependencies replaceable.

## Visual system
- Warm/neutral near-white canvas, deep ink text, one confident accent, semantic status colors.
- Expressive display face for headings and readable sans for controls/body; reliable fallbacks and licensed fonts.
- 4/8 spacing scale, generous desktop rhythm and tighter mobile spacing.
- Restrained corners/elevation; favor borders and surface contrast over shadows.
- Fixed artwork aspect ratios, correctly sized/lazy images and neutral fallback.
- Semantic tokens make dark mode possible later without rewriting components.

## Home
Compact brand/navigation/account header; prominent title/artist search; recent activity only when meaningful; saved playlist area/create action; source-labelled discovery rows; advanced filters/mood as secondary actions. Search rows provide sample preview, reviews, a playlist picker and explicit Quick download. Reserve image dimensions, show useful skeletons, and make first interaction fast.

## Screens/states
- Search: persistent query, filters in drawer/dialog, source labels, careful dedupe, correction guidance, partial-outage state.
- Track: title/artist/album, source/artwork, short preview when the catalog supplies it, review summary, playlist picker and Quick download.
- Playlist: editable title/description/visibility, accessible reorder, item count, sharing only when enabled, destructive confirmation.
- Discover/mood: explain selection (“tagged mellow”), allow dismissal/correction.
- Downloads: recent files, queued/running/completed/failed status, stage label, determinate progress when yt-dlp reports byte estimates, found source title, play, device download, open-in-Studio and delete.
- Player: persistent playback bar with artwork/title, play/pause, previous/next, seek and shuffle. The home record spins while audio is playing. Playlist queues prefer a listener's downloaded file, then use the catalog's short preview where available.
- Audio Studio: choose a completed private download; edit trim points, fades, bass, treble, volume and speed; select MP3/AAC/OGG/MP4/WAV/FLAC and bitrate/lossless output; preview and save a new copy. Preserve the original.
- Save: each Save action opens a radio-list picker for the destination playlist. Creating the first playlist should preserve and add the pending track.
- Account: identity provider, privacy/share settings, data actions and sign-out.
- Review: one per user/track initially; edit/delete/report and length limit.

Every route needs loading, empty, error, timeout/offline and permission-denied states. Use inline errors/request IDs, avoid full-screen spinners.

## Motion
Use 180–320 ms opacity and 8–16 px movement for small page entry; restrained results crossfade; subtle artwork hover on pointer devices; short list staggering only if useful; clear reorder feedback; dialogs restore focus and support Escape. Content remains visible if animation fails. Avoid scroll hijacking, long pinned sections, bounce overload, cursor gimmicks, auto-play and delayed actions. Honor `prefers-reduced-motion: reduce`; motion is never the only status cue.

## Accessibility/responsive
Target WCAG 2.2 AA: contrast, keyboard, visible focus, labels, headings, screen-reader status announcements and adequate targets. Test all controls keyboard-only. Use real buttons/links and appropriate artwork alt. Design from 320px up; test mobile/tablet/desktop; avoid overflow; support zoom/system text.

## Performance/checklist
Keep initial bundle small; lazy-load advanced/review/admin routes; debounce search 250–400 ms and cancel stale calls; use small list thumbnails; cache with freshness semantics; never expose server keys in bundles. Add analytics only after privacy/consent decision. For each component ask keyboard/focus/screen reader? loading/empty/error? mobile? reduced motion? attribution? unnecessary dependency?
