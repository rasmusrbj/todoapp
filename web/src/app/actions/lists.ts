'use server'

/**
 * List, membership, and label Server Actions.
 *
 * Each one calls the API, invalidates the paths whose data it changed, and returns
 * a result the form can render. Authorization is not repeated here — the server owns
 * it, and duplicating the rules in the client would be one more place to get wrong.
 */

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'

import { ListColor, ListVisibility, MemberRole } from '@/gen/todo/v1/enums_pb'
import { listClient } from '@/lib/api'
import { type ActionResult, fail, succeed, toFailure } from '@/lib/errors'

function text(form: FormData, key: string): string {
  const value = form.get(key)
  return typeof value === 'string' ? value.trim() : ''
}

function enumValue(form: FormData, key: string, fallback: number): number {
  const raw = form.get(key)
  const parsed = Number(raw)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

export async function createList(_previous: unknown, form: FormData): Promise<ActionResult<string>> {
  const name = text(form, 'name')
  if (!name) return fail('ERROR_REASON_FIELD_REQUIRED', 'name')

  try {
    const response = await listClient.createList({
      name,
      description: text(form, 'description'),
      color: enumValue(form, 'color', ListColor.ZINC),
      visibility: enumValue(form, 'visibility', ListVisibility.PRIVATE),
    })
    revalidatePath('/lists')
    revalidatePath('/dashboard')
    return succeed(response.list?.id ?? '')
  } catch (error) {
    return toFailure(error)
  }
}

export async function updateList(_previous: unknown, form: FormData): Promise<ActionResult> {
  const id = text(form, 'id')
  if (!id) return fail('ERROR_REASON_FIELD_REQUIRED', 'id')

  // Only the fields the form actually submitted are sent, so a dialog that edits the
  // name never silently rewrites the description.
  const request: Parameters<typeof listClient.updateList>[0] = { id }
  if (form.has('name')) {
    const name = text(form, 'name')
    if (!name) return fail('ERROR_REASON_FIELD_REQUIRED', 'name')
    request.name = name
  }
  if (form.has('description')) request.description = text(form, 'description')
  if (form.has('color')) request.color = enumValue(form, 'color', ListColor.ZINC)
  if (form.has('visibility')) {
    request.visibility = enumValue(form, 'visibility', ListVisibility.PRIVATE)
  }

  try {
    await listClient.updateList(request)
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/lists')
  revalidatePath(`/lists/${id}`)
  return succeed(undefined)
}

export async function setListArchived(id: string, archived: boolean): Promise<ActionResult> {
  try {
    await listClient.setListArchived({ id, archived })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/lists')
  revalidatePath(`/lists/${id}`)
  revalidatePath('/dashboard')
  return succeed(undefined)
}

export async function deleteList(id: string): Promise<ActionResult> {
  try {
    await listClient.deleteList({ id })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/lists')
  revalidatePath('/dashboard')
  revalidatePath('/tasks')
  // The list's own page no longer exists, so there is nowhere to stay.
  redirect('/lists')
}

export async function reorderLists(listIds: string[]): Promise<ActionResult> {
  try {
    await listClient.reorderLists({ listIds })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/lists')
  return succeed(undefined)
}

// --- Membership --------------------------------------------------------------

export async function addMember(_previous: unknown, form: FormData): Promise<ActionResult> {
  const listId = text(form, 'listId')
  const email = text(form, 'email')
  if (!email) return fail('ERROR_REASON_FIELD_REQUIRED', 'email')

  try {
    await listClient.addMember({
      listId,
      invitee: { case: 'email', value: email },
      role: enumValue(form, 'role', MemberRole.EDITOR),
    })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath(`/lists/${listId}`)
  return succeed(undefined)
}

export async function updateMemberRole(
  listId: string,
  userId: string,
  role: MemberRole,
): Promise<ActionResult> {
  try {
    await listClient.updateMemberRole({ listId, userId, role })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath(`/lists/${listId}`)
  return succeed(undefined)
}

export async function removeMember(listId: string, userId: string): Promise<ActionResult> {
  try {
    await listClient.removeMember({ listId, userId })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath(`/lists/${listId}`)
  revalidatePath('/lists')
  return succeed(undefined)
}

/** Removes the caller from a list they were shared into. */
export async function leaveList(listId: string, userId: string): Promise<ActionResult> {
  try {
    await listClient.removeMember({ listId, userId })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/lists')
  // The list is no longer readable, so its page would 404.
  redirect('/lists')
}

// --- Labels ------------------------------------------------------------------

export async function createLabel(_previous: unknown, form: FormData): Promise<ActionResult> {
  const listId = text(form, 'listId')
  const name = text(form, 'name')
  if (!name) return fail('ERROR_REASON_FIELD_REQUIRED', 'name')

  try {
    await listClient.createLabel({
      listId,
      name,
      color: enumValue(form, 'color', ListColor.ZINC),
    })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath(`/lists/${listId}`)
  return succeed(undefined)
}

export async function updateLabel(
  labelId: string,
  listId: string,
  changes: { name?: string; color?: ListColor },
): Promise<ActionResult> {
  try {
    await listClient.updateLabel({ id: labelId, ...changes })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath(`/lists/${listId}`)
  return succeed(undefined)
}

export async function deleteLabel(labelId: string, listId: string): Promise<ActionResult> {
  try {
    await listClient.deleteLabel({ id: labelId })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath(`/lists/${listId}`)
  revalidatePath('/tasks')
  return succeed(undefined)
}
