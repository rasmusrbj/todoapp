'use client'

import {
  faChartSimple,
  faClockRotateLeft,
  faListUl,
  faSquareCheck,
  faUsers,
} from '@fortawesome/pro-solid-svg-icons'
import {
  faChartSimple as faChartSimpleLight,
  faClockRotateLeft as faClockRotateLeftLight,
  faListUl as faListUlLight,
  faSquareCheck as faSquareCheckLight,
  faUsers as faUsersLight,
} from '@fortawesome/pro-light-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useTranslations } from 'next-intl'

import { cn } from '@/lib/utils'

// Solid for the active route, light for the rest — the house sidebar pattern.
const ITEMS = [
  { href: '/dashboard', key: 'dashboard', active: faChartSimple, idle: faChartSimpleLight },
  { href: '/lists', key: 'lists', active: faListUl, idle: faListUlLight },
  { href: '/tasks', key: 'tasks', active: faSquareCheck, idle: faSquareCheckLight },
  {
    href: '/activity',
    key: 'activity',
    active: faClockRotateLeft,
    idle: faClockRotateLeftLight,
  },
] as const

const ADMIN_ITEM = {
  href: '/admin/users',
  key: 'users',
  active: faUsers,
  idle: faUsersLight,
} as const

/** `/lists/abc` lights up `/lists`, but `/dashboard` must not match `/`. */
function useIsActive() {
  const pathname = usePathname()
  return (href: string) => pathname === href || pathname.startsWith(`${href}/`)
}

/** The sidebar navigation, from `lg` up. */
export function NavLinks({ isAdmin }: { isAdmin: boolean }) {
  const t = useTranslations('nav')
  const isActive = useIsActive()
  const items = isAdmin ? [...ITEMS, ADMIN_ITEM] : ITEMS

  return (
    <>
      {items.map((item) => {
        const active = isActive(item.href)
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? 'page' : undefined}
            className={cn(
              // Roomier than a menu row needs to be, because these are the app's
              // primary targets and 40px is the difference on a laptop trackpad.
              'press flex h-10 w-full items-center gap-3 rounded-xl px-3 text-[15px] font-medium transition-colors duration-100',
              active
                ? 'bg-accent text-accent-foreground'
                : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground',
            )}
          >
            <FontAwesomeIcon
              icon={active ? item.active : item.idle}
              className={cn('h-4 w-4 shrink-0', active && 'text-foreground')}
            />
            {t(item.key)}
          </Link>
        )
      })}
    </>
  )
}

/**
 * The bottom tab bar, below `lg`.
 *
 * Icon over label, evenly divided, with `pb-[env(safe-area-inset-bottom)]` so the row
 * clears the home indicator on a modern phone instead of sitting under it.
 */
export function BottomNav({ isAdmin }: { isAdmin: boolean }) {
  const t = useTranslations('nav')
  const isActive = useIsActive()
  const items = isAdmin ? [...ITEMS, ADMIN_ITEM] : ITEMS

  return (
    <nav
      aria-label={t('dashboard')}
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-sm lg:hidden"
    >
      <div className="flex items-stretch">
        {items.map((item) => {
          const active = isActive(item.href)
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'press flex flex-1 flex-col items-center justify-center gap-1 py-2.5 text-[11px] font-medium transition-colors duration-100',
                active ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <FontAwesomeIcon
                icon={active ? item.active : item.idle}
                className="h-[18px] w-[18px]"
              />
              <span className="max-w-full truncate px-0.5">{t(item.key)}</span>
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
