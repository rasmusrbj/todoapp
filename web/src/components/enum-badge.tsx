import {
  faBan,
  faCircle,
  faCircleCheck,
  faCircleHalfStroke,
  faTriangleExclamation,
} from '@fortawesome/pro-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { getTranslations } from 'next-intl/server'

import { Badge } from '@/components/ui/badge'
import {
  ListColor,
  listColorClasses,
  TaskPriority,
  taskPriorityClasses,
  TaskStatus,
  taskStatusClasses,
  valueName,
} from '@/lib/enums'
import { MemberRoleSchema, TaskPrioritySchema, TaskStatusSchema } from '@/gen/todo/v1/enums_pb'
import { ListVisibilitySchema } from '@/gen/todo/v1/enums_pb'
import type { MemberRole, ListVisibility } from '@/lib/enums'
import { cn } from '@/lib/utils'

// An icon per status, so colour is never the only thing distinguishing them.
const STATUS_ICONS: Record<TaskStatus, typeof faCircle> = {
  [TaskStatus.UNSPECIFIED]: faCircle,
  [TaskStatus.TODO]: faCircle,
  [TaskStatus.IN_PROGRESS]: faCircleHalfStroke,
  [TaskStatus.BLOCKED]: faTriangleExclamation,
  [TaskStatus.DONE]: faCircleCheck,
  [TaskStatus.CANCELLED]: faBan,
}

/** Localized status badge. */
export async function StatusBadge({
  status,
  className,
}: {
  status: TaskStatus
  className?: string
}) {
  const t = await getTranslations('enums.taskStatus')
  return (
    <Badge
      variant="outline"
      className={cn('gap-1.5 rounded-full bg-transparent', taskStatusClasses[status], className)}
    >
      <FontAwesomeIcon icon={STATUS_ICONS[status]} className="h-3 w-3" />
      {t(valueName(TaskStatusSchema, status))}
    </Badge>
  )
}

/**
 * Localized priority badge.
 *
 * `none` renders nothing: a badge saying "no priority" is noise on every row.
 */
export async function PriorityBadge({
  priority,
  className,
}: {
  priority: TaskPriority
  className?: string
}) {
  if (priority === TaskPriority.NONE || priority === TaskPriority.UNSPECIFIED) return null
  const t = await getTranslations('enums.taskPriority')
  return (
    <Badge
      variant="outline"
      className={cn('rounded-full bg-transparent', taskPriorityClasses[priority], className)}
    >
      {t(valueName(TaskPrioritySchema, priority))}
    </Badge>
  )
}

/** Localized membership-role badge. */
export async function RoleBadge({ role, className }: { role: MemberRole; className?: string }) {
  const t = await getTranslations('enums.memberRole')
  return (
    <Badge variant="outline" className={cn('rounded-full bg-transparent', className)}>
      {t(valueName(MemberRoleSchema, role))}
    </Badge>
  )
}

/** Localized visibility badge. */
export async function VisibilityBadge({
  visibility,
  className,
}: {
  visibility: ListVisibility
  className?: string
}) {
  const t = await getTranslations('enums.listVisibility')
  return (
    <Badge variant="outline" className={cn('rounded-full bg-transparent', className)}>
      {t(valueName(ListVisibilitySchema, visibility))}
    </Badge>
  )
}

/** The coloured dot that identifies a list at a glance. */
export function ColorDot({ color, className }: { color: ListColor; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn('inline-block size-2.5 shrink-0 rounded-full', listColorClasses[color].dot, className)}
    />
  )
}

/** A label chip. Tinted by its own colour, and always carrying its name. */
export function LabelChip({
  name,
  color,
  className,
}: {
  name: string
  color: ListColor
  className?: string
}) {
  const tokens = listColorClasses[color]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        tokens.tint,
        tokens.ring,
        className,
      )}
    >
      <span aria-hidden className={cn('size-1.5 rounded-full', tokens.dot)} />
      {name}
    </span>
  )
}
