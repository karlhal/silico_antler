import type { CachedAgentRunSnapshot } from '../types'

const RUN_CACHE_STORAGE_KEY = 'silico.agent.run-cache.v1'
const MAX_CACHED_SNAPSHOTS = 12

interface CachedAgentRunStore {
  schemaVersion: 1
  snapshots: CachedAgentRunSnapshot[]
}

function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function stableStringify(value: unknown): string {
  if (value === null) {
    return 'null'
  }

  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(',')}]`
  }

  switch (typeof value) {
    case 'boolean':
      return value ? 'true' : 'false'
    case 'number':
      return Number.isFinite(value) ? String(value) : 'null'
    case 'string':
      return JSON.stringify(value)
    case 'object': {
      const entries = Object.entries(value as Record<string, unknown>)
        .filter(([, entryValue]) => typeof entryValue !== 'undefined')
        .sort(([left], [right]) => left.localeCompare(right))

      return `{${entries
        .map(([entryKey, entryValue]) => `${JSON.stringify(entryKey)}:${stableStringify(entryValue)}`)
        .join(',')}}`
    }
    default:
      return 'null'
  }
}

function hashString(value: string): string {
  let hash = 2166136261

  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash += (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24)
  }

  return `agent-run-${(hash >>> 0).toString(16).padStart(8, '0')}`
}

function normalizeSnapshot(value: unknown): CachedAgentRunSnapshot | null {
  if (!isObjectRecord(value)) {
    return null
  }

  const origin = value.origin
  if (
    value.schemaVersion !== 1 ||
    typeof value.requestHash !== 'string' ||
    typeof value.createdAt !== 'string' ||
    !['live', 'cached', 'demo_safe', 'live_degraded'].includes(String(origin)) ||
    !isObjectRecord(value.request) ||
    !isObjectRecord(value.report)
  ) {
    return null
  }

  return {
    schemaVersion: 1,
    requestHash: value.requestHash,
    createdAt: value.createdAt,
    origin: origin as CachedAgentRunSnapshot['origin'],
    request: value.request,
    report: value.report as unknown as CachedAgentRunSnapshot['report'],
    runtimeSummary: isObjectRecord(value.runtimeSummary)
      ? (value.runtimeSummary as unknown as CachedAgentRunSnapshot['runtimeSummary'])
      : null
  }
}

function readStore(): CachedAgentRunStore {
  if (!isBrowser()) {
    return { schemaVersion: 1, snapshots: [] }
  }

  try {
    const rawValue = window.localStorage.getItem(RUN_CACHE_STORAGE_KEY)
    if (!rawValue) {
      return { schemaVersion: 1, snapshots: [] }
    }

    const parsed = JSON.parse(rawValue) as Partial<CachedAgentRunStore>
    if (parsed.schemaVersion !== 1 || !Array.isArray(parsed.snapshots)) {
      return { schemaVersion: 1, snapshots: [] }
    }

    return {
      schemaVersion: 1,
      snapshots: parsed.snapshots
        .map((snapshot) => normalizeSnapshot(snapshot))
        .filter((snapshot): snapshot is CachedAgentRunSnapshot => Boolean(snapshot))
        .sort((left, right) => right.createdAt.localeCompare(left.createdAt))
        .slice(0, MAX_CACHED_SNAPSHOTS)
    }
  } catch {
    return { schemaVersion: 1, snapshots: [] }
  }
}

function writeStore(store: CachedAgentRunStore) {
  if (!isBrowser()) {
    return
  }

  window.localStorage.setItem(RUN_CACHE_STORAGE_KEY, JSON.stringify(store))
}

export function buildAgentRunRequestHash(request: Record<string, unknown>): string {
  return hashString(stableStringify(request))
}

export function getCachedAgentRunSnapshot(requestHash: string): CachedAgentRunSnapshot | null {
  if (!requestHash) {
    return null
  }

  return readStore().snapshots.find((snapshot) => snapshot.requestHash === requestHash) || null
}

export function listCachedAgentRunSnapshots(): CachedAgentRunSnapshot[] {
  return readStore().snapshots
}

export function saveCachedAgentRunSnapshot(snapshot: CachedAgentRunSnapshot) {
  if (!isBrowser()) {
    return
  }

  const store = readStore()
  const remainingSnapshots = store.snapshots.filter(
    (existingSnapshot) => existingSnapshot.requestHash !== snapshot.requestHash
  )

  writeStore({
    schemaVersion: 1,
    snapshots: [snapshot, ...remainingSnapshots]
      .sort((left, right) => right.createdAt.localeCompare(left.createdAt))
      .slice(0, MAX_CACHED_SNAPSHOTS)
  })
}
