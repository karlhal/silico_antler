function normalizeRoute(route: string): string {
  const withLeadingSlash = route.startsWith('/') ? route : `/${route}`
  const trimmed = withLeadingSlash.replace(/\/+$/, '')
  return trimmed || '/'
}

function normalizePathname(pathname: string): string {
  const trimmed = pathname.replace(/\/+$/, '')
  return trimmed || '/'
}

function getAgentBasePath(pathname: string): string {
  return normalizePathname(pathname).startsWith('/agent') ? '/agent' : ''
}

export function getAgentAppPath(pathname: string): string {
  const normalized = normalizePathname(pathname)
  return normalized.startsWith('/agent')
    ? normalized.replace(/^\/agent(?=\/|$)/, '') || '/'
    : normalized
}

export function buildAgentAppHref(route: string, pathname?: string): string {
  const currentPathname =
    pathname ?? (typeof window !== 'undefined' ? window.location.pathname : '/')
  const prefix = getAgentBasePath(currentPathname)
  const normalizedRoute = normalizeRoute(route)

  if (!prefix) {
    return normalizedRoute
  }

  return normalizedRoute === '/' ? prefix : `${prefix}${normalizedRoute}`
}

export function navigateAgentAppRoute(route: string) {
  if (typeof window === 'undefined') {
    return
  }

  const nextHref = buildAgentAppHref(route)
  const currentHref = `${window.location.pathname}${window.location.search}`
  if (currentHref !== nextHref) {
    window.history.pushState(window.history.state, '', nextHref)
  }

  window.dispatchEvent(new Event('popstate'))
}

export function replaceAgentAppRoute(route: string) {
  if (typeof window === 'undefined') {
    return
  }

  const nextHref = buildAgentAppHref(route)
  const currentHref = `${window.location.pathname}${window.location.search}`
  if (currentHref !== nextHref) {
    window.history.replaceState(window.history.state, '', nextHref)
  }

  window.dispatchEvent(new Event('popstate'))
}
