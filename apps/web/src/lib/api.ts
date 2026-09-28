export type SearchResult = {
  id: string
  title: string
  artist: string
  album?: string
  duration_ms?: number
  artwork_url?: string
  source_url?: string
  source: string
}

export type SearchResponse = {
  query: string
  results: SearchResult[]
  providers: Record<string, string>
}

export type PlaylistItem = { id: string; position: number; track: SearchResult }
export type Playlist = {
  id: string
  title: string
  description?: string | null
  visibility: 'private' | 'public'
  share_token?: string | null
  items: PlaylistItem[]
}
export type Review = { id: string; rating: number; body?: string | null; created_at?: string }
export type ReviewList = { count: number; average_rating: number | null; reviews: Review[] }
export type DiscoverySection = { id: string; title: string; query: string; status: string; tracks: SearchResult[] }

async function request<T>(path: string, token?: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(path, { ...init, headers })
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(payload?.detail ?? `Request failed (${response.status}).`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function searchTracks(query: string, signal?: AbortSignal, field = 'all'): Promise<SearchResponse> {
  return request(`/api/v1/search?q=${encodeURIComponent(query)}&field=${encodeURIComponent(field)}`, undefined, { signal })
}

export function getDiscover(): Promise<{ sections: DiscoverySection[] }> {
  return request('/api/v1/search/discover')
}

export function getPlaylists(token: string): Promise<Playlist[]> {
  return request('/api/v1/playlists', token)
}

export function createPlaylist(token: string, title: string, description: string): Promise<Playlist> {
  return request('/api/v1/playlists', token, { method: 'POST', body: JSON.stringify({ title, description }) })
}

export function updatePlaylist(token: string, playlistId: string, changes: Partial<Pick<Playlist, 'title' | 'description' | 'visibility'>>): Promise<Playlist> {
  return request(`/api/v1/playlists/${playlistId}`, token, { method: 'PATCH', body: JSON.stringify(changes) })
}

export function deletePlaylist(token: string, playlistId: string): Promise<void> {
  return request(`/api/v1/playlists/${playlistId}`, token, { method: 'DELETE' })
}

export function addTrack(token: string, playlistId: string, trackId: string): Promise<Playlist> {
  return request(`/api/v1/playlists/${playlistId}/items`, token, { method: 'POST', body: JSON.stringify({ track_id: trackId }) })
}

export function removePlaylistItem(token: string, playlistId: string, itemId: string): Promise<void> {
  return request(`/api/v1/playlists/${playlistId}/items/${itemId}`, token, { method: 'DELETE' })
}

export function reorderPlaylist(token: string, playlistId: string, itemIds: string[]): Promise<Playlist> {
  return request(`/api/v1/playlists/${playlistId}/items/order`, token, { method: 'PATCH', body: JSON.stringify({ item_ids: itemIds }) })
}

export function getReviews(trackId: string): Promise<ReviewList> {
  return request(`/api/v1/tracks/${trackId}/reviews`)
}

export function getMyReview(token: string, trackId: string): Promise<Review | null> {
  return request(`/api/v1/tracks/${trackId}/reviews/mine`, token)
}

export function saveReview(token: string, trackId: string, rating: number, body: string): Promise<Review> {
  return request(`/api/v1/tracks/${trackId}/reviews`, token, { method: 'PUT', body: JSON.stringify({ rating, body }) })
}

export function deleteReview(token: string, trackId: string): Promise<void> {
  return request(`/api/v1/tracks/${trackId}/reviews`, token, { method: 'DELETE' })
}
