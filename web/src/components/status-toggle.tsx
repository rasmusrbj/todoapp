'use client'

import {
  faBan,
  faChevronDown,
  faCircle,
  faCircleCheck,
  faCircleHalfStroke,
  faTriangleExclamation,
} from '@fortawesome/pro-solid-svg-icons'
import { faCircle as faCircleLight } from '@fortawesome/pro-light-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useTransition } from 'react'
import { toast } from 'sonner'

import { setTaskStatus } from '@/app/actions/tasks'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { TaskStatusSchema } from '@/gen/todo/v1/enums_pb'
import { options, TaskStatus, taskStatusClasses, valueName } from '@/lib/enums'
import { cn } from '@/lib/utils'

const ICONS: Record<TaskStatus, typeof faCircle> = {
  [TaskStatus.UNSPECIFIED]: faCircleLight,
  [TaskStatus.TODO]: faCircleLight,
  [TaskStatus.IN_PROGRESS]: faCircleHalfStroke,
  [TaskStatus.BLOCKED]: faTriangleExclamation,
  [TaskStatus.DONE]: faCircleCheck,
  [TaskStatus.CANCELLED]: faBan,
}

const STATUS_OPTIONS = options(TaskStatusSchema, 'x')

/**
 * The status control on a task row.
 *
 * A click ticks the task off — the action nine times in ten — and the dropdown covers
 * the rest. Completing a repeating task tells the reader the follow-up exists, which
 * is otherwise invisible until they scroll for it.
 */
export function StatusToggle({
  taskId,
  status,
  disabled = false,
}: {
  taskId: string
  status: TaskStatus
  disabled?: boolean
}) {
  const t = useTranslations('tasks')
  const labels = useTranslations('enums.taskStatus')
  const [pending, startTransition] = useTransition()

  const apply = (next: TaskStatus) => {
    startTransition(async () => {
      const result = await setTaskStatus(taskId, next)
      if (!result.ok) {
        toast.error(t('updateDone'))
        return
      }
      toast.success(t('statusChanged', { status: labels(valueName(TaskStatusSchema, next)) }))
      if (result.data) {
        toast.info(t('nextOccurrence', { date: '' }).trim())
      }
    })
  }

  const finished = status === TaskStatus.DONE || status === TaskStatus.CANCELLED
  const nextOnClick = finished ? TaskStatus.TODO : TaskStatus.DONE

  return (
    <span className="flex items-center">
      <button
        type="button"
        disabled={disabled || pending}
        aria-label={labels(valueName(TaskStatusSchema, nextOnClick))}
        onClick={() => apply(nextOnClick)}
        className={cn(
          'press-icon flex size-5 items-center justify-center rounded-full disabled:cursor-not-allowed disabled:opacity-50',
          taskStatusClasses[status],
          'border-0',
        )}
      >
        <FontAwesomeIcon icon={ICONS[status]} className="h-4 w-4" />
      </button>

      {!disabled && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              disabled={pending}
              aria-label={t('status')}
              className="press-icon ml-0.5 flex size-4 items-center justify-center text-muted-foreground opacity-0 transition-opacity duration-100 group-hover:opacity-100 focus-visible:opacity-100"
            >
              <FontAwesomeIcon icon={faChevronDown} className="h-2.5 w-2.5" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="min-w-44">
            {STATUS_OPTIONS.map((option) => (
              <DropdownMenuItem
                key={option.value}
                className="cursor-pointer gap-2"
                onClick={() => apply(option.value as TaskStatus)}
              >
                <FontAwesomeIcon
                  icon={ICONS[option.value as TaskStatus]}
                  className={cn('h-3.5 w-3.5', taskStatusClasses[option.value as TaskStatus])}
                />
                {labels(option.name)}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </span>
  )
}
