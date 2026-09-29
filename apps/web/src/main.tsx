import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './pages/HomePage'
import './styles/global.css'
import { AuthProvider } from './lib/auth'
import { AudioPlayerProvider } from './lib/audioPlayer'
import './styles/media.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider><AudioPlayerProvider><App /></AudioPlayerProvider></AuthProvider>
  </React.StrictMode>,
)
