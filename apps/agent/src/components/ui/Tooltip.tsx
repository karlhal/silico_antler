import { useId } from 'react'
import { CircleHelp } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TooltipProps {
  label: string
  content: string
  className?: string
}

export function Tooltip({ label, content, className }: TooltipProps) {
  const tooltipId = useId()

  return (
    <span className={cn('group/tooltip relative inline-flex items-center', className)}>
      <button
        type="button"
        aria-describedby={tooltipId}
        aria-label={label}
        className="inline-flex size-4 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 focus-visible:ring-offset-2"
      >
        <CircleHelp className="size-3.5" />
      </button>
      <span
        id={tooltipId}
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-30 mt-2 hidden w-56 -translate-x-1/2 rounded-md border border-border bg-background px-3 py-2 text-left text-[11px] leading-relaxed text-foreground shadow-[0_14px_32px_rgba(15,23,42,0.08)] group-hover/tooltip:block group-focus-within/tooltip:block"
      >
        {content}
      </span>
    </span>
  )
}
