'use client'

import { faUser, faUserPlus } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useTransition } from 'react'

import { assignTask } from '@/app/actions/tasks'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

/**
 * Who is on the hook for a task.
 *
 * Only people who can write the list are offered, matching the API's rule: assigning
 * work to someone who cannot open the list is never what was meant.
 */
export function TaskAssignee({
  taskId,
  assigneeId,
  assigneeName,
  viewerId,
  members,
  canEdit,
}: {
  taskId: string
  assigneeId?: string
  assigneeName?: string
  viewerId: string
  members: Array<{ id: string; displayName: string }>
  canEdit: boolean
}) {
  const t = useTranslations('tasks')
  const [pending, startTransition] = useTransition()

  if (!canEdit) {
    return (
      <p className="inline-flex items-center gap-2 text-sm">
        <FontAwesomeIcon icon={faUser} className="h-3.5 w-3.5 text-muted-foreground" />
        {assigneeName ?? t('unassigned')}
      </p>
    )
  }

  const canTakeIt = !assigneeId && members.some((member) => member.id === viewerId)

  return (
    <div className="space-y-2">
      <Select
        value={assigneeId ?? 'none'}
        disabled={pending}
        onValueChange={(value) =>
          startTransition(() => void assignTask(taskId, value === 'none' ? undefined : value))
        }
      >
        <SelectTrigger className="w-full cursor-pointer" size="sm" aria-label={t('assignee')}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="none" className="cursor-pointer">
            {t('unassigned')}
          </SelectItem>
          {members.map((member) => (
            <SelectItem key={member.id} value={member.id} className="cursor-pointer">
              {member.displayName}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* The one-click case: taking an unassigned task yourself. */}
      {canTakeIt && (
        <Button
          variant="outline"
          size="sm"
          disabled={pending}
          className="press w-full"
          onClick={() => startTransition(() => void assignTask(taskId, viewerId))}
        >
          <FontAwesomeIcon icon={faUserPlus} className="h-3.5 w-3.5" />
          {t('assignToMe')}
        </Button>
      )}
    </div>
  )
}
