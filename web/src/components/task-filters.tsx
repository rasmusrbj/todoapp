'use client'

import { faFilter, faMagnifyingGlass, faXmark } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useRouter, useSearchParams } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { useEffect, useState, useTransition } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { TaskSortFieldSchema } from '@/gen/todo/v1/enums_pb'
import { options } from '@/lib/enums'
import { cn } from '@/lib/utils'

const SORT_OPTIONS = options(TaskSortFieldSchema, 'x')

/** The quick filters, as URL state so a filtered view is a shareable link. */
const TOGGLES = [
  { param: 'filter', value: 'open', key: 'filterOpen' },
  { param: 'filter', value: 'overdue', key: 'filterOverdue' },
  { param: 'mine', value: '1', key: 'filterMine' },
  { param: 'unassigned', value: '1', key: 'filterUnassigned' },
] as const

/**
 * Search, quick filters, and sorting for a task list.
 *
 * All of it lives in the query string rather than in component state: the server does
 * the filtering, the back button works, and a filtered view can be pasted to someone.
 */
export function TaskFilters({ className }: { className?: string }) {
  const t = useTranslations('tasks')
  const sorts = useTranslations('enums.taskSortField')
  const router = useRouter()
  const params = useSearchParams()
  const [pending, startTransition] = useTransition()
  const [query, setQuery] = useState(params.get('q') ?? '')

  // Keep the box in step when the URL changes from elsewhere (a link, the palette).
  useEffect(() => setQuery(params.get('q') ?? ''), [params])

  const update = (mutate: (next: URLSearchParams) => void) => {
    const next = new URLSearchParams(params.toString())
    mutate(next)
    startTransition(() => router.push(next.toString() ? `?${next}` : '?'))
  }

  const isActive = (param: string, value: string) => params.get(param) === value
  const hasFilters = ['filter', 'mine', 'unassigned', 'q'].some((key) => params.has(key))

  return (
    <div className={cn('space-y-3', className)}>
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          update((next) => {
            if (query.trim()) next.set('q', query.trim())
            else next.delete('q')
          })
        }}
      >
        <div className="relative flex-1">
          <FontAwesomeIcon
            icon={faMagnifyingGlass}
            className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('title')}
            aria-label={t('title')}
            className="h-10 rounded-full pl-9"
          />
        </div>

        <Select
          value={params.get('sort') ?? String(SORT_OPTIONS[0]?.value ?? 1)}
          onValueChange={(value) => update((next) => next.set('sort', value))}
        >
          <SelectTrigger
            className="h-10 w-auto cursor-pointer gap-2 rounded-full"
            aria-label={t('sortBy')}
          >
            <FontAwesomeIcon icon={faFilter} className="h-3.5 w-3.5" />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((option) => (
              <SelectItem
                key={option.value}
                value={String(option.value)}
                className="cursor-pointer"
              >
                {sorts(option.name)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </form>

      <div className="flex flex-wrap items-center gap-2">
        {TOGGLES.map((toggle) => {
          const active = isActive(toggle.param, toggle.value)
          return (
            <button
              key={`${toggle.param}-${toggle.value}`}
              type="button"
              disabled={pending}
              aria-pressed={active}
              onClick={() =>
                update((next) => {
                  if (active) next.delete(toggle.param)
                  else next.set(toggle.param, toggle.value)
                })
              }
              className={cn(
                'press-icon h-8 rounded-full border px-3.5 text-sm font-medium transition-colors duration-100',
                active
                  ? 'border-foreground/20 bg-foreground text-background'
                  : 'border-border text-muted-foreground hover:bg-accent/50 hover:text-foreground',
              )}
            >
              {t(toggle.key)}
            </button>
          )
        })}

        {hasFilters && (
          <Button
            variant="ghost"
            size="sm"
            disabled={pending}
            className="press h-7 gap-1.5 px-2 text-xs"
            onClick={() => startTransition(() => router.push('?'))}
          >
            <FontAwesomeIcon icon={faXmark} className="h-3 w-3" />
            {t('clearFilters')}
          </Button>
        )}
      </div>
    </div>
  )
}

/** Per-status counts, rendered as chips beside the list. */
export function StatusCounts({
  counts,
  labels,
}: {
  counts: Record<string, number>
  labels: Record<string, string>
}) {
  const entries = Object.entries(counts).filter(([, count]) => count > 0)
  if (entries.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2">
      {entries.map(([status, count]) => (
        <Badge
          key={status}
          variant="outline"
          className="rounded-full bg-transparent px-2.5 py-0.5 tabular-nums"
        >
          {labels[status] ?? status}: {count}
        </Badge>
      ))}
    </div>
  )
}
