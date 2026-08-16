'use client'

import { faDesktop, faMobile, faTerminal } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useTransition } from 'react'
import { toast } from 'sonner'

import { revokeSession } from '@/app/actions/auth'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SessionClientSchema } from '@/gen/todo/v1/enums_pb'
import { SessionClient, valueName } from '@/lib/enums'

const ICONS: Record<number, typeof faDesktop> = {
  [SessionClient.UNSPECIFIED]: faDesktop,
  [SessionClient.WEB]: faDesktop,
  [SessionClient.MOBILE]: faMobile,
  [SessionClient.CLI]: faTerminal,
}

type Session = {
  id: string
  client: number
  userAgent: string
  ipAddress: string
  isCurrent: boolean
  lastUsedAt: string
  expiresAt: string
}

/** Where this account is signed in, with a way to close any of them. */
export function SessionList({ sessions }: { sessions: Session[] }) {
  const t = useTranslations('auth')
  const clients = useTranslations('enums.sessionClient')
  const [pending, startTransition] = useTransition()

  return (
    <Card className="rounded-xl py-0">
      <CardHeader className="border-b border-border py-4">
        <CardTitle className="text-sm">{t('sessions')}</CardTitle>
        <CardDescription>{t('sessionsSubtitle')}</CardDescription>
      </CardHeader>

      <CardContent className="p-0">
        <ul className="divide-y divide-border">
          {sessions.map((session) => (
            <li key={session.id} className="flex items-center gap-3 px-6 py-3">
              <FontAwesomeIcon
                icon={ICONS[session.client] ?? faDesktop}
                className="h-4 w-4 shrink-0 text-muted-foreground"
              />

              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-medium">
                    {clients(valueName(SessionClientSchema, session.client))}
                  </span>
                  {session.isCurrent && (
                    <Badge variant="outline" className="rounded-full bg-transparent">
                      {t('sessionCurrent')}
                    </Badge>
                  )}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {session.userAgent || '—'}
                  {session.ipAddress && ` · ${session.ipAddress}`}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t('sessionLastUsed')}: {session.lastUsedAt} · {t('sessionExpires')}:{' '}
                  {session.expiresAt}
                </p>
              </div>

              <Button
                variant="outline"
                size="sm"
                disabled={pending}
                className="press shrink-0"
                onClick={() =>
                  startTransition(async () => {
                    const result = await revokeSession(session.id)
                    if (result.ok) toast.success(t('revokeSessionDone'))
                  })
                }
              >
                {t('revokeSession')}
              </Button>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
