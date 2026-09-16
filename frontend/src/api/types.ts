/** Typed mirror of backend `app.models.health.HealthResponse`. */
export interface HealthResponse {
  status: 'ok'
  service: string
  version: string
  environment: string
  phase: string
}

export function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return (
    record['status'] === 'ok' &&
    typeof record['service'] === 'string' &&
    typeof record['version'] === 'string' &&
    typeof record['environment'] === 'string' &&
    typeof record['phase'] === 'string'
  )
}
