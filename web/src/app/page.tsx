import { redirect } from 'next/navigation'

import { hasSession } from '@/lib/session'

/**
 * The root path is a signpost, not a screen.
 *
 * There is no marketing page to show: the app is the product. Deciding here rather
 * than in middleware keeps the redirect next to the cookie check it depends on.
 */
export default async function RootPage() {
  redirect((await hasSession()) ? '/dashboard' : '/login')
}
