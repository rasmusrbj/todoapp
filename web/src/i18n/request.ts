/**
 * Per-request next-intl configuration.
 *
 * Resolution order: the locale cookie, then the signed-in user's stored preference
 * is applied by `setLocaleCookie` at sign-in, then `Accept-Language`, then Danish.
 * Reading the cookie here means every Server Component gets the right language
 * without a round-trip or a client-side re-render.
 */

import { cookies, headers } from 'next/headers'
import { getRequestConfig } from 'next-intl/server'

import { asLocale, defaultLocale, intlTags, localeCookieName, type Locale } from './config'

/** Picks the best supported locale from an `Accept-Language` header. */
function fromAcceptLanguage(header: string | null): Locale | undefined {
  if (!header) return undefined
  for (const part of header.split(',')) {
    const tag = part.split(';')[0]?.trim().toLowerCase()
    const candidate = asLocale(tag?.split('-')[0])
    if (candidate) return candidate
  }
  return undefined
}

export default getRequestConfig(async () => {
  const [cookieStore, headerList] = await Promise.all([cookies(), headers()])

  const locale =
    asLocale(cookieStore.get(localeCookieName)?.value) ??
    fromAcceptLanguage(headerList.get('accept-language')) ??
    defaultLocale

  return {
    locale,
    messages: (await import(`../../messages/${locale}.json`)).default,
    // `Intl` needs a region to format dates and numbers the way each locale expects.
    formats: {
      dateTime: {
        short: { day: 'numeric', month: 'short' },
        long: { day: 'numeric', month: 'long', year: 'numeric' },
        full: { dateStyle: 'long', timeStyle: 'short' },
      },
    },
    timeZone: 'Europe/Copenhagen',
    onError(error) {
      // A missing key is a bug, not something to swallow silently in development.
      if (process.env.NODE_ENV !== 'production') {
        console.error('[next-intl]', error.message)
      }
    },
    getMessageFallback({ key, namespace }) {
      const path = [namespace, key].filter(Boolean).join('.')
      return process.env.NODE_ENV === 'production' ? path : `⚠️ ${path}`
    },
    // Exposed so components can build an Intl formatter with the right tag.
    now: new Date(),
    ...{ _intlTag: intlTags[locale] },
  }
})
