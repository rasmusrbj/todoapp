import type { IconDefinition } from '@fortawesome/fontawesome-svg-core'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import Link from 'next/link'

import { cn } from '@/lib/utils'

/** How prominent the number is. `alert` is for a count you want acted on. */
type Tone = 'neutral' | 'alert' | 'positive'

const NUMBER_TONE: Record<Tone, string> = {
  neutral: 'text-foreground',
  alert: 'text-red-600 dark:text-red-400',
  positive: 'text-emerald-600 dark:text-emerald-400',
}

const ICON_TONE: Record<Tone, string> = {
  neutral: 'bg-muted text-muted-foreground',
  alert: 'bg-red-50 text-red-600 dark:bg-red-950/50 dark:text-red-400',
  positive: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400',
}

/**
 * One number, big, with a word for what it counts.
 *
 * The icon sits in a tinted circle rather than floating grey in a corner — it gives the
 * card a fixed anchor so a row of them reads as a set. The tint is the only place a
 * hue appears, and it is always paired with the number's own colour so the state is
 * never carried by colour alone.
 */
export function StatCard({
  label,
  value,
  icon,
  href,
  tone = 'neutral',
  hint,
}: {
  label: string
  value: number
  icon: IconDefinition
  href?: string
  tone?: Tone
  hint?: string
}) {
  const content = (
    <>
      <span
        className={cn(
          'flex size-9 shrink-0 items-center justify-center rounded-full sm:size-10',
          ICON_TONE[tone],
        )}
      >
        <FontAwesomeIcon icon={icon} className="h-4 w-4" />
      </span>

      <span className="min-w-0">
        <span
          className={cn(
            'block text-2xl font-semibold leading-none tabular-nums sm:text-[28px]',
            NUMBER_TONE[tone],
          )}
        >
          {value}
        </span>
        <span className="mt-1.5 block truncate text-sm text-muted-foreground">{label}</span>
        {hint && <span className="mt-0.5 block truncate text-xs text-muted-foreground">{hint}</span>}
      </span>
    </>
  )

  // A card that goes nowhere must not look clickable, so the link is conditional.
  if (!href) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 sm:gap-4 sm:p-5">
        {content}
      </div>
    )
  }

  return (
    <Link
      href={href}
      className="card-interactive flex items-center gap-3 rounded-xl border bg-card p-4 sm:gap-4 sm:p-5"
    >
      {content}
    </Link>
  )
}
