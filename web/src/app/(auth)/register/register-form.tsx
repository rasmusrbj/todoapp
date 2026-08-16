'use client'

import { useLocale, useTranslations } from 'next-intl'
import { useActionState, useEffect, useState } from 'react'

import { signUp } from '@/app/actions/auth'
import { FieldError, FormError } from '@/components/form-message'
import { SubmitButton } from '@/components/submit-button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { ActionResult } from '@/lib/errors'

/** Matches the server's policy, so the hint and the rule agree. */
const MIN_PASSWORD_LENGTH = 10

export function RegisterForm() {
  const t = useTranslations('auth')
  const locale = useLocale()
  const [result, action] = useActionState<ActionResult | null, FormData>(signUp, null)
  const [timeZone, setTimeZone] = useState('')
  const failure = result && !result.ok ? result : null

  // Only the browser knows the reader's zone, and the server needs it to decide what
  // "today" and "overdue" mean for them. Read after mount: it is not available during
  // server rendering, and guessing would be worse than asking.
  useEffect(() => {
    setTimeZone(Intl.DateTimeFormat().resolvedOptions().timeZone)
  }, [])

  return (
    <form action={action} className="space-y-4" noValidate>
      {failure && !failure.field && <FormError failure={failure} />}
      <input type="hidden" name="locale" value={locale} />
      <input type="hidden" name="timeZone" value={timeZone} />

      <div className="space-y-2">
        <Label htmlFor="displayName">{t('displayName')}</Label>
        <Input
          id="displayName"
          name="displayName"
          autoComplete="name"
          autoFocus
          required
          placeholder={t('displayNamePlaceholder')}
          aria-invalid={failure?.field === 'displayName'}
        />
        <FieldError failure={failure} field="displayName" />
      </div>

      <div className="space-y-2">
        <Label htmlFor="email">{t('email')}</Label>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          required
          placeholder={t('emailPlaceholder')}
          aria-invalid={failure?.field === 'email'}
        />
        <FieldError failure={failure} field="email" />
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">{t('password')}</Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          required
          placeholder={t('passwordPlaceholder')}
          aria-invalid={failure?.field === 'password'}
        />
        <FieldError failure={failure} field="password" />
      </div>

      <SubmitButton className="w-full" pendingLabel={t('creatingAccount')}>
        {t('signUp')}
      </SubmitButton>
    </form>
  )
}
