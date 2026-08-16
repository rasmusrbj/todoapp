'use server'

/**
 * Profile and admin account Server Actions.
 */

import { revalidatePath } from 'next/cache'

import { Locale as ProtoLocale, ThemePreference, UserRole, UserStatus } from '@/gen/todo/v1/enums_pb'
import { asLocale } from '@/i18n/config'
import { userClient } from '@/lib/api'
import { fromProtoLocale } from '@/lib/enums'
import { type ActionResult, fail, succeed, toFailure } from '@/lib/errors'
import { setLocaleCookie } from '@/lib/session'

function text(form: FormData, key: string): string {
  const value = form.get(key)
  return typeof value === 'string' ? value.trim() : ''
}

export async function updateProfile(_previous: unknown, form: FormData): Promise<ActionResult> {
  const id = text(form, 'id')
  if (!id) return fail('ERROR_REASON_FIELD_REQUIRED', 'id')

  const request: Parameters<typeof userClient.updateUser>[0] = { id }
  if (form.has('displayName')) {
    const displayName = text(form, 'displayName')
    if (!displayName) return fail('ERROR_REASON_FIELD_REQUIRED', 'displayName')
    request.displayName = displayName
  }
  if (form.has('bio')) request.bio = text(form, 'bio')
  if (form.has('avatarUrl')) request.avatarUrl = text(form, 'avatarUrl')
  if (form.has('timeZone')) request.timeZone = text(form, 'timeZone')

  try {
    await userClient.updateUser(request)
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/settings')
  revalidatePath('/', 'layout')
  return succeed(undefined)
}

/**
 * Saves language and appearance together.
 *
 * The locale cookie is written alongside the profile so the very next render is in the
 * new language, rather than waiting for the reader to reload.
 */
export async function updatePreferences(
  _previous: unknown,
  form: FormData,
): Promise<ActionResult> {
  const id = text(form, 'id')
  if (!id) return fail('ERROR_REASON_FIELD_REQUIRED', 'id')

  const localeValue = Number(form.get('locale')) || ProtoLocale.DA
  const themeValue = Number(form.get('theme')) || ThemePreference.SYSTEM

  try {
    await userClient.updateUser({
      id,
      locale: localeValue,
      theme: themeValue,
      ...(form.has('timeZone') ? { timeZone: text(form, 'timeZone') } : {}),
    })
    const locale = asLocale(fromProtoLocale(localeValue))
    if (locale) await setLocaleCookie(locale)
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/', 'layout')
  return succeed(undefined)
}

// --- Admin -------------------------------------------------------------------

export async function createUser(_previous: unknown, form: FormData): Promise<ActionResult> {
  const email = text(form, 'email')
  const displayName = text(form, 'displayName')
  const password = String(form.get('password') ?? '')

  if (!displayName) return fail('ERROR_REASON_FIELD_REQUIRED', 'displayName')
  if (!email) return fail('ERROR_REASON_FIELD_REQUIRED', 'email')
  if (password.length < 10) return fail('ERROR_REASON_PASSWORD_TOO_WEAK', 'password')

  try {
    await userClient.createUser({
      email,
      password,
      displayName,
      role: Number(form.get('role')) || UserRole.MEMBER,
      locale: Number(form.get('locale')) || ProtoLocale.DA,
      timeZone: text(form, 'timeZone') || 'Europe/Copenhagen',
    })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/admin/users')
  return succeed(undefined)
}

export async function setUserStatus(
  id: string,
  status: UserStatus,
  reason: string,
): Promise<ActionResult> {
  try {
    await userClient.updateUserStatus({ id, status, reason })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/admin/users')
  return succeed(undefined)
}

export async function setUserRole(id: string, role: UserRole): Promise<ActionResult> {
  try {
    await userClient.updateUser({ id, role })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/admin/users')
  return succeed(undefined)
}
