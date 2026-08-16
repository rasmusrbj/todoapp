'use server'

/**
 * Locale and appearance preferences.
 *
 * The locale lives in a cookie so the server can render the right language on the
 * first byte. When the reader is signed in, the choice is also written to their
 * profile, so it follows them to another browser and to the CLI.
 */

import { revalidatePath } from 'next/cache'

import { asLocale } from '@/i18n/config'
import { userClient } from '@/lib/api'
import { toProtoLocale } from '@/lib/enums'
import { type ActionResult, fail, succeed } from '@/lib/errors'
import { hasSession, setLocaleCookie } from '@/lib/session'

/**
 * Switches the interface language.
 *
 * The cookie is written first so the change lands even for a signed-out reader on
 * the sign-in screen. Persisting to the profile is best-effort for the same reason:
 * failing to save a preference must not block reading the page in that language.
 */
export async function setLocale(value: string): Promise<ActionResult> {
  const locale = asLocale(value)
  if (!locale) return fail('ERROR_REASON_INVALID_ENUM_VALUE', 'locale')

  await setLocaleCookie(locale)

  if (await hasSession()) {
    try {
      const me = await userClient.getCurrentUser({})
      if (me.user) {
        await userClient.updateUser({ id: me.user.id, locale: toProtoLocale(locale) })
      }
    } catch (error) {
      console.error('[preferences] could not persist locale to the profile:', error)
    }
  }

  revalidatePath('/', 'layout')
  return succeed(undefined)
}

