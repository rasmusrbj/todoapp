'use server'

/**
 * Search behind the ⌘K palette.
 *
 * One action, three parallel reads, one flat result set. The palette calls it on a
 * debounce, so it has to be a single round-trip rather than one request per kind of
 * thing — and it must never leak anything the caller could not already reach, which is
 * why it goes through the same authorized RPCs as every screen.
 */

import { taskClient, listClient, userClient } from '@/lib/api'
import { isUnauthenticated } from '@/lib/errors'
import type { ListColor, TaskStatus } from '@/lib/enums'

/** One row in the palette. */
export type SearchHit =
  | {
      kind: 'task'
      id: string
      title: string
      listName: string
      color: ListColor
      status: TaskStatus
      overdue: boolean
    }
  | { kind: 'list'; id: string; title: string; color: ListColor; openCount: number }
  | { kind: 'person'; id: string; title: string; email: string }

/** How many of each kind to offer. Enough to be useful, few enough to scan. */
const PER_KIND = 6

export async function search(query: string): Promise<SearchHit[]> {
  const trimmed = query.trim()
  if (trimmed.length < 2) return []

  try {
    const [tasks, lists, people] = await Promise.all([
      taskClient.listTasks({ page: { limit: PER_KIND }, query: trimmed }),
      listClient.listLists({ page: { limit: PER_KIND }, query: trimmed, includeArchived: true }),
      // People search needs a verified address, and a member may legitimately not
      // have one yet — so a failure here drops the section instead of the whole search.
      userClient.searchUsers({ query: trimmed, limit: PER_KIND }).catch(() => ({ users: [] })),
    ])

    return [
      ...tasks.tasks.map(
        (task): SearchHit => ({
          kind: 'task',
          id: task.id,
          title: task.title,
          listName: task.list?.name ?? '',
          color: task.list?.color ?? 1,
          status: task.status,
          overdue: task.overdue,
        }),
      ),
      ...lists.lists.map(
        (list): SearchHit => ({
          kind: 'list',
          id: list.id,
          title: list.name,
          color: list.color,
          openCount: list.stats?.openTaskCount ?? 0,
        }),
      ),
      ...people.users.map(
        (user): SearchHit => ({
          kind: 'person',
          id: user.id,
          title: user.displayName,
          email: user.email,
        }),
      ),
    ]
  } catch (error) {
    if (isUnauthenticated(error)) return []
    console.error('[search] failed:', error)
    return []
  }
}
