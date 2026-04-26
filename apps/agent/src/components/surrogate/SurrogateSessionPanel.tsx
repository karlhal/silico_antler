import { AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { DummySurrogateSession } from '../../types'

type BadgeTone = 'neutral' | 'warning' | 'success' | 'error'

function badgeToneClass(tone: BadgeTone): string {
  switch (tone) {
    case 'warning':
      return 'border-amber-300/60 bg-amber-50 text-amber-950 dark:border-amber-500/35 dark:bg-amber-500/10 dark:text-amber-100'
    case 'success':
      return 'border-emerald-300/60 bg-emerald-50 text-emerald-950 dark:border-emerald-500/35 dark:bg-emerald-500/10 dark:text-emerald-100'
    case 'error':
      return 'border-red-300/60 bg-red-50 text-red-950 dark:border-red-500/35 dark:bg-red-500/10 dark:text-red-100'
    default:
      return 'border-border bg-background text-foreground/82'
  }
}

function postureTone(posture: 'stable' | 'watch' | 'unstable'): BadgeTone {
  switch (posture) {
    case 'stable':
      return 'success'
    case 'watch':
      return 'warning'
    default:
      return 'error'
  }
}

function SurrogateBadge({
  label,
  tone = 'neutral'
}: {
  label: string
  tone?: BadgeTone
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.18em]',
        badgeToneClass(tone)
      )}
    >
      {label}
    </span>
  )
}

function MetricField({
  label,
  value,
  tone = 'neutral'
}: {
  label: string
  value: string
  tone?: BadgeTone
}) {
  return (
    <div className={cn('rounded-xl border px-4 py-4', badgeToneClass(tone))}>
      <p className="text-[10px] font-bold uppercase tracking-[0.18em] opacity-70">{label}</p>
      <p className="mt-2 text-sm font-medium leading-relaxed">{value}</p>
    </div>
  )
}

export function SurrogateSessionPanel({
  session,
  className
}: {
  session: DummySurrogateSession
  className?: string
}) {
  return (
    <div className={cn('space-y-4', className)}>
      <div className="rounded-2xl border border-border bg-background/90 px-5 py-5">
        <div className="flex flex-wrap gap-2">
          <SurrogateBadge label={session.modeLabel} />
          <SurrogateBadge label={session.simulationLabel} tone="warning" />
        </div>
        <p className="mt-4 text-[10px] font-bold uppercase tracking-[0.18em] text-primary/70">
          Surrogate composition
        </p>
        <h2 className="mt-2 font-serif text-[1.75rem] leading-tight text-foreground">
          {session.methodTitle}
        </h2>
        <p className="mt-4 text-sm font-medium text-foreground">{session.prediction.headline}</p>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-foreground/76">
          {session.prediction.summary}
        </p>
        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <MetricField
            label="Predicted retention window"
            value={`${session.prediction.predictedRetentionWindowMin[0]} to ${session.prediction.predictedRetentionWindowMin[1]} min`}
          />
          <MetricField
            label="Confidence"
            value={session.prediction.confidenceLabel}
            tone="warning"
          />
          <MetricField
            label="Synthetic signal quality"
            value={session.prediction.signalQualityLabel}
            tone="neutral"
          />
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card/60 px-5 py-5">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
          Operating-window scan
        </p>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          {session.operatingWindows.map((windowScan) => (
            <div key={windowScan.id} className="rounded-xl border border-border bg-background/90 px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-foreground">{windowScan.label}</p>
                <SurrogateBadge label={windowScan.posture} tone={postureTone(windowScan.posture)} />
              </div>
              <p className="mt-3 text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                {windowScan.testedWindow}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-foreground/76">
                {windowScan.summary}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(18rem,0.9fr)]">
        <div className="rounded-2xl border border-border bg-background/90 px-5 py-5">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
            Suggested next evaluation
          </p>
          <p className="mt-3 text-sm font-medium text-foreground">{session.nextStepLabel}</p>
          <p className="mt-2 text-sm leading-relaxed text-foreground/76">
            {session.nextStepSummary}
          </p>
        </div>

        <div className="rounded-2xl border border-amber-300/60 bg-amber-50/80 px-5 py-5 text-amber-950 dark:border-amber-500/35 dark:bg-amber-500/10 dark:text-amber-100">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-4" />
            <p className="text-[10px] font-bold uppercase tracking-[0.18em]">Demo warnings</p>
          </div>
          <div className="mt-3 space-y-2 text-sm leading-relaxed">
            {session.warnings.map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
