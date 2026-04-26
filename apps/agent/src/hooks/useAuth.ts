import { useEffect, useState } from 'react'

const STORAGE_KEY = 'silico.agent.session.v1'
const LEGACY_STORAGE_KEY = 'silico.agent.studio.session.v1'
const AUTH_EVENT = 'silico:agent-auth-change'

interface LocalSession {
  identifier: string
}

const LOCAL_PREVIEW_CREDENTIALS = new Map<string, string>([
  ['YC', 'YC'],
  ['Astra', 'Astra'],
  ['Katarina', 'Katarina']
])

function parseSession(raw: string | null): LocalSession | null {
  if (!raw) {
    return null
  }

  try {
    const parsed = JSON.parse(raw) as { identifier?: unknown; email?: unknown }
    const identifier =
      typeof parsed.identifier === 'string'
        ? parsed.identifier
        : typeof parsed.email === 'string'
          ? parsed.email
          : null

    if (!identifier) {
      return null
    }

    return { identifier }
  } catch {
    return null
  }
}

function readSession(): LocalSession | null {
  if (typeof window === 'undefined') {
    return null
  }

  return (
    parseSession(window.localStorage.getItem(STORAGE_KEY)) ||
    parseSession(window.localStorage.getItem(LEGACY_STORAGE_KEY))
  )
}

function emitAuthChange() {
  window.dispatchEvent(new Event(AUTH_EVENT))
}

export function signIn(identifier: string) {
  const normalized = identifier.trim()
  if (!normalized) {
    return
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ identifier: normalized }))
  window.localStorage.removeItem(LEGACY_STORAGE_KEY)
  emitAuthChange()
}

export function authenticateLocalCredentials(
  identifier: string,
  password: string
): string | null {
  const normalizedIdentifier = identifier.trim()
  const normalizedPassword = password.trim()
  const expectedPassword = LOCAL_PREVIEW_CREDENTIALS.get(normalizedIdentifier)

  if (!expectedPassword || normalizedPassword !== expectedPassword) {
    return null
  }

  return normalizedIdentifier
}

export function signOut() {
  window.localStorage.removeItem(STORAGE_KEY)
  window.localStorage.removeItem(LEGACY_STORAGE_KEY)
  emitAuthChange()
}

export function useAuth() {
  const [session, setSession] = useState<LocalSession | null>(() => readSession())

  useEffect(() => {
    const sync = () => setSession(readSession())
    window.addEventListener('storage', sync)
    window.addEventListener(AUTH_EVENT, sync)

    return () => {
      window.removeEventListener('storage', sync)
      window.removeEventListener(AUTH_EVENT, sync)
    }
  }, [])

  return {
    session,
    user: session
      ? {
          identifier: session.identifier,
          // Preserve the legacy shape used inside the imported Studio shell.
          email: session.identifier
        }
      : null,
    loading: false,
    signOut
  }
}
