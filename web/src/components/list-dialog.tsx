'use client'

import { faPlus } from '@fortawesome/pro-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useActionState, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { createList, updateList } from '@/app/actions/lists'
import { FieldError, FormError } from '@/components/form-message'
import { SubmitButton } from '@/components/submit-button'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { ListColorSchema, ListVisibilitySchema } from '@/gen/todo/v1/enums_pb'
import { ListColor, listColorClasses, ListVisibility, options } from '@/lib/enums'
import type { ActionResult } from '@/lib/errors'
import { cn } from '@/lib/utils'

const COLOR_OPTIONS = options(ListColorSchema, 'x')
const VISIBILITY_OPTIONS = options(ListVisibilitySchema, 'x')

type ListDialogProps = {
  /** Present to edit; absent to create. */
  list?: { id: string; name: string; description: string; color: ListColor; visibility: ListVisibility }
  /** Only the owner may change visibility, so the field is hidden for an editor. */
  canChangeVisibility?: boolean
  trigger?: React.ReactNode
}

/**
 * Create or edit a list.
 *
 * One component for both, because the fields are identical — a separate "edit" dialog
 * would be the same form twice and drift within a week.
 */
export function ListDialog({ list, canChangeVisibility = true, trigger }: ListDialogProps) {
  const t = useTranslations('lists')
  const app = useTranslations('app')
  const colors = useTranslations('enums.listColor')
  const visibilities = useTranslations('enums.listVisibility')
  const hints = useTranslations('enums.listVisibilityHint')

  const [open, setOpen] = useState(false)
  const [color, setColor] = useState<number>(list?.color ?? ListColor.ZINC)
  const [visibility, setVisibility] = useState<number>(list?.visibility ?? ListVisibility.PRIVATE)
  const [result, action] = useActionState<ActionResult<string> | ActionResult | null, FormData>(
    list ? updateList : createList,
    null,
  )
  const failure = result && !result.ok ? result : null

  useEffect(() => {
    if (result?.ok) {
      setOpen(false)
      toast.success(list ? t('updateDone') : t('createDone'))
    }
  }, [result, list, t])

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button className="press">
            <FontAwesomeIcon icon={faPlus} className="h-4 w-4" />
            {t('newList')}
          </Button>
        )}
      </DialogTrigger>

      <DialogContent className="sm:max-w-md" closeLabel={app('close')}>
        <DialogHeader>
          <DialogTitle>{list ? t('name') : t('createTitle')}</DialogTitle>
          <DialogDescription>{t('createSubtitle')}</DialogDescription>
        </DialogHeader>

        <form action={action} className="space-y-4" noValidate>
          {list && <input type="hidden" name="id" value={list.id} />}
          <input type="hidden" name="color" value={color} />
          {canChangeVisibility && <input type="hidden" name="visibility" value={visibility} />}
          {failure && !failure.field && <FormError failure={failure} />}

          <div className="space-y-2">
            <Label htmlFor="list-name">{t('name')}</Label>
            <Input
              id="list-name"
              name="name"
              defaultValue={list?.name}
              autoFocus
              required
              placeholder={t('namePlaceholder')}
              aria-invalid={failure?.field === 'name'}
            />
            <FieldError failure={failure} field="name" />
          </div>

          <div className="space-y-2">
            <Label htmlFor="list-description">
              {t('description')}{' '}
              <span className="font-normal text-muted-foreground">({app('optional')})</span>
            </Label>
            <Textarea
              id="list-description"
              name="description"
              defaultValue={list?.description}
              rows={2}
              placeholder={t('descriptionPlaceholder')}
            />
          </div>

          <div className="space-y-2">
            <Label>{t('color')}</Label>
            {/* Swatches rather than a dropdown: seven options are faster to pick from
                than to read, and each carries its name as a tooltip. */}
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
                    'press-icon flex size-8 items-center justify-center rounded-full border-2',
                    color === option.value ? 'border-ring' : 'border-transparent',
                  )}
                >
                  <span
                    aria-hidden
                    className={cn(
                      'size-5 rounded-full',
                      listColorClasses[option.value as ListColor].dot,
                    )}
                  />
                </button>
              ))}
            </div>
          </div>

          {canChangeVisibility && (
            <div className="space-y-2">
              <Label htmlFor="list-visibility">{t('visibility')}</Label>
              <Select value={String(visibility)} onValueChange={(v) => setVisibility(Number(v))}>
                <SelectTrigger id="list-visibility" className="cursor-pointer">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {VISIBILITY_OPTIONS.map((option) => (
                    <SelectItem
                      key={option.value}
                      value={String(option.value)}
                      className="cursor-pointer"
                    >
                      {visibilities(option.name)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                {hints(
                  VISIBILITY_OPTIONS.find((option) => option.value === visibility)?.name ??
                    'LIST_VISIBILITY_PRIVATE',
                )}
              </p>
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              className="press"
              onClick={() => setOpen(false)}
            >
              {app('cancel')}
            </Button>
            <SubmitButton pendingLabel={app('saving')}>
              {list ? app('save') : app('create')}
            </SubmitButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
