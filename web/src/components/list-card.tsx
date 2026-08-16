import { faBoxArchive, faUsers } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import Link from 'next/link'
import { getLocale, getTranslations } from 'next-intl/server'

import { ColorDot, VisibilityBadge } from '@/components/enum-badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import type { TodoList } from '@/gen/todo/v1/list_pb'
import type { Locale } from '@/i18n/config'
import { formatShortDate, relativePhrase, toDate } from '@/lib/format'
import { cn } from '@/lib/utils'

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  return ((words[0]?.[0] ?? '') + (words.length > 1 ? (words.at(-1)?.[0] ?? '') : '')).toUpperCase()
}

/**
 * One list on the board.
 *
 * A card rather than a row: the progress bar and the counters are the point, and they
 * need two dimensions. The layout reads top to bottom as name → what it is → how far
 * along → who is on it, so a wall of these is scannable without reading any of them
 * closely.
 *
 * Depth comes from the border darkening on hover. The system forbids shadow elevation,
 * and at this density a lift would make the grid feel restless anyway.
 */
export async function ListCard({ list }: { list: TodoList }) {
  const [t, time, locale] = await Promise.all([
    getTranslations('lists'),
    getTranslations('time'),
    getLocale(),
  ])

  const nextDue = toDate(list.stats?.nextDueAt)
  const phrase = relativePhrase(nextDue)
  const nextDueLabel = nextDue
    ? (phrase ? time(phrase.key, phrase.values) : formatShortDate(nextDue, locale as Locale))
    : undefined

  const percent = list.stats?.completionPercent ?? 0
  const overdue = list.stats?.overdueTaskCount ?? 0
  // The owner is always a member, so anyone beyond them makes this a shared list.
  const others = list.members.filter((member) => member.user?.id !== list.owner?.id)

  return (
    <Link
      href={`/lists/${list.id}`}
      className={cn(
        'card-interactive flex flex-col rounded-xl border bg-card p-6 text-card-foreground',
        list.archived && 'opacity-70',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <ColorDot color={list.color} className="size-3" />
          <h3 className="min-w-0 truncate text-base font-semibold leading-none tracking-tight">
            {list.name}
          </h3>
        </div>
        {list.archived ? (
          <Badge variant="outline" className="shrink-0 gap-1 rounded-full bg-transparent">
            <FontAwesomeIcon icon={faBoxArchive} className="h-3 w-3" />
            {t('archived')}
          </Badge>
        ) : (
          <VisibilityBadge visibility={list.visibility} className="shrink-0" />
        )}
      </div>

      {/* Reserved either way, so cards in a row keep their progress bars aligned. */}
      <p className="mt-2 line-clamp-2 min-h-10 text-sm text-muted-foreground text-pretty">
        {list.description}
      </p>

      <div className="mt-5 space-y-2.5">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-2xl font-semibold leading-none tabular-nums">{percent}%</span>
          <span className="text-sm text-muted-foreground tabular-nums">
            {t('openTasksOf', {
              open: list.stats?.openTaskCount ?? 0,
              total: list.stats?.totalTaskCount ?? 0,
            })}
          </span>
        </div>

        <Progress value={percent} className="h-1.5" />
      </div>

      <div className="mt-4 flex min-h-8 items-center justify-between gap-3 border-t border-border pt-4">
        {/* Faces, not a count: who is on a list is the thing you want to see. */}
        {others.length > 0 ? (
          <div className="flex items-center gap-2">
            <div className="flex -space-x-2">
              {others.slice(0, 3).map((member) => (
                <Avatar
                  key={member.id}
                  className="size-6 ring-2 ring-card"
                  title={member.user?.displayName}
                >
                  {member.user?.avatarUrl && <AvatarImage src={member.user.avatarUrl} alt="" />}
                  <AvatarFallback className="text-[9px]">
                    {initials(member.user?.displayName ?? '')}
                  </AvatarFallback>
                </Avatar>
              ))}
            </div>
            {others.length > 3 && (
              <span className="text-xs text-muted-foreground tabular-nums">
                +{others.length - 3}
              </span>
            )}
          </div>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <FontAwesomeIcon icon={faUsers} className="h-3 w-3" />
            {t('memberCount', { count: list.stats?.memberCount ?? 1 })}
          </span>
        )}

        <span className="text-right text-xs">
          {overdue > 0 ? (
            <span className="font-medium text-red-600 tabular-nums dark:text-red-400">
              {t('overdueCount', { count: overdue })}
            </span>
          ) : nextDueLabel ? (
            <span className="text-muted-foreground">{t('nextDue', { date: nextDueLabel })}</span>
          ) : null}
        </span>
      </div>
    </Link>
  )
}
