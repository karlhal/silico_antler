import { type ComponentPropsWithoutRef, type ElementType, useEffect, useMemo, useRef, useState } from 'react'

function usePrefersReducedMotion() {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return
    }

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    const updatePreference = () => setPrefersReducedMotion(mediaQuery.matches)

    updatePreference()
    mediaQuery.addEventListener('change', updatePreference)
    return () => mediaQuery.removeEventListener('change', updatePreference)
  }, [])

  return prefersReducedMotion
}

export function useTypewriterText({
  text,
  active = true,
  tickMs = 18,
  charsPerTick = 2,
  completionKey,
  onComplete
}: {
  text: string
  active?: boolean
  tickMs?: number
  charsPerTick?: number
  completionKey?: string
  onComplete?: () => void
}) {
  const prefersReducedMotion = usePrefersReducedMotion()
  const [visibleLength, setVisibleLength] = useState(active ? 0 : text.length)
  const completionEmittedRef = useRef(false)

  const finish = () => {
    setVisibleLength(text.length)
  }

  useEffect(() => {
    completionEmittedRef.current = false
    setVisibleLength(active && !prefersReducedMotion ? 0 : text.length)
  }, [active, completionKey, prefersReducedMotion, text])

  useEffect(() => {
    if (!active || prefersReducedMotion || visibleLength >= text.length) {
      if (visibleLength >= text.length && !completionEmittedRef.current) {
        completionEmittedRef.current = true
        onComplete?.()
      }
      return
    }

    const timer = window.setTimeout(() => {
      setVisibleLength((current) => Math.min(text.length, current + charsPerTick))
    }, tickMs)

    return () => window.clearTimeout(timer)
  }, [active, charsPerTick, onComplete, prefersReducedMotion, text.length, tickMs, visibleLength])

  return {
    displayText: text.slice(0, visibleLength),
    isComplete: visibleLength >= text.length,
    prefersReducedMotion,
    finish
  }
}

export function TypewriterText<T extends ElementType = 'p'>({
  as,
  text,
  active = true,
  completionKey,
  cursor = true,
  className,
  onComplete,
  ...props
}: {
  as?: T
  text: string
  active?: boolean
  completionKey?: string
  cursor?: boolean
  className?: string
  onComplete?: () => void
} & Omit<ComponentPropsWithoutRef<T>, 'as' | 'children' | 'className'>) {
  const Component = (as || 'p') as ElementType
  const { displayText, isComplete, finish } = useTypewriterText({
    text,
    active,
    completionKey,
    onComplete
  })

  const cursorClassName = useMemo(
    () =>
      cursor && !isComplete
        ? 'after:ml-0.5 after:inline-block after:h-[1em] after:w-px after:translate-y-[0.12em] after:bg-current after:align-baseline after:content-[""]'
        : '',
    [cursor, isComplete]
  )

  return (
    <Component
      className={[className, cursorClassName].filter(Boolean).join(' ')}
      onClick={finish}
      {...props}
    >
      {displayText}
    </Component>
  )
}
