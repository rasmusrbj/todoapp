'use client'

import { faBan, faCircleCheck, faEllipsis } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useState, useTransition } from 'react'
import { toast } from 'sonner'

import { setUserRole, setUserStatus } from '@/app/actions/users'
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
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { UserRoleSchema, UserStatusSchema } from '@/gen/todo/v1/enums_pb'
import { options, UserRole, UserStatus, valueName } from '@/lib/enums'

const ROLE_OPTIONS = options(UserRoleSchema, 'x')

type AdminUser = {
  id: string
  displayName: string
  email: string
  avatarUrl: string
  role: number
  status: number
  emailVerified: boolean
  ownedListCount: number
  openTaskCount: number
  overdueTaskCount: number
  lastSeenAt: string
}

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  return ((words[0]?.[0] ?? '') + (words.length > 1 ? (words.at(-1)?.[0] ?? '') : '')).toUpperCase()
}

/**
 * Every account, with the two things an admin actually does: change a role, and
 * suspend or reactivate.
 *
 * Suspension takes a reason, because the person on the other end is shown it — and an
 * admin cannot suspend themselves, which the API refuses anyway.
 */
export function UserTable({ users, viewerId }: { users: AdminUser[]; viewerId: string }) {
  const t = useTranslations('admin')
  const app = useTranslations('app')
  const roles = useTranslations('enums.userRole')
  const statuses = useTranslations('enums.userStatus')

  const [suspending, setSuspending] = useState<AdminUser | null>(null)
  const [reason, setReason] = useState('')
  const [pending, startTransition] = useTransition()

  if (users.length === 0) {
    return (
      <p className="rounded-xl border border-border bg-card px-4 py-8 text-center text-sm text-muted-foreground">
        {t('empty')}
      </p>
    )
  }

  return (
    <>
      <Card className="rounded-xl py-0">
        <CardContent className="p-0">
          {/* Wide tables scroll inside their own container, never the page body. */}
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('title')}</TableHead>
                  <TableHead>{t('role')}</TableHead>
                  <TableHead>{t('status')}</TableHead>
                  <TableHead className="text-right">{t('lists')}</TableHead>
                  <TableHead className="text-right">{t('openTasks')}</TableHead>
                  <TableHead>{t('lastSeen')}</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>

              <TableBody>
                {users.map((user) => {
                  const isSelf = user.id === viewerId
                  const isSuspended = user.status === UserStatus.SUSPENDED
                  return (
                    <TableRow key={user.id} className="transition-colors hover:bg-muted/50">
                      <TableCell>
                        <div className="flex items-center gap-2.5">
                          <Avatar className="size-8 shrink-0">
                            {user.avatarUrl && <AvatarImage src={user.avatarUrl} alt="" />}
                            <AvatarFallback className="text-xs">
                              {initials(user.displayName)}
                            </AvatarFallback>
                          </Avatar>
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium">
                              {user.displayName}
                              {user.emailVerified && (
                                <FontAwesomeIcon
                                  icon={faCircleCheck}
                                  className="ml-1.5 h-3 w-3 text-emerald-600 dark:text-emerald-400"
                                />
                              )}
                            </p>
                            <p className="truncate text-xs text-muted-foreground">{user.email}</p>
                          </div>
                        </div>
                      </TableCell>

                      <TableCell>
                        <Badge variant="outline" className="rounded-full bg-transparent">
                          {roles(valueName(UserRoleSchema, user.role))}
                        </Badge>
                      </TableCell>

                      <TableCell>
                        <Badge
                          variant="outline"
                          className={
                            isSuspended
                              ? 'rounded-full border-red-200 bg-transparent text-red-700 dark:border-red-900 dark:text-red-300'
                              : 'rounded-full bg-transparent'
                          }
                        >
                          {statuses(valueName(UserStatusSchema, user.status))}
                        </Badge>
                      </TableCell>

                      <TableCell className="text-right tabular-nums">
                        {user.ownedListCount}
                      </TableCell>

                      <TableCell className="text-right tabular-nums">
                        {user.openTaskCount}
                        {user.overdueTaskCount > 0 && (
                          <span className="ml-1 text-red-600 dark:text-red-400">
                            ({user.overdueTaskCount})
                          </span>
                        )}
                      </TableCell>

                      <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                        {user.lastSeenAt || t('never')}
                      </TableCell>

                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label={app('edit')}
                              className="press-icon"
                            >
                              <FontAwesomeIcon icon={faEllipsis} className="h-3.5 w-3.5" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-48">
                            <DropdownMenuLabel>{t('role')}</DropdownMenuLabel>
                            {ROLE_OPTIONS.map((option) => (
                              <DropdownMenuItem
                                key={option.value}
                                disabled={pending || user.role === option.value}
                                className="cursor-pointer"
                                onClick={() =>
                                  startTransition(async () => {
                                    const result = await setUserRole(
                                      user.id,
                                      option.value as UserRole,
                                    )
                                    if (result.ok) toast.success(t('statusChanged'))
                                  })
                                }
                              >
                                {roles(option.name)}
                              </DropdownMenuItem>
                            ))}

                            {/* An admin cannot suspend themselves — the API refuses,
                                and offering it would just produce an error. */}
                            {!isSelf && (
                              <>
                                <DropdownMenuSeparator />
                                {isSuspended ? (
                                  <DropdownMenuItem
                                    disabled={pending}
                                    className="cursor-pointer"
                                    onClick={() =>
                                      startTransition(async () => {
                                        const result = await setUserStatus(
                                          user.id,
                                          UserStatus.ACTIVE,
                                          '',
                                        )
                                        if (result.ok) toast.success(t('statusChanged'))
                                      })
                                    }
                                  >
                                    <FontAwesomeIcon icon={faCircleCheck} className="h-3.5 w-3.5" />
                                    {t('activate')}
                                  </DropdownMenuItem>
                                ) : (
                                  <DropdownMenuItem
                                    className="cursor-pointer text-destructive focus:text-destructive"
                                    onClick={() => {
                                      setReason('')
                                      setSuspending(user)
                                    }}
                                  >
                                    <FontAwesomeIcon icon={faBan} className="h-3.5 w-3.5" />
                                    {t('suspend')}
                                  </DropdownMenuItem>
                                )}
                              </>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <AlertDialog
        open={suspending !== null}
        onOpenChange={(open) => !open && setSuspending(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t('suspendTitle', { name: suspending?.displayName ?? '' })}
            </AlertDialogTitle>
            <AlertDialogDescription>{t('suspendBody')}</AlertDialogDescription>
          </AlertDialogHeader>

          <div className="space-y-2">
            <Label htmlFor="suspend-reason">{t('reason')}</Label>
            <Input
              id="suspend-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder={t('reasonPlaceholder')}
            />
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel className="press">{app('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              disabled={pending}
              className="press bg-destructive text-white hover:bg-destructive/90"
              onClick={() => {
                const target = suspending
                if (!target) return
                startTransition(async () => {
                  const result = await setUserStatus(target.id, UserStatus.SUSPENDED, reason)
                  if (result.ok) toast.success(t('statusChanged'))
                  setSuspending(null)
                })
              }}
            >
              {t('suspend')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
