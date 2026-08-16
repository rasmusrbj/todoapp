'use server'

/**
 * Task, subtask, and comment Server Actions.
 */

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { timestampFromDate } from '@bufbuild/protobuf/wkt'

import { RecurrenceFrequency, TaskPriority, TaskStatus } from '@/gen/todo/v1/enums_pb'
import { taskClient } from '@/lib/api'
import { type ActionResult, fail, succeed, toFailure } from '@/lib/errors'

function text(form: FormData, key: string): string {
  const value = form.get(key)
  return typeof value === 'string' ? value.trim() : ''
}

function enumValue(form: FormData, key: string, fallback: number): number {
  const parsed = Number(form.get(key))
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

/**
 * Combines a `<input type="date">` and an optional `<input type="time">`.
 *
 * A date with no time becomes 09:00 local, because an all-day task due "Tuesday"
 * must not read as overdue one minute after midnight. The boolean says whether the
 * clock time is meaningful, which is what the client uses to decide how to render it.
 */
function readDueDate(form: FormData): { dueAt?: ReturnType<typeof timestampFromDate>; dueHasTime: boolean } {
  const date = text(form, 'dueDate')
  if (!date) return { dueHasTime: false }
  const time = text(form, 'dueTime')
  const [year, month, day] = date.split('-').map(Number)
  if (year === undefined || month === undefined || day === undefined) return { dueHasTime: false }
  const [hours, minutes] = (time || '09:00').split(':').map(Number)
  const value = new Date(year, month - 1, day, hours ?? 9, minutes ?? 0)
  return { dueAt: timestampFromDate(value), dueHasTime: Boolean(time) }
}

function readDate(form: FormData, key: string): ReturnType<typeof timestampFromDate> | undefined {
  const raw = text(form, key)
  if (!raw) return undefined
  const [year, month, day] = raw.split('-').map(Number)
  if (year === undefined || month === undefined || day === undefined) return undefined
  return timestampFromDate(new Date(year, month - 1, day, 9, 0))
}

export async function createTask(_previous: unknown, form: FormData): Promise<ActionResult<string>> {
  const listId = text(form, 'listId')
  const title = text(form, 'title')
  if (!listId) return fail('ERROR_REASON_FIELD_REQUIRED', 'listId')
  if (!title) return fail('ERROR_REASON_FIELD_REQUIRED', 'title')

  const { dueAt, dueHasTime } = readDueDate(form)
  const frequency = enumValue(form, 'recurrenceFrequency', RecurrenceFrequency.NONE)
  const assigneeId = text(form, 'assigneeId')

  try {
    const response = await taskClient.createTask({
      listId,
      title,
      description: text(form, 'description'),
      status: enumValue(form, 'status', TaskStatus.TODO),
      priority: enumValue(form, 'priority', TaskPriority.NONE),
      assigneeId: assigneeId || undefined,
      labelIds: form.getAll('labelIds').map(String).filter(Boolean),
      dueAt,
      dueHasTime,
      startsAt: readDate(form, 'startsAt'),
      estimateMinutes: Number(form.get('estimateMinutes')) || 0,
      recurrence: {
        frequency,
        interval: Math.max(Number(form.get('recurrenceInterval')) || 1, 1),
      },
      subtaskTitles: form
        .getAll('subtaskTitles')
        .map((value) => String(value).trim())
        .filter(Boolean),
    })
    revalidatePath('/tasks')
    revalidatePath('/dashboard')
    revalidatePath(`/lists/${listId}`)
    return succeed(response.task?.id ?? '')
  } catch (error) {
    return toFailure(error)
  }
}

export async function updateTask(_previous: unknown, form: FormData): Promise<ActionResult> {
  const id = text(form, 'id')
  if (!id) return fail('ERROR_REASON_FIELD_REQUIRED', 'id')

  const request: Parameters<typeof taskClient.updateTask>[0] = { id }
  if (form.has('title')) {
    const title = text(form, 'title')
    if (!title) return fail('ERROR_REASON_FIELD_REQUIRED', 'title')
    request.title = title
  }
  if (form.has('description')) request.description = text(form, 'description')
  if (form.has('priority')) request.priority = enumValue(form, 'priority', TaskPriority.NONE)
  if (form.has('estimateMinutes')) {
    request.estimateMinutes = Number(form.get('estimateMinutes')) || 0
  }
  if (form.has('recurrenceFrequency')) {
    request.recurrence = {
      frequency: enumValue(form, 'recurrenceFrequency', RecurrenceFrequency.NONE),
      interval: Math.max(Number(form.get('recurrenceInterval')) || 1, 1),
    }
  }
  if (form.has('dueDate')) {
    const { dueAt, dueHasTime } = readDueDate(form)
    // Proto3 presence cannot express "remove this", so the API takes an explicit
    // clear flag and the form sends an empty date to mean exactly that.
    if (dueAt) {
      request.dueAt = dueAt
      request.dueHasTime = dueHasTime
    } else {
      request.clearDueAt = true
    }
  }
  if (form.has('startsAt')) {
    const startsAt = readDate(form, 'startsAt')
    if (startsAt) request.startsAt = startsAt
    else request.clearStartsAt = true
  }

  try {
    await taskClient.updateTask(request)
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/tasks')
  revalidatePath(`/tasks/${id}`)
  revalidatePath('/dashboard')
  revalidatePath('/lists', 'layout')
  return succeed(undefined)
}

export async function setTaskStatus(id: string, status: TaskStatus): Promise<ActionResult<string>> {
  try {
    const response = await taskClient.setTaskStatus({ id, status })
    revalidatePath('/tasks')
    revalidatePath(`/tasks/${id}`)
    revalidatePath('/dashboard')
    revalidatePath('/lists', 'layout')
    // The id of the follow-up occurrence, when completing a repeating task made one.
    return succeed(response.nextOccurrence?.id ?? '')
  } catch (error) {
    return toFailure(error)
  }
}

export async function assignTask(id: string, assigneeId: string | undefined): Promise<ActionResult> {
  try {
    await taskClient.assignTask({ id, assigneeId })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/tasks')
  revalidatePath(`/tasks/${id}`)
  revalidatePath('/lists', 'layout')
  return succeed(undefined)
}

export async function moveTask(
  id: string,
  position: number,
  listId?: string,
): Promise<ActionResult> {
  try {
    await taskClient.moveTask({ id, position, listId })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/tasks')
  revalidatePath('/lists', 'layout')
  return succeed(undefined)
}

export async function deleteTask(id: string, returnTo?: string): Promise<ActionResult> {
  try {
    await taskClient.deleteTask({ id })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath('/tasks')
  revalidatePath('/dashboard')
  revalidatePath('/lists', 'layout')
  if (returnTo) redirect(returnTo)
  return succeed(undefined)
}

export async function bulkSetStatus(taskIds: string[], status: TaskStatus): Promise<ActionResult<number>> {
  try {
    const response = await taskClient.bulkUpdateTasks({
      taskIds,
      change: { case: 'status', value: status },
    })
    revalidatePath('/tasks')
    revalidatePath('/dashboard')
    revalidatePath('/lists', 'layout')
    return succeed(response.updatedCount)
  } catch (error) {
    return toFailure(error)
  }
}

export async function bulkSetPriority(
  taskIds: string[],
  priority: TaskPriority,
): Promise<ActionResult<number>> {
  try {
    const response = await taskClient.bulkUpdateTasks({
      taskIds,
      change: { case: 'priority', value: priority },
    })
    revalidatePath('/tasks')
    revalidatePath('/lists', 'layout')
    return succeed(response.updatedCount)
  } catch (error) {
    return toFailure(error)
  }
}

export async function setTaskLabels(taskId: string, labelIds: string[]): Promise<ActionResult> {
  try {
    await taskClient.setTaskLabels({ taskId, labelIds })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath(`/tasks/${taskId}`)
  revalidatePath('/tasks')
  return succeed(undefined)
}

// --- Subtasks ----------------------------------------------------------------

export async function createSubtask(_previous: unknown, form: FormData): Promise<ActionResult> {
  const taskId = text(form, 'taskId')
  const title = text(form, 'title')
  if (!title) return fail('ERROR_REASON_FIELD_REQUIRED', 'title')

  try {
    await taskClient.createSubtask({ taskId, title })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath(`/tasks/${taskId}`)
  revalidatePath('/tasks')
  return succeed(undefined)
}

export async function setSubtaskCompleted(
  id: string,
  taskId: string,
  completed: boolean,
): Promise<ActionResult> {
  try {
    await taskClient.updateSubtask({ id, completed })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath(`/tasks/${taskId}`)
  revalidatePath('/tasks')
  return succeed(undefined)
}

export async function deleteSubtask(id: string, taskId: string): Promise<ActionResult> {
  try {
    await taskClient.deleteSubtask({ id })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath(`/tasks/${taskId}`)
  revalidatePath('/tasks')
  return succeed(undefined)
}

// --- Comments ----------------------------------------------------------------

export async function createComment(_previous: unknown, form: FormData): Promise<ActionResult> {
  const taskId = text(form, 'taskId')
  const body = text(form, 'body')
  if (!body) return fail('ERROR_REASON_FIELD_REQUIRED', 'body')

  try {
    await taskClient.createComment({ taskId, body })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath(`/tasks/${taskId}`)
  return succeed(undefined)
}

export async function updateComment(
  id: string,
  taskId: string,
  body: string,
): Promise<ActionResult> {
  if (!body.trim()) return fail('ERROR_REASON_FIELD_REQUIRED', 'body')
  try {
    await taskClient.updateComment({ id, body: body.trim() })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath(`/tasks/${taskId}`)
  return succeed(undefined)
}

export async function deleteComment(id: string, taskId: string): Promise<ActionResult> {
  try {
    await taskClient.deleteComment({ id })
  } catch (error) {
    return toFailure(error)
  }
  revalidatePath(`/tasks/${taskId}`)
  return succeed(undefined)
}
