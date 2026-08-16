'use client'

import { faCircleCheck } from '@fortawesome/pro-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useActionState, useEffect } from 'react'
import { toast } from 'sonner'

import { updateProfile } from '@/app/actions/users'
import { FieldError, FormError } from '@/components/form-message'
import { SubmitButton } from '@/components/submit-button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { UserRoleSchema, UserStatusSchema } from '@/gen/todo/v1/enums_pb'
import { type UserRole, UserRole as Roles, type UserStatus, valueName } from '@/lib/enums'
import type { ActionResult } from '@/lib/errors'

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  return ((words[0]?.[0] ?? '') + (words.length > 1 ? (words.at(-1)?.[0] ?? '') : '')).toUpperCase()
}

export function ProfileForm({
  user,
}: {
  user: {
    id: string
    displayName: string
    email: string
    bio: string
    avatarUrl: string
    emailVerified: boolean
    role: UserRole
    status: UserStatus
  }
}) {
  const t = useTranslations('settings')
  const app = useTranslations('app')
  const auth = useTranslations('auth')
  const roles = useTranslations('enums.userRole')
  const statuses = useTranslations('enums.userStatus')
  const [result, action] = useActionState<ActionResult | null, FormData>(updateProfile, null)
  const failure = result && !result.ok ? result : null

  useEffect(() => {
    if (result?.ok) toast.success(t('saved'))
  }, [result, t])

  return (
    <Card className="rounded-xl">
      <CardHeader>
        <CardTitle className="text-sm">{t('profile')}</CardTitle>
        <CardDescription>{t('profileSubtitle')}</CardDescription>
      </CardHeader>

      <CardContent>
        <form action={action} className="space-y-4" noValidate>
          <input type="hidden" name="id" value={user.id} />
          {failure && !failure.field && <FormError failure={failure} />}

          <div className="flex items-center gap-4">
            <Avatar className="size-14">
              {user.avatarUrl && <AvatarImage src={user.avatarUrl} alt="" />}
              <AvatarFallback>{initials(user.displayName)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 space-y-1.5">
              <p className="truncate text-sm font-medium">{user.email}</p>
              <div className="flex flex-wrap gap-1.5">
                <Badge variant="outline" className="rounded-full bg-transparent">
                  {roles(valueName(UserRoleSchema, user.role))}
                </Badge>
                <Badge variant="outline" className="rounded-full bg-transparent">
                  {statuses(valueName(UserStatusSchema, user.status))}
                </Badge>
                {user.emailVerified && (
                  <Badge
                    variant="outline"
                    className="gap-1 rounded-full border-emerald-200 bg-transparent text-emerald-700 dark:border-emerald-900 dark:text-emerald-300"
                  >
                    <FontAwesomeIcon icon={faCircleCheck} className="h-3 w-3" />
                    {auth('verifyDone')}
                  </Badge>
                )}
                {user.role === Roles.ADMIN && null}
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="displayName">{auth('displayName')}</Label>
            <Input
              id="displayName"
              name="displayName"
              defaultValue={user.displayName}
              required
              aria-invalid={failure?.field === 'displayName'}
            />
            <FieldError failure={failure} field="displayName" />
          </div>

          <div className="space-y-2">
            <Label htmlFor="bio">
              {t('bio')}{' '}
              <span className="font-normal text-muted-foreground">({app('optional')})</span>
            </Label>
            <Textarea id="bio" name="bio" defaultValue={user.bio} rows={2} placeholder={t('bioPlaceholder')} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="avatarUrl">
              {t('avatarUrl')}{' '}
              <span className="font-normal text-muted-foreground">({app('optional')})</span>
            </Label>
            <Input
              id="avatarUrl"
              name="avatarUrl"
              type="url"
              inputMode="url"
              defaultValue={user.avatarUrl}
              placeholder="https://…"
              aria-invalid={failure?.field === 'avatarUrl'}
            />
            <FieldError failure={failure} field="avatarUrl" />
          </div>

          <div className="flex justify-end">
            <SubmitButton pendingLabel={app('saving')}>{app('save')}</SubmitButton>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
