'use client'

import { faXmark } from '@fortawesome/pro-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { createContext, useCallback, useContext, useMemo, useState, useTransition } from 'react'
import { toast } from 'sonner'

import { bulkSetPriority, bulkSetStatus } from '@/app/actions/tasks'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { TaskPrioritySchema, TaskStatusSchema } from '@/gen/todo/v1/enums_pb'
import { options, type TaskPriority, type TaskStatus } from '@/lib/enums'

const STATUS_OPTIONS = options(TaskStatusSchema, 'x')
const PRIORITY_OPTIONS = options(TaskPrioritySchema, 'x')

type SelectionValue = {
  selected: ReadonlySet<string>
  toggle: (id: string) => void
  /** Whether any row is selected, which is what puts rows into selectable mode. */
  active: boolean
}

const SelectionContext = createContext<SelectionValue | null>(null)

/**
 * Multi-select over a task list, with a bar of actions once anything is picked.
 *
 * The state lives in a context rather than in the page, because the rows are Server
 * Components: they cannot hold it, but they can render a small client checkbox that
 * reads it. That keeps the list itself server-rendered while still allowing selection.
 *
 * The server decides what the caller may actually edit and reports how many rows it
 * changed, so the bar tells the reader when some of their selection was skipped rather
 * than pretending everything applied.
 */
export function TaskSelectionProvider({ children }: { children: React.ReactNode }) {
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set())

  const toggle = useCallback((id: string) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const clear = useCallback(() => setSelected(new Set()), [])

  const value = useMemo<SelectionValue>(
    () => ({ selected, toggle, active: selected.size > 0 }),
    [selected, toggle],
  )

  return (
    <SelectionContext.Provider value={value}>
      {children}
      <BulkBar ids={[...selected]} onDone={clear} />
    </SelectionContext.Provider>
  )
}

/** Returns the selection, or `null` when the list is not selectable. */
export function useTaskSelection(): SelectionValue | null {
  return useContext(SelectionContext)
}

/**
 * The checkbox on a task row.
 *
 * Invisible until hovered or checked, so a list that nobody is selecting from does not
 * carry a column of empty boxes.
 */
export function TaskCheckbox({ taskId, label }: { taskId: string; label: string }) {
  const selection = useTaskSelection()
  if (!selection) return null

  const checked = selection.selected.has(taskId)

  return (
    <Checkbox
      checked={checked}
      aria-label={label}
      onCheckedChange={() => selection.toggle(taskId)}
      className={
        checked || selection.active
          ? 'cursor-pointer'
          : 'cursor-pointer opacity-0 transition-opacity duration-100 group-hover:opacity-100 focus-visible:opacity-100'
      }
    />
  )
}

/** The floating action bar, shown only while something is selected. */
function BulkBar({ ids, onDone }: { ids: string[]; onDone: () => void }) {
  const t = useTranslations('tasks')
  const statuses = useTranslations('enums.taskStatus')
  const priorities = useTranslations('enums.taskPriority')
  const [pending, startTransition] = useTransition()

  if (ids.length === 0) return null

  /** Runs a bulk action and reports what actually changed. */
  const apply = (work: () => Promise<{ ok: boolean; data?: number }>) =>
    startTransition(async () => {
      const result = await work()
      if (!result.ok) return
      const updated = result.data ?? 0
      toast.success(t('bulkDone', { count: updated }))
      if (updated < ids.length) {
        toast.warning(t('bulkSkipped', { count: ids.length - updated }))
      }
      onDone()
    })

  return (
    // Sits above the mobile tab bar, and centred on wider screens.
    <div className="fixed inset-x-0 bottom-20 z-40 flex justify-center px-4 lg:bottom-6">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-2 shadow-md">
        <span className="px-2 text-sm font-medium tabular-nums">
          {t('selected', { count: ids.length })}
        </span>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" disabled={pending} className="press">
              {t('bulkStatus')}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="center" className="min-w-44">
            <DropdownMenuLabel>{t('status')}</DropdownMenuLabel>
            {STATUS_OPTIONS.map((option) => (
              <DropdownMenuItem
                key={option.value}
                className="cursor-pointer"
                onClick={() => apply(() => bulkSetStatus(ids, option.value as TaskStatus))}
              >
                {statuses(option.name)}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" disabled={pending} className="press">
              {t('bulkPriority')}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="center" className="min-w-44">
            <DropdownMenuLabel>{t('priority')}</DropdownMenuLabel>
            {PRIORITY_OPTIONS.map((option) => (
              <DropdownMenuItem
                key={option.value}
                className="cursor-pointer"
                onClick={() => apply(() => bulkSetPriority(ids, option.value as TaskPriority))}
              >
                {priorities(option.name)}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={t('clearSelection')}
          disabled={pending}
          className="press-icon"
          onClick={onDone}
        >
          <FontAwesomeIcon icon={faXmark} className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}
