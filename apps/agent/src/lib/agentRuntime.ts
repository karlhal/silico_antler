import type {
  AgentCachePolicy,
  AgentDesktopRuntimeConfig,
  AgentServiceHealth,
  AgentStartupHealth,
  AgentStartupHealthStatus
} from '../types'

declare global {
  interface Window {
    __TAURI__?: unknown
  }
}

type RuntimeTarget = 'desktop' | 'web'

type RuntimeEnv = ImportMetaEnv & {
  VITE_AGENT_API_BASE_URL?: string
  VITE_AGENT_METHOD_DEV_BASE_URL?: string
  VITE_AGENT_ENABLE_LEGACY_STUDIO?: string
  VITE_AGENT_OPERATOR_MODE_ENABLED?: string
  VITE_AGENT_CACHE_POLICY?: string
  VITE_AGENT_DEMO_SNAPSHOT_VERSION?: string
  VITE_AGENT_STARTUP_HEALTH_TTL_SEC?: string
}

const runtimeEnv = import.meta.env as RuntimeEnv
const DEFAULT_HEALTH_TIMEOUT_MS = 4000
const DEFAULT_RUNTIME_CONFIG: AgentDesktopRuntimeConfig = {
  apiBaseUrl: '',
  methodDevBaseUrl: '',
  operatorModeEnabled: false,
  cachePolicy: 'live_preferred',
  demoSnapshotVersion: '2026-04-18',
  startupHealthTtlSec: 30
}

let currentRuntimeConfig = resolveWebRuntimeConfig()

export interface AgentRuntimeBootState {
  runtimeTarget: RuntimeTarget
  runtimeConfig: AgentDesktopRuntimeConfig
  startupHealth: AgentStartupHealth | null
  bootError: string | null
}

function isDesktopTauriRuntime(): boolean {
  return typeof window !== 'undefined' && Boolean(window.__TAURI__)
}

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, '')
}

function parseCachePolicy(value: string | undefined): AgentCachePolicy {
  switch (value?.trim()) {
    case 'cached_preferred':
      return 'cached_preferred'
    case 'demo_safe':
      return 'demo_safe'
    case 'live_preferred':
    default:
      return 'live_preferred'
  }
}

function parseBoolean(value: string | undefined, fallback: boolean): boolean {
  if (!value) {
    return fallback
  }

  return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase())
}

export function isLegacyStudioEnabled(): boolean {
  return parseBoolean(runtimeEnv.VITE_AGENT_ENABLE_LEGACY_STUDIO, false)
}

function parsePositiveNumber(value: string | undefined, fallback: number): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

function normalizeRuntimeConfig(config: AgentDesktopRuntimeConfig): AgentDesktopRuntimeConfig {
  return {
    apiBaseUrl: normalizeBaseUrl(config.apiBaseUrl),
    methodDevBaseUrl: normalizeBaseUrl(config.methodDevBaseUrl),
    operatorModeEnabled: Boolean(config.operatorModeEnabled),
    cachePolicy: parseCachePolicy(config.cachePolicy),
    demoSnapshotVersion: config.demoSnapshotVersion?.trim() || DEFAULT_RUNTIME_CONFIG.demoSnapshotVersion,
    startupHealthTtlSec:
      typeof config.startupHealthTtlSec === 'number' && Number.isFinite(config.startupHealthTtlSec)
        ? Math.max(5, Math.round(config.startupHealthTtlSec))
        : DEFAULT_RUNTIME_CONFIG.startupHealthTtlSec
  }
}

function resolveWebRuntimeConfig(): AgentDesktopRuntimeConfig {
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  return normalizeRuntimeConfig({
    apiBaseUrl: runtimeEnv.VITE_AGENT_API_BASE_URL ?? origin,
    methodDevBaseUrl: runtimeEnv.VITE_AGENT_METHOD_DEV_BASE_URL ?? `${origin}/method-dev`,
    operatorModeEnabled: parseBoolean(
      runtimeEnv.VITE_AGENT_OPERATOR_MODE_ENABLED,
      DEFAULT_RUNTIME_CONFIG.operatorModeEnabled
    ),
    cachePolicy: parseCachePolicy(runtimeEnv.VITE_AGENT_CACHE_POLICY),
    demoSnapshotVersion:
      runtimeEnv.VITE_AGENT_DEMO_SNAPSHOT_VERSION ?? DEFAULT_RUNTIME_CONFIG.demoSnapshotVersion,
    startupHealthTtlSec: parsePositiveNumber(
      runtimeEnv.VITE_AGENT_STARTUP_HEALTH_TTL_SEC,
      DEFAULT_RUNTIME_CONFIG.startupHealthTtlSec
    )
  })
}

function joinBaseAndPath(baseUrl: string, path: string): string {
  const normalizedPath = path.replace(/^\/+/, '')
  if (!baseUrl) {
    return `/${normalizedPath}`
  }

  return `${normalizeBaseUrl(baseUrl)}/${normalizedPath}`
}

function buildHealthStatus(
  endpoint: string,
  status: AgentStartupHealthStatus,
  responseTimeMs: number,
  detail?: string | null
): AgentServiceHealth {
  return {
    status,
    checkedAt: new Date().toISOString(),
    endpoint,
    responseTimeMs,
    detail: detail || null
  }
}

function combineHealthStatuses(
  apiStatus: AgentStartupHealthStatus,
  methodDevStatus: AgentStartupHealthStatus
): AgentStartupHealthStatus {
  if (apiStatus === 'healthy' && methodDevStatus === 'healthy') {
    return 'healthy'
  }

  if (apiStatus === 'unavailable' && methodDevStatus === 'unavailable') {
    return 'unavailable'
  }

  return 'degraded'
}

function createTimeoutSignal(timeoutMs: number): {
  signal: AbortSignal
  cleanup: () => void
} {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)

  return {
    signal: controller.signal,
    cleanup: () => window.clearTimeout(timeoutId)
  }
}

async function runHealthCheck(
  endpoint: string,
  classify: (payload: Record<string, unknown> | null) => {
    status: AgentStartupHealthStatus
    detail?: string | null
  }
): Promise<AgentServiceHealth> {
  const startedAt = typeof performance !== 'undefined' ? performance.now() : Date.now()
  const { signal, cleanup } = createTimeoutSignal(DEFAULT_HEALTH_TIMEOUT_MS)

  try {
    const response = await fetch(endpoint, { method: 'GET', signal })
    const durationMs = Math.round(
      (typeof performance !== 'undefined' ? performance.now() : Date.now()) - startedAt
    )

    if (!response.ok) {
      return buildHealthStatus(endpoint, 'unavailable', durationMs, `HTTP ${response.status}`)
    }

    const payload = (await response.json().catch(() => null)) as Record<string, unknown> | null
    const result = classify(payload)
    return buildHealthStatus(endpoint, result.status, durationMs, result.detail)
  } catch (error) {
    const durationMs = Math.round(
      (typeof performance !== 'undefined' ? performance.now() : Date.now()) - startedAt
    )
    if (error instanceof DOMException && error.name === 'AbortError') {
      return buildHealthStatus(endpoint, 'unavailable', durationMs, 'Request timed out')
    }

    return buildHealthStatus(
      endpoint,
      'unavailable',
      durationMs,
      error instanceof Error ? error.message : 'Health check failed'
    )
  } finally {
    cleanup()
  }
}

async function loadWebStartupHealth(
  runtimeConfig: AgentDesktopRuntimeConfig
): Promise<AgentStartupHealth> {
  const [api, methodDev] = await Promise.all([
    runHealthCheck(joinBaseAndPath(runtimeConfig.apiBaseUrl, '/api/health'), (payload) => {
      const rawStatus = payload?.status
      if (rawStatus === 'ok' || rawStatus === 'ready') {
        return { status: 'healthy' as const }
      }
      if (typeof rawStatus === 'string' && rawStatus.trim()) {
        return {
          status: 'degraded' as const,
          detail: `status=${rawStatus}`
        }
      }
      return {
        status: 'degraded' as const,
        detail: 'Unexpected API health payload'
      }
    }),
    runHealthCheck(joinBaseAndPath(runtimeConfig.methodDevBaseUrl, '/health'), (payload) => {
      const rawStatus = payload?.status
      const retrievalStore = payload?.retrieval_store
      if (rawStatus === 'ok' && retrievalStore === 'ready') {
        return { status: 'healthy' as const }
      }

      const detailParts = [
        typeof rawStatus === 'string' ? `status=${rawStatus}` : null,
        typeof retrievalStore === 'string' ? `retrieval_store=${retrievalStore}` : null
      ].filter(Boolean)

      return {
        status: 'degraded' as const,
        detail: detailParts.length ? detailParts.join(', ') : 'Unexpected method-dev health payload'
      }
    })
  ])

  return {
    status: combineHealthStatuses(api.status, methodDev.status),
    checkedAt: new Date().toISOString(),
    cached: false,
    api,
    methodDev
  }
}

async function invokeDesktopRuntime<T>(
  command: string,
  args?: Record<string, unknown>
): Promise<T> {
  const module = await import('@tauri-apps/api/core')
  return module.invoke<T>(command, args)
}

export function configureAgentRuntime(config: AgentDesktopRuntimeConfig): AgentDesktopRuntimeConfig {
  currentRuntimeConfig = normalizeRuntimeConfig(config)
  return getCurrentAgentRuntimeConfig()
}

export function getCurrentAgentRuntimeConfig(): AgentDesktopRuntimeConfig {
  return { ...currentRuntimeConfig }
}

export async function setAgentRuntimeConfig(
  config: AgentDesktopRuntimeConfig
): Promise<AgentDesktopRuntimeConfig> {
  const normalized = normalizeRuntimeConfig(config)

  if (isDesktopTauriRuntime()) {
    const saved = await invokeDesktopRuntime<AgentDesktopRuntimeConfig>('set_agent_runtime_config', {
      config: normalized
    })
    return configureAgentRuntime(saved)
  }

  return configureAgentRuntime(normalized)
}

export function buildApiServiceUrl(path: string): string {
  return joinBaseAndPath(currentRuntimeConfig.apiBaseUrl, path)
}

export function buildMethodDevServiceUrl(path: string): string {
  return joinBaseAndPath(currentRuntimeConfig.methodDevBaseUrl, path)
}

export async function loadAgentRuntimeBootState(): Promise<AgentRuntimeBootState> {
  const runtimeTarget: RuntimeTarget = isDesktopTauriRuntime() ? 'desktop' : 'web'

  try {
    const runtimeConfig =
      runtimeTarget === 'desktop'
        ? await invokeDesktopRuntime<AgentDesktopRuntimeConfig>('get_agent_runtime_config')
        : resolveWebRuntimeConfig()
    const normalizedRuntimeConfig = configureAgentRuntime(runtimeConfig)
    const startupHealth =
      runtimeTarget === 'desktop'
        ? await invokeDesktopRuntime<AgentStartupHealth>('get_agent_startup_health')
        : await loadWebStartupHealth(normalizedRuntimeConfig)

    return {
      runtimeTarget,
      runtimeConfig: normalizedRuntimeConfig,
      startupHealth,
      bootError: null
    }
  } catch (error) {
    const fallbackRuntimeConfig = configureAgentRuntime(resolveWebRuntimeConfig())
    const bootError =
      error instanceof Error && error.message ? error.message : 'Unable to load the agent runtime.'

    return {
      runtimeTarget,
      runtimeConfig: fallbackRuntimeConfig,
      startupHealth:
        runtimeTarget === 'web'
          ? await loadWebStartupHealth(fallbackRuntimeConfig).catch(() => null)
          : null,
      bootError
    }
  }
}
