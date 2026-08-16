'use client'

import { faGlobe } from '@fortawesome/pro-regular-svg-icons'
import { faCheck } from '@fortawesome/pro-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useLocale, useTranslations } from 'next-intl'
import { useTransition } from 'react'

import { setLocale } from '@/app/actions/preferences'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { localeNames, locales, type Locale } from '@/i18n/config'

/**
 * Language switcher.
 *
 * Writing the locale cookie is a Server Action, so the next render comes back in the
 * new language with no client-side message bundle swap and no flash of the old one.
 */
export function LocaleSwitcher() {
  const current = useLocale() as Locale
  const t = useTranslations('nav')
  const [pending, startTransition] = useTransition()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={t('language')}
          disabled={pending}
          className="press-icon"
        >
          <FontAwesomeIcon icon={faGlobe} className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-36">
        {locales.map((locale) => (
          <DropdownMenuItem
            key={locale}
            className="cursor-pointer justify-between"
            onClick={() => startTransition(() => void setLocale(locale))}
          >
            {localeNames[locale]}
            {locale === current && <FontAwesomeIcon icon={faCheck} className="h-3.5 w-3.5" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
