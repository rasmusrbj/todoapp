'use client'

import { faPlus, faTrash } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useActionState, useEffect, useRef, useTransition } from 'react'

import { createSubtask, deleteSubtask, setSubtaskCompleted } from '@/app/actions/tasks'
import { FormError } from '@/components/form-message'
import { SubmitButton } from '@/components/submit-button'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import type { ActionResult } from '@/lib/errors'
import { cn } from '@/lib/utils'

type Subtask = { id: string; title: string; completed: boolean }

/**
 * A task's checklist.
 *
 * Ticking an item is a single action with no confirmation and no save button — the
 * whole value of a checklist is that it costs nothing to use.
 */
export function SubtaskList({
  taskId,
  subtasks,
  canEdit,
}: {
  taskId: string
  subtasks: Subtask[]
  canEdit: boolean
}) {
  const t = useTranslations('tasks')
  const app = useTranslations('app')
  const [pending, startTransition] = useTransition()
  const [result, action] = useActionState<ActionResult | null, FormData>(createSubtask, null)
  const formRef = useRef<HTMLFormElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const failure = result && !result.ok ? result : null

  // Clear and refocus so several items can be typed in a row.
  useEffect(() => {
    if (result?.ok) {
      formRef.current?.reset()
      inputRef.current?.focus()
    }
  }, [result])

  return (
    <div>
      {subtasks.length > 0 && (
        <ul className="divide-y divide-border">
          {subtasks.map((subtask) => (
            <li key={subtask.id} className="group flex items-center gap-3 px-6 py-2.5">
              <Checkbox
                id={`subtask-${subtask.id}`}
                checked={subtask.completed}
                disabled={!canEdit || pending}
                className="cursor-pointer"
                onCheckedChange={(checked) =>
                  startTransition(() =>
                    void setSubtaskCompleted(subtask.id, taskId, checked === true),
                  )
                }
              />
              <label
                htmlFor={`subtask-${subtask.id}`}
                className={cn(
                  'min-w-0 flex-1 cursor-pointer text-sm',
                  subtask.completed && 'text-muted-foreground line-through',
                )}
              >
                {subtask.title}
              </label>
              {canEdit && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={app('delete')}
                  disabled={pending}
                  className="press-icon text-muted-foreground opacity-0 transition-opacity duration-100 group-hover:opacity-100 hover:text-destructive focus-visible:opacity-100"
                  onClick={() => startTransition(() => void deleteSubtask(subtask.id, taskId))}
                >
                  <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {canEdit && (
        <form
          ref={formRef}
          action={action}
          className={cn('px-6 py-3', subtasks.length > 0 && 'border-t border-border')}
          noValidate
        >
          <input type="hidden" name="taskId" value={taskId} />
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              name="title"
              required
              aria-label={t('addSubtask')}
              placeholder={t('subtaskPlaceholder')}
            />
            <SubmitButton variant="outline" className="shrink-0">
              <FontAwesomeIcon icon={faPlus} className="h-4 w-4" />
              {t('addSubtask')}
            </SubmitButton>
          </div>
          {failure && <FormError failure={failure} className="mt-2" />}
        </form>
      )}

      {!canEdit && subtasks.length === 0 && (
        <p className="px-6 py-4 text-sm text-muted-foreground">{t('subtasks')} —</p>
      )}
    </div>
  )
}
