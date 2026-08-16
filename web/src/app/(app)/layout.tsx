import { redirect } from 'next/navigation'

import { AppShell } from '@/components/app-shell'
import { userClient } from '@/lib/api'
import { isUnauthenticated } from '@/lib/errors'
import { clearSessionToken, hasSession } from '@/lib/session'

/**
 * Shell for every signed-in screen.
 *
 * The current user is loaded once here and handed to the navigation, so no page has
 * to fetch it again. A session that the server rejects is cleared before redirecting:
 * otherwise a stale cookie would bounce the reader between `/login` and `/dashboard`.
 */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  if (!(await hasSession())) {
    redirect('/login')
  }

  try {
    const { user } = await userClient.getCurrentUser({})
    if (!user) {
      await clearSessionToken()
      redirect('/login')
    }
    return <AppShell user={user}>{children}</AppShell>
  } catch (error) {
    if (isUnauthenticated(error)) {
      await clearSessionToken()
      redirect('/login')
    }
    throw error
  }
}
