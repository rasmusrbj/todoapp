import { faListCheck } from '@fortawesome/pro-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { redirect } from 'next/navigation'
import { getTranslations } from 'next-intl/server'

import { LocaleSwitcher } from '@/components/locale-switcher'
import { ThemeToggle } from '@/components/theme-toggle'
import { hasSession } from '@/lib/session'

/**
 * Shell for the unauthenticated screens.
 *
 * A single centred card on a tinted page — no navigation, because there is nowhere
 * to go until you are signed in. Language and appearance are reachable here on
 * purpose: someone who cannot read the sign-in form cannot get far enough to change
 * the language later.
 */
export default async function AuthLayout({ children }: { children: React.ReactNode }) {
  // Already signed in: there is nothing to do on these pages.
  if (await hasSession()) {
    redirect('/dashboard')
  }
  const t = await getTranslations('app')

  return (
    <div className="flex min-h-svh flex-col bg-zinc-50 dark:bg-zinc-950">
      <header className="flex items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <FontAwesomeIcon icon={faListCheck} className="h-4 w-4" />
          </span>
          <span className="text-sm font-semibold">{t('name')}</span>
        </div>
        <div className="flex items-center gap-1">
          <LocaleSwitcher />
          <ThemeToggle />
        </div>
      </header>

      <main className="flex flex-1 items-start justify-center px-4 pb-16 pt-6 sm:items-center sm:pt-0">
        <div className="w-full max-w-[26rem]">{children}</div>
      </main>

      <footer className="px-6 pb-6 text-center text-sm text-muted-foreground">
        {t('tagline')}
      </footer>
    </div>
  )
}
