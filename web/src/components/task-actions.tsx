'use client'

import { faEllipsis, faPen, faTrash } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useState, useTransition } from 'react'
import { toast } from 'sonner'

import { deleteTask } from '@/app/actions/tasks'
import { TaskDialog, type TaskDialogList, type TaskDialogTask } from '@/components/task-dialog'
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
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

/** Edit and delete for one task. */
export function TaskActions({
  task,
  lists,
  canEdit,
  returnTo,
}: {
  task: TaskDialogTask
  lists: TaskDialogList[]
  canEdit: boolean
  /** Where to land after deleting, since the task's own page will be gone. */
  returnTo: string
}) {
  const t = useTranslations('tasks')
  const app = useTranslations('app')
  const [confirming, setConfirming] = useState(false)
  const [pending, startTransition] = useTransition()

  if (!canEdit) return null

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="icon" aria-label={app('edit')} className="press">
            <FontAwesomeIcon icon={faEllipsis} className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <TaskDialog
            lists={lists}
            task={task}
            trigger={
              <DropdownMenuItem
                className="cursor-pointer"
                // Keep the menu from closing before the dialog it owns has opened.
                onSelect={(event) => event.preventDefault()}
              >
                <FontAwesomeIcon icon={faPen} className="h-3.5 w-3.5" />
                {app('edit')}
              </DropdownMenuItem>
            }
          />
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="cursor-pointer text-destructive focus:text-destructive"
            onClick={() => setConfirming(true)}
          >
            <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" />
            {app('delete')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteBody', { title: task.title })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="press">{app('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              disabled={pending}
              className="press bg-destructive text-white hover:bg-destructive/90"
              onClick={() =>
                startTransition(async () => {
                  const result = await deleteTask(task.id, returnTo)
                  if (result.ok) toast.success(t('deleteDone'))
                })
              }
            >
              {app('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
