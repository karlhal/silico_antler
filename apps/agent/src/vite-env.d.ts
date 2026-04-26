/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AGENT_API_BASE_URL?: string
  readonly VITE_AGENT_METHOD_DEV_BASE_URL?: string
  readonly VITE_AGENT_ENABLE_LEGACY_STUDIO?: string
  readonly VITE_AGENT_OPERATOR_MODE_ENABLED?: string
  readonly VITE_AGENT_CACHE_POLICY?: string
  readonly VITE_AGENT_DEMO_SNAPSHOT_VERSION?: string
  readonly VITE_AGENT_STARTUP_HEALTH_TTL_SEC?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
