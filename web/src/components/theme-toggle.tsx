'use client'

import { faDesktop, faMoon, faSun } from '@fortawesome/pro-regular-svg-icons'
import { faCheck } from '@fortawesome/pro-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const OPTIONS = [
  { value: 'light', icon: faSun, key: 'THEME_PREFERENCE_LIGHT' },
  { value: 'dark', icon: faMoon, key: 'THEME_PREFERENCE_DARK' },
  { value: 'system', icon: faDesktop, key: 'THEME_PREFERENCE_SYSTEM' },
] as const

/**
 * Light / dark / system switch.
 *
 * The icon is resolved after mount: on the server there is no way to know which
 * theme the system prefers, and rendering a guess produces a visible swap.
 */
export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme()
  const t = useTranslations('nav')
  const labels = useTranslations('enums.theme')
  const [mounted, setMounted] = useState(false)

  useEffect(() => setMounted(true), [])

  const icon = !mounted ? faDesktop : resolvedTheme === 'dark' ? faMoon : faSun

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={t('theme')} className="press-icon">
          <FontAwesomeIcon icon={icon} className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-40">
        {OPTIONS.map((option) => (
          <DropdownMenuItem
            key={option.value}
            className="cursor-pointer justify-between"
            onClick={() => setTheme(option.value)}
          >
            <span className="flex items-center gap-2">
              <FontAwesomeIcon icon={option.icon} className="h-3.5 w-3.5" />
              {labels(option.key)}
            </span>
            {mounted && theme === option.value && (
              <FontAwesomeIcon icon={faCheck} className="h-3.5 w-3.5" />
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
