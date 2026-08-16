import { faCompass } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import type { Metadata } from 'next'
import Link from 'next/link'
import { getTranslations } from 'next-intl/server'

import { Button } from '@/components/ui/button'
import { hasSession } from '@/lib/session'

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('app')
  return { title: t('notFoundTitle') }
}

/**
 * The 404 for the whole app.
 *
 * Also what a `notFound()` from a page renders, which is the common case: a task or
 * list id that no longer exists, or one the reader may not see — the API reports both
 * the same way, and so does this.
 *
 * Where "back" points depends on whether there is a session, because sending a
 * signed-out reader to the dashboard just bounces them to sign-in.
 */
export default async function NotFound() {
  const [t, signedIn] = await Promise.all([getTranslations('app'), hasSession()])

  return (
    <main className="flex min-h-svh items-center justify-center bg-zinc-50 px-4 dark:bg-zinc-950">
      <div className="flex w-full max-w-md flex-col items-center gap-6 rounded-xl border border-border bg-card px-6 py-14 text-center">
        <span className="flex size-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <FontAwesomeIcon icon={faCompass} className="h-6 w-6" />
        </span>
        <div className="space-y-1.5">
          <h1 className="text-2xl font-semibold tracking-tight text-balance">
            {t('notFoundTitle')}
          </h1>
          <p className="text-[15px] text-muted-foreground text-pretty">{t('notFoundBody')}</p>
        </div>
        <Button asChild className="press">
          <Link href={signedIn ? '/dashboard' : '/login'}>{t('goToDashboard')}</Link>
        </Button>
      </div>
    </main>
  )
}
