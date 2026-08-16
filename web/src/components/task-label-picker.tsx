'use client'

import { useTranslations } from 'next-intl'
import { useTransition } from 'react'

import { setTaskLabels } from '@/app/actions/tasks'
import { Label } from '@/components/ui/label'
import { type ListColor, listColorClasses } from '@/lib/enums'
import { cn } from '@/lib/utils'

/**
 * Toggle a task's labels.
 *
 * The whole set is visible and one tap adds or removes — a multi-select would hide the
 * options behind a click for no gain at this size. Each change sends the complete
 * desired set, which is what the API's `SetTaskLabels` takes.
 */
export function TaskLabelPicker({
  taskId,
  selected,
  labels,
}: {
  taskId: string
  selected: string[]
  labels: Array<{ id: string; name: string; color: ListColor }>
}) {
  const t = useTranslations('tasks')
  const [pending, startTransition] = useTransition()

  return (
    <div className="space-y-2 border-t border-border pt-4">
      <Label>{t('labels')}</Label>
      <div className="flex flex-wrap gap-2">
        {labels.map((label) => {
          const active = selected.includes(label.id)
          const tokens = listColorClasses[label.color]
          return (
            <button
              key={label.id}
              type="button"
              disabled={pending}
              aria-pressed={active}
              onClick={() =>
                startTransition(() =>
                  void setTaskLabels(
                    taskId,
                    active ? selected.filter((id) => id !== label.id) : [...selected, label.id],
                  ),
                )
              }
              className={cn(
                'press-icon inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors duration-100 disabled:opacity-50',
                active
                  ? cn(tokens.tint, 'border-ring')
                  : 'border-border text-muted-foreground hover:bg-accent/50',
              )}
            >
              <span aria-hidden className={cn('size-1.5 rounded-full', tokens.dot)} />
              {label.name}
            </button>
          )
        })}
      </div>
    </div>
  )
}
