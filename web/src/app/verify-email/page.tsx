import { faCircleCheck, faCircleExclamation, faListCheck } from '@fortawesome/pro-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import type { Metadata } from 'next'
import Link from 'next/link'
import { getTranslations } from 'next-intl/server'

import { verifyEmail } from '@/app/actions/auth'
import { LocaleSwitcher } from '@/components/locale-switcher'
import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { asLocale } from '@/i18n/config'
import { hasSession, setLocaleCookie } from '@/lib/session'

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('auth')
  return { title: t('verifyTitle') }
}

/**
 * Confirms an email address from the link in the verification message.
 *
 * Outside the `(auth)` group on purpose: that layout redirects a signed-in reader
 * away, and following this link while already signed in is the common case — you
 * registered in this browser a minute ago.
 */
export default async function VerifyEmailPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string; lang?: string }>
}) {
  const { token, lang } = await searchParams

  const requested = asLocale(lang)
  if (requested) {
    await setLocaleCookie(requested)
  }

  const [t, app] = await Promise.all([getTranslations('auth'), getTranslations('app')])
  const result = await verifyEmail(token ?? '')
  const signedIn = await hasSession()

  return (
    <div className="flex min-h-svh flex-col bg-zinc-50 dark:bg-zinc-950">
      <header className="flex items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <FontAwesomeIcon icon={faListCheck} className="h-4 w-4" />
          </span>
          <span className="text-sm font-semibold">{app('name')}</span>
        </div>
        <div className="flex items-center gap-1">
          <LocaleSwitcher />
          <ThemeToggle />
        </div>
      </header>

      <main className="flex flex-1 items-start justify-center px-4 pb-16 pt-6 sm:items-center sm:pt-0">
        <Card className="w-full max-w-sm rounded-xl">
          <CardHeader>
            <div className="flex items-center gap-3">
              <span
                className={
                  result.ok
                    ? 'flex size-9 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                    : 'flex size-9 items-center justify-center rounded-full bg-destructive/10 text-destructive'
                }
              >
                <FontAwesomeIcon
                  icon={result.ok ? faCircleCheck : faCircleExclamation}
                  className="h-4 w-4"
                />
              </span>
              <div className="min-w-0">
                <CardTitle className="text-lg">{t('verifyTitle')}</CardTitle>
                <CardDescription>
                  {result.ok ? t('verifyDone') : t('verifyFailed')}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Button asChild className="press w-full">
              <Link href={signedIn ? '/dashboard' : '/login'}>
                {signedIn ? app('goToDashboard') : t('signIn')}
              </Link>
            </Button>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
