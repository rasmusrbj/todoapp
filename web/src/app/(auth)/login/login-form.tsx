'use client'

import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { useActionState } from 'react'

import { signIn } from '@/app/actions/auth'
import { FieldError, FormError } from '@/components/form-message'
import { SubmitButton } from '@/components/submit-button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { ActionResult } from '@/lib/errors'

export function LoginForm() {
  const t = useTranslations('auth')
  // `useActionState` keeps the failure across the submit without any local state, and
  // pairs with `useFormStatus` inside SubmitButton for the pending label.
  const [result, action] = useActionState<ActionResult | null, FormData>(signIn, null)
  const failure = result && !result.ok ? result : null

  return (
    <form action={action} className="space-y-4" noValidate>
      {/* Only shown when the failure is not attributable to one field. */}
      {failure && !failure.field && <FormError failure={failure} />}

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

      <div className="space-y-2">
        <div className="flex items-baseline justify-between">
          <Label htmlFor="password">{t('password')}</Label>
          <Link
            href="/forgot-password"
            className="cursor-pointer text-sm text-muted-foreground underline underline-offset-4 transition-colors duration-100 hover:text-foreground"
          >
            {t('forgotPassword')}
          </Link>
        </div>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          aria-invalid={failure?.field === 'password'}
        />
        <FieldError failure={failure} field="password" />
      </div>

      <SubmitButton className="w-full" pendingLabel={t('signingIn')}>
        {t('signIn')}
      </SubmitButton>
    </form>
  )
}
