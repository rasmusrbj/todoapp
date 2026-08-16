import { faListCheck } from '@fortawesome/pro-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import Link from 'next/link'
import { getTranslations } from 'next-intl/server'

import { CommandPalette } from '@/components/command-palette'
import { EmailVerificationBanner } from '@/components/email-verification-banner'
import { LocaleSwitcher } from '@/components/locale-switcher'
import { BottomNav, NavLinks } from '@/components/nav-links'
import { ThemeToggle } from '@/components/theme-toggle'
import { UserMenu } from '@/components/user-menu'
import type { User } from '@/gen/todo/v1/user_pb'
import { UserRole } from '@/lib/enums'

/**
 * The signed-in chrome.
 *
 * Two layouts rather than one squeezed into both: a sidebar from `lg` up, and on narrow
 * screens a top bar for identity and utilities with the primary navigation moved to a
 * bottom tab bar. Five nav items plus three utilities plus a logo do not fit in a 390px
 * header — trying produced a clipped icon and nothing comfortably tappable.
 *
 * A Server Component, so the chrome ships no JavaScript beyond the parts that need it.
 */
export async function AppShell({ user, children }: { user: User; children: React.ReactNode }) {
  const t = await getTranslations('app')
  const isAdmin = user.role === UserRole.ADMIN

  return (
    <div className="min-h-svh bg-zinc-50 dark:bg-zinc-950">
      {/* Sidebar: fixed from `lg` up, absent below it. */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-border bg-background lg:flex">
        <div className="flex h-16 items-center border-b border-border px-5">
          <Link href="/dashboard" className="press flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <FontAwesomeIcon icon={faListCheck} className="h-4 w-4" />
            </span>
            <span className="font-semibold tracking-tight">{t('name')}</span>
          </Link>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          <NavLinks isAdmin={isAdmin} />
        </nav>
        <div className="border-t border-border p-3">
          <UserMenu user={user} />
        </div>
      </aside>

      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur-sm sm:px-8">
          <Link href="/dashboard" className="press flex items-center gap-2.5 lg:hidden">
            <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <FontAwesomeIcon icon={faListCheck} className="h-4 w-4" />
            </span>
            <span className="font-semibold tracking-tight">{t('name')}</span>
          </Link>

          {/* Search is the fastest way into anything, so it gets real width. */}
          <div className="ml-auto hidden sm:block">
            <CommandPalette isAdmin={isAdmin} />
          </div>

          <div className="ml-auto flex items-center gap-1 sm:ml-0">
            <LocaleSwitcher />
            <ThemeToggle />
            <span className="lg:hidden">
              <UserMenu user={user} compact />
            </span>
          </div>
        </header>

        {/* The bottom padding below `lg` keeps the last row clear of the tab bar. */}
        <main className="mx-auto w-full max-w-6xl px-4 pt-8 pb-28 sm:px-8 sm:pt-10 lg:pb-10">
          {!user.emailVerified && <EmailVerificationBanner className="mb-6" />}
          {children}
        </main>
      </div>

      <BottomNav isAdmin={isAdmin} />
    </div>
  )
}
