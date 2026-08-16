'use client'

import { faUserPlus } from '@fortawesome/pro-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useActionState, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { createUser } from '@/app/actions/users'
import { FieldError, FormError } from '@/components/form-message'
import { SubmitButton } from '@/components/submit-button'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { LocaleSchema, UserRoleSchema } from '@/gen/todo/v1/enums_pb'
import { options, ProtoLocale, UserRole } from '@/lib/enums'
import type { ActionResult } from '@/lib/errors'

const ROLE_OPTIONS = options(UserRoleSchema, 'x')
const LOCALE_OPTIONS = options(LocaleSchema, 'x')

/** Creates an account directly, skipping self-signup. Admin only. */
export function UserCreateDialog() {
  const t = useTranslations('admin')
  const auth = useTranslations('auth')
  const app = useTranslations('app')
  const settings = useTranslations('settings')
  const roles = useTranslations('enums.userRole')
  const locales = useTranslations('enums.locale')

  const [open, setOpen] = useState(false)
  const [role, setRole] = useState<number>(UserRole.MEMBER)
  const [locale, setLocale] = useState<number>(ProtoLocale.DA)
  const [result, action] = useActionState<ActionResult | null, FormData>(createUser, null)
  const failure = result && !result.ok ? result : null

  useEffect(() => {
    if (result?.ok) {
      setOpen(false)
      toast.success(t('userCreated'))
    }
  }, [result, t])

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="press">
          <FontAwesomeIcon icon={faUserPlus} className="h-4 w-4" />
          {t('newUser')}
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-md" closeLabel={app('close')}>
        <DialogHeader>
          <DialogTitle>{t('createTitle')}</DialogTitle>
          <DialogDescription>{t('createSubtitle')}</DialogDescription>
        </DialogHeader>

        <form action={action} className="space-y-4" noValidate>
          <input type="hidden" name="role" value={role} />
          <input type="hidden" name="locale" value={locale} />
          {failure && !failure.field && <FormError failure={failure} />}

          <div className="space-y-2">
            <Label htmlFor="new-user-name">{auth('displayName')}</Label>
            <Input
              id="new-user-name"
              name="displayName"
              autoFocus
              required
              placeholder={auth('displayNamePlaceholder')}
              aria-invalid={failure?.field === 'displayName'}
            />
            <FieldError failure={failure} field="displayName" />
          </div>

          <div className="space-y-2">
            <Label htmlFor="new-user-email">{auth('email')}</Label>
            <Input
              id="new-user-email"
              name="email"
              type="email"
              required
              placeholder={auth('emailPlaceholder')}
              aria-invalid={failure?.field === 'email'}
            />
            <FieldError failure={failure} field="email" />
          </div>

          <div className="space-y-2">
            <Label htmlFor="new-user-password">{auth('password')}</Label>
            <Input
              id="new-user-password"
              name="password"
              type="password"
              autoComplete="new-password"
              minLength={10}
              required
              placeholder={auth('passwordPlaceholder')}
              aria-invalid={failure?.field === 'password'}
            />
            <FieldError failure={failure} field="password" />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="new-user-role">{t('role')}</Label>
              <Select value={String(role)} onValueChange={(value) => setRole(Number(value))}>
                <SelectTrigger id="new-user-role" className="cursor-pointer">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLE_OPTIONS.map((option) => (
                    <SelectItem
                      key={option.value}
                      value={String(option.value)}
                      className="cursor-pointer"
                    >
                      {roles(option.name)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="new-user-locale">{settings('language')}</Label>
              <Select value={String(locale)} onValueChange={(value) => setLocale(Number(value))}>
                <SelectTrigger id="new-user-locale" className="cursor-pointer">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LOCALE_OPTIONS.map((option) => (
                    <SelectItem
                      key={option.value}
                      value={String(option.value)}
                      className="cursor-pointer"
                    >
                      {locales(option.name)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" className="press" onClick={() => setOpen(false)}>
              {app('cancel')}
            </Button>
            <SubmitButton pendingLabel={app('saving')}>{app('create')}</SubmitButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
