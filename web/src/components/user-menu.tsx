'use client'

import { faArrowRightFromBracket, faGear, faUser } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { useTransition } from 'react'

import { signOut } from '@/app/actions/auth'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { User } from '@/gen/todo/v1/user_pb'
import { UserRole } from '@/lib/enums'
import { cn } from '@/lib/utils'

/** Initials for the avatar fallback: at most two, from the first and last word. */
function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  const first = words[0]?.[0] ?? ''
  const last = words.length > 1 ? (words[words.length - 1]?.[0] ?? '') : ''
  return (first + last).toUpperCase()
}

export function UserMenu({ user, compact = false }: { user: User; compact?: boolean }) {
  const t = useTranslations('nav')
  const roles = useTranslations('enums.userRole')
  const [pending, startTransition] = useTransition()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(
            'press flex items-center gap-2.5 rounded-md text-left transition-colors duration-100 hover:bg-accent/50',
            compact ? 'p-1' : 'w-full px-2 py-2',
          )}
        >
          <Avatar className="size-8">
            {user.avatarUrl && <AvatarImage src={user.avatarUrl} alt="" />}
            <AvatarFallback className="text-xs">{initials(user.displayName)}</AvatarFallback>
          </Avatar>
          {!compact && (
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{user.displayName}</span>
              <span className="block truncate text-xs text-muted-foreground">{user.email}</span>
            </span>
          )}
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" side={compact ? 'bottom' : 'top'} className="w-60">
        <div className="px-2 py-1.5">
          <p className="truncate text-sm font-medium">{user.displayName}</p>
          <p className="truncate text-xs text-muted-foreground">{user.email}</p>
          {user.role === UserRole.ADMIN && (
            <Badge variant="outline" className="mt-1.5 rounded-full text-xs">
              {roles('USER_ROLE_ADMIN')}
            </Badge>
          )}
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild className="cursor-pointer">
          <Link href="/settings">
            <FontAwesomeIcon icon={faUser} className="h-3.5 w-3.5" />
            {t('profile')}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild className="cursor-pointer">
          <Link href="/settings">
            <FontAwesomeIcon icon={faGear} className="h-3.5 w-3.5" />
            {t('settings')}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          disabled={pending}
          className="cursor-pointer text-destructive focus:text-destructive"
          onClick={() => startTransition(() => void signOut())}
        >
          <FontAwesomeIcon icon={faArrowRightFromBracket} className="h-3.5 w-3.5" />
          {t('signOut')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
