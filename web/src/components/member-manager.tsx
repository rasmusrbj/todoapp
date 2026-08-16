'use client'

import { faUserPlus, faUserXmark } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useActionState, useEffect, useState, useTransition } from 'react'
import { toast } from 'sonner'

import { addMember, removeMember, updateMemberRole } from '@/app/actions/lists'
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
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import { MemberRoleSchema } from '@/gen/todo/v1/enums_pb'
import { MemberRole, options, valueName } from '@/lib/enums'
import type { ActionResult } from '@/lib/errors'

// Ownership is not something a role dropdown grants, so it is not on offer.
const ROLE_OPTIONS = options(MemberRoleSchema, 'x').filter(
  (option) => option.value !== MemberRole.OWNER,
)

type Member = {
  userId: string
  displayName: string
  email: string
  avatarUrl: string
  role: MemberRole
  invitedBy?: string
}

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  return ((words[0]?.[0] ?? '') + (words.length > 1 ? (words.at(-1)?.[0] ?? '') : '')).toUpperCase()
}

/** Who can reach a list, and at what level. */
export function MemberManager({
  listId,
  listName,
  members,
  viewerId,
  canAdminister,
}: {
  listId: string
  listName: string
  members: Member[]
  viewerId: string
  canAdminister: boolean
}) {
  const t = useTranslations('lists')
  const app = useTranslations('app')
  const auth = useTranslations('auth')
  const roles = useTranslations('enums.memberRole')
  const hints = useTranslations('enums.memberRoleHint')

  const [shareOpen, setShareOpen] = useState(false)
  const [role, setRole] = useState<number>(MemberRole.EDITOR)
  const [removing, setRemoving] = useState<Member | null>(null)
  const [pending, startTransition] = useTransition()
  const [result, action] = useActionState<ActionResult | null, FormData>(addMember, null)
  const failure = result && !result.ok ? result : null

  useEffect(() => {
    if (result?.ok) {
      setShareOpen(false)
      toast.success(t('shareDone', { name: '' }).replace('  ', ' ').trim())
    }
  }, [result, t])

  return (
    <>
      <Card className="rounded-xl">
        <CardHeader>
          <CardTitle className="text-sm">{t('members')}</CardTitle>
          <CardDescription>{t('membersSubtitle')}</CardDescription>
          {canAdminister && (
            <div className="col-start-2 row-span-2 row-start-1 self-start justify-self-end">
              <Dialog open={shareOpen} onOpenChange={setShareOpen}>
                <DialogTrigger asChild>
                  <Button size="sm" className="press">
                    <FontAwesomeIcon icon={faUserPlus} className="h-3.5 w-3.5" />
                    {t('share')}
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-md" closeLabel={app('close')}>
                  <DialogHeader>
                    <DialogTitle>{t('shareTitle', { name: listName })}</DialogTitle>
                    <DialogDescription>{t('shareSubtitle')}</DialogDescription>
                  </DialogHeader>
                  <form action={action} className="space-y-4" noValidate>
                    <input type="hidden" name="listId" value={listId} />
                    <input type="hidden" name="role" value={role} />
                    {failure && !failure.field && <FormError failure={failure} />}

                    <div className="space-y-2">
                      <Label htmlFor="share-email">{auth('email')}</Label>
                      <Input
                        id="share-email"
                        name="email"
                        type="email"
                        autoFocus
                        required
                        placeholder={auth('emailPlaceholder')}
                        aria-invalid={failure?.field === 'email'}
                      />
                      <FieldError failure={failure} field="email" />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="share-role">{t('role')}</Label>
                      <Select value={String(role)} onValueChange={(v) => setRole(Number(v))}>
                        <SelectTrigger id="share-role" className="cursor-pointer">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ROLE_OPTIONS.map((option) => (
                            <SelectItem
                              key={option.value}
                              value={String(option.value)}
                              className="cursor-pointer"
                            >
                              {roles(option.name)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <p className="text-sm text-muted-foreground">
                        {hints(valueName(MemberRoleSchema, role))}
                      </p>
                    </div>

                    <DialogFooter>
                      <Button
                        type="button"
                        variant="outline"
                        className="press"
                        onClick={() => setShareOpen(false)}
                      >
                        {app('cancel')}
                      </Button>
                      <SubmitButton pendingLabel={app('saving')}>{t('shareSubmit')}</SubmitButton>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
            </div>
          )}
        </CardHeader>

        <CardContent className="p-0">
          <ul className="divide-y divide-border border-t border-border">
            {members.map((member) => {
              const isOwnerRow = member.role === MemberRole.OWNER
              const isSelf = member.userId === viewerId
              return (
                <li key={member.userId} className="flex items-center gap-3 px-6 py-3">
                  <Avatar className="size-8 shrink-0">
                    {member.avatarUrl && <AvatarImage src={member.avatarUrl} alt="" />}
                    <AvatarFallback className="text-xs">
                      {initials(member.displayName)}
                    </AvatarFallback>
                  </Avatar>

                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {member.displayName}
                      {isSelf && (
                        <span className="text-muted-foreground"> · {t('memberIsYou')}</span>
                      )}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">{member.email}</p>
                    {member.invitedBy && (
                      <p className="truncate text-xs text-muted-foreground">
                        {t('invitedBy', { name: member.invitedBy })}
                      </p>
                    )}
                  </div>

                  {/* The owner's role is fixed: a list without one could not be shared
                      or deleted, and the database enforces exactly one. */}
                  {isOwnerRow || !canAdminister ? (
                    <Badge variant="outline" className="shrink-0 rounded-full bg-transparent">
                      {roles(valueName(MemberRoleSchema, member.role))}
                    </Badge>
                  ) : (
                    <Select
                      value={String(member.role)}
                      disabled={pending}
                      onValueChange={(value) =>
                        startTransition(async () => {
                          const outcome = await updateMemberRole(
                            listId,
                            member.userId,
                            Number(value) as MemberRole,
                          )
                          if (outcome.ok) toast.success(t('changeRoleDone'))
                        })
                      }
                    >
                      <SelectTrigger className="w-36 shrink-0 cursor-pointer" size="sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ROLE_OPTIONS.map((option) => (
                          <SelectItem
                            key={option.value}
                            value={String(option.value)}
                            className="cursor-pointer"
                          >
                            {roles(option.name)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}

                  {canAdminister && !isOwnerRow && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={t('removeMember')}
                      className="press-icon shrink-0 text-muted-foreground hover:text-destructive"
                      onClick={() => setRemoving(member)}
                    >
                      <FontAwesomeIcon icon={faUserXmark} className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </li>
              )
            })}
          </ul>
        </CardContent>
      </Card>

      <AlertDialog open={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('removeMember')}</AlertDialogTitle>
            <AlertDialogDescription>
              {removing?.displayName} · {removing?.email}
            </AlertDialogDescription>
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
                  const outcome = await removeMember(listId, target.userId)
                  if (outcome.ok) toast.success(t('removeMemberDone'))
                  setRemoving(null)
                })
              }}
            >
              {t('removeMember')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
