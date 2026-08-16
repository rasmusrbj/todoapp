'use client'

import { faCircleCheck, faCircleExclamation } from '@fortawesome/pro-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'

import type { ActionFailure } from '@/lib/errors'
import { cn } from '@/lib/utils'

/**
 * Renders a Server Action failure in the reader's language.
 *
 * The server sends a reason key, never a sentence, so the same failure reads
 * natively in Danish and English. Keys that are not error reasons — a client-side
 * check like `passwordsDiffer` — fall through to the `validation` namespace.
 */
export function FormError({ failure, className }: { failure: ActionFailure | null; className?: string }) {
  const errors = useTranslations('errors')
  const validation = useTranslations('validation')

  if (!failure) return null

  const isReason = failure.reasonKey.startsWith('ERROR_REASON_')
  const isCatalogued = isReason || failure.reasonKey === 'network' || failure.reasonKey === 'unknown'
  const message = isCatalogued
    ? errors(failure.reasonKey, failure.values)
    : validation(failure.reasonKey, failure.values)

  return (
    <p
      role="alert"
      aria-live="polite"
      className={cn(
        'flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive',
        className,
      )}
    >
      <FontAwesomeIcon icon={faCircleExclamation} className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{message}</span>
    </p>
  )
}

/** A confirmation line, for flows that stay on the page after succeeding. */
export function FormSuccess({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <p
      role="status"
      aria-live="polite"
      className={cn(
        'flex items-start gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300',
        className,
      )}
    >
      <FontAwesomeIcon icon={faCircleCheck} className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{children}</span>
    </p>
  )
}

/** The inline message under one field, when a failure names that field. */
export function FieldError({ failure, field }: { failure: ActionFailure | null; field: string }) {
  const errors = useTranslations('errors')
  const validation = useTranslations('validation')

  if (!failure || failure.field !== field) return null

  const isCatalogued = failure.reasonKey.startsWith('ERROR_REASON_')
  return (
    <p className="text-sm text-destructive" role="alert">
      {isCatalogued
        ? errors(failure.reasonKey, failure.values)
        : validation(failure.reasonKey, failure.values)}
    </p>
  )
}
