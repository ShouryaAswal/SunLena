import {
  ArrowDownRight, ArrowRight, ArrowUpRight, AudioLines, Check, Disc3, Download, Headphones,
  ListMusic, LogOut, MessageCircle, Music2, Play, Plus, Search, Sparkles, Star, Trash2,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import {
  addTrack, createPlaylist, deletePlaylist, deleteReview, getDiscover, getPlaylists,
  getMyReview, getReviews, removePlaylistItem, reorderPlaylist, saveReview, searchTracks,
  createMediaJob, createMediaPlaybackUrl, getMediaJobs, updatePlaylist, type DiscoverySection, type Playlist, type ReviewList, type SearchResponse,
  type SearchResult,
} from '../lib/api'
import { useAuth } from '../lib/auth'
import { useAudioPlayer } from '../lib/audioPlayer'
import MediaWorkspace from '../components/MediaWorkspace'

const moods = [
  { id: 'soft-focus', name: 'Soft focus', note: 'A little room to think', color: 'moss' },
  { id: 'golden-hour', name: 'Golden hour', note: 'Warmth for the way home', color: 'amber' },
  { id: 'after-hours', name: 'After hours', note: 'When the day gets quiet', color: 'plum' },
]

function formatDuration(milliseconds?: number) {
  if (!milliseconds) return ''
  const total = Math.floor(milliseconds / 1000)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

function Artwork({ track }: { track?: SearchResult }) {
  return track?.artwork_url
    ? <img className="track-artwork" src={track.artwork_url} alt={`Album artwork for ${track.album || track.title}`} loading="lazy" />
    : <span className="track-artwork artwork-fallback" aria-hidden="true"><Music2 size={19} /></span>
}

export default function HomePage() {
  const { user, ready: authReady, configured, signIn, signOutUser, getToken } = useAuth()
  const player = useAudioPlayer()
  const [activeTab, setActiveTab] = useState<'discover' | 'downloads' | 'editor'>('discover')
  const [query, setQuery] = useState('')
  const [downloadMode, setDownloadMode] = useState<'search' | 'url'>('search')
  const [mediaUrl, setMediaUrl] = useState('')
  const [urlSubmitting, setUrlSubmitting] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [searchField, setSearchField] = useState('all')
  const [response, setResponse] = useState<SearchResponse | null>(null)
  const [searchError, setSearchError] = useState('')
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState('')
  const [discover, setDiscover] = useState<DiscoverySection[]>([])
  const [playlists, setPlaylists] = useState<Playlist[]>([])
  const [selectedPlaylistId, setSelectedPlaylistId] = useState('')
  const [managerOpen, setManagerOpen] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [creating, setCreating] = useState(false)
  const [activeTrack, setActiveTrack] = useState<SearchResult | null>(null)
  const [reviewData, setReviewData] = useState<ReviewList | null>(null)
  const [myReview, setMyReview] = useState<{ id: string; rating: number; body?: string | null } | null>(null)
  const [reviewRating, setReviewRating] = useState(5)
  const [reviewBody, setReviewBody] = useState('')
  const [reviewBusy, setReviewBusy] = useState(false)
  const [sharePlaylist, setSharePlaylist] = useState<Playlist | null>(null)
  const [sharedPlaylist, setSharedPlaylist] = useState<Playlist | null>(null)
  const [savingTrackId, setSavingTrackId] = useState('')
  const [saveTrackTarget, setSaveTrackTarget] = useState<SearchResult | null>(null)
  const [savePlaylistId, setSavePlaylistId] = useState('')
  const [pendingSaveTrack, setPendingSaveTrack] = useState<SearchResult | null>(null)
  const [downloadingTrackId, setDownloadingTrackId] = useState('')
  const [downloadFormat, setDownloadFormat] = useState('auto')
  const [downloadBitrate, setDownloadBitrate] = useState('192')
  const [editorJobId, setEditorJobId] = useState('')
  const controller = useRef<AbortController | null>(null)
  const createDialog = useRef<HTMLDialogElement>(null)
  const managerDialog = useRef<HTMLDialogElement>(null)
  const accountDialog = useRef<HTMLDialogElement>(null)
  const reviewDialog = useRef<HTMLDialogElement>(null)
  const shareDialog = useRef<HTMLDialogElement>(null)
  const sharedDialog = useRef<HTMLDialogElement>(null)
  const saveDialog = useRef<HTMLDialogElement>(null)

  const selectedPlaylist = useMemo(
    () => playlists.find((playlist) => playlist.id === selectedPlaylistId) ?? null,
    [playlists, selectedPlaylistId],
  )

  useEffect(() => () => controller.current?.abort(), [])
  useEffect(() => {
    const pairs = [
      [createOpen, createDialog], [managerOpen, managerDialog], [accountOpen, accountDialog], [Boolean(activeTrack), reviewDialog],
      [Boolean(sharePlaylist), shareDialog], [Boolean(sharedPlaylist), sharedDialog],
      [Boolean(saveTrackTarget), saveDialog],
    ] as const
    for (const [open, ref] of pairs) {
      const dialog = ref.current
      if (!dialog) continue
      if (open && !dialog.open) dialog.showModal()
      if (!open && dialog.open) dialog.close()
    }
  }, [createOpen, managerOpen, accountOpen, activeTrack, sharePlaylist, sharedPlaylist, saveTrackTarget])

  useEffect(() => {
    let live = true
    getDiscover().then((data) => { if (live) setDiscover(data.sections) }).catch(() => undefined)
    const token = new URLSearchParams(window.location.search).get('share')
    if (token) {
      fetch(`/api/v1/playlists/shared/${encodeURIComponent(token)}`)
        .then(async (result) => {
          if (!result.ok) throw new Error('This shared playlist is no longer available.')
          return result.json() as Promise<Playlist>
        })
        .then((playlist) => { if (live) setSharedPlaylist(playlist) })
        .catch((error: Error) => { if (live) setNotice(error.message) })
    }
    return () => { live = false }
  }, [])

  const refreshPlaylists = useCallback(async () => {
    const token = await getToken()
    if (!token) {
      setPlaylists([])
      setSelectedPlaylistId('')
      return
    }
    const rows = await getPlaylists(token)
    setPlaylists(rows)
    setSelectedPlaylistId((current) => rows.some((playlist) => playlist.id === current) ? current : (rows[0]?.id ?? ''))
  }, [getToken])

  useEffect(() => {
    if (!authReady) return
    refreshPlaylists().catch((error: Error) => setNotice(error.message))
  }, [authReady, user, refreshPlaylists])

  async function runSearch(value: string, field = searchField) {
    const clean = value.trim()
    if (!clean) return
    controller.current?.abort()
    controller.current = new AbortController()
    setQuery(clean)
    setActiveTab('discover')
    setLoading(true)
    setSearchError('')
    setResponse(null)
    try {
      setResponse(await searchTracks(clean, controller.current.signal, field))
      requestAnimationFrame(() => document.getElementById('search-results')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') return
      setSearchError(cause instanceof Error ? cause.message : 'Search is temporarily unavailable.')
    } finally {
      setLoading(false)
    }
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void runSearch(query, searchField)
  }

  async function handleSignIn() {
    try {
      await signIn()
      setNotice('Signed in. Your library is ready.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Google sign-in could not be completed.')
    }
  }

  function openCreatePlaylist(trackToSave?: SearchResult) {
    if (!user) {
      setNotice('Sign in with Google to create and save playlists.')
      return
    }
    setNewTitle('')
    setNewDescription('')
    setPendingSaveTrack(trackToSave ?? null)
    setCreateOpen(true)
  }

  async function submitCreatePlaylist(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const token = await getToken()
    if (!token) return setNotice('Sign in before creating a playlist.')
    setCreating(true)
    try {
      const created = await createPlaylist(token, newTitle.trim(), newDescription.trim())
      let ready = created
      if (pendingSaveTrack) ready = await addTrack(token, created.id, pendingSaveTrack.id)
      setPlaylists((rows) => [ready, ...rows])
      setSelectedPlaylistId(ready.id)
      setPendingSaveTrack(null)
      setCreateOpen(false)
      setNotice(pendingSaveTrack ? `“${pendingSaveTrack.title}” saved to “${ready.title}”.` : `“${ready.title}” is ready.`)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not create that playlist.')
    } finally {
      setCreating(false)
    }
  }

  function saveTrack(track: SearchResult) {
    if (!user) return setNotice('Sign in with Google to save music.')
    if (!selectedPlaylistId) {
      setPendingSaveTrack(track)
      setNewTitle('Saved songs')
      setNewDescription('A place for the music you want to keep close.')
      setCreateOpen(true)
      setNotice('Create your first playlist and this song will be added to it.')
      return
    }
    setSavePlaylistId(playlists.some((playlist) => playlist.id === selectedPlaylistId) ? selectedPlaylistId : playlists[0].id)
    setSaveTrackTarget(track)
  }

  async function confirmSaveTrack(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const track = saveTrackTarget
    if (!track || !savePlaylistId) return
    const token = await getToken()
    if (!token) return setNotice('Your sign-in expired. Please sign in again.')
    setSavingTrackId(track.id)
    try {
      const updated = await addTrack(token, savePlaylistId, track.id)
      setPlaylists((rows) => rows.map((playlist) => playlist.id === updated.id ? updated : playlist))
      setNotice(`Saved to “${updated.title}”.`)
      setSaveTrackTarget(null)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not save this track.')
    } finally {
      setSavingTrackId('')
    }
  }

  async function startDownload(track: SearchResult) {
    if (!user) return setNotice('Sign in with Google in the top-right corner, then choose Quick download again.')
    const token = await getToken()
    if (!token) return setNotice('Your sign-in expired. Please sign in again.')
    setDownloadingTrackId(track.id)
    try {
      await createMediaJob(token, { track_id: track.id }, downloadFormat, downloadBitrate)
      setActiveTab('downloads')
      setNotice(`Finding a YouTube match for “${track.title}”.`)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not start this download.')
    } finally { setDownloadingTrackId('') }
  }

  async function submitUrlDownload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!user) return setNotice('Sign in with Google in the top-right corner to download media.')
    const token = await getToken()
    if (!token) return setNotice('Your sign-in expired. Please sign in again.')
    setUrlSubmitting(true)
    try {
      await createMediaJob(token, { source_url: mediaUrl.trim() }, downloadFormat, downloadBitrate)
      setMediaUrl('')
      setActiveTab('downloads')
      setNotice('Your URL download has been added to the queue.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not start this download.')
    } finally {
      setUrlSubmitting(false)
    }
  }

  async function playPlaylist(playlist: Playlist, shuffle = false) {
    const tracks = playlist.items.map((item) => item.track)
    if (!tracks.length) return setNotice('This playlist is empty.')
    try {
      const token = await getToken()
      const downloads = token ? await getMediaJobs(token) : []
      const entries = tracks.map((track) => {
        const local = downloads.find((job) => job.track_id === track.id && job.status === 'completed')
        return {
          track,
          source: track.preview_url ?? null,
          resolveSource: async () => local && token
            ? await createMediaPlaybackUrl(token, local.id, true)
            : track.preview_url ?? null,
        }
      }).filter((entry) => entry.source || downloads.some((job) => job.track_id === entry.track.id && job.status === 'completed'))
      if (!entries.length) return setNotice('No previews or downloaded files are available for this playlist yet.')
      player.playEntries(entries, shuffle)
      setNotice(shuffle ? 'Shuffling your playlist.' : 'Playing your playlist.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'This playlist could not be played.')
    }
  }

  async function loadReviews(track: SearchResult) {
    setActiveTrack(track)
    setReviewData(null)
    setMyReview(null)
    setReviewRating(5)
    setReviewBody('')
    try {
      setReviewData(await getReviews(track.id))
      const token = await getToken()
      if (token) {
        const mine = await getMyReview(token, track.id)
        setMyReview(mine)
        if (mine) {
          setReviewRating(mine.rating)
          setReviewBody(mine.body ?? '')
        }
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Reviews are unavailable right now.')
    }
  }

  async function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!activeTrack) return
    const token = await getToken()
    if (!token) return setNotice('Sign in with Google to leave a review.')
    setReviewBusy(true)
    try {
      const saved = await saveReview(token, activeTrack.id, reviewRating, reviewBody.trim())
      setMyReview(saved)
      setReviewData(await getReviews(activeTrack.id))
      setNotice('Your review has been saved.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not save your review.')
    } finally {
      setReviewBusy(false)
    }
  }

  async function removeReview() {
    if (!activeTrack) return
    const token = await getToken()
    if (!token) return
    try {
      await deleteReview(token, activeTrack.id)
      setMyReview(null)
      setReviewData(await getReviews(activeTrack.id))
      setNotice('Your review was removed.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not remove your review.')
    }
  }

  async function changeVisibility(playlist: Playlist) {
    const token = await getToken()
    if (!token) return
    try {
      const updated = await updatePlaylist(token, playlist.id, { visibility: playlist.visibility === 'public' ? 'private' : 'public' })
      setPlaylists((rows) => rows.map((row) => row.id === updated.id ? updated : row))
      setSharePlaylist(updated.share_token ? updated : null)
      setNotice(updated.visibility === 'public' ? 'Copy your new share link now; it is only shown once.' : 'Playlist is private again.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not update playlist visibility.')
    }
  }

  async function removePlaylist(playlist: Playlist) {
    if (!window.confirm(`Delete “${playlist.title}” and its playlist items?`)) return
    const token = await getToken()
    if (!token) return
    try {
      await deletePlaylist(token, playlist.id)
      const rows = playlists.filter((row) => row.id !== playlist.id)
      setPlaylists(rows)
      setSelectedPlaylistId(rows[0]?.id ?? '')
      setNotice('Playlist deleted.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not delete that playlist.')
    }
  }

  async function movePlaylistItem(itemIndex: number, direction: -1 | 1) {
    if (!selectedPlaylist) return
    const items = [...selectedPlaylist.items]
    const target = itemIndex + direction
    if (target < 0 || target >= items.length) return
    ;[items[itemIndex], items[target]] = [items[target], items[itemIndex]]
    const token = await getToken()
    if (!token) return
    try {
      const updated = await reorderPlaylist(token, selectedPlaylist.id, items.map((item) => item.id))
      setPlaylists((rows) => rows.map((row) => row.id === updated.id ? updated : row))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not reorder playlist.')
    }
  }

  async function removeItem(itemId: string) {
    if (!selectedPlaylist) return
    const token = await getToken()
    if (!token) return
    try {
      await removePlaylistItem(token, selectedPlaylist.id, itemId)
      await refreshPlaylists()
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not remove that track.')
    }
  }

  function copyShareLink(playlist: Playlist) {
    if (!playlist.share_token) return
    const link = `${window.location.origin}/?share=${encodeURIComponent(playlist.share_token)}`
    navigator.clipboard.writeText(link).then(() => setNotice('Share link copied. Anyone with the link can view this playlist.'))
      .catch(() => setNotice(link))
  }

  return (
    <main>
      <header className="topbar">
        <a className="wordmark" href="#top" aria-label="SunLena home"><span className="brand-mark"><AudioLines size={18} strokeWidth={1.8} /></span>sunlena</a>
        <nav aria-label="Main navigation" className="main-nav">
          <a className={activeTab === 'discover' ? 'nav-active' : ''} href="#discover" onClick={(event) => { event.preventDefault(); setActiveTab('discover') }}>Discover</a>
          <a className={activeTab === 'downloads' ? 'nav-active' : ''} href="#downloads" onClick={(event) => { event.preventDefault(); setActiveTab('downloads') }}>Downloads</a>
          <a className={activeTab === 'editor' ? 'nav-active' : ''} href="#studio" onClick={(event) => { event.preventDefault(); setActiveTab('editor') }}>Studio</a>
          <a href="#playlists" onClick={(event) => { event.preventDefault(); user ? setManagerOpen(true) : setNotice('Sign in with Google to open your playlists.') }}>Playlists</a>
          <a href="#about" onClick={() => setActiveTab('discover')}>About</a>
        </nav>
        {user ? <button className="account-button" type="button" onClick={() => setAccountOpen(true)} title="Account settings"><span className="avatar-dot">{(user.displayName || user.email || 'S').slice(0, 1).toUpperCase()}</span><span>{user.displayName?.split(' ')[0] || 'Account'}</span></button> : <button className="account-button" type="button" onClick={() => void handleSignIn()} title={configured ? 'Sign in with Google' : 'Add Firebase settings to .env to enable Google sign-in'}><span className="avatar-dot">S</span><span>{authReady ? 'Sign in' : 'Loading…'}</span></button>}
      </header>

      {notice && <div className="notice" role="status"><span>{notice}</span><button type="button" aria-label="Dismiss message" onClick={() => setNotice('')}><X size={15} /></button></div>}

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow"><span className="eyebrow-line" />A little more room for music</p>
          <h1>Find the song<br />you <em>feel</em> like.</h1>
          <p className="hero-description">A thoughtful place to search, collect, and come back to the music that stays with you.</p>
          <div className="download-mode" role="tablist" aria-label="Choose download input">
            <button type="button" role="tab" aria-selected={downloadMode === 'search'} className={downloadMode === 'search' ? 'selected' : ''} onClick={() => setDownloadMode('search')}>Search music</button>
            <button type="button" role="tab" aria-selected={downloadMode === 'url'} className={downloadMode === 'url' ? 'selected' : ''} onClick={() => setDownloadMode('url')}>Use a media URL</button>
          </div>
          {downloadMode === 'search' ? <form className="search-form" onSubmit={submitSearch} role="search">
            <Search size={20} aria-hidden="true" />
            <label className="sr-only" htmlFor="music-search">Search songs, artists, or albums</label>
            <input id="music-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Songs, artists, albums…" autoComplete="off" />
            <button type="submit" aria-label="Search music" disabled={loading}><ArrowRight size={20} /></button>
          </form> : <form className="search-form" onSubmit={(event) => void submitUrlDownload(event)}>
            <label className="sr-only" htmlFor="media-url">Paste a public media URL</label>
            <input id="media-url" type="url" value={mediaUrl} onChange={(event) => setMediaUrl(event.target.value)} placeholder="Paste a YouTube, TikTok, Vimeo, or other supported URL" required />
            <button type="submit" aria-label="Download media URL" disabled={urlSubmitting}><Download size={18} /></button>
          </form>}
          <details className="download-settings">
            <summary>Advanced download settings</summary>
            <div className="url-download-options"><label>Output format<select value={downloadFormat} onChange={(event) => setDownloadFormat(event.target.value)}><option value="auto">Keep source format</option><option value="mp3">MP3 audio</option><option value="m4a">M4A audio</option><option value="opus">Opus audio</option><option value="ogg">OGG audio</option><option value="wav">WAV audio</option><option value="mp4">MP4 video</option></select></label>{downloadFormat !== 'auto' && <label>Quality<select value={downloadBitrate} onChange={(event) => setDownloadBitrate(event.target.value)}><option value="128">128 kbps</option><option value="192">192 kbps</option><option value="256">256 kbps</option><option value="320">320 kbps</option></select></label>}</div>
            <p>Keep source format uses Cobalt’s defaults; yt-dlp keeps its MP3 default. An explicit format is converted with FFmpeg.</p>
          </details>
          <div className="search-underbar"><button className="advanced-toggle" type="button" aria-expanded={advancedOpen} onClick={() => setAdvancedOpen((open) => !open)}>{advancedOpen ? 'Hide search options' : 'Advanced search'} <span>{advancedOpen ? '−' : '+'}</span></button><p className="search-hint">Search Apple’s music catalog. No sign-in needed.</p></div>
          {advancedOpen && <div className="advanced-search"><label htmlFor="search-field">Search in</label><select id="search-field" value={searchField} onChange={(event) => setSearchField(event.target.value)}><option value="all">Song, artist, or album</option><option value="song">Song title</option><option value="artist">Artist</option><option value="album">Album</option></select><span>Explicit results are filtered out for family-friendly browsing.</span><button className="advanced-submit" type="button" disabled={loading || !query.trim()} onClick={() => void runSearch(query, searchField)}>Search this field <ArrowRight size={14} /></button></div>}
          </div>
        <div className="hero-art" aria-hidden="true">
          <div className="orb orb-one" /><div className="orb orb-two" /><div className="orb orb-three" />
          <div className="art-halo" />
          <div className={`art-disc ${player.isPlaying ? 'disc-playing' : ''}`}><div className="disc-groove groove-one" /><div className="disc-groove groove-two" /><div className="disc-groove groove-three" /><div className="disc-label"><AudioLines size={22} /></div></div>
          <div className="art-note note-top">SIDE A <span>01 — 08</span></div>
          <div className="art-note note-bottom"><span className="playing-bars"><i /><i /><i /><i /></span> made for this moment</div>
          <div className="art-spark spark-a">✳</div><div className="art-spark spark-b">✳</div>
        </div>
        <a className="scroll-cue" href="#discover"><span>Take a look around</span><ArrowDownRight size={16} /></a>
      </section>

      {activeTab === 'discover' && <>
      {(loading || searchError || response) && <section className="search-results" id="search-results" aria-live="polite">
        {loading && <div className="search-state"><span className="spinner" /> Searching the music catalog…</div>}
        {searchError && <div className="search-state search-error" role="alert">{searchError}</div>}
        {response && <>
          <div className="section-heading result-heading"><div><p className="eyebrow">Apple Music catalog</p><h2>Results for “{response.query}”</h2></div><div className="result-tools"><span className="result-count">{response.results.length} tracks · {downloadFormat === 'auto' ? 'source format' : downloadFormat.toUpperCase()}</span></div></div>
          {response.results.length ? <div className="track-list">{response.results.map((track) => <article className="track-row" key={track.id}>
            <Artwork track={track} /><div className="track-main"><h3>{track.title}</h3><p>{track.artist}{track.album ? ` · ${track.album}` : ''}</p><span className="track-source">APPLE MUSIC CATALOG</span></div>
            <span className="track-duration">{formatDuration(track.duration_ms)}</span>
            <button type="button" className="icon-action preview-action" onClick={() => track.preview_url ? player.playTrack(track) : setNotice('A preview is not available for this track.')} disabled={!track.preview_url} title={track.preview_url ? 'Preview song' : 'Preview not available'}><Play size={15} fill="currentColor" /><span>Preview</span></button>
            <button type="button" className="icon-action review-action" onClick={() => void loadReviews(track)} title="Read or write a review"><MessageCircle size={17} /><span>Reviews</span></button>
            <button type="button" className="save-track" onClick={() => saveTrack(track)} disabled={savingTrackId === track.id} title={user ? 'Choose a playlist' : 'Sign in to save'}><Plus size={17} /><span>Save</span></button>
            <button type="button" className="icon-action quick-download" onClick={() => void startDownload(track)} disabled={downloadingTrackId === track.id} title={user ? 'Find and download this track' : 'Sign in to download'}><Download size={15} /><span>{downloadingTrackId === track.id ? 'Adding…' : 'Quick download'}</span></button>
            {track.source_url && <a className="icon-action source-action" href={track.source_url} target="_blank" rel="noreferrer" aria-label="Open track in Apple Music">Apple Music <ArrowUpRight size={14} /></a>}
          </article>)}</div> : <div className="empty-results">No matching tracks came back. Try a shorter song title or search by artist.</div>}
        </>}
      </section>}

      <section className="discovery section-wrap" id="discover">
        <div className="section-heading"><div><p className="eyebrow">A place to begin</p><h2>What sounds like <em>you</em> today?</h2></div><button className="text-link button-link" type="button" onClick={() => void runSearch('mellow music')}>Explore music <ArrowUpRight size={16} /></button></div>
        <div className="mood-grid" id="moods">
          {moods.map((mood, index) => {
            const section = discover.find((item) => item.id === mood.id)
            return <button className={`mood-card mood-${mood.color}`} key={mood.id} onClick={() => void runSearch(section?.query ?? mood.name)}>
              <span className="mood-topline"><span>0{index + 1} / LISTENING NOTES</span><ArrowUpRight size={17} /></span>
              <span className="mood-art" aria-hidden="true"><i className="mood-shape shape-a" /><i className="mood-shape shape-b" /><i className="mood-shape shape-c" />{index === 1 ? <Sparkles size={23} /> : <Disc3 size={26} />}</span>
              <span className="mood-info"><span><strong>{mood.name}</strong><small>{section?.tracks?.[0] ? `${section.tracks[0].title} · ${section.tracks[0].artist}` : mood.note}</small></span><i className="mood-arrow"><ArrowRight size={17} /></i></span>
            </button>
          })}
        </div>
        <p className="sample-note"><Sparkles size={14} /> A few starting points from Apple’s catalog. Mood labels are editorial prompts, not personalized recommendations.</p>
      </section>

      <section className="collection-band" id="playlists">
        <div className="collection-icon"><Headphones size={22} strokeWidth={1.5} /></div>
        <div><p className="eyebrow">Your corner of the library</p><h2>Good music deserves<br />a place to <em>stay.</em></h2><p className="collection-copy">Save the songs you love, shape them into playlists, and keep the feeling close.</p></div>
        <div className="collection-cta"><span>{user ? `${playlists.length} PLAYLIST${playlists.length === 1 ? '' : 'S'} IN YOUR LIBRARY` : 'YOUR PLAYLISTS, YOUR WAY'}</span><button type="button" onClick={() => user ? setManagerOpen(true) : void handleSignIn()}><>{user ? 'Open your library' : 'Sign in to begin'} <ArrowRight size={16} /></></button><button className="create-playlist-link" type="button" onClick={() => openCreatePlaylist()}><Plus size={15} /> Create playlist</button></div>
        <div className="collection-orbit orbit-a" /><div className="collection-orbit orbit-b" />
      </section>
      </>}

      {activeTab !== 'discover' && <MediaWorkspace tab={activeTab} user={Boolean(user)} getToken={getToken} onNotice={setNotice} onPlay={player.playTrack} onEditJob={(jobId) => { setEditorJobId(jobId); setActiveTab('editor') }} editorJobId={editorJobId} />}

      <footer className="footer" id="about"><a className="wordmark footer-brand" href="#top"><span className="brand-mark"><AudioLines size={17} /></span>sunlena</a><p>Made with care, for the songs we keep.</p><span className="footer-meta">CATALOG BY APPLE <span>© 2026</span></span></footer>

      <dialog className="app-dialog account-dialog" ref={accountDialog} onClose={() => setAccountOpen(false)} aria-labelledby="account-title">
        {user && <><div className="dialog-head"><div><p className="eyebrow">Your SunLena account</p><h2 id="account-title">Good to have you.</h2></div><button className="dialog-close" type="button" onClick={() => setAccountOpen(false)} aria-label="Close"><X size={20} /></button></div><div className="account-profile"><span className="account-large-avatar">{user.photoURL ? <img src={user.photoURL} alt="" /> : (user.displayName || user.email || 'S').slice(0, 1).toUpperCase()}</span><div><strong>{user.displayName || 'SunLena listener'}</strong><small>{user.email}</small><small>Signed in with Google</small></div></div><p className="account-privacy">Your playlists and reviews are tied to this Google sign-in. Private playlists are visible only to you; a share link is available only when you make one public.</p><div className="account-actions"><a className="quiet-button" href="https://myaccount.google.com/" target="_blank" rel="noreferrer">Google account <ArrowUpRight size={14} /></a><button className="danger-button" type="button" onClick={() => { void signOutUser(); setAccountOpen(false) }}><LogOut size={14} /> Sign out</button></div></>}
      </dialog>

      <dialog className="app-dialog create-dialog" ref={createDialog} onClose={() => setCreateOpen(false)} aria-labelledby="create-title">
        <div className="dialog-head"><div><p className="eyebrow">A new collection</p><h2 id="create-title">Make it yours.</h2></div><button className="dialog-close" type="button" onClick={() => setCreateOpen(false)} aria-label="Close"><X size={20} /></button></div>
        <form onSubmit={(event) => void submitCreatePlaylist(event)} className="dialog-form"><label>Playlist name<input autoFocus value={newTitle} maxLength={100} required onChange={(event) => setNewTitle(event.target.value)} placeholder="Sunday morning" /></label><label>A note, if you like<textarea value={newDescription} maxLength={500} onChange={(event) => setNewDescription(event.target.value)} placeholder="What does this collection feel like?" rows={3} /></label><div className="dialog-actions"><button type="button" className="quiet-button" onClick={() => { setCreateOpen(false); setPendingSaveTrack(null) }}>Cancel</button><button type="submit" className="primary-button" disabled={creating}>{creating ? 'Creating…' : pendingSaveTrack ? 'Create & save song' : 'Create playlist'} <ArrowRight size={16} /></button></div></form>
      </dialog>

      <dialog className="app-dialog save-track-dialog" ref={saveDialog} onClose={() => setSaveTrackTarget(null)} aria-labelledby="save-track-title">
        {saveTrackTarget && <><div className="dialog-head"><div><p className="eyebrow">A song to keep close</p><h2 id="save-track-title">Choose a playlist.</h2><p className="shared-description">{saveTrackTarget.title} · {saveTrackTarget.artist}</p></div><button className="dialog-close" type="button" onClick={() => setSaveTrackTarget(null)} aria-label="Close"><X size={20} /></button></div>
          <form className="save-playlist-form" onSubmit={(event) => void confirmSaveTrack(event)}><div className="save-playlist-options">{playlists.map((playlist) => <label className={`save-playlist-option ${savePlaylistId === playlist.id ? 'selected' : ''}`} key={playlist.id}><input type="radio" name="save-playlist" value={playlist.id} checked={savePlaylistId === playlist.id} onChange={() => setSavePlaylistId(playlist.id)} /><ListMusic size={18} /><span><strong>{playlist.title}</strong><small>{playlist.items.length} tracks · {playlist.visibility}</small></span></label>)}</div><div className="dialog-actions"><button type="button" className="quiet-button" onClick={() => { setSaveTrackTarget(null); openCreatePlaylist(saveTrackTarget) }}><Plus size={14} /> New playlist</button><button type="submit" className="primary-button" disabled={savingTrackId === saveTrackTarget.id || !savePlaylistId}>{savingTrackId === saveTrackTarget.id ? 'Saving…' : 'Save song'} <ArrowRight size={15} /></button></div></form>
        </>}
      </dialog>

      <dialog className="app-dialog manager-dialog" ref={managerDialog} onClose={() => setManagerOpen(false)} aria-labelledby="library-title">
        <div className="dialog-head"><div><p className="eyebrow">Your corner of the library</p><h2 id="library-title">Your playlists</h2></div><div className="dialog-head-actions"><button className="primary-button compact-button" type="button" onClick={() => openCreatePlaylist()}><Plus size={15} /> New playlist</button><button className="dialog-close" type="button" onClick={() => setManagerOpen(false)} aria-label="Close"><X size={20} /></button></div></div>
        {!user ? <p className="dialog-empty">Sign in with Google to see your private library.</p> : playlists.length === 0 ? <div className="dialog-empty"><ListMusic size={28} /><p>Your library is ready for its first playlist.</p><button className="primary-button" onClick={() => openCreatePlaylist()} type="button">Create a playlist <ArrowRight size={16} /></button></div> : <div className="library-layout">
          <div className="library-sidebar" aria-label="Playlist list">{playlists.map((playlist) => <button className={`playlist-choice ${selectedPlaylistId === playlist.id ? 'selected' : ''}`} key={playlist.id} onClick={() => setSelectedPlaylistId(playlist.id)}><ListMusic size={17} /><span><strong>{playlist.title}</strong><small>{playlist.items.length} tracks · {playlist.visibility}</small></span></button>)}</div>
          {selectedPlaylist && <section className="playlist-detail">
            <div className="playlist-listen-tools"><button className="quiet-button" type="button" onClick={() => void playPlaylist(selectedPlaylist)}><Play size={14} fill="currentColor" /> Play playlist</button><button className="quiet-button" type="button" onClick={() => void playPlaylist(selectedPlaylist, true)}><Sparkles size={14} /> Shuffle</button></div>
            <form className="playlist-edit" onSubmit={async (event) => { event.preventDefault(); const token = await getToken(); if (!token) return; try { const updated = await updatePlaylist(token, selectedPlaylist.id, { title: selectedPlaylist.title, description: selectedPlaylist.description ?? '' }); setPlaylists((rows) => rows.map((row) => row.id === updated.id ? updated : row)); setNotice('Playlist details saved.') } catch (error) { setNotice(error instanceof Error ? error.message : 'Could not update playlist.') } }}>
              <input aria-label="Playlist name" value={selectedPlaylist.title} maxLength={100} onChange={(event) => setPlaylists((rows) => rows.map((row) => row.id === selectedPlaylist.id ? { ...row, title: event.target.value } : row))} />
              <textarea aria-label="Playlist description" value={selectedPlaylist.description ?? ''} maxLength={500} onChange={(event) => setPlaylists((rows) => rows.map((row) => row.id === selectedPlaylist.id ? { ...row, description: event.target.value } : row))} placeholder="Add a note" rows={2} />
              <div className="playlist-tools"><button className="quiet-button" type="submit">Save details</button><button className="quiet-button" type="button" onClick={() => void changeVisibility(selectedPlaylist)}>{selectedPlaylist.visibility === 'public' ? 'Make private' : 'Create share link'}</button>{selectedPlaylist.visibility === 'public' && <button className="quiet-button" type="button" onClick={() => setSharePlaylist(selectedPlaylist)}>Share</button>}<button className="danger-button" type="button" onClick={() => void removePlaylist(selectedPlaylist)}><Trash2 size={14} /> Delete</button></div>
            </form>
            <div className="playlist-items">{selectedPlaylist.items.length ? selectedPlaylist.items.map((item, index) => <div className="playlist-item" key={item.id}><Artwork track={item.track} /><div><strong>{item.track.title}</strong><small>{item.track.artist}</small></div>{item.track.source_url && <a className="icon-action mini-source" href={item.track.source_url} target="_blank" rel="noreferrer">Apple Music <ArrowUpRight size={12} /></a>}<div className="item-controls"><button type="button" disabled={index === 0} onClick={() => void movePlaylistItem(index, -1)} aria-label="Move track up">↑</button><button type="button" disabled={index === selectedPlaylist.items.length - 1} onClick={() => void movePlaylistItem(index, 1)} aria-label="Move track down">↓</button><button type="button" onClick={() => void removeItem(item.id)} aria-label="Remove track"><X size={14} /></button></div></div>) : <p className="empty-results">Search for a song and choose Save to add it here.</p>}</div>
          </section>}
        </div>}
      </dialog>

      <dialog className="app-dialog review-dialog" ref={reviewDialog} onClose={() => setActiveTrack(null)} aria-labelledby="review-title">
        {activeTrack && <><div className="dialog-head"><div className="dialog-track"><Artwork track={activeTrack} /><span><p className="eyebrow">Track notes</p><h2 id="review-title">{activeTrack.title}</h2><small>{activeTrack.artist}</small>{activeTrack.source_url && <a className="apple-music-link" href={activeTrack.source_url} target="_blank" rel="noreferrer">View this track on Apple Music <ArrowUpRight size={13} /></a>}</span></div><button className="dialog-close" type="button" onClick={() => setActiveTrack(null)} aria-label="Close"><X size={20} /></button></div>
          {reviewData && <div className="review-summary"><span className="rating-stars">{'★'.repeat(Math.round(reviewData.average_rating ?? 0))}{'☆'.repeat(5 - Math.round(reviewData.average_rating ?? 0))}</span><span>{reviewData.average_rating ? `${reviewData.average_rating} average` : 'No ratings yet'} · {reviewData.count} {reviewData.count === 1 ? 'review' : 'reviews'}</span></div>}
          <div className="review-list">{reviewData?.reviews.length ? reviewData.reviews.map((review) => <article className="review-card" key={review.id}><span className="rating-stars">{'★'.repeat(review.rating)}{'☆'.repeat(5 - review.rating)}</span><p>{review.body || 'A rating, without a note.'}</p></article>) : <p className="dialog-empty">Be the first to leave a note about this track.</p>}</div>
          <form className="review-form" onSubmit={(event) => void submitReview(event)}><p className="eyebrow">{myReview ? 'Edit your review' : 'Your review'}</p><div className="rating-picker" aria-label="Choose a rating">{[1, 2, 3, 4, 5].map((rating) => <button type="button" key={rating} aria-label={`${rating} stars`} aria-pressed={reviewRating === rating} onClick={() => setReviewRating(rating)}><Star size={20} fill={rating <= reviewRating ? 'currentColor' : 'none'} /></button>)}</div><textarea value={reviewBody} onChange={(event) => setReviewBody(event.target.value)} maxLength={1000} rows={3} placeholder="What stayed with you?" /><div className="review-submit"><small>{reviewBody.length}/1000 · Sign in required</small><button className="primary-button" type="submit" disabled={reviewBusy || !user}>{reviewBusy ? 'Saving…' : 'Save review'} <ArrowRight size={15} /></button></div>{myReview && <button className="danger-button review-delete" type="button" onClick={() => void removeReview()}>Delete my review</button>}</form>
        </>}
      </dialog>

      <dialog className="app-dialog share-dialog" ref={shareDialog} onClose={() => setSharePlaylist(null)} aria-labelledby="share-title">
        <div className="dialog-head"><div><p className="eyebrow">Anyone with the link can view</p><h2 id="share-title">Share playlist</h2></div><button className="dialog-close" type="button" onClick={() => setSharePlaylist(null)} aria-label="Close"><X size={20} /></button></div>
        {sharePlaylist?.share_token ? <><p className="share-description">The link is secret, unlisted, and can be revoked by making this playlist private.</p><div className="share-link-box">{`${window.location.origin}/?share=${sharePlaylist.share_token}`}</div><button className="primary-button" type="button" onClick={() => copyShareLink(sharePlaylist)}><Check size={16} /> Copy link</button></> : <p className="dialog-empty">The private share token is only displayed when created. Make the playlist private and public again to rotate and reveal a new link.</p>}
      </dialog>

      <dialog className="app-dialog shared-dialog" ref={sharedDialog} onClose={() => setSharedPlaylist(null)} aria-labelledby="shared-title">
        {sharedPlaylist && <><div className="dialog-head"><div><p className="eyebrow">A shared collection</p><h2 id="shared-title">{sharedPlaylist.title}</h2><p className="shared-description">{sharedPlaylist.description}</p></div><button className="dialog-close" type="button" onClick={() => setSharedPlaylist(null)} aria-label="Close"><X size={20} /></button></div><div className="playlist-items">{sharedPlaylist.items.map((item) => <div className="playlist-item" key={item.id}><Artwork track={item.track} /><div><strong>{item.track.title}</strong><small>{item.track.artist}</small></div>{item.track.source_url && <a href={item.track.source_url} className="icon-action mini-source" target="_blank" rel="noreferrer">Apple Music <ArrowUpRight size={12} /></a>}</div>)}</div></>}
      </dialog>
    </main>
  )
}
