'use client'

import { faArrowDown, faArrowUp, faBars } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useState, useTransition } from 'react'
import { toast } from 'sonner'

import { reorderLists } from '@/app/actions/lists'
import { Button } from '@/components/ui/button'
import { type ListColor, listColorClasses } from '@/lib/enums'
import { cn } from '@/lib/utils'

type ReorderItem = { id: string; name: string; color: ListColor }

/**
 * Reordering the board.
 *
 * Buttons rather than drag-and-drop, deliberately: a move-up/move-down pair is
 * keyboard-operable, works on a touch screen without a long-press, and needs no pointer
 * capture to get right. Dragging looks nicer in a demo and is worse for anyone not using
 * a mouse.
 *
 * The order is applied locally as you go and saved in one call, so a five-step
 * rearrangement is one request rather than five.
 */
export function ListReorder({ lists }: { lists: ReorderItem[] }) {
  const t = useTranslations('lists')
  const app = useTranslations('app')
  const [open, setOpen] = useState(false)
  const [order, setOrder] = useState(lists)
  const [pending, startTransition] = useTransition()

  const move = (index: number, delta: number) => {
    const target = index + delta
    if (target < 0 || target >= order.length) return
    setOrder((current) => {
      const next = [...current]
      const [item] = next.splice(index, 1)
      if (item) next.splice(target, 0, item)
      return next
    })
  }

  const save = () =>
    startTransition(async () => {
      const result = await reorderLists(order.map((item) => item.id))
      if (result.ok) {
        toast.success(t('reorderDone'))
        setOpen(false)
      }
    })

  if (lists.length < 2) return null

  if (!open) {
    return (
      <Button
        variant="outline"
        size="sm"
        className="press"
        onClick={() => {
          // Start from what is on screen now, not from a stale earlier snapshot.
          setOrder(lists)
          setOpen(true)
        }}
      >
        <FontAwesomeIcon icon={faBars} className="h-3.5 w-3.5" />
        {t('reorder')}
      </Button>
    )
  }

  return (
    <div className="w-full rounded-xl border border-border bg-card p-3 sm:w-80">
      <ul className="space-y-1">
        {order.map((item, index) => (
          <li
            key={item.id}
            className="flex items-center gap-2 rounded-lg px-2 py-1.5 transition-colors duration-100 hover:bg-muted/50"
          >
            <span
              aria-hidden
              className={cn('size-2 shrink-0 rounded-full', listColorClasses[item.color].dot)}
            />
            <span className="min-w-0 flex-1 truncate text-sm">{item.name}</span>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t('moveUp')}
              disabled={index === 0 || pending}
              className="press-icon"
              onClick={() => move(index, -1)}
            >
              <FontAwesomeIcon icon={faArrowUp} className="h-3 w-3" />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t('moveDown')}
              disabled={index === order.length - 1 || pending}
              className="press-icon"
              onClick={() => move(index, 1)}
            >
              <FontAwesomeIcon icon={faArrowDown} className="h-3 w-3" />
            </Button>
          </li>
        ))}
      </ul>

      <div className="mt-3 flex justify-end gap-2 border-t border-border pt-3">
        <Button variant="ghost" size="sm" className="press" onClick={() => setOpen(false)}>
          {app('cancel')}
        </Button>
        <Button size="sm" disabled={pending} className="press" onClick={save}>
          {app('save')}
        </Button>
      </div>
    </div>
  )
}
