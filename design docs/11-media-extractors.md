# Media extraction backends

SunLena accepts either a catalog result or a public media URL. Both create the existing persistent `MediaJob`; the worker still owns job state, quota checks, the private media volume, and completion/error handling. Only source resolution and extraction vary:

```text
homepage catalog search ── Apple search ── selected track
                                           ├─ yt-dlp: title/artist search + download (default, also under Cobalt)
                                           └─ Cobalt: only if SUNLENA_YOUTUBE_EXTRACTOR=cobalt

homepage URL input ───────────────────────────────┐
                                                  ▼
                           per-job routing (choose_extractor)
                    YouTube host ─► yt-dlp + bgutil PO tokens
                    other hosts  ─► SUNLENA_MEDIA_EXTRACTOR (yt-dlp or Cobalt)
                                                  ▼
                                   worker scratch → FFmpeg only if needed
                                                  ▼
                                   existing private media volume
```

`SUNLENA_MEDIA_EXTRACTOR` selects `yt-dlp` (default) or `cobalt` for non-YouTube sources. When it is `cobalt`, `SUNLENA_YOUTUBE_EXTRACTOR` (default `yt-dlp`) decides who handles YouTube URLs (`youtube.com`, `youtu.be`, `music.youtube.com`, `youtube-nocookie.com`) and catalog searches. The worker selects the backend per job, and every later step (FFmpeg normalization, FFprobe extension detection) uses the backend that actually ran, not the global setting. There is no automatic retry on a different backend after a failure. URL jobs are accepted only for the public hostnames listed in `apps/api/app/modules/media/schemas.py`; URL jobs never accept credentials or local/private hosts. Authentication cookies, browser profiles, and Google credentials are not supported.

### Why YouTube is routed to yt-dlp (October 2026 investigation)

With Cobalt 11.7.1, YouTube jobs failed with `Cobalt returned an empty tunnel (HTTP 200, advertised length=0)`, while Instagram worked. Reproduced findings:

- Cobalt `POST /` returns `status=tunnel` for every YouTube video, but the tunnel body is 0 bytes for many videos (for example `kTpyO8iwlSY`, `jCQ401VHXmY`). Some videos still worked (`dQw4w9WgXcQ`). The `downloadMode=audio`, `youtubeHLS`, and `youtubeVideoCodec=h264` options all gave the same empty body.
- From the same container and IP, yt-dlp downloaded the same videos. Its verbose log shows `Detected experiment to bind GVS PO Token to video ID`: YouTube now requires a per-video PO token for media (GVS) requests on many videos. yt-dlp gets it from the bgutil provider. Cobalt can only get one from the optional `YOUTUBE_SESSION_SERVER`, which uses browser automation and is excluded here.
- A second bug meant the app never used bgutil at all: `extractor_args` passed `base_url` as a string. yt-dlp's Python API expects a list and split the string into characters (`['h','t','t','p',…]`). The README's CLI check passed because the CLI parses the argument correctly. Without PO tokens, yt-dlp also fails from datacenter/EC2 IPs. The value is now a list.

Set `SUNLENA_YOUTUBE_EXTRACTOR=cobalt` only after you add a working Cobalt YouTube session server.

## Cobalt behavior and project status

Cobalt is the open-source, self-hostable media conversion/downloading API maintained by imputnet. Its `POST /` API accepts JSON with a source `url` plus optional settings such as `downloadMode`, `audioFormat`, `audioBitrate`, and `youtubeVideoContainer`. The documented defaults are `downloadMode=auto`, `audioFormat=mp3`, `audioBitrate=128`, `videoQuality=1080`, and `youtubeVideoContainer=auto`. The `audioFormat` default applies when an audio-mode result is requested; `auto` mode may return audio or video according to the source/platform and does not promise one universal extension. SunLena therefore omits all format-forcing options by default, sets only `url` and `alwaysProxy=true`, downloads the tunnel stream, and uses FFprobe to validate its actual container and codecs. When the user explicitly selects an output format in Advanced download settings, the worker uses FFmpeg to convert the extracted source. Cobalt's tunnel URLs are short-lived (default 90 seconds), so SunLena downloads the tunnel response immediately in the worker. The adapter consumes `tunnel` responses only; it rejects redirects, picker responses and `local-processing` responses with a clear error.

Cobalt's current supported-services table lists Bilibili, Bluesky, Dailymotion, Facebook, Instagram, Loom, Newgrounds, OK.ru, Pinterest, Reddit, Rutube, Snapchat, SoundCloud, Streamable, TikTok, Tumblr, Twitch clips, Twitter/X, Vimeo, VK, and YouTube. Support modes vary per service; for example, Facebook and Loom are video-only, while SoundCloud is audio-only. Consult the current [supported services](https://github.com/imputnet/cobalt/blob/main/api/README.md) and [API schema/response documentation](https://github.com/imputnet/cobalt/blob/main/docs/api.md). The current project documentation says the API can be self-hosted and documents Docker Compose as its recommended package method. `API_URL` is required; `API_PORT` defaults to 9000. The [official Compose sample](https://github.com/imputnet/cobalt/blob/main/docs/examples/docker-compose.example.yml) is the reference for the Cobalt service settings. SunLena adapts it by keeping Cobalt on an internal-only Compose network, setting `API_URL` to the internal service URL that the worker can reach, and pinning the image by version and digest. It retains the sample's `init: true`, `read_only`, and restart behavior. It intentionally omits the sample's public host port and Watchtower (automatic unpinned image updates conflict with reproducible/pinned deployment). Cobalt's documented optional YouTube session generator is not enabled; see the YouTube limitations below.

Cobalt's own API documentation credits `youtube.js`/Innertube for YouTube access and `ffmpeg-static` for media muxing/encoding; Cobalt does not document yt-dlp as its YouTube extractor. The official environment-variable docs list default rate limits of 20 API requests per 60-second window and 40 tunnel requests per 60-second window; operators can configure these. These are per-instance defaults, not promises about third-party hosted service quotas.

The API can optionally require `Api-Key` or `Bearer` authentication. Self-hosting does not inherently require an account or key when authentication is disabled. There is no general public Cobalt endpoint that third-party projects may freely depend on: the official docs explicitly say hosted instances (including api.cobalt.tools) are not intended for other projects without the instance owner's permission. No standard account signup, general hosted-service price, or blanket API key is documented. Ask the operator for permission and credentials before using an external compatible API. Cobalt applies rate limits to its processing and tunnel endpoints; self-hosting avoids another operator's limits but not upstream platform restrictions or Cobalt's own configured rate limits.

The project license is AGPL-3.0. The Cobalt API README says use/modification is allowed subject to appropriate credit, linking the license and indicating changes, and releasing code under the same license. Review the [license](https://github.com/imputnet/cobalt/blob/main/LICENSE) before modifying or redistributing Cobalt itself; this is not a legal interpretation. Cobalt may need outbound access to media platforms/CDNs. Its internal API network is private to the worker; a separate Cobalt-only egress network provides those outbound connections. Do not publish its port or expose an unauthenticated instance to the public Internet.

Official references reviewed for this design:

- [Cobalt API](https://github.com/imputnet/cobalt/blob/main/docs/api.md)
- [Run an instance](https://github.com/imputnet/cobalt/blob/main/docs/run-an-instance.md)
- [API environment variables](https://github.com/imputnet/cobalt/blob/main/docs/api-env-variables.md)
- [Docker Compose example](https://github.com/imputnet/cobalt/blob/main/docs/examples/docker-compose.example.yml)
- [Supported services](https://github.com/imputnet/cobalt/blob/main/api/README.md)
- [AGPL-3.0 license](https://github.com/imputnet/cobalt/blob/main/LICENSE)

## Run locally

Default local development continues to use yt-dlp:

```bash
docker compose up --build -d
```

To run the self-hosted Cobalt variant instead, use the optional overlay (no host port is published for Cobalt):

```bash
docker compose -f compose.yaml -f compose.cobalt.yaml up --build -d
docker compose -f compose.yaml -f compose.cobalt.yaml ps
docker compose -f compose.yaml -f compose.cobalt.yaml logs worker cobalt
```

The overlay sets `SUNLENA_MEDIA_EXTRACTOR=cobalt` (with `SUNLENA_YOUTUBE_EXTRACTOR=yt-dlp`), starts the pinned official Cobalt image, and places worker and Cobalt on a private internal network. Cobalt also joins an unshared egress network for source platform/CDN access. The worker still needs the existing application network, outbound YouTube access, and the `bgutil-provider` sidecar because it downloads YouTube itself; apply host-level outbound controls if that traffic must be restricted. Cobalt itself has no host-published port. PostgreSQL, the API, web frontend, authentication, and the `media_data` volume are unchanged. To return to the base yt-dlp stack, stop the overlay stack with `docker compose -f compose.yaml -f compose.cobalt.yaml down` (without `-v`) and start the base stack.

For a full local smoke test, sign in on the website, switch the hero input from **Search music** to **Use a media URL**, and submit a publicly accessible URL. Test both a YouTube URL (handled by yt-dlp) and an Instagram/other URL (handled by Cobalt). Watch the job under **Downloads** until it completes. The worker log line `media_job_started ... extractor=` shows which backend ran. Play the result and use **Save file to device** to check the API playback/download path. To check catalog search, search for a song and choose **Quick download** on a result. That job runs a yt-dlp `ytsearch1:` download.

Run the mocked adapter/schema tests from the API project directory after installing the test extra:

```bash
cd apps/api
python -m pip install -e '.[test]'
python -m pytest
```

Or, without a local Python, inside the built image:

```powershell
docker run --rm -v "${PWD}\apps\api:/src:ro" -w /src sunlena-worker sh -c "pip install -q --target /tmp/pt 'pytest>=8,<9'; PYTHONPATH=/tmp/pt:/src python -m pytest -q -p no:cacheprovider"
```

`tests/test_extractor_routing.py` covers per-job routing, the list-typed PO-token argument, MP4/OGG options, explicit duration/size/no-match errors, and bot-check retry.

An external Cobalt-compatible API can be selected by changing `SUNLENA_COBALT_API_BASE_URL` and optionally providing `SUNLENA_COBALT_API_TOKEN` plus `SUNLENA_COBALT_AUTH_SCHEME=Api-Key` or `Bearer`. Do not use a third-party endpoint without its operator's permission. For an external instance, configure its `API_URL` to an address that the worker can reach: Cobalt's tunnel URLs point back to that address. In the self-hosted Compose overlay, this single variable configures both the worker's API client and Cobalt's `API_URL`, preventing the two tunnel endpoints from drifting apart.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `SUNLENA_MEDIA_EXTRACTOR` | `yt-dlp` | Selects `yt-dlp` or `cobalt` for non-YouTube sources. |
| `SUNLENA_YOUTUBE_EXTRACTOR` | `yt-dlp` | When Cobalt is selected, picks the backend for YouTube URLs and catalog searches. Use `cobalt` only with a Cobalt YouTube session server. |
| `SUNLENA_YTDLP_CACHE_DIR` | `/tmp/yt-dlp-cache` | Writable yt-dlp cache (player/signature JS). The containers' root filesystem is read-only. |
| `SUNLENA_COBALT_API_BASE_URL` | `http://cobalt:9000/` | Cobalt API root. |
| `SUNLENA_COBALT_API_TOKEN` | empty | Optional key/token supplied by the instance operator. Keep it in the existing secret/environment mechanism. |
| `SUNLENA_COBALT_AUTH_SCHEME` | `Api-Key` | `Api-Key` or `Bearer`. |
| `SUNLENA_COBALT_REQUEST_TIMEOUT_SECONDS` | `30` | API request timeout. |
| `SUNLENA_COBALT_DOWNLOAD_TIMEOUT_SECONDS` | `180` | Tunnel download timeout. |
| `COBALT_API_INSTANCE_COUNT` | `1` | Number of Cobalt API instances; one keeps initial single-host resource use bounded. |
| `COBALT_API_AUTH_REQUIRED` | `false` | Enables Cobalt authentication when configured with matching key material. |
| `COBALT_API_KEY_URL` | empty | Optional Cobalt-supported URL for API key configuration. |
| `COBALT_TUNNEL_LIFESPAN` | `90` | Self-hosted tunnel lifetime in seconds; keep long enough for SunLena to begin a download. |
| `COBALT_DURATION_LIMIT` | `1800` | Self-hosted maximum source duration in seconds; aligned with SunLena's 30-minute job limit. |

The sample `.env.example` contains blank token values only. For production, pass credentials through your existing secret-file/environment management. The application does not log the token.

## Catalog search versus URL input

Direct URL downloads go to the backend chosen by the routing above. Catalog search remains the existing Apple Music search, and catalog jobs download through yt-dlp's `ytsearch1:` (title + artist). If `SUNLENA_YOUTUBE_EXTRACTOR=cobalt`, the worker first uses yt-dlp's flat search, with the same PO-token settings, to resolve a canonical YouTube URL, then Cobalt extracts it. The existing duration limit (30 minutes), per-file size limit (150 MB), active-job cap and per-user media quota still apply. yt-dlp resolves metadata before downloading, so long, live, oversized or unmatched sources fail with a specific message. Previously, yt-dlp skipped them silently, which showed up as "could not be converted".

By default, Cobalt's auto-selected output is retained in its returned format. FFprobe validates the media and determines the saved extension from the detected container/codecs, rather than trusting the filename alone. The **Advanced download settings** control offers explicit MP3, M4A, Opus, OGG, WAV, or MP4 output. For Cobalt jobs, the shared worker FFmpeg stage normalizes those choices. A selected audio format extracts the audio stream from the Cobalt result, while MP4 converts available video/audio streams. If FFmpeg cannot produce the selected format (for example, MP4 from an audio-only source), the job fails with the conversion diagnostic. For yt-dlp jobs, “Keep source format” produces MP3. OGG maps to yt-dlp's `vorbis` codec. MP4 merges the best video (≤720p, H.264 preferred) with audio, instead of the old `best[ext=mp4]`, which on YouTube only matched a 360p progressive stream that is often missing.

## Troubleshooting

- **Worker does not use Cobalt:** check `SUNLENA_MEDIA_EXTRACTOR=cobalt` in the worker environment and make sure the overlay file was included in the Compose command.
- **Cobalt unavailable:** check `docker compose ... ps` and worker/Cobalt logs; from worker, confirm `http://cobalt:9000/` resolves on the shared internal network.
- **Timeout:** increase the corresponding request/download timeout only after checking Cobalt and upstream platform health. A tunnel may expire if the worker waits too long before downloading.
- **Invalid response or unsupported URL:** inspect the structured job error; Cobalt may return `error`, `picker`, `redirect`, or `local-processing`, which this adapter currently does not process. Check Cobalt's supported-service list.
- **Authentication failure:** verify the API key/token and `Api-Key` versus `Bearer` scheme with the instance operator. Never add the token to logs or documentation.
- **Expired media URL:** Cobalt tunnel URLs expire quickly; check worker scheduling/network latency and Cobalt's tunnel lifespan.
- **Catalog search cannot be resolved:** yt-dlp may be blocked while searching YouTube from the server. Use direct URL input, or check the bgutil provider (see the README diagnostic command).
- **"YouTube asked this server to prove it is not a bot":** YouTube is rate-limiting the server IP (HTTP 429 / sign-in challenge). The worker retries once after 8 seconds. If it persists, wait several minutes. Heavy repeated testing from one IP triggers this, and EC2 addresses are more exposed. Confirm the worker log shows PO tokens being generated, and keep yt-dlp up to date.
- **Cobalt will not start:** `API_URL` must be syntactically valid and reachable by the worker because Cobalt returns tunnel URLs based on it. Confirm it matches `SUNLENA_COBALT_API_BASE_URL` and that both point to the same service address.
- **YouTube gives an empty tunnel:** this happens only when `SUNLENA_YOUTUBE_EXTRACTOR=cobalt`. HTTP 200 from `GET /tunnel` with zero bytes means YouTube refused Cobalt's media request, usually because a video-bound GVS PO token is required. It is not a SunLena FFmpeg/storage failure. Switch back to `SUNLENA_YOUTUBE_EXTRACTOR=yt-dlp`, or run Cobalt's optional `YOUTUBE_SESSION_SERVER` (browser automation, currently excluded by this deployment). A successful `GET /` healthcheck only proves the API process is up. It does not prove platform extraction works.

## Production shape

No deployment has been performed. To use Cobalt in a future deployment, supply the same overlay alongside `compose.ec2.yaml`, review the selected Cobalt image/version and outbound firewall policy, configure `SUNLENA_COBALT_API_BASE_URL` to the internal Cobalt service URL, and recreate only the worker/Cobalt services after review. Caddy remains the only public SunLena entry point, and Cobalt has no host port or public domain. Preserve PostgreSQL and media volumes; never use `down -v` for an upgrade.

The deployment command, when separately approved and scheduled, will use both files, for example `sudo docker compose -f compose.ec2.yaml -f compose.cobalt.yaml up -d --build worker cobalt`. This has not been run against EC2.
