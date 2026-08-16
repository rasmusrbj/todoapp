/**
 * Session and locale cookies, read and written only on the server.
 *
 * The API's bearer token never reaches the browser. The Next.js server holds it in
 * an `HttpOnly` cookie on *its own* origin and attaches it as an `Authorization`
 * header when it calls the backend. That means:
 *
 * - No token in `document.cookie`, so an XSS bug cannot read it.
 * - No cross-origin cookie, so no CORS and no `SameSite` gymnastics between
 *   `localhost:3000` and the API.
 * - Server Components can fetch data directly, with no client-side round-trip.
 */

import 'server-only'

import { cookies } from 'next/headers'

import {
  asLocale,
  defaultLocale,
  localeCookieMaxAge,
  localeCookieName,
  type Locale,
} from '@/i18n/config'

/** Cookie holding the API bearer token. Never exposed to client JavaScript. */
const SESSION_COOKIE = 'todoapp_session'

/** Matches the backend's session TTL, so the cookie and the session expire together. */
const SESSION_MAX_AGE = 60 * 60 * 24 * 30

/** Returns the API token for this request, or `undefined` when signed out. */
export async function getSessionToken(): Promise<string | undefined> {
  return (await cookies()).get(SESSION_COOKIE)?.value
}

/** Whether this request carries a session cookie at all. */
export async function hasSession(): Promise<boolean> {
  return (await getSessionToken()) !== undefined
}

/**
 * Stores the API token.
 *
 * `secure` follows `NODE_ENV` because local development is plain HTTP; a production
 * deployment must serve HTTPS, and the flag then keeps the cookie off any
 * accidental cleartext request.
 */
export async function setSessionToken(token: string): Promise<void> {
  ;(await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: SESSION_MAX_AGE,
  })
}

/** Forgets the API token. */
export async function clearSessionToken(): Promise<void> {
  ;(await cookies()).delete(SESSION_COOKIE)
}

/** Returns the reader's locale from the cookie, falling back to Danish. */
export async function getLocaleCookie(): Promise<Locale> {
  return asLocale((await cookies()).get(localeCookieName)?.value) ?? defaultLocale
}

/**
 * Stores the locale.
 *
 * Not `httpOnly`: the theme and language are the two things a client component may
 * legitimately want to read, and neither is a secret.
 */
export async function setLocaleCookie(locale: Locale): Promise<void> {
  ;(await cookies()).set(localeCookieName, locale, {
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: localeCookieMaxAge,
  })
}
