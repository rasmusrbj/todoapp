'use client'

import { faEnvelopeCircleCheck } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useState, useTransition } from 'react'

import { resendVerification } from '@/app/actions/auth'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/**
 * Prompts an unverified account to confirm its address.
 *
 * Not a blocker: an unverified account can use the whole app except the parts that
 * reach other people, which is what confirmation actually protects.
 */
export function EmailVerificationBanner({ className }: { className?: string }) {
  const t = useTranslations('auth')
  const [sent, setSent] = useState(false)
  const [pending, startTransition] = useTransition()

  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 sm:flex-row sm:items-center dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-200',
        className,
      )}
    >
      <FontAwesomeIcon icon={faEnvelopeCircleCheck} className="h-4 w-4 shrink-0" />
      <p className="flex-1">{sent ? t('verifyResent') : t('verifyBanner')}</p>
      {!sent && (
        <Button
          variant="outline"
          size="sm"
          disabled={pending}
          className="press shrink-0 border-amber-300 bg-transparent hover:bg-amber-100 dark:border-amber-800 dark:hover:bg-amber-900/40"
          onClick={() =>
            startTransition(async () => {
              const result = await resendVerification()
              if (result.ok) setSent(true)
            })
          }
        >
          {t('verifyResend')}
        </Button>
      )}
    </div>
  )
}
