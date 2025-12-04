import { defineConfig } from 'vite'
import fs from 'fs'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const useHttps = process.env.HTTPS === 'true'
  const certPath = process.env.SSL_CRT_FILE || 'certs/dev.crt'
  const keyPath = process.env.SSL_KEY_FILE || 'certs/dev.key'
  const proxyTarget = process.env.API_PROXY_TARGET || 'http://localhost:8000'
  let https: any = undefined
  if (useHttps) {
    try {
      https = { cert: fs.readFileSync(certPath), key: fs.readFileSync(keyPath) }
    } catch {
      // fallback to true which lets Vite attempt self-signed
      https = true
    }
  }
  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      https,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          rewrite: (path: string) => path.replace(/^\/api/, ''),
        }
      }
    },
  }
})
