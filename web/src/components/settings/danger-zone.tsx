'use client'

import { faTriangleExclamation } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useState, useTransition } from 'react'

import { deleteAccount } from '@/app/actions/auth'
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

/**
 * Account deletion.
 *
 * Typing the confirmation word is the point: this cascades to every list the account
 * owns, and a single click is too cheap for that.
 */
export function DangerZone() {
  const t = useTranslations('settings')
  const app = useTranslations('app')
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const [pending, startTransition] = useTransition()

  // Localized, so the word matches the language the warning is written in.
  const confirmation = t('deleteAccount')

  return (
    <>
      <Card className="rounded-xl border-destructive/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm text-destructive">
            <FontAwesomeIcon icon={faTriangleExclamation} className="h-3.5 w-3.5" />
            {t('dangerZone')}
          </CardTitle>
          <CardDescription>{t('dangerSubtitle')}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="outline"
            className="press border-destructive/50 text-destructive hover:bg-destructive/10"
            onClick={() => setOpen(true)}
          >
            {t('deleteAccount')}
          </Button>
        </CardContent>
      </Card>

      <AlertDialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next)
          if (!next) setTyped('')
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteAccountTitle')}</AlertDialogTitle>
            <AlertDialogDescription>{t('deleteAccountBody')}</AlertDialogDescription>
          </AlertDialogHeader>

          <div className="space-y-2">
            <Label htmlFor="delete-confirmation">{confirmation}</Label>
            <Input
              id="delete-confirmation"
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              autoComplete="off"
              placeholder={confirmation}
            />
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel className="press">{app('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              disabled={pending || typed.trim().toLowerCase() !== confirmation.toLowerCase()}
              className="press bg-destructive text-white hover:bg-destructive/90"
              onClick={() => startTransition(() => void deleteAccount())}
            >
              {app('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
