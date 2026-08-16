'use client'

import {
  faChartSimple,
  faClockRotateLeft,
  faGear,
  faListUl,
  faMagnifyingGlass,
  faSquareCheck,
  faUser,
  faUsers,
} from '@fortawesome/pro-regular-svg-icons'
import { faCircleHalfStroke, faSpinnerThird } from '@fortawesome/pro-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { useCallback, useEffect, useRef, useState, useTransition } from 'react'

import { search, type SearchHit } from '@/app/actions/search'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/components/ui/command'
import { Kbd } from '@/components/ui/kbd'
import { listColorClasses, taskStatusClasses } from '@/lib/enums'
import { cn } from '@/lib/utils'

/** Static destinations, always offered so the palette is also a jump list. */
const PAGES = [
  { href: '/dashboard', key: 'dashboard', icon: faChartSimple },
  { href: '/lists', key: 'lists', icon: faListUl },
  { href: '/tasks', key: 'tasks', icon: faSquareCheck },
  { href: '/activity', key: 'activity', icon: faClockRotateLeft },
  { href: '/settings', key: 'settings', icon: faGear },
] as const

/** Wait this long after the last keystroke before asking the server. */
const DEBOUNCE_MS = 200

/**
 * The ⌘K palette: search and navigate without leaving the keyboard.
 *
 * Searching runs on the server through the same authorized RPCs the pages use, so the
 * palette cannot surface a task the reader could not open. Results are debounced and
 * the in-flight request is tracked by sequence number, because a fast typist will have
 * several outstanding at once and the last one typed must win — not the last to return.
 */
export function CommandPalette({ isAdmin }: { isAdmin: boolean }) {
  const t = useTranslations('nav')
  const app = useTranslations('app')
  const tasks = useTranslations('tasks')
  const lists = useTranslations('lists')

  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<SearchHit[]>([])
  const [pending, startTransition] = useTransition()

  // Monotonic request id: a slower earlier response must not overwrite a newer one.
  const latest = useRef(0)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'k' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        setOpen((current) => !current)
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])

  useEffect(() => {
    if (query.trim().length < 2) {
      setHits([])
      return
    }
    const sequence = ++latest.current
    const timer = setTimeout(() => {
      startTransition(async () => {
        const results = await search(query)
        if (sequence === latest.current) setHits(results)
      })
    }, DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [query])

  const go = useCallback(
    (href: string) => {
      setOpen(false)
      setQuery('')
      router.push(href)
    },
    [router],
  )

  const taskHits = hits.filter((hit) => hit.kind === 'task')
  const listHits = hits.filter((hit) => hit.kind === 'list')
  const peopleHits = hits.filter((hit) => hit.kind === 'person')
  const pages = isAdmin
    ? [...PAGES, { href: '/admin/users', key: 'users', icon: faUsers } as const]
    : PAGES

  return (
    <>
      {/* The trigger doubles as the affordance that the shortcut exists. */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="press flex h-9 w-full items-center gap-2 rounded-md border border-border bg-background px-3 text-sm text-muted-foreground transition-colors duration-100 hover:border-zinc-300 sm:w-56 dark:hover:border-zinc-700"
      >
        <FontAwesomeIcon icon={faMagnifyingGlass} className="h-3.5 w-3.5" />
        <span className="flex-1 text-left">{app('search')}</span>
        <Kbd className="hidden sm:inline-flex">⌘K</Kbd>
      </button>

      <CommandDialog
        open={open}
        onOpenChange={setOpen}
        title={app('search')}
        description={tasks('title')}
        // The server already matched the query; filtering again client-side would
        // hide results whose match was in a field the palette does not display.
        shouldFilter={false}
      >
        <CommandInput
          value={query}
          onValueChange={setQuery}
          placeholder={app('search')}
        />
        <CommandList>
          {pending && query.trim().length >= 2 && (
            <div className="flex items-center gap-2 px-3 py-6 text-sm text-muted-foreground">
              <FontAwesomeIcon icon={faSpinnerThird} className="h-3.5 w-3.5 animate-spin" />
              {app('loading')}
            </div>
          )}

          {!pending && query.trim().length >= 2 && hits.length === 0 && (
            <CommandEmpty>{tasks('emptyFiltered')}</CommandEmpty>
          )}

          {taskHits.length > 0 && (
            <CommandGroup heading={tasks('title')}>
              {taskHits.map((hit) => (
                <CommandItem
                  key={hit.id}
                  value={`task-${hit.id}`}
                  onSelect={() => go(`/tasks/${hit.id}`)}
                  className="cursor-pointer gap-2"
                >
                  <FontAwesomeIcon
                    icon={faCircleHalfStroke}
                    className={cn('h-3.5 w-3.5', taskStatusClasses[hit.status])}
                  />
                  <span className="min-w-0 flex-1 truncate">{hit.title}</span>
                  <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span
                      aria-hidden
                      className={cn('size-1.5 rounded-full', listColorClasses[hit.color].dot)}
                    />
                    {hit.listName}
                  </span>
                  {hit.overdue && (
                    <span className="text-xs font-medium text-red-600 dark:text-red-400">
                      {tasks('overdue')}
                    </span>
                  )}
                </CommandItem>
              ))}
            </CommandGroup>
          )}

          {listHits.length > 0 && (
            <CommandGroup heading={lists('title')}>
              {listHits.map((hit) => (
                <CommandItem
                  key={hit.id}
                  value={`list-${hit.id}`}
                  onSelect={() => go(`/lists/${hit.id}`)}
                  className="cursor-pointer gap-2"
                >
                  <span
                    aria-hidden
                    className={cn('size-2 rounded-full', listColorClasses[hit.color].dot)}
                  />
                  <span className="min-w-0 flex-1 truncate">{hit.title}</span>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {hit.openCount}
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          )}

          {peopleHits.length > 0 && (
            <CommandGroup heading={t('users')}>
              {peopleHits.map((hit) => (
                <CommandItem
                  key={hit.id}
                  value={`person-${hit.id}`}
                  onSelect={() => go(`/tasks?assignee=${hit.id}`)}
                  className="cursor-pointer gap-2"
                >
                  <FontAwesomeIcon icon={faUser} className="h-3.5 w-3.5" />
                  <span className="min-w-0 flex-1 truncate">{hit.title}</span>
                  <span className="truncate text-xs text-muted-foreground">{hit.email}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          )}

          {hits.length > 0 && <CommandSeparator />}

          <CommandGroup heading={t('pages')}>
            {pages.map((page) => (
              <CommandItem
                key={page.href}
                value={`page-${page.key}`}
                onSelect={() => go(page.href)}
                className="cursor-pointer gap-2"
              >
                <FontAwesomeIcon icon={page.icon} className="h-3.5 w-3.5" />
                {t(page.key)}
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  )
}
