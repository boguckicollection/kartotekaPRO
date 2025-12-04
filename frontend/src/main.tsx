import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'

const container = document.getElementById('root')!
createRoot(container).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)

// Register SW only in production builds
if ((import.meta as any).env?.PROD) {
  if (window.isSecureContext || location.hostname === 'localhost') {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {})
    }
  }
}

// PWA install prompt support
declare global { interface Window { deferredPrompt?: any } }
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault()
  window.deferredPrompt = e
})
