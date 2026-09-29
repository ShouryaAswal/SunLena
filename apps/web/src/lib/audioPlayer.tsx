import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Pause, Play, Shuffle, SkipBack, SkipForward, Volume2, X } from 'lucide-react'
import type { SearchResult } from './api'

export type QueueEntry = { track: SearchResult; source?: string | null; resolveSource?: () => Promise<string | null> }
type PlayerValue = {
  current: SearchResult | null
  isPlaying: boolean
  playTrack: (track: SearchResult, source?: string) => void
  playQueue: (tracks: SearchResult[], shuffle?: boolean) => void
  playEntries: (entries: QueueEntry[], shuffle?: boolean) => void
}
const PlayerContext = createContext<PlayerValue | null>(null)

export function useAudioPlayer() {
  const value = useContext(PlayerContext)
  if (!value) throw new Error('useAudioPlayer must be used inside AudioPlayerProvider.')
  return value
}

function timeLabel(seconds: number) {
  if (!Number.isFinite(seconds)) return '0:00'
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
}

export function AudioPlayerProvider({ children }: { children: ReactNode }) {
  const audio = useRef<HTMLAudioElement>(null)
  const objectSource = useRef('')
  const [queue, setQueue] = useState<QueueEntry[]>([])
  const [index, setIndex] = useState(0)
  const [activeSource, setActiveSource] = useState('')
  const [isPlaying, setPlaying] = useState(false)
  const [shuffle, setShuffle] = useState(false)
  const [position, setPosition] = useState(0)
  const [duration, setDuration] = useState(0)
  const current = queue[index]?.track ?? null
  const entry = queue[index]
  const source = activeSource

  const playTrack = useCallback((track: SearchResult, fileSource?: string) => {
    const url = fileSource ?? track.preview_url
    if (!url) return
    setQueue([{ track, source: url }])
    setIndex(0)
    setActiveSource(url)
    setPlaying(true)
  }, [])

  const playQueue = useCallback((tracks: SearchResult[], shuffled = false) => {
    const available = tracks.filter((track) => track.preview_url)
    if (!available.length) return
    const entries = shuffled ? [...available].sort(() => Math.random() - 0.5) : available
    playEntries(entries.map((track) => ({ track, source: track.preview_url })), shuffled)
  }, [])

  const playEntries = useCallback((entries: QueueEntry[], shuffled = false) => {
    const available = entries.filter((item) => item.source || item.resolveSource)
    if (!available.length) return
    const nextQueue = shuffled ? [...available].sort(() => Math.random() - 0.5) : available
    setQueue(nextQueue)
    setIndex(0)
    setActiveSource('')
    setShuffle(shuffled)
    setPlaying(true)
  }, [])

  const move = useCallback((direction: -1 | 1) => {
    setIndex((currentIndex) => {
      if (queue.length < 2) return currentIndex
      if (shuffle && direction === 1) {
        let next = currentIndex
        while (next === currentIndex) next = Math.floor(Math.random() * queue.length)
        return next
      }
      return (currentIndex + direction + queue.length) % queue.length
    })
    setPlaying(true)
  }, [queue.length, shuffle])

  useEffect(() => {
    let alive = true
    setActiveSource('')
    async function resolve() {
      const selectedSource = entry?.resolveSource ? await entry.resolveSource() : entry?.source ?? null
      if (alive) {
        setActiveSource(selectedSource ?? '')
        if (!selectedSource) setPlaying(false)
      }
    }
    void resolve().catch(() => { if (alive) setPlaying(false) })
    return () => { alive = false }
  }, [entry])

  useEffect(() => {
    const player = audio.current
    if (!player || !source) return
    if (objectSource.current && objectSource.current !== source && objectSource.current.startsWith('blob:')) {
      URL.revokeObjectURL(objectSource.current)
    }
    objectSource.current = source
    player.src = source
    player.load()
  }, [source])

  useEffect(() => {
    const player = audio.current
    if (!player || !source) return
    if (isPlaying) void player.play().catch(() => setPlaying(false))
    else player.pause()
  }, [isPlaying, source])

  useEffect(() => () => {
    if (objectSource.current.startsWith('blob:')) URL.revokeObjectURL(objectSource.current)
  }, [])

  const value = useMemo(() => ({ current, isPlaying, playTrack, playQueue, playEntries }), [current, isPlaying, playTrack, playQueue, playEntries])
  return <PlayerContext.Provider value={value}>
    {children}
    <aside className={`global-player ${isPlaying ? 'player-playing' : ''}`} aria-label="Music player">
      <div className="player-track">{current?.artwork_url ? <img src={current.artwork_url} alt="" /> : <span><Volume2 size={16} /></span>}<div><strong>{current?.title ?? 'Your listening room'}</strong><small>{current?.artist ?? 'Choose a preview or a download to begin'}</small></div></div>
      <div className="player-controls">
        <button type="button" aria-label="Play previous track" onClick={() => move(-1)} disabled={!current}><SkipBack size={17} fill="currentColor" /></button>
        <button type="button" className="player-main-control" aria-label={isPlaying ? 'Pause' : 'Play'} onClick={() => { setPlaying((playing) => !playing) }} disabled={!current}>{isPlaying ? <Pause size={17} fill="currentColor" /> : <Play size={17} fill="currentColor" />}</button>
        <button type="button" aria-label="Play next track" onClick={() => move(1)} disabled={!current}><SkipForward size={17} fill="currentColor" /></button>
        <button type="button" className={shuffle ? 'control-on' : ''} aria-label="Toggle shuffle" aria-pressed={shuffle} onClick={() => setShuffle((value) => !value)}><Shuffle size={15} /></button>
      </div>
      <div className="player-timeline"><span>{timeLabel(position)}</span><input aria-label="Playback position" type="range" min="0" max={duration || 1} step="0.1" value={Math.min(position, duration || 1)} onChange={(event) => { if (audio.current) audio.current.currentTime = Number(event.target.value) }} /><span>{timeLabel(duration)}</span></div>
      <audio ref={audio} onTimeUpdate={(event) => setPosition(event.currentTarget.currentTime)} onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)} onEnded={() => { if (queue.length > 1) move(1); else setPlaying(false) }} onPause={() => setPlaying(false)} onPlay={() => setPlaying(true)} />
      {!current && <button type="button" className="player-dismiss" aria-label="Player is idle"><X size={14} /></button>}
    </aside>
  </PlayerContext.Provider>
}
