import { faCalendar, faClock } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import type { Timestamp } from '@bufbuild/protobuf/wkt'
import { getLocale, getTranslations } from 'next-intl/server'

import type { Locale } from '@/i18n/config'
import { formatShortDate, relativePhrase, toDate } from '@/lib/format'
import { cn } from '@/lib/utils'

/**
 * A due date, shown relatively when that is more useful than a date.
 *
 * "in 3 days" beats "18 Aug" inside a week; beyond that the date is clearer. An
 * overdue task is tinted *and* carries the word, so the state is not colour-only.
 */
export async function DueDate({
  dueAt,
  hasTime,
  overdue,
  className,
}: {
  dueAt: Timestamp | undefined
  hasTime?: boolean
  overdue?: boolean
  className?: string
}) {
  if (!dueAt) return null

  const [locale, t] = await Promise.all([getLocale(), getTranslations('time')])
  const date = toDate(dueAt)
  if (!date) return null

  const phrase = relativePhrase(date)
  const label = phrase ? t(phrase.key, phrase.values) : formatShortDate(date, locale as Locale)
  const time = hasTime
    ? new Intl.DateTimeFormat(locale === 'en' ? 'en-GB' : 'da-DK', {
        hour: '2-digit',
        minute: '2-digit',
      }).format(date)
    : undefined

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 text-xs',
        overdue ? 'font-medium text-red-600 dark:text-red-400' : 'text-muted-foreground',
        className,
      )}
      title={formatShortDate(date, locale as Locale)}
    >
      <FontAwesomeIcon icon={hasTime ? faClock : faCalendar} className="h-3 w-3" />
      {label}
      {time && <span className="tabular-nums">{time}</span>}
    </span>
  )
}
