import { faComment, faListCheck, faRepeat } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import Link from 'next/link'
import { getTranslations } from 'next-intl/server'

import { DueDate } from '@/components/due-date'
import { ColorDot, LabelChip, PriorityBadge } from '@/components/enum-badge'
import { StatusToggle } from '@/components/status-toggle'
import { TaskCheckbox } from '@/components/task-selection'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import type { Task } from '@/gen/todo/v1/task_pb'
import { isOpen, RecurrenceFrequency, TaskStatus } from '@/lib/enums'
import { cn } from '@/lib/utils'

/** Initials for a compact avatar. */
function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  return ((words[0]?.[0] ?? '') + (words.length > 1 ? (words.at(-1)?.[0] ?? '') : '')).toUpperCase()
}

/**
 * One task in a list.
 *
 * Two lines: the title, then everything that gives it context. The status control is
 * the only interactive part besides the link, so ticking a task off never means
 * opening it first — and the meta line means you rarely need to.
 *
 * Roomy on purpose. A denser row fits more on screen but stops being scannable, and
 * this is a list people read rather than audit.
 */
export async function TaskRow({
  task,
  showList = true,
  canEdit = true,
  selectable = false,
}: {
  task: Task
  /** Hide the list name when the surrounding page is already one list. */
  showList?: boolean
  canEdit?: boolean
  /** Render the multi-select checkbox. Needs a `TaskSelectionProvider` above. */
  selectable?: boolean
}) {
  const [t, statuses] = await Promise.all([
    getTranslations('tasks'),
    getTranslations('enums.taskStatus'),
  ])
  const finished = !isOpen(task.status)
  const repeats =
    task.recurrence !== undefined &&
    task.recurrence.frequency !== RecurrenceFrequency.NONE &&
    task.recurrence.frequency !== RecurrenceFrequency.UNSPECIFIED

  // `todo` and `done` are already obvious from the control, so only the in-between
  // states earn a word of their own on the row.
  const statusWord =
    task.status === TaskStatus.IN_PROGRESS
      ? statuses('TASK_STATUS_IN_PROGRESS')
      : task.status === TaskStatus.BLOCKED
        ? statuses('TASK_STATUS_BLOCKED')
        : task.status === TaskStatus.CANCELLED
          ? statuses('TASK_STATUS_CANCELLED')
          : undefined

  return (
    <li className="feed-row group flex items-start gap-3.5 border-b border-border px-5 py-4 last:border-b-0">
      {selectable && (
        <div className="pt-1">
          <TaskCheckbox taskId={task.id} label={task.title} />
        </div>
      )}

      <div className="pt-0.5">
        <StatusToggle taskId={task.id} status={task.status} disabled={!canEdit} />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
          <Link
            href={`/tasks/${task.id}`}
            className={cn(
              'press min-w-0 text-[15px] font-medium leading-snug underline-offset-4 hover:underline',
              finished && 'text-muted-foreground line-through',
            )}
          >
            {task.title}
          </Link>
          <PriorityBadge priority={task.priority} />
          {statusWord && <span className="text-xs text-muted-foreground">{statusWord}</span>}
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-x-3.5 gap-y-1.5">
          {showList && task.list && (
            <Link
              href={`/lists/${task.list.id}`}
              className="press inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors duration-100 hover:text-foreground"
            >
              <ColorDot color={task.list.color} className="size-2" />
              {task.list.name}
            </Link>
          )}

          <DueDate dueAt={task.dueAt} hasTime={task.dueHasTime} overdue={task.overdue} />

          {task.subtaskCount > 0 && (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground tabular-nums">
              <FontAwesomeIcon icon={faListCheck} className="h-3 w-3" />
              {t('subtaskProgress', {
                done: task.completedSubtaskCount,
                total: task.subtaskCount,
              })}
            </span>
          )}

          {task.commentCount > 0 && (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground tabular-nums">
              <FontAwesomeIcon icon={faComment} className="h-3 w-3" />
              {task.commentCount}
            </span>
          )}

          {repeats && (
            <span
              className="inline-flex items-center text-xs text-muted-foreground"
              title={t('repeat')}
            >
              <FontAwesomeIcon icon={faRepeat} className="h-3 w-3" />
            </span>
          )}

          {task.labels.map((label) => (
            <LabelChip key={label.id} name={label.name} color={label.color} />
          ))}
        </div>
      </div>

      {task.assignee && (
        <Avatar className="mt-0.5 size-8 shrink-0" title={task.assignee.displayName}>
          {task.assignee.avatarUrl && <AvatarImage src={task.assignee.avatarUrl} alt="" />}
          <AvatarFallback className="text-[11px]">
            {initials(task.assignee.displayName)}
          </AvatarFallback>
        </Avatar>
      )}
    </li>
  )
}
