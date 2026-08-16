'use client'

import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { useActionState } from 'react'

import { resetPassword } from '@/app/actions/auth'
import { FieldError, FormError, FormSuccess } from '@/components/form-message'
import { SubmitButton } from '@/components/submit-button'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { ActionResult } from '@/lib/errors'

const MIN_PASSWORD_LENGTH = 10

export function ResetPasswordForm({ token }: { token: string }) {
  const t = useTranslations('auth')
  const [result, action] = useActionState<ActionResult | null, FormData>(resetPassword, null)
  const failure = result && !result.ok ? result : null

  // A link without a token cannot be completed, so say so before the reader types a
  // password they will lose.
  if (!token) {
    return (
      <div className="space-y-4">
        <FormError failure={{ ok: false, reasonKey: 'ERROR_REASON_TOKEN_INVALID', values: {} }} />
        <p className="text-sm text-muted-foreground">{t('resetMissingToken')}</p>
        <Button asChild variant="outline" className="press w-full">
          <Link href="/forgot-password">{t('forgotSubmit')}</Link>
        </Button>
      </div>
    )
  }

  if (result?.ok) {
    return (
      <div className="space-y-4">
        <FormSuccess>{t('resetDone')}</FormSuccess>
        <Button asChild className="press w-full">
          <Link href="/login">{t('signIn')}</Link>
        </Button>
      </div>
    )
  }

  return (
    <form action={action} className="space-y-4" noValidate>
      {failure && !failure.field && <FormError failure={failure} />}
      <input type="hidden" name="token" value={token} />

      <div className="space-y-2">
        <Label htmlFor="password">{t('newPassword')}</Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          autoFocus
          required
          placeholder={t('passwordPlaceholder')}
          aria-invalid={failure?.field === 'password'}
        />
        <FieldError failure={failure} field="password" />
      </div>

      <div className="space-y-2">
        <Label htmlFor="passwordConfirmation">{t('newPassword')}</Label>
        <Input
          id="passwordConfirmation"
          name="passwordConfirmation"
          type="password"
          autoComplete="new-password"
          required
          aria-invalid={failure?.field === 'passwordConfirmation'}
        />
        <FieldError failure={failure} field="passwordConfirmation" />
      </div>

      <SubmitButton className="w-full">{t('resetSubmit')}</SubmitButton>
    </form>
  )
}
