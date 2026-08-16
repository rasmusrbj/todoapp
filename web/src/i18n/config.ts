/**
 * Locale configuration.
 *
 * The locale lives in a cookie rather than in the URL: there is one canonical path
 * per screen, and switching language does not change the address you would share.
 * The cookie is readable by the server, so a Server Component renders the right
 * language on the first byte with no client-side flash.
 */

/** Every locale this build ships. Kept in step with the `Locale` proto enum. */
export const locales = ['da', 'en'] as const

export type Locale = (typeof locales)[number]

/** Danish is the product's first language, so it is the fallback. */
export const defaultLocale: Locale = 'da'

/** Name of the cookie holding the reader's choice. */
export const localeCookieName = 'todoapp_locale'

/** A year: a language preference is not something to ask about again next week. */
export const localeCookieMaxAge = 60 * 60 * 24 * 365

/** Narrows an arbitrary string to a supported locale, or `undefined`. */
export function asLocale(value: string | undefined | null): Locale | undefined {
  return locales.includes(value as Locale) ? (value as Locale) : undefined
}

/** IETF tag for `Intl` formatting, which needs a region to format dates well. */
export const intlTags: Record<Locale, string> = {
  da: 'da-DK',
  en: 'en-GB',
}

/** What each locale is called *in that locale*, for the language switcher. */
export const localeNames: Record<Locale, string> = {
  da: 'Dansk',
  en: 'English',
}
