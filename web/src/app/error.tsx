'use client'

import { faTriangleExclamation } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useEffect } from 'react'

import { Button } from '@/components/ui/button'

/**
 * The error boundary for every route.
 *
 * Deliberately says nothing about what broke: `error.message` from a Server Component
 * is a stack-adjacent string in development and an opaque digest in production, and
 * neither belongs in front of a reader. The digest is logged so it can be matched
 * against the server log, and `reset()` re-renders the segment — which is usually
 * enough, because the common cause is a failed API call rather than bad state.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  const t = useTranslations('app')

  useEffect(() => {
    console.error('[error boundary]', error.digest ?? error.message)
  }, [error])

  return (
    <div className="flex min-h-[60svh] items-center justify-center px-4">
      <div className="flex w-full max-w-md flex-col items-center gap-6 rounded-xl border border-border bg-card px-6 py-14 text-center">
        <span className="flex size-14 items-center justify-center rounded-full bg-destructive/10 text-destructive">
          <FontAwesomeIcon icon={faTriangleExclamation} className="h-6 w-6" />
        </span>
        <div className="space-y-1.5">
          <h1 className="text-2xl font-semibold tracking-tight text-balance">
            {t('somethingWentWrong')}
          </h1>
          <p className="text-[15px] text-muted-foreground text-pretty">{t('tryAgain')}</p>
        </div>
        <Button onClick={reset} className="press">
          {t('retry')}
        </Button>
      </div>
    </div>
  )
}
