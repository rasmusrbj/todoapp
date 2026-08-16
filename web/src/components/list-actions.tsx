'use client'

import {
  faArrowRotateLeft,
  faBoxArchive,
  faEllipsis,
  faPen,
  faRightFromBracket,
  faTrash,
} from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useState, useTransition } from 'react'
import { toast } from 'sonner'

import { deleteList, leaveList, setListArchived } from '@/app/actions/lists'
import { ListDialog } from '@/components/list-dialog'
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
import type { ListColor, ListVisibility } from '@/lib/enums'

type ListSummary = {
  id: string
  name: string
  description: string
  color: ListColor
  visibility: ListVisibility
  archived: boolean
}

/**
 * The overflow menu on a list.
 *
 * Destructive actions go behind an `AlertDialog` that names what is about to be lost —
 * a confirmation that says "are you sure?" without saying what happens is not one.
 */
export function ListActions({
  list,
  viewerId,
  canEdit,
  canAdminister,
  isMember,
}: {
  list: ListSummary
  viewerId: string
  canEdit: boolean
  canAdminister: boolean
  isMember: boolean
}) {
  const t = useTranslations('lists')
  const app = useTranslations('app')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [confirmLeave, setConfirmLeave] = useState(false)
  const [pending, startTransition] = useTransition()

  const run = (work: () => Promise<{ ok: boolean }>, success: string) =>
    startTransition(async () => {
      const result = await work()
      if (result.ok) toast.success(success)
    })

  // Nothing to offer someone with read-only access who is not even a member.
  if (!canEdit && !isMember) return null

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="icon" aria-label={app('edit')} className="press">
            <FontAwesomeIcon icon={faEllipsis} className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-52">
          {canEdit && (
            <ListDialog
              list={list}
              canChangeVisibility={canAdminister}
              trigger={
                <DropdownMenuItem
                  className="cursor-pointer"
                  // The dialog is the trigger's child, so the menu must not close
                  // before it opens.
                  onSelect={(event) => event.preventDefault()}
                >
                  <FontAwesomeIcon icon={faPen} className="h-3.5 w-3.5" />
                  {app('edit')}
                </DropdownMenuItem>
              }
            />
          )}

          {canAdminister && (
            <DropdownMenuItem
              className="cursor-pointer"
              disabled={pending}
              onClick={() =>
                run(
                  () => setListArchived(list.id, !list.archived),
                  list.archived ? t('restoreDone') : t('archiveDone'),
                )
              }
            >
              <FontAwesomeIcon
                icon={list.archived ? faArrowRotateLeft : faBoxArchive}
                className="h-3.5 w-3.5"
              />
              {list.archived ? t('restore') : t('archive')}
            </DropdownMenuItem>
          )}

          {isMember && !canAdminister && (
            <DropdownMenuItem
              className="cursor-pointer"
              onClick={() => setConfirmLeave(true)}
            >
              <FontAwesomeIcon icon={faRightFromBracket} className="h-3.5 w-3.5" />
              {t('leaveList')}
            </DropdownMenuItem>
          )}

          {canAdminister && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="cursor-pointer text-destructive focus:text-destructive"
                onClick={() => setConfirmDelete(true)}
              >
                <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" />
                {app('delete')}
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteBody', { name: list.name })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="press">{app('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              disabled={pending}
              className="press bg-destructive text-white hover:bg-destructive/90"
              onClick={() => run(() => deleteList(list.id), t('deleteDone'))}
            >
              {app('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={confirmLeave} onOpenChange={setConfirmLeave}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('leaveList')}</AlertDialogTitle>
            <AlertDialogDescription>{list.name}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="press">{app('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              disabled={pending}
              className="press"
              onClick={() => run(() => leaveList(list.id, viewerId), t('leaveDone'))}
            >
              {app('confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
