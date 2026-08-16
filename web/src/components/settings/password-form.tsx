'use client'

import { useTranslations } from 'next-intl'
import { useActionState, useEffect, useRef } from 'react'
import { toast } from 'sonner'

import { changePassword } from '@/app/actions/auth'
import { FieldError, FormError } from '@/components/form-message'
import { SubmitButton } from '@/components/submit-button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { ActionResult } from '@/lib/errors'

const MIN_PASSWORD_LENGTH = 10

export function PasswordForm() {
  const t = useTranslations('auth')
  const settings = useTranslations('settings')
  const app = useTranslations('app')
  const [result, action] = useActionState<ActionResult | null, FormData>(changePassword, null)
  const formRef = useRef<HTMLFormElement>(null)
  const failure = result && !result.ok ? result : null

  useEffect(() => {
    if (result?.ok) {
      formRef.current?.reset()
      // Worth a toast rather than an inline note: it also signed other devices out.
      toast.success(t('changePasswordDone'))
    }
  }, [result, t])

  return (
    <Card className="rounded-xl">
      <CardHeader>
        <CardTitle className="text-sm">{settings('security')}</CardTitle>
        <CardDescription>{settings('securitySubtitle')}</CardDescription>
      </CardHeader>

      <CardContent>
        <form ref={formRef} action={action} className="space-y-4" noValidate>
          {failure && !failure.field && <FormError failure={failure} />}

          <div className="space-y-2">
            <Label htmlFor="currentPassword">{t('currentPassword')}</Label>
            <Input
              id="currentPassword"
              name="currentPassword"
              type="password"
              autoComplete="current-password"
              required
              aria-invalid={failure?.field === 'currentPassword'}
            />
            <FieldError failure={failure} field="currentPassword" />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="newPassword">{t('newPassword')}</Label>
              <Input
                id="newPassword"
                name="newPassword"
                type="password"
                autoComplete="new-password"
                minLength={MIN_PASSWORD_LENGTH}
                required
                placeholder={t('passwordPlaceholder')}
                aria-invalid={failure?.field === 'newPassword'}
              />
              <FieldError failure={failure} field="newPassword" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="newPasswordConfirmation">{t('newPassword')}</Label>
              <Input
                id="newPasswordConfirmation"
                name="newPasswordConfirmation"
                type="password"
                autoComplete="new-password"
                required
                aria-invalid={failure?.field === 'newPasswordConfirmation'}
              />
              <FieldError failure={failure} field="newPasswordConfirmation" />
            </div>
          </div>

          <div className="flex justify-end">
            <SubmitButton pendingLabel={app('saving')}>{t('changePassword')}</SubmitButton>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
