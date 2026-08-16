'use client'

import { useTranslations } from 'next-intl'
import { useTheme } from 'next-themes'
import { useActionState, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { updatePreferences } from '@/app/actions/users'
import { FormError } from '@/components/form-message'
import { SubmitButton } from '@/components/submit-button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { LocaleSchema, ThemePreferenceSchema } from '@/gen/todo/v1/enums_pb'
import { options, ThemePreference, valueName } from '@/lib/enums'
import type { ActionResult } from '@/lib/errors'

const LOCALE_OPTIONS = options(LocaleSchema, 'x')
const THEME_OPTIONS = options(ThemePreferenceSchema, 'x')

/** Maps the stored preference onto what `next-themes` understands. */
const THEME_TO_CLASS: Record<number, string> = {
  [ThemePreference.SYSTEM]: 'system',
  [ThemePreference.LIGHT]: 'light',
  [ThemePreference.DARK]: 'dark',
}

export function PreferencesForm({
  user,
}: {
  user: { id: string; locale: number; theme: number; timeZone: string }
}) {
  const t = useTranslations('settings')
  const app = useTranslations('app')
  const auth = useTranslations('auth')
  const locales = useTranslations('enums.locale')
  const themes = useTranslations('enums.theme')

  const { setTheme } = useTheme()
  const [locale, setLocale] = useState(String(user.locale))
  const [theme, setTheme_] = useState(String(user.theme))
  const [result, action] = useActionState<ActionResult | null, FormData>(updatePreferences, null)
  const failure = result && !result.ok ? result : null

  useEffect(() => {
    if (result?.ok) toast.success(t('saved'))
  }, [result, t])

  return (
    <Card className="rounded-xl">
      <CardHeader>
        <CardTitle className="text-sm">{t('preferences')}</CardTitle>
        <CardDescription>{t('preferencesSubtitle')}</CardDescription>
      </CardHeader>

      <CardContent>
        <form action={action} className="space-y-4" noValidate>
          <input type="hidden" name="id" value={user.id} />
          <input type="hidden" name="locale" value={locale} />
          <input type="hidden" name="theme" value={theme} />
          {failure && <FormError failure={failure} />}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="pref-locale">{t('language')}</Label>
              <Select value={locale} onValueChange={setLocale}>
                <SelectTrigger id="pref-locale" className="cursor-pointer">
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

            <div className="space-y-2">
              <Label htmlFor="pref-theme">{t('theme')}</Label>
              <Select
                value={theme}
                onValueChange={(value) => {
                  setTheme_(value)
                  // Apply immediately: waiting for the save would make the control
                  // feel broken. The submit is what makes it stick to the account.
                  const mapped = THEME_TO_CLASS[Number(value)]
                  if (mapped) setTheme(mapped)
                }}
              >
                <SelectTrigger id="pref-theme" className="cursor-pointer">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {THEME_OPTIONS.map((option) => (
                    <SelectItem
                      key={option.value}
                      value={String(option.value)}
                      className="cursor-pointer"
                    >
                      {themes(option.name)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="pref-timezone">{auth('timeZone')}</Label>
            <Input
              id="pref-timezone"
              name="timeZone"
              defaultValue={user.timeZone}
              placeholder="Europe/Copenhagen"
            />
            <p className="text-sm text-muted-foreground">
              {/* The zone decides what "today" and "overdue" mean for this account. */}
              {valueName(ThemePreferenceSchema, Number(theme)) && null}
              {Intl.DateTimeFormat().resolvedOptions().timeZone}
            </p>
          </div>

          <div className="flex justify-end">
            <SubmitButton pendingLabel={app('saving')}>{app('save')}</SubmitButton>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
