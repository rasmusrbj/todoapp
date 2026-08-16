'use client'

import { faArrowUp } from '@fortawesome/pro-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useActionState, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { createTask } from '@/app/actions/tasks'
import { FormError } from '@/components/form-message'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ListColor } from '@/lib/enums'
import { listColorClasses } from '@/lib/enums'
import type { ActionResult } from '@/lib/errors'
import { cn } from '@/lib/utils'

type ListOption = { id: string; name: string; color: ListColor }

/** Initials for the composer's avatar. */
function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  return ((words[0]?.[0] ?? '') + (words.length > 1 ? (words.at(-1)?.[0] ?? '') : '')).toUpperCase()
}

/**
 * One line to add a task: a title, a list, and enter.
 *
 * Shaped like a social composer on purpose — your own avatar, a single pill-shaped
 * field, and a send button that only lights up once there is something to send. The
 * list picker and the button stay hidden until the field has focus or content, so at
 * rest this is one calm row rather than a form.
 *
 * Everything else about a task is editable afterwards. Making the fast path this short
 * is the difference between capturing a thought and losing it.
 */
export function QuickAdd({
  lists,
  defaultListId,
  user,
}: {
  lists: ListOption[]
  defaultListId?: string
  user?: { displayName: string; avatarUrl: string }
}) {
  const t = useTranslations('dashboard')
  const tasks = useTranslations('tasks')
  const [result, action] = useActionState<ActionResult<string> | null, FormData>(createTask, null)
  const [listId, setListId] = useState(defaultListId ?? lists[0]?.id ?? '')
  const [value, setValue] = useState('')
  const [focused, setFocused] = useState(false)
  const formRef = useRef<HTMLFormElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const failure = result && !result.ok ? result : null

  // Clear the field on success and keep focus, so several tasks can be typed in a row.
  useEffect(() => {
    if (result?.ok) {
      formRef.current?.reset()
      setValue('')
      inputRef.current?.focus()
      toast.success(tasks('createDone'))
    }
  }, [result, tasks])

  if (lists.length === 0) return null

  const expanded = focused || value.trim().length > 0
  const selected = lists.find((list) => list.id === listId)

  return (
    <form
      ref={formRef}
      action={action}
      className={cn(
        'rounded-xl border bg-card p-3 transition-colors duration-150',
        expanded ? 'border-zinc-300 dark:border-zinc-700' : 'border-border',
      )}
      noValidate
    >
      <input type="hidden" name="listId" value={listId} />

      <div className="flex items-center gap-3">
        {user && (
          <Avatar className="size-9 shrink-0">
            {user.avatarUrl && <AvatarImage src={user.avatarUrl} alt="" />}
            <AvatarFallback className="text-xs">{initials(user.displayName)}</AvatarFallback>
          </Avatar>
        )}

        {/* A pill-shaped field with no visible box of its own — the card is the box. */}
        <input
          ref={inputRef}
          name="title"
          required
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          aria-label={t('quickAddPlaceholder')}
          placeholder={t('quickAddPlaceholder')}
          className="h-10 min-w-0 flex-1 rounded-full bg-muted/60 px-4 text-[15px] outline-none transition-colors duration-150 placeholder:text-muted-foreground focus-visible:bg-muted"
        />

        <Button
          type="submit"
          size="icon"
          disabled={!value.trim()}
          aria-label={t('quickAdd')}
          className="press size-9 shrink-0 rounded-full"
        >
          <FontAwesomeIcon icon={faArrowUp} className="h-4 w-4" />
        </Button>
      </div>

      {/* The list picker appears only once you are actually composing. */}
      {expanded && lists.length > 1 && (
        <div className="mt-3 flex items-center gap-2 border-t border-border pt-3 pl-0 sm:pl-12">
          <span className="text-sm text-muted-foreground">{tasks('list')}</span>
          <Select value={listId} onValueChange={setListId}>
            <SelectTrigger
              size="sm"
              className="w-auto cursor-pointer gap-2 rounded-full"
              aria-label={tasks('list')}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {lists.map((list) => (
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
      )}

      {/* With one list there is nothing to pick, so just name it. */}
      {expanded && lists.length === 1 && selected && (
        <p className="mt-3 flex items-center gap-2 border-t border-border pt-3 pl-0 text-sm text-muted-foreground sm:pl-12">
          <span
            aria-hidden
            className={cn('size-2 rounded-full', listColorClasses[selected.color].dot)}
          />
          {selected.name}
        </p>
      )}

      {failure && <FormError failure={failure} className="mt-3" />}
    </form>
  )
}
