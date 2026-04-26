import { useEffect, useState } from 'react'
import { Dashboard } from './pages/Dashboard'
import { AuthPage } from './pages/AuthPage'
import ReviewQueue from './pages/ReviewQueue'
import { SurrogatePlaygroundPage } from './pages/SurrogatePlayground'
import { StudioApp } from './studio/StudioApp'
import { useAuth } from './hooks/useAuth'
import { getAgentAppPath, replaceAgentAppRoute } from './lib/appNavigation'
import {
  getCurrentAgentRuntimeConfig,
  isLegacyStudioEnabled,
  loadAgentRuntimeBootState,
  type AgentRuntimeBootState
} from './lib/agentRuntime'

function RuntimeLoadingShell() {
  return (
    <div className="flex min-h-screen items-center justify-center px-6 py-10">
      <div className="w-full max-w-xl rounded-xl border border-border bg-card/95 px-6 py-6">
        <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-primary/70">
          Agent Runtime
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-foreground">
          Initializing standalone launch state
        </h1>
        <p className="mt-3 max-w-lg text-sm leading-relaxed text-muted-foreground">
          Loading runtime-configured service endpoints and startup health before the workflow UI
          becomes interactive.
        </p>
      </div>
    </div>
  )
}

export function App() {
  const [path, setPath] = useState(window.location.pathname)
  const [runtimeBootState, setRuntimeBootState] = useState<AgentRuntimeBootState | null>(null)
  const { user } = useAuth()
  const appPath = getAgentAppPath(path)
  const legacyStudioEnabled = isLegacyStudioEnabled()
  const isLegacyStudioRoute = appPath === '/studio' || appPath === '/studio/classic'

  useEffect(() => {
    const handlePopState = () => setPath(window.location.pathname)
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  useEffect(() => {
    let cancelled = false

    loadAgentRuntimeBootState()
      .then((state) => {
        if (!cancelled) {
          setRuntimeBootState(state)
        }
      })
      .catch((error) => {
        if (cancelled) {
          return
        }

        setRuntimeBootState({
          runtimeTarget:
            typeof window !== 'undefined' && window.__TAURI__ ? 'desktop' : 'web',
          runtimeConfig: getCurrentAgentRuntimeConfig(),
          startupHealth: null,
          bootError:
            error instanceof Error && error.message
              ? error.message
              : 'Unable to load the agent runtime.'
        })
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!legacyStudioEnabled && isLegacyStudioRoute) {
      replaceAgentAppRoute('/')
    }
  }, [isLegacyStudioRoute, legacyStudioEnabled])

  if (!legacyStudioEnabled && isLegacyStudioRoute) {
    return null
  }

  if (!user) {
    return <AuthPage />
  }

  if (!runtimeBootState) {
    return <RuntimeLoadingShell />
  }

  if (appPath === '/review') {
    return <ReviewQueue />
  }

  if (appPath === '/surrogate') {
    return <SurrogatePlaygroundPage />
  }

  if (legacyStudioEnabled && isLegacyStudioRoute) {
    return (
      <StudioApp
        runtimeBootState={runtimeBootState}
        mode={appPath === '/studio/classic' ? 'classic' : 'integrated'}
      />
    )
  }

  return <Dashboard runtimeBootState={runtimeBootState} />
}
