import { useEffect, useState } from 'react'
import { ArrowLeft, Loader2, Moon, RefreshCcw, Sun } from 'lucide-react'
import { navigateAgentAppRoute } from '../../lib/appNavigation'
import { useTheme } from '../../hooks/useTheme'
import type { Recommendation } from '../../types'
import { Button } from '../ui/Button'
import { SurrogateWorkbench } from './SurrogateWorkbench'
import { createSurrogateTuningValues, type SurrogateTuningValues } from './surrogateModel'

export function SurrogatePlayground() {
  const { theme, toggle } = useTheme()
  const [reloadToken, setReloadToken] = useState(0)
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [selectedRecommendationId, setSelectedRecommendationId] = useState<string>('')
  const [tuning, setTuning] = useState<SurrogateTuningValues | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    window.setTimeout(() => {
      if (cancelled) {
        return
      }

      try {
        const stored = sessionStorage.getItem('silico_surrogate_recommendations')
        const parsed: Recommendation[] = stored ? JSON.parse(stored) : []
        const candidateParam = new URLSearchParams(window.location.search).get('candidate')
        setRecommendations(parsed)
        if (candidateParam) {
          setSelectedRecommendationId(candidateParam)
        } else if (parsed.length > 0) {
          setSelectedRecommendationId(parsed[0].paper_id)
        }
        setError(parsed.length === 0 ? 'No recommendations loaded. Run a search first.' : null)
      } catch {
        setError('Failed to load recommendations.')
      }
      setLoading(false)
    }, 0)

    return () => {
      cancelled = true
    }
  }, [reloadToken])

  const selectedRecommendation =
    recommendations.find((item) => item.paper_id === selectedRecommendationId) ||
    recommendations[0] ||
    null

  useEffect(() => {
    if (!selectedRecommendation) {
      setTuning(null)
      return
    }

    setTuning(createSurrogateTuningValues(selectedRecommendation))
  }, [reloadToken, selectedRecommendation?.paper_id])

  useEffect(() => {
    if (!selectedRecommendationId) {
      return
    }

    const url = new URL(window.location.href)
    url.searchParams.set('candidate', selectedRecommendationId)
    window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}`)
  }, [selectedRecommendationId])

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-7xl px-4 py-6 md:px-6 md:py-8">
        <div className="flex flex-col gap-4 border-b border-border/80 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <h1 className="font-serif text-4xl tracking-tight text-foreground">
              silico AI-surrogate
            </h1>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => navigateAgentAppRoute('/')}
              variant="outline"
              className="h-9 rounded-lg px-4 text-[11px] font-medium"
            >
              <ArrowLeft className="mr-2 size-3.5" />
              Back to dashboard
            </Button>
            <Button
              onClick={() => setReloadToken((current) => current + 1)}
              variant="outline"
              className="h-9 rounded-lg px-4 text-[11px] font-medium"
            >
              <RefreshCcw className="mr-2 size-3.5" />
              Reload demo
            </Button>
            <Button
              onClick={toggle}
              variant="outline"
              className="h-9 rounded-lg px-4 text-[11px] font-medium"
            >
              {theme === 'dark' ? (
                <Moon className="mr-2 size-3.5" />
              ) : (
                <Sun className="mr-2 size-3.5" />
              )}
              {theme}
            </Button>
          </div>
        </div>

        {loading ? (
          <div className="mt-8 rounded-2xl border border-border bg-card/70 px-6 py-8">
            <div className="flex items-center gap-3">
              <Loader2 className="size-5 animate-spin text-primary" />
              <div>
                <p className="text-sm font-medium text-foreground">Loading surrogate demo inputs</p>
              </div>
            </div>
          </div>
        ) : null}

        {!loading && error ? (
          <div className="mt-8 rounded-2xl border border-red-300/60 bg-red-50 px-6 py-8 text-red-950 dark:border-red-500/35 dark:bg-red-500/10 dark:text-red-100">
            <p className="text-sm font-medium">Unable to load silico AI-surrogate</p>
            <p className="mt-2 text-sm leading-relaxed">{error}</p>
          </div>
        ) : null}

        {!loading && !error && selectedRecommendation && tuning ? (
          <SurrogateWorkbench
            selectedRecommendation={selectedRecommendation}
            selectedRecommendationId={selectedRecommendationId}
            resetToken={reloadToken}
            tuning={tuning}
            onTuningChange={setTuning}
          />
        ) : null}
      </div>
    </div>
  )
}
