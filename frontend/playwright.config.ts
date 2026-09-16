import { existsSync } from 'node:fs'
import path from 'node:path'

import { defineConfig, devices } from '@playwright/test'

/**
 * Frontend smoke tests (P0). Playwright starts BOTH servers:
 *   - FastAPI backend  (uvicorn) on FLYBRAIN_BACKEND_PORT  (default 8000)
 *   - Vite dev server            on FLYBRAIN_FRONTEND_PORT (default 5173)
 * and points Vite's `/api` proxy at the backend. Set FLYBRAIN_PYTHON to choose the
 * interpreter; otherwise `backend/.venv` is used when present, else `python3`.
 */
const frontendDir = import.meta.dirname
const backendDir = path.resolve(frontendDir, '..', 'backend')

const backendPort = Number(process.env['FLYBRAIN_BACKEND_PORT'] ?? 8000)
const frontendPort = Number(process.env['FLYBRAIN_FRONTEND_PORT'] ?? 5173)
const backendUrl = `http://127.0.0.1:${backendPort}`
const frontendUrl = `http://127.0.0.1:${frontendPort}`

function resolvePython(): string {
  const fromEnv = process.env['FLYBRAIN_PYTHON']
  if (fromEnv) return fromEnv
  const candidates = [
    path.join(backendDir, '.venv', 'bin', 'python'),
    path.join(backendDir, '.venv', 'Scripts', 'python.exe'),
  ]
  return candidates.find((candidate) => existsSync(candidate)) ?? 'python3'
}

const isCI = Boolean(process.env['CI'])

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  reporter: isCI ? 'github' : 'list',
  use: {
    baseURL: frontendUrl,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `"${resolvePython()}" -m uvicorn app.main:app --host 127.0.0.1 --port ${backendPort} --log-level warning`,
      cwd: backendDir,
      url: `${backendUrl}/health`,
      reuseExistingServer: !isCI,
      timeout: 60_000,
    },
    {
      command: 'npm run dev',
      cwd: frontendDir,
      env: {
        FLYBRAIN_FRONTEND_PORT: String(frontendPort),
        FLYBRAIN_BACKEND_URL: backendUrl,
      },
      url: frontendUrl,
      reuseExistingServer: !isCI,
      timeout: 60_000,
    },
  ],
})
