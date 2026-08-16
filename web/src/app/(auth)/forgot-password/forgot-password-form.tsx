'use client'

import { useLocale, useTranslations } from 'next-intl'
import { useActionState } from 'react'

import { requestPasswordReset } from '@/app/actions/auth'
import { FieldError, FormError, FormSuccess } from '@/components/form-message'
import { SubmitButton } from '@/components/submit-button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { ActionResult } from '@/lib/errors'

export function ForgotPasswordForm() {
  const t = useTranslations('auth')
  const locale = useLocale()
  const [result, action] = useActionState<ActionResult | null, FormData>(
    requestPasswordReset,
    null,
  )
  const failure = result && !result.ok ? result : null

  // The API reports success whether or not the address exists, so this screen says
  // "if there is an account" rather than confirming one — the same wording as the
  // email, and the reason the endpoint cannot be used to enumerate addresses.
  if (result?.ok) {
    return <FormSuccess>{t('forgotSent')}</FormSuccess>
  }

  return (
    <form action={action} className="space-y-4" noValidate>
      {failure && !failure.field && <FormError failure={failure} />}
      <input type="hidden" name="locale" value={locale} />

      <div className="space-y-2">
        <Label htmlFor="email">{t('email')}</Label>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          autoFocus
          required
          placeholder={t('emailPlaceholder')}
          aria-invalid={failure?.field === 'email'}
        />
        <FieldError failure={failure} field="email" />
      </div>

      <SubmitButton className="w-full">{t('forgotSubmit')}</SubmitButton>
    </form>
  )
}
