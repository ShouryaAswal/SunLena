import { ArrowDownToLine, AudioLines, Check, Clock3, Disc3, Edit3, Play, RotateCcw, Trash2, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { createMediaPlaybackUrl, deleteMediaJob, editMediaFile, getMediaJobs, type MediaJob, type SearchResult } from '../lib/api'

type Props = {
  tab: 'downloads' | 'editor'
  user: boolean
  getToken: () => Promise<string | null>
  onNotice: (message: string) => void
  onPlay: (track: SearchResult, source: string) => void
  onEditJob: (jobId: string) => void
  editorJobId: string
}

const formatNames: Record<string, string> = { mp3: 'MP3', aac: 'AAC', ogg: 'OGG', mp4: 'MP4', wav: 'WAV', flac: 'FLAC' }
function fileSize(size?: number | null) {
  if (!size) return '—'
  return size > 1024 * 1024 ? `${(size / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(size / 1024)} KB`
}
function titleTrack(job: MediaJob): SearchResult {
  return { id: job.track_id, title: job.title || 'SunLena download', artist: job.artist || '', source: 'download' }
}

export default function MediaWorkspace({ tab, user, getToken, onNotice, onPlay, onEditJob, editorJobId }: Props) {
  const [jobs, setJobs] = useState<MediaJob[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState(editorJobId)
  const [editing, setEditing] = useState(false)
  const [previewUrl, setPreviewUrl] = useState('')
  const [trimStart, setTrimStart] = useState('0')
  const [trimEnd, setTrimEnd] = useState('')
  const [fadeIn, setFadeIn] = useState('0')
  const [fadeOut, setFadeOut] = useState('0')
  const [bass, setBass] = useState(0)
  const [treble, setTreble] = useState(0)
  const [volume, setVolume] = useState(0)
  const [speed, setSpeed] = useState(1)
  const [outputFormat, setOutputFormat] = useState('mp3')
  const [quality, setQuality] = useState('192')
  const [outputBlob, setOutputBlob] = useState<Blob | null>(null)

  const refresh = useCallback(async () => {
    const token = await getToken()
    if (!token) { setJobs([]); return }
    setLoading(true)
    try { setJobs(await getMediaJobs(token)); setError('') }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Downloads could not be loaded.') }
    finally { setLoading(false) }
  }, [getToken])

  useEffect(() => { if (user) void refresh(); else setJobs([]) }, [user, refresh])
  const hasActive = jobs.some((job) => job.status === 'queued' || job.status === 'running')
  useEffect(() => {
    if (!user || !hasActive) return
    const timer = window.setInterval(() => { void refresh() }, 2200)
    return () => window.clearInterval(timer)
  }, [user, hasActive, refresh])
  useEffect(() => { if (editorJobId) setSelectedId(editorJobId) }, [editorJobId])
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])

  const completed = useMemo(() => jobs.filter((job) => job.status === 'completed'), [jobs])
  const selected = completed.find((job) => job.id === selectedId) ?? completed[0] ?? null
  const qualityOptions = outputFormat === 'aac' || outputFormat === 'mp4' ? ['128', '192', '256'] : outputFormat === 'mp3' || outputFormat === 'ogg' ? ['128', '192', '320'] : ['lossless']

  async function withToken() {
    const token = await getToken()
    if (!token) throw new Error('Sign in with Google to manage your downloads.')
    return token
  }

  async function downloadFile(job: MediaJob) {
    try {
      const token = await withToken()
      const url = await createMediaPlaybackUrl(token, job.id, false)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = job.file_name || `${job.title || 'sunlena-track'}.${job.output_format}`
      anchor.click()
    } catch (cause) { onNotice(cause instanceof Error ? cause.message : 'The file could not be downloaded.') }
  }

  async function playFile(job: MediaJob) {
    try {
      const token = await withToken()
      const url = await createMediaPlaybackUrl(token, job.id, true)
      onPlay(titleTrack(job), url)
    } catch (cause) { onNotice(cause instanceof Error ? cause.message : 'The file could not be played.') }
  }

  async function removeFile(job: MediaJob) {
    if (!window.confirm(`Remove “${job.file_name || job.title}” from your SunLena downloads?`)) return
    try { await deleteMediaJob(await withToken(), job.id); await refresh(); onNotice('Download removed from your library.') }
    catch (cause) { onNotice(cause instanceof Error ? cause.message : 'Could not remove this download.') }
  }

  async function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected) return
    setEditing(true); setOutputBlob(null)
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl('')
    try {
      const form = new FormData()
      form.set('job_id', selected.id)
      form.set('trim_start_ms', String(Math.max(0, Number(trimStart) || 0) * 1000))
      form.set('trim_end_ms', trimEnd ? String(Math.max(1, Number(trimEnd)) * 1000) : '-1')
      form.set('fade_in_ms', String(Math.max(0, Number(fadeIn) || 0) * 1000))
      form.set('fade_out_ms', String(Math.max(0, Number(fadeOut) || 0) * 1000))
      form.set('bass_boost_db', String(bass)); form.set('treble_boost_db', String(treble))
      form.set('volume_change_db', String(volume)); form.set('speed_factor', String(speed))
      form.set('output_format', outputFormat); form.set('output_quality', quality)
      const blob = await editMediaFile(await withToken(), form)
      const url = URL.createObjectURL(blob)
      setOutputBlob(blob); setPreviewUrl(url); onNotice('Your new mix is ready to preview or save.')
    } catch (cause) { onNotice(cause instanceof Error ? cause.message : 'Audio editing could not be completed.') }
    finally { setEditing(false) }
  }

  function saveEditedFile() {
    if (!previewUrl || !outputBlob) return
    const anchor = document.createElement('a'); anchor.href = previewUrl
    anchor.download = `${(selected?.title || 'sunlena-track').replace(/[^\p{L}\p{N} ._-]/gu, '').trim()}-edited.${outputFormat}`
    anchor.click()
  }

  return <section className="media-workspace section-wrap">
    <div className="media-title-row"><div><p className="eyebrow"><span className="eyebrow-line" />Your listening room</p><h1>{tab === 'downloads' ? <>Made to <em>keep.</em></> : <>Shape the <em>sound.</em></>}</h1><p>{tab === 'downloads' ? 'Your recent files, ready when the moment is.' : 'A small studio for the details that make a track yours.'}</p></div>{tab === 'downloads' ? <span className="media-count"><Disc3 size={18} /> {completed.length} READY</span> : <span className="media-count"><AudioLines size={18} /> SUNLENA STUDIO</span>}</div>
    {!user ? <div className="media-empty"><AudioLines size={28} /><h2>Your library is waiting</h2><p>Sign in with Google to keep downloads private to your account.</p></div> : error ? <div className="media-empty media-error">{error}<button className="quiet-button" type="button" onClick={() => void refresh()}><RotateCcw size={14} /> Try again</button></div> : tab === 'downloads' ? <>
      <div className="media-subheading"><div><h2>Recent downloads</h2><p>Search a song and choose Quick download to add it here.</p></div><button className="quiet-button" type="button" onClick={() => void refresh()}><RotateCcw size={14} /> Refresh</button></div>
        {loading && !jobs.length ? <div className="media-empty"><span className="spinner" /> Loading your library…</div> : jobs.length ? <div className="download-list">{jobs.map((job) => <article className="download-card" key={job.id}><span className={`download-art ${job.status === 'running' ? 'processing' : ''}`}>{job.status === 'completed' ? <Disc3 size={23} /> : job.status === 'failed' ? <X size={21} /> : <AudioLines size={22} />}</span><div className="download-meta"><div className="download-name"><strong>{job.title || 'Untitled track'}</strong><span>{job.output_format.toUpperCase()} · {job.status === 'completed' ? fileSize(job.file_size) : job.stage}</span></div><small>{job.artist}{job.source_title && job.source_title !== job.title ? ` · Found: ${job.source_title}` : ''}</small>{job.status === 'queued' || job.status === 'running' ? <div className="progress-track" role="progressbar" aria-label={`${job.title} download progress`} aria-valuenow={job.progress} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${job.progress}%` }} /></div> : job.status === 'failed' ? <small className="download-failure">{job.error || 'Try again from search.'}</small> : <small className="download-ready"><Check size={12} /> Ready to listen · {new Date(job.created_at).toLocaleDateString()}</small>}</div><div className="download-actions">{job.status === 'completed' && <><button className="download-icon-action" type="button" title="Play" onClick={() => void playFile(job)}><Play size={16} fill="currentColor" /></button><button className="download-icon-action" type="button" title="Edit audio" onClick={() => { setSelectedId(job.id); onEditJob(job.id) }}><Edit3 size={16} /></button><button className="download-icon-action" type="button" title="Save file to device" onClick={() => void downloadFile(job)}><ArrowDownToLine size={17} /></button></>}<button className="download-icon-action delete-download" type="button" title="Remove download" disabled={job.status === 'running'} onClick={() => void removeFile(job)}><Trash2 size={15} /></button></div></article>)}</div> : <div className="media-empty"><Clock3 size={28} /><h2>A little room for what you love</h2><p>Your downloads will show here with progress while they are being prepared.</p></div>}
      <p className="media-footnote">Your files stay in your private SunLena library on this server. Save a copy to your device for offline listening.</p>
    </> : <>
      <div className="editor-layout"><div className="editor-controls"><div className="editor-select"><label htmlFor="edit-source">Choose a downloaded track</label><select id="edit-source" value={selected?.id ?? ''} onChange={(event) => { setSelectedId(event.target.value); setOutputBlob(null); if (previewUrl) URL.revokeObjectURL(previewUrl); setPreviewUrl('') }}><option value="">Select from your downloads</option>{completed.map((job) => <option key={job.id} value={job.id}>{job.title} — {job.artist}</option>)}</select></div>
        {selected ? <><div className="editor-source"><Disc3 size={18} /><span><strong>{selected.title}</strong><small>{selected.artist} · {selected.output_format.toUpperCase()}</small></span></div><form className="sound-form" onSubmit={(event) => void submitEdit(event)}>
          <div className="editor-field-pair"><label>Trim start · seconds<input type="number" min="0" max="1800" step="0.1" value={trimStart} onChange={(event) => setTrimStart(event.target.value)} /></label><label>Trim end · seconds<input type="number" min="0" max="1800" step="0.1" value={trimEnd} onChange={(event) => setTrimEnd(event.target.value)} placeholder="End of track" /></label></div>
          <label className="sound-slider">Bass <span>{bass > 0 ? '+' : ''}{bass} dB</span><input type="range" min="-12" max="12" step="1" value={bass} onChange={(event) => setBass(Number(event.target.value))} /></label>
          <label className="sound-slider">Treble <span>{treble > 0 ? '+' : ''}{treble} dB</span><input type="range" min="-12" max="12" step="1" value={treble} onChange={(event) => setTreble(Number(event.target.value))} /></label>
          <label className="sound-slider">Volume <span>{volume > 0 ? '+' : ''}{volume} dB</span><input type="range" min="-12" max="12" step="1" value={volume} onChange={(event) => setVolume(Number(event.target.value))} /></label>
          <div className="editor-field-pair"><label>Fade in · seconds<input type="number" min="0" max="30" step="0.5" value={fadeIn} onChange={(event) => setFadeIn(event.target.value)} /></label><label>Fade out · seconds<input type="number" min="0" max="30" step="0.5" value={fadeOut} onChange={(event) => setFadeOut(event.target.value)} /></label></div>
          <label className="editor-speed">Playback speed <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))}><option value="0.5">0.5×</option><option value="0.75">0.75×</option><option value="1">Original</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option><option value="2">2×</option></select></label>
          <div className="editor-field-pair"><label>Export format<select value={outputFormat} onChange={(event) => { const next = event.target.value; setOutputFormat(next); setQuality(next === 'flac' || next === 'wav' ? 'lossless' : '192') }}><option value="mp3">MP3</option><option value="aac">AAC</option><option value="ogg">OGG Vorbis</option><option value="mp4">MP4 · audio track</option><option value="wav">WAV · lossless</option><option value="flac">FLAC · lossless</option></select></label><label>Bitrate<select value={quality} onChange={(event) => setQuality(event.target.value)}>{qualityOptions.map((option) => <option key={option} value={option}>{option === 'lossless' ? 'Lossless' : `${option} kbps`}</option>)}</select></label></div>
          <button className="primary-button editor-render" type="submit" disabled={editing}>{editing ? <><span className="spinner" /> Rendering your mix…</> : <><AudioLines size={16} /> Apply edits</>}</button>
        </form></> : <div className="editor-no-source">{completed.length ? 'Choose a track above to begin editing.' : 'Download a track first, and it will be ready to edit here.'}</div>}</div>
        <div className="editor-preview"><div className={`studio-record ${editing ? 'record-rendering' : ''}`}><Disc3 size={130} strokeWidth={0.6} /><span><AudioLines size={22} /></span></div><p className="eyebrow">{outputBlob ? 'NEW MIX' : selected ? 'ORIGINAL FILE' : 'YOUR STUDIO'}</p><h2>{outputBlob ? 'Listen it over.' : 'Every detail, yours.'}</h2><p>{outputBlob ? 'Listen to the result, then save the new file to your device.' : 'Shape the dynamics and export a version that feels like you.'}</p>{previewUrl ? <><audio className="editor-audio" controls src={previewUrl} /><button className="primary-button" type="button" onClick={saveEditedFile}><ArrowDownToLine size={15} /> Save edited file · {formatNames[outputFormat] || outputFormat.toUpperCase()}</button></> : selected && <button className="quiet-button" type="button" onClick={() => void playFile(selected)}><Play size={14} fill="currentColor" /> Preview original</button>}</div></div>
      <p className="media-footnote">Editing creates a new file and leaves your original download untouched. WAV and FLAC preserve the decoded audio but cannot restore quality lost by a compressed source.</p>
    </>}
  </section>
}
