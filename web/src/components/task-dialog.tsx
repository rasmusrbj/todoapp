'use client'

import { faPlus, faXmark } from '@fortawesome/pro-solid-svg-icons'
import { faCalendar, faRepeat, faTag, faUser } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useLocale, useTranslations } from 'next-intl'
import { useActionState, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { createTask, updateTask } from '@/app/actions/tasks'
import { DatePicker, DateTimePicker } from '@/components/date-time-picker'
import { FieldError, FormError } from '@/components/form-message'
import { SubmitButton } from '@/components/submit-button'
import { Badge } from '@/components/ui/badge'
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
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import {
  RecurrenceFrequencySchema,
  TaskPrioritySchema,
  TaskStatusSchema,
} from '@/gen/todo/v1/enums_pb'
import {
  type ListColor,
  listColorClasses,
  options,
  RecurrenceFrequency,
  TaskPriority,
  TaskStatus,
} from '@/lib/enums'
import type { ActionResult } from '@/lib/errors'
import { cn } from '@/lib/utils'

const STATUS_OPTIONS = options(TaskStatusSchema, 'x')
const PRIORITY_OPTIONS = options(TaskPrioritySchema, 'x')
const RECURRENCE_OPTIONS = options(RecurrenceFrequencySchema, 'x')

/** A list the dialog can create into, with the people and labels it offers. */
export type TaskDialogList = {
  id: string
  name: string
  color: ListColor
  members: Array<{ id: string; displayName: string }>
  labels: Array<{ id: string; name: string; color: ListColor }>
}

/** The task being edited, or nothing when creating. */
export type TaskDialogTask = {
  id: string
  listId: string
  title: string
  description: string
  status: TaskStatus
  priority: TaskPriority
  assigneeId?: string
  labelIds: string[]
  dueDate: string
  dueTime: string
  startsAt: string
  estimateMinutes: number
  recurrenceFrequency: RecurrenceFrequency
  recurrenceInterval: number
}

type TaskDialogProps = {
  lists: TaskDialogList[]
  task?: TaskDialogTask
  defaultListId?: string
  trigger?: React.ReactNode
}

/**
 * Create or edit a task, with everything the model supports in one place.
 *
 * Laid out in three bands: what it is, when it happens, who and what it touches.
 * Everything past the title is optional, so the form stays usable at the speed of a
 * single-line capture while still exposing recurrence and checklists to the people
 * who want them.
 */
export function TaskDialog({ lists, task, defaultListId, trigger }: TaskDialogProps) {
  const t = useTranslations('tasks')
  const app = useTranslations('app')
  const statuses = useTranslations('enums.taskStatus')
  const priorities = useTranslations('enums.taskPriority')
  const recurrences = useTranslations('enums.recurrence')
  const locale = useLocale()

  const [open, setOpen] = useState(false)

  const [listId, setListId] = useState(task?.listId ?? defaultListId ?? lists[0]?.id ?? '')
  const [status, setStatus] = useState<number>(task?.status ?? TaskStatus.TODO)
  const [priority, setPriority] = useState<number>(task?.priority ?? TaskPriority.NONE)
  const [assigneeId, setAssigneeId] = useState(task?.assigneeId ?? '')
  const [labelIds, setLabelIds] = useState<string[]>(task?.labelIds ?? [])
  const [frequency, setFrequency] = useState<number>(
    task?.recurrenceFrequency ?? RecurrenceFrequency.NONE,
  )
  const [subtasks, setSubtasks] = useState<string[]>([])
  const [subtaskDraft, setSubtaskDraft] = useState('')
  // The picker works in one combined `yyyy-MM-ddTHH:mm` string; the action still takes
  // a date and a time separately, so the two are split back apart on submit. An empty
  // time is what tells the server this is an all-day task.
  const [due, setDue] = useState(
    task?.dueDate ? `${task.dueDate}T${task.dueTime || '09:00'}` : '',
  )
  const [startsAt, setStartsAt] = useState(task?.startsAt ?? '')
  const [dueDate = '', dueTime = ''] = due ? due.split('T') : []

  const [result, action] = useActionState<ActionResult<string> | ActionResult | null, FormData>(
    task ? updateTask : createTask,
    null,
  )
  const failure = result && !result.ok ? result : null

  // Labels and assignees belong to one list, so both reset when the list changes —
  // sending a label from another list is exactly what the API rejects.
  const selected = useMemo(() => lists.find((list) => list.id === listId), [lists, listId])

  useEffect(() => {
    if (task) return
    setLabelIds([])
    setAssigneeId('')
  }, [listId, task])

  useEffect(() => {
    if (result?.ok) {
      setOpen(false)
      toast.success(task ? t('updateDone') : t('createDone'))
      if (!task) {
        // Reset so the next open starts clean rather than echoing the last task.
        setSubtasks([])
        setSubtaskDraft('')
        setStatus(TaskStatus.TODO)
        setPriority(TaskPriority.NONE)
        setFrequency(RecurrenceFrequency.NONE)
        setDue('')
        setStartsAt('')
      }
    }
  }, [result, task, t])

  const repeats = frequency !== RecurrenceFrequency.NONE && frequency !== RecurrenceFrequency.UNSPECIFIED

  const addSubtask = () => {
    const value = subtaskDraft.trim()
    if (!value) return
    setSubtasks((current) => [...current, value])
    setSubtaskDraft('')
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button className="press">
            <FontAwesomeIcon icon={faPlus} className="h-4 w-4" />
            {t('newTask')}
          </Button>
        )}
      </DialogTrigger>

      <DialogContent
        className="max-h-[90svh] overflow-y-auto sm:max-w-2xl"
        closeLabel={app('close')}
      >
        <DialogHeader>
          <DialogTitle>{task ? t('taskTitle') : t('createTitle')}</DialogTitle>
          <DialogDescription>
            {selected ? selected.name : t('list')}
          </DialogDescription>
        </DialogHeader>

        <form action={action} className="space-y-5" noValidate>
          {task ? (
            <input type="hidden" name="id" value={task.id} />
          ) : (
            <input type="hidden" name="listId" value={listId} />
          )}
          {!task && <input type="hidden" name="status" value={status} />}
          <input type="hidden" name="priority" value={priority} />
          {!task && assigneeId && <input type="hidden" name="assigneeId" value={assigneeId} />}
          {!task && labelIds.map((id) => <input key={id} type="hidden" name="labelIds" value={id} />)}
          <input type="hidden" name="recurrenceFrequency" value={frequency} />
          {!task &&
            subtasks.map((title, index) => (
              <input key={`${title}-${index}`} type="hidden" name="subtaskTitles" value={title} />
            ))}

          {failure && !failure.field && <FormError failure={failure} />}

          {/* --- What it is ------------------------------------------------- */}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="task-title">{t('taskTitle')}</Label>
              <Input
                id="task-title"
                name="title"
                defaultValue={task?.title}
                autoFocus
                required
                placeholder={t('titlePlaceholder')}
                aria-invalid={failure?.field === 'title'}
              />
              <FieldError failure={failure} field="title" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="task-description">
                {t('description')}{' '}
                <span className="font-normal text-muted-foreground">({app('optional')})</span>
              </Label>
              <Textarea
                id="task-description"
                name="description"
                defaultValue={task?.description}
                rows={3}
                placeholder={t('descriptionPlaceholder')}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              {!task && lists.length > 1 && (
                <div className="space-y-2">
                  <Label htmlFor="task-list">{t('list')}</Label>
                  <Select value={listId} onValueChange={setListId}>
                    <SelectTrigger id="task-list" className="cursor-pointer">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {lists.map((list) => (
                        <SelectItem key={list.id} value={list.id} className="cursor-pointer">
                          <span className="flex items-center gap-2">
                            <span
                              aria-hidden
                              className={cn(
                                'size-2 rounded-full',
                                listColorClasses[list.color].dot,
                              )}
                            />
                            {list.name}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {!task && (
                <div className="space-y-2">
                  <Label htmlFor="task-status">{t('status')}</Label>
                  <Select value={String(status)} onValueChange={(v) => setStatus(Number(v))}>
                    <SelectTrigger id="task-status" className="cursor-pointer">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUS_OPTIONS.map((option) => (
                        <SelectItem
                          key={option.value}
                          value={String(option.value)}
                          className="cursor-pointer"
                        >
                          {statuses(option.name)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="task-priority">{t('priority')}</Label>
                <Select value={String(priority)} onValueChange={(v) => setPriority(Number(v))}>
                  <SelectTrigger id="task-priority" className="cursor-pointer">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PRIORITY_OPTIONS.map((option) => (
                      <SelectItem
                        key={option.value}
                        value={String(option.value)}
                        className="cursor-pointer"
                      >
                        {priorities(option.name)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <Separator />

          {/* --- When it happens -------------------------------------------- */}
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="task-due" className="gap-1.5">
                  <FontAwesomeIcon icon={faCalendar} className="h-3.5 w-3.5" />
                  {t('dueDate')}
                </Label>
                <DateTimePicker
                  id="task-due"
                  value={due}
                  onChange={setDue}
                  locale={locale}
                  placeholder={t('noDueDate')}
                  timeLabel={t('dueTime')}
                />
                <input type="hidden" name="dueDate" value={dueDate} />
                <input type="hidden" name="dueTime" value={dueTime} />
              </div>

              <div className="space-y-2">
                <Label htmlFor="task-estimate">{t('estimate')}</Label>
                <Input
                  id="task-estimate"
                  name="estimateMinutes"
                  type="number"
                  min={0}
                  step={5}
                  inputMode="numeric"
                  defaultValue={task?.estimateMinutes || ''}
                  placeholder="30"
                  className="tabular-nums"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="task-starts" className="gap-1.5">
                  <FontAwesomeIcon icon={faCalendar} className="h-3.5 w-3.5" />
                  {t('startDate')}
                </Label>
                <DatePicker
                  id="task-starts"
                  value={startsAt}
                  onChange={setStartsAt}
                  locale={locale}
                  placeholder={t('startDate')}
                />
                <input type="hidden" name="startsAt" value={startsAt} />
              </div>

              <div className="space-y-2">
                <Label htmlFor="task-repeat" className="gap-1.5">
                  <FontAwesomeIcon icon={faRepeat} className="h-3.5 w-3.5" />
                  {t('repeat')}
                </Label>
                <Select value={String(frequency)} onValueChange={(v) => setFrequency(Number(v))}>
                  <SelectTrigger id="task-repeat" className="cursor-pointer">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {RECURRENCE_OPTIONS.map((option) => (
                      <SelectItem
                        key={option.value}
                        value={String(option.value)}
                        className="cursor-pointer"
                      >
                        {recurrences(option.name)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Only meaningful alongside a frequency. */}
              {repeats && (
                <div className="space-y-2">
                  <Label htmlFor="task-interval">{t('repeatEvery')}</Label>
                  <Input
                    id="task-interval"
                    name="recurrenceInterval"
                    type="number"
                    min={1}
                    max={365}
                    inputMode="numeric"
                    defaultValue={task?.recurrenceInterval || 1}
                    className="tabular-nums"
                  />
                </div>
              )}
            </div>
          </div>

          {/* --- Who and what ---------------------------------------------- */}
          {!task && (selected?.members.length || selected?.labels.length) ? (
            <>
              <Separator />
              <div className="space-y-4">
                {selected.members.length > 0 && (
                  <div className="space-y-2">
                    <Label htmlFor="task-assignee" className="gap-1.5">
                      <FontAwesomeIcon icon={faUser} className="h-3.5 w-3.5" />
                      {t('assignee')}
                    </Label>
                    <Select
                      value={assigneeId || 'none'}
                      onValueChange={(value) => setAssigneeId(value === 'none' ? '' : value)}
                    >
                      <SelectTrigger id="task-assignee" className="cursor-pointer">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none" className="cursor-pointer">
                          {t('unassigned')}
                        </SelectItem>
                        {selected.members.map((member) => (
                          <SelectItem
                            key={member.id}
                            value={member.id}
                            className="cursor-pointer"
                          >
                            {member.displayName}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                {selected.labels.length > 0 && (
                  <div className="space-y-2">
                    <Label className="gap-1.5">
                      <FontAwesomeIcon icon={faTag} className="h-3.5 w-3.5" />
                      {t('labels')}
                    </Label>
                    {/* Toggle chips rather than a multi-select: the whole set is
                        visible, and one tap adds or removes. */}
                    <div className="flex flex-wrap gap-2">
                      {selected.labels.map((label) => {
                        const active = labelIds.includes(label.id)
                        const tokens = listColorClasses[label.color]
                        return (
                          <button
                            key={label.id}
                            type="button"
                            aria-pressed={active}
                            onClick={() =>
                              setLabelIds((current) =>
                                active
                                  ? current.filter((id) => id !== label.id)
                                  : [...current, label.id],
                              )
                            }
                            className={cn(
                              'press-icon inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors duration-100',
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
                )}
              </div>
            </>
          ) : null}

          {/* --- Checklist -------------------------------------------------- */}
          {!task && (
            <>
              <Separator />
              <div className="space-y-2">
                <Label htmlFor="task-subtask">{t('subtasks')}</Label>
                {subtasks.length > 0 && (
                  <ul className="space-y-1.5">
                    {subtasks.map((title, index) => (
                      <li
                        key={`${title}-${index}`}
                        className="flex items-center gap-2 rounded-md border border-border px-2.5 py-1.5 text-sm"
                      >
                        <span className="min-w-0 flex-1 truncate">{title}</span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          aria-label={app('delete')}
                          className="press-icon"
                          onClick={() =>
                            setSubtasks((current) => current.filter((_, i) => i !== index))
                          }
                        >
                          <FontAwesomeIcon icon={faXmark} className="h-3.5 w-3.5" />
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="flex gap-2">
                  <Input
                    id="task-subtask"
                    value={subtaskDraft}
                    onChange={(event) => setSubtaskDraft(event.target.value)}
                    placeholder={t('subtaskPlaceholder')}
                    // Enter adds an item instead of submitting the whole form, which
                    // is what a checklist field has to do to be usable.
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault()
                        addSubtask()
                      }
                    }}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    className="press shrink-0"
                    disabled={!subtaskDraft.trim()}
                    onClick={addSubtask}
                  >
                    <FontAwesomeIcon icon={faPlus} className="h-4 w-4" />
                    {t('addSubtask')}
                  </Button>
                </div>
                {subtasks.length > 0 && (
                  <Badge variant="outline" className="rounded-full bg-transparent">
                    {t('subtaskProgress', { done: 0, total: subtasks.length })}
                  </Badge>
                )}
              </div>
            </>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" className="press" onClick={() => setOpen(false)}>
              {app('cancel')}
            </Button>
            <SubmitButton pendingLabel={app('saving')}>
              {task ? app('save') : app('create')}
            </SubmitButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
