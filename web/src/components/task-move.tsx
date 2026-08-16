'use client'

import { faRightLeft } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useTransition } from 'react'
import { toast } from 'sonner'

import { moveTask } from '@/app/actions/tasks'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { type ListColor, listColorClasses } from '@/lib/enums'
import { cn } from '@/lib/utils'

/**
 * Moves a task to another list.
 *
 * Its own control rather than a field in the edit dialog, because moving is not an edit:
 * it drops the task's labels — they belong to the list it is leaving — and the server
 * requires write access to *both* lists. A select that quietly discarded labels inside a
 * general-purpose form would be a trap.
 *
 * Only lists the caller can write are offered; the current one is excluded, since
 * "move here" where you already are is not an action.
 */
export function TaskMove({
  taskId,
  currentListId,
  lists,
}: {
  taskId: string
  currentListId: string
  lists: Array<{ id: string; name: string; color: ListColor }>
}) {
  const t = useTranslations('tasks')
  const [pending, startTransition] = useTransition()

  const targets = lists.filter((list) => list.id !== currentListId)
  if (targets.length === 0) return null

  return (
    <div className="space-y-1.5">
      <Label htmlFor="task-move" className="gap-1.5 text-xs font-medium text-muted-foreground">
        <FontAwesomeIcon icon={faRightLeft} className="h-3 w-3" />
        {t('moveToList')}
      </Label>
      <Select
        // Never shows a selection: it is an action, not a stored value.
        value=""
        disabled={pending}
        onValueChange={(listId) =>
          startTransition(async () => {
            // Index 0 puts the task at the top of the list it lands in, which is where
            // someone moving it will look for it.
            const result = await moveTask(taskId, 0, listId)
            if (result.ok) toast.success(t('moveDone'))
          })
        }
      >
        <SelectTrigger id="task-move" size="sm" className="w-full cursor-pointer">
          <SelectValue placeholder={t('moveToList')} />
        </SelectTrigger>
        <SelectContent>
          {targets.map((list) => (
            <SelectItem key={list.id} value={list.id} className="cursor-pointer">
              <span className="flex items-center gap-2">
                <span
                  aria-hidden
                  className={cn('size-2 rounded-full', listColorClasses[list.color].dot)}
                />
                {list.name}
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
