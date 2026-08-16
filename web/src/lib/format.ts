/**
 * Date and time formatting.
 *
 * Protobuf timestamps arrive as `{seconds, nanos}`; these helpers turn them into
 * `Date`s and into locale-correct strings. Relative phrases ("in 3 days") come from
 * the message catalogue rather than `Intl.RelativeTimeFormat`, because Danish wants
 * "om 3 dage" and the catalogue is where a translator can see and fix that.
 */

import type { Timestamp } from '@bufbuild/protobuf/wkt'

import { intlTags, type Locale } from '@/i18n/config'

/** Converts a protobuf timestamp to a `Date`, preserving `undefined`. */
export function toDate(stamp: Timestamp | undefined): Date | undefined {
  if (!stamp) return undefined
  return new Date(Number(stamp.seconds) * 1000 + Math.floor(stamp.nanos / 1_000_000))
}

/** Formats a date as e.g. "15. aug." / "15 Aug". */
export function formatShortDate(date: Date | undefined, locale: Locale): string {
  if (!date) return ''
  return new Intl.DateTimeFormat(intlTags[locale], { day: 'numeric', month: 'short' }).format(date)
}

/** Formats a date as e.g. "15. august 2026" / "15 August 2026". */
export function formatLongDate(date: Date | undefined, locale: Locale): string {
  if (!date) return ''
  return new Intl.DateTimeFormat(intlTags[locale], {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(date)
}

/** Formats a date and time, for timestamps where the clock matters. */
export function formatDateTime(date: Date | undefined, locale: Locale): string {
  if (!date) return ''
  return new Intl.DateTimeFormat(intlTags[locale], {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

/** Whole days from today to `date`, in the reader's own timezone. */
export function daysFromToday(date: Date, now = new Date()): number {
  const startOfDay = (value: Date) =>
    new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime()
  return Math.round((startOfDay(date) - startOfDay(now)) / 86_400_000)
}

/** The message key and values for a relative phrase, or `undefined` for absolute. */
export type RelativePhrase = { key: string; values?: Record<string, number> } | undefined

/**
 * Picks the relative phrase for a due date, or nothing when a date reads better.
 *
 * Inside a week either way, "in 3 days" is more useful than a date. Beyond that the
 * date itself is clearer, so the caller falls back to {@link formatShortDate}.
 */
export function relativePhrase(date: Date | undefined, now = new Date()): RelativePhrase {
  if (!date) return undefined
  const days = daysFromToday(date, now)
  if (days === 0) return { key: 'today' }
  if (days === 1) return { key: 'tomorrow' }
  if (days === -1) return { key: 'yesterday' }
  if (days > 1 && days <= 7) return { key: 'inDays', values: { count: days } }
  if (days < -1 && days >= -7) return { key: 'daysAgo', values: { count: Math.abs(days) } }
  return undefined
}

/** The relative phrase for something that happened, used by the activity feed. */
export function pastPhrase(date: Date | undefined, now = new Date()): RelativePhrase {
  if (!date) return undefined
  const minutes = Math.round((now.getTime() - date.getTime()) / 60_000)
  if (minutes < 2) return { key: 'justNow' }
  if (minutes < 60) return { key: 'minutesAgo', values: { count: minutes } }
  const hours = Math.round(minutes / 60)
  if (hours < 24) return { key: 'hoursAgo', values: { count: hours } }
  const days = Math.abs(daysFromToday(date, now))
  if (days === 1) return { key: 'yesterday' }
  if (days <= 7) return { key: 'daysAgo', values: { count: days } }
  return undefined
}

/** Formats a `<input type="date">` value from a `Date`, in local time. */
export function toDateInputValue(date: Date | undefined): string {
  if (!date) return ''
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** Formats a `<input type="time">` value from a `Date`, in local time. */
export function toTimeInputValue(date: Date | undefined): string {
  if (!date) return ''
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/**
 * Parses date and optional time inputs into an ISO string for the API.
 *
 * A date with no time becomes 09:00 local: an all-day task due "Tuesday" should not
 * read as overdue from one minute past midnight.
 */
export function fromDateInput(date: string, time?: string): string | undefined {
  if (!date) return undefined
  const [hours, minutes] = (time || '09:00').split(':').map(Number)
  const parts = date.split('-').map(Number)
  const [year, month, day] = parts
  if (year === undefined || month === undefined || day === undefined) return undefined
  return new Date(year, month - 1, day, hours ?? 9, minutes ?? 0).toISOString()
}

/** Formats a duration in minutes as "45 min" or "2 t 30 min". */
export function formatMinutes(minutes: number, locale: Locale): string {
  if (minutes <= 0) return ''
  const hourLabel = locale === 'da' ? 't' : 'h'
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest === 0 ? `${hours} ${hourLabel}` : `${hours} ${hourLabel} ${rest} min`
}
