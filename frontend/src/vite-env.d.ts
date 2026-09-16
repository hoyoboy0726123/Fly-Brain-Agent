/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL for backend API calls. Defaults to `/api` (proxied by Vite in development). */
  readonly VITE_API_BASE_URL?: string
}
