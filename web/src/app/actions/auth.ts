'use server'

/**
 * Authentication Server Actions.
 *
 * Forms post here rather than to the API directly, which is what keeps the bearer
 * token server-side: the action calls Connect, stores the token in an `HttpOnly`
 * cookie, and returns only a result the form can render.
 */

import { redirect } from 'next/navigation'
import { revalidatePath } from 'next/cache'

import { SessionClient } from '@/gen/todo/v1/enums_pb'
import { asLocale, defaultLocale } from '@/i18n/config'
import { authClient, userClient } from '@/lib/api'
import { fromProtoLocale, toProtoLocale } from '@/lib/enums'
import { type ActionResult, fail, succeed, toFailure } from '@/lib/errors'
import { clearSessionToken, setLocaleCookie, setSessionToken } from '@/lib/session'

/** Minimum length the server enforces; checked here too for an instant message. */
const MIN_PASSWORD_LENGTH = 10

function readString(form: FormData, key: string): string {
  const value = form.get(key)
  return typeof value === 'string' ? value.trim() : ''
}

export async function signIn(_previous: unknown, form: FormData): Promise<ActionResult> {
  const email = readString(form, 'email')
  const password = String(form.get('password') ?? '')

  if (!email) return fail('ERROR_REASON_FIELD_REQUIRED', 'email')
  if (!password) return fail('ERROR_REASON_FIELD_REQUIRED', 'password')

  try {
    const response = await authClient.login({
      credentials: { email, password },
      client: SessionClient.WEB,
    })
    await setSessionToken(response.token)
    // Adopt the account's own language, so signing in on a fresh browser lands the
    // reader in the language they chose rather than the browser's default.
    if (response.user) {
      await setLocaleCookie(fromProtoLocale(response.user.locale))
    }
  } catch (error) {
    return toFailure(error)
  }

  // Outside the try: `redirect` throws by design, and catching it would swallow the
  // navigation and report it as a failure.
  redirect('/dashboard')
}

export async function signUp(_previous: unknown, form: FormData): Promise<ActionResult> {
  const email = readString(form, 'email')
  const password = String(form.get('password') ?? '')
  const displayName = readString(form, 'displayName')
  const locale = asLocale(readString(form, 'locale')) ?? defaultLocale

  if (!displayName) return fail('ERROR_REASON_FIELD_REQUIRED', 'displayName')
  if (!email) return fail('ERROR_REASON_FIELD_REQUIRED', 'email')
  if (password.length < MIN_PASSWORD_LENGTH) return fail('ERROR_REASON_PASSWORD_TOO_WEAK', 'password')

  try {
    const response = await authClient.register({
      credentials: { email, password },
      displayName,
      locale: toProtoLocale(locale),
      // The browser knows the reader's zone; the server needs it to decide what
      // "today" and "overdue" mean for them.
      timeZone: readString(form, 'timeZone') || 'Europe/Copenhagen',
      client: SessionClient.WEB,
    })
    await setSessionToken(response.token)
    await setLocaleCookie(locale)
  } catch (error) {
    return toFailure(error)
  }

  redirect('/dashboard')
}

export async function signOut(): Promise<void> {
  try {
    await authClient.logout({})
  } catch {
    // The session may already be gone server-side; the cookie still has to go.
  }
  await clearSessionToken()
  redirect('/login')
}

export async function requestPasswordReset(
  _previous: unknown,
  form: FormData,
): Promise<ActionResult> {
  const email = readString(form, 'email')
  if (!email) return fail('ERROR_REASON_FIELD_REQUIRED', 'email')

  try {
    await authClient.requestPasswordReset({
      email,
      locale: toProtoLocale(asLocale(readString(form, 'locale')) ?? defaultLocale),
    })
  } catch (error) {
    return toFailure(error)
  }
  // Always a success, matching the API: saying otherwise would disclose whether the
  // address is registered.
  return succeed(undefined)
}

export async function resetPassword(_previous: unknown, form: FormData): Promise<ActionResult> {
  const token = readString(form, 'token')
  const password = String(form.get('password') ?? '')
  const confirmation = String(form.get('passwordConfirmation') ?? '')

  if (!token) return fail('ERROR_REASON_TOKEN_INVALID', 'token')
  if (password.length < MIN_PASSWORD_LENGTH) return fail('ERROR_REASON_PASSWORD_TOO_WEAK', 'password')
  if (password !== confirmation) return fail('passwordsDiffer', 'passwordConfirmation')

  try {
    await authClient.resetPassword({ token, newPassword: password })
    // Every session was revoked server-side, so drop the local cookie too.
    await clearSessionToken()
  } catch (error) {
    return toFailure(error)
  }
  return succeed(undefined)
}

export async function verifyEmail(token: string): Promise<ActionResult> {
  if (!token) return fail('ERROR_REASON_TOKEN_INVALID', 'token')
  try {
    await authClient.verifyEmail({ token })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/', 'layout')
  return succeed(undefined)
}

export async function resendVerification(): Promise<ActionResult> {
  try {
    await authClient.resendVerificationEmail({})
  } catch (error) {
    return toFailure(error)
  }
  return succeed(undefined)
}

export async function changePassword(_previous: unknown, form: FormData): Promise<ActionResult> {
  const current = String(form.get('currentPassword') ?? '')
  const next = String(form.get('newPassword') ?? '')
  const confirmation = String(form.get('newPasswordConfirmation') ?? '')

  if (!current) return fail('ERROR_REASON_FIELD_REQUIRED', 'currentPassword')
  if (next.length < MIN_PASSWORD_LENGTH) return fail('ERROR_REASON_PASSWORD_TOO_WEAK', 'newPassword')
  if (next !== confirmation) return fail('passwordsDiffer', 'newPasswordConfirmation')

  try {
    const response = await authClient.changePassword({
      currentPassword: current,
      newPassword: next,
    })
    // Every other session was closed; adopt the replacement token so the reader is
    // not signed out of the tab they are standing in.
    await setSessionToken(response.token)
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/settings')
  return succeed(undefined)
}

export async function revokeSession(sessionId: string): Promise<ActionResult> {
  try {
    await authClient.revokeSession({ id: sessionId })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/settings')
  return succeed(undefined)
}

/** Signs out everywhere, then deletes the account. */
export async function deleteAccount(): Promise<ActionResult> {
  try {
    const me = await userClient.getCurrentUser({})
    if (!me.user) return fail('ERROR_REASON_USER_NOT_FOUND')
    await userClient.deleteUser({ id: me.user.id })
    await clearSessionToken()
  } catch (error) {
    return toFailure(error)
  }
  redirect('/login')
}
