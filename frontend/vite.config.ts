import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

/**
 * Dev-server configuration.
 *
 * The UI calls the backend through the `/api` prefix; in development Vite proxies
 * `/api/*` to the FastAPI server (strip the prefix, so `/api/health` -> `/health`).
 * Override the target with FLYBRAIN_BACKEND_URL and the port with FLYBRAIN_FRONTEND_PORT.
 */
const backendUrl = process.env['FLYBRAIN_BACKEND_URL'] ?? 'http://127.0.0.1:8000'
const frontendPort = Number(process.env['FLYBRAIN_FRONTEND_PORT'] ?? 5173)

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: frontendPort,
    strictPort: true,
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
