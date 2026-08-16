import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowRotateLeft,
  faBoxArchive,
  faComment,
  faPen,
  faPlus,
  faRightLeft,
  faTrash,
  faUserMinus,
  faUserPlus,
} from '@fortawesome/pro-regular-svg-icons'
import Link from 'next/link'
import { getLocale, getTranslations } from 'next-intl/server'

import { ColorDot } from '@/components/enum-badge'
import type { Activity } from '@/gen/todo/v1/task_pb'
import {
  ActivityActionSchema,
  ListColorSchema,
  ListVisibilitySchema,
  MemberRoleSchema,
  TaskPrioritySchema,
  TaskStatusSchema,
} from '@/gen/todo/v1/enums_pb'
import type { Locale } from '@/i18n/config'
import { ActivityAction, valueName } from '@/lib/enums'
import { formatDateTime, pastPhrase, toDate } from '@/lib/format'

const ICONS: Partial<Record<ActivityAction, typeof faPlus>> = {
  [ActivityAction.CREATED]: faPlus,
  [ActivityAction.UPDATED]: faPen,
  [ActivityAction.STATUS_CHANGED]: faRightLeft,
  [ActivityAction.ASSIGNED]: faUserPlus,
  [ActivityAction.UNASSIGNED]: faUserMinus,
  [ActivityAction.COMMENTED]: faComment,
  [ActivityAction.ARCHIVED]: faBoxArchive,
  [ActivityAction.RESTORED]: faArrowRotateLeft,
  [ActivityAction.DELETED]: faTrash,
  [ActivityAction.MEMBER_ADDED]: faUserPlus,
  [ActivityAction.MEMBER_REMOVED]: faUserMinus,
  [ActivityAction.MEMBER_ROLE_CHANGED]: faRightLeft,
}

/**
 * Which enum a diff value belongs to, by the field it came from.
 *
 * The server stores raw labels — `done`, `editor` — precisely so the client can
 * localize them. Without this table a status change would read "done" in a Danish
 * feed, which is the whole thing the design avoids.
 */
const FIELD_ENUMS = {
  status: { schema: TaskStatusSchema, namespace: 'taskStatus', prefix: 'TASK_STATUS_' },
  priority: { schema: TaskPrioritySchema, namespace: 'taskPriority', prefix: 'TASK_PRIORITY_' },
  role: { schema: MemberRoleSchema, namespace: 'memberRole', prefix: 'MEMBER_ROLE_' },
  visibility: {
    schema: ListVisibilitySchema,
    namespace: 'listVisibility',
    prefix: 'LIST_VISIBILITY_',
  },
  color: { schema: ListColorSchema, namespace: 'listColor', prefix: 'LIST_COLOR_' },
} as const

export async function ActivityFeed({
  activities,
  emptyMessage,
  showList = true,
}: {
  activities: Activity[]
  emptyMessage: string
  showList?: boolean
}) {
  const [actions, fields, time, locale, enums] = await Promise.all([
    getTranslations('enums.activityAction'),
    getTranslations('enums.activityField'),
    getTranslations('time'),
    getLocale(),
    getTranslations('enums'),
  ])

  if (activities.length === 0) {
    return (
      <p className="rounded-xl border border-border bg-card px-5 py-8 text-center text-sm text-muted-foreground">
        {emptyMessage}
      </p>
    )
  }

  /** Localizes a diff value when its field maps to an enum; truncates otherwise. */
  const renderValue = (field: string, value: string): string => {
    if (!value) return '—'
    const meta = FIELD_ENUMS[field as keyof typeof FIELD_ENUMS]
    if (meta) {
      const key = `${meta.prefix}${value.toUpperCase()}`
      return enums(`${meta.namespace}.${key}`)
    }
    return value.length > 40 ? `${value.slice(0, 39)}…` : value
  }

  return (
    <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
      {activities.map((entry) => {
        const when = toDate(entry.createdAt)
        const phrase = pastPhrase(when)
        const relative = phrase
          ? time(phrase.key, phrase.values)
          : formatDateTime(when, locale as Locale)

        return (
          <li key={entry.id} className="feed-row flex items-start gap-3.5 px-5 py-4">
            <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <FontAwesomeIcon icon={ICONS[entry.action] ?? faPen} className="h-3.5 w-3.5" />
            </span>

            <div className="min-w-0 flex-1 text-[15px]">
              <p className="leading-snug text-pretty">
                <span className="font-medium">{entry.actor?.displayName ?? '—'}</span>{' '}
                <span className="text-muted-foreground">
                  {actions(valueName(ActivityActionSchema, entry.action))}
                </span>{' '}
                <span className="font-medium">{entry.targetLabel || '—'}</span>
              </p>

              {entry.change?.field && (
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {fields(entry.change.field)}: {renderValue(entry.change.field, entry.change.fromValue)}{' '}
                  → {renderValue(entry.change.field, entry.change.toValue)}
                </p>
              )}

              <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                <span title={formatDateTime(when, locale as Locale)}>{relative}</span>
                {showList && entry.list && (
                  <>
                    <span aria-hidden>·</span>
                    <Link
                      href={`/lists/${entry.list.id}`}
                      className="press inline-flex items-center gap-1.5 hover:text-foreground"
                    >
                      <ColorDot color={entry.list.color} className="size-1.5" />
                      {entry.list.name}
                    </Link>
                  </>
                )}
              </p>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
