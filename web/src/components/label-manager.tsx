'use client'

import { faPlus, faTag, faTrash } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useActionState, useEffect, useRef, useState, useTransition } from 'react'
import { toast } from 'sonner'

import { createLabel, deleteLabel, updateLabel } from '@/app/actions/lists'
import { FieldError, FormError } from '@/components/form-message'
import { SubmitButton } from '@/components/submit-button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label as FieldLabel } from '@/components/ui/label'
import { ListColorSchema } from '@/gen/todo/v1/enums_pb'
import { ListColor, listColorClasses, options } from '@/lib/enums'
import type { ActionResult } from '@/lib/errors'
import { cn } from '@/lib/utils'

const COLOR_OPTIONS = options(ListColorSchema, 'x')

type LabelItem = { id: string; name: string; color: ListColor }

/**
 * Labels on one list.
 *
 * Deliberately list-scoped, matching the model: a label belongs to a list, so moving a
 * task elsewhere drops it. Colour is picked from swatches — seven options read faster
 * as colour than as words.
 */
export function LabelManager({
  listId,
  labels,
  canEdit,
}: {
  listId: string
  labels: LabelItem[]
  canEdit: boolean
}) {
  const t = useTranslations('lists')
  const app = useTranslations('app')
  const colors = useTranslations('enums.listColor')

  const [color, setColor] = useState<number>(ListColor.ZINC)
  const [removing, setRemoving] = useState<LabelItem | null>(null)
  const [pending, startTransition] = useTransition()
  const [result, action] = useActionState<ActionResult | null, FormData>(createLabel, null)
  const formRef = useRef<HTMLFormElement>(null)
  const failure = result && !result.ok ? result : null

  useEffect(() => {
    if (result?.ok) {
      formRef.current?.reset()
      setColor(ListColor.ZINC)
      toast.success(t('labelCreated'))
    }
  }, [result, t])

  return (
    <>
      <Card className="rounded-xl">
        <CardHeader>
          <CardTitle className="text-sm">{t('labels')}</CardTitle>
          <CardDescription>{t('labelsSubtitle')}</CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {labels.length === 0 ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <FontAwesomeIcon icon={faTag} className="h-3.5 w-3.5" />
              {t('noLabels')}
            </p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {labels.map((label) => {
                const tokens = listColorClasses[label.color]
                return (
                  <li
                    key={label.id}
                    className={cn(
                      'inline-flex items-center gap-2 rounded-full border py-1 pl-2.5 pr-1',
                      tokens.tint,
                      tokens.ring,
                    )}
                  >
                    <span aria-hidden className={cn('size-1.5 rounded-full', tokens.dot)} />
                    <span className="text-xs">{label.name}</span>

                    {canEdit && (
                      <>
                        {/* Recolouring in place: the swatch row would be more UI than
                            the action deserves, so a click cycles to the next colour. */}
                        <button
                          type="button"
                          disabled={pending}
                          aria-label={t('color')}
                          className="press-icon flex size-5 items-center justify-center rounded-full text-muted-foreground hover:text-foreground"
                          onClick={() => {
                            const index = COLOR_OPTIONS.findIndex((o) => o.value === label.color)
                            const next = COLOR_OPTIONS[(index + 1) % COLOR_OPTIONS.length]
                            if (!next) return
                            startTransition(async () => {
                              const outcome = await updateLabel(label.id, listId, {
                                color: next.value as ListColor,
                              })
                              if (outcome.ok) toast.success(t('labelUpdated'))
                            })
                          }}
                        >
                          <FontAwesomeIcon icon={faTag} className="h-3 w-3" />
                        </button>

                        <button
                          type="button"
                          aria-label={app('delete')}
                          className="press-icon flex size-5 items-center justify-center rounded-full text-muted-foreground hover:text-destructive"
                          onClick={() => setRemoving(label)}
                        >
                          <FontAwesomeIcon icon={faTrash} className="h-3 w-3" />
                        </button>
                      </>
                    )}
                  </li>
                )
              })}
            </ul>
          )}

          {canEdit && (
            <form ref={formRef} action={action} className="space-y-3 border-t border-border pt-4" noValidate>
              <input type="hidden" name="listId" value={listId} />
              <input type="hidden" name="color" value={color} />
              {failure && !failure.field && <FormError failure={failure} />}

              <div className="space-y-2">
                <FieldLabel htmlFor="label-name">{t('newLabel')}</FieldLabel>
                <div className="flex gap-2">
                  <Input
                    id="label-name"
                    name="name"
                    required
                    placeholder={t('labelNamePlaceholder')}
                    aria-invalid={failure?.field === 'name'}
                  />
                  <SubmitButton className="shrink-0">
                    <FontAwesomeIcon icon={faPlus} className="h-4 w-4" />
                    {app('create')}
                  </SubmitButton>
                </div>
                <FieldError failure={failure} field="name" />
              </div>

              <div className="flex flex-wrap gap-2">
                {COLOR_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    title={colors(option.name)}
                    aria-label={colors(option.name)}
                    aria-pressed={color === option.value}
                    onClick={() => setColor(option.value)}
                    className={cn(
                      'press-icon flex size-7 items-center justify-center rounded-full border-2',
                      color === option.value ? 'border-ring' : 'border-transparent',
                    )}
                  >
                    <span
                      aria-hidden
                      className={cn(
                        'size-4 rounded-full',
                        listColorClasses[option.value as ListColor].dot,
                      )}
                    />
                  </button>
                ))}
              </div>
            </form>
          )}
        </CardContent>
      </Card>

      <AlertDialog open={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{app('delete')}</AlertDialogTitle>
            <AlertDialogDescription>{removing?.name}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="press">{app('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              disabled={pending}
              className="press bg-destructive text-white hover:bg-destructive/90"
              onClick={() => {
                const target = removing
                if (!target) return
                startTransition(async () => {
                  const outcome = await deleteLabel(target.id, listId)
                  if (outcome.ok) toast.success(t('labelDeleted'))
                  setRemoving(null)
                })
              }}
            >
              {app('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
