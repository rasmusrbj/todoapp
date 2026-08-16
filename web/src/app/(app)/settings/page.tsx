import type { Metadata } from 'next'
import { redirect } from 'next/navigation'
import { getLocale, getTranslations } from 'next-intl/server'

import { DangerZone } from '@/components/settings/danger-zone'
import { PasswordForm } from '@/components/settings/password-form'
import { PreferencesForm } from '@/components/settings/preferences-form'
import { ProfileForm } from '@/components/settings/profile-form'
import { SessionList } from '@/components/settings/session-list'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { authClient, userClient } from '@/lib/api'
import type { Locale } from '@/i18n/config'
import { formatDateTime, formatLongDate, toDate } from '@/lib/format'

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('settings')
  return { title: t('title') }
}

export default async function SettingsPage() {
  const [t, locale] = await Promise.all([getTranslations('settings'), getLocale()])
  const [me, sessions] = await Promise.all([
    userClient.getCurrentUser({}),
    authClient.listSessions({}),
  ])

  const user = me.user
  if (!user) redirect('/login')

  const stats = [
    { key: 'ownedLists', value: user.stats?.ownedListCount ?? 0 },
    { key: 'sharedLists', value: user.stats?.sharedListCount ?? 0 },
    { key: 'openTasks', value: user.stats?.openTaskCount ?? 0 },
    { key: 'completedTasks', value: user.stats?.completedTaskCount ?? 0 },
    { key: 'overdueTasks', value: user.stats?.overdueTaskCount ?? 0 },
  ] as const

  return (
    <>
      <PageHeader title={t('title')} description={t('subtitle')} />

      <div className="space-y-6">
        <ProfileForm
          user={{
            id: user.id,
            displayName: user.displayName,
            email: user.email,
            bio: user.bio,
            avatarUrl: user.avatarUrl,
            emailVerified: user.emailVerified,
            role: user.role,
            status: user.status,
          }}
        />

        <PreferencesForm
          user={{
            id: user.id,
            locale: user.locale,
            theme: user.theme,
            timeZone: user.timeZone,
          }}
        />

        {/* Numbers, not a chart: five counters do not need axes. */}
        <Card className="rounded-xl">
          <CardHeader>
            <CardTitle className="text-sm">{t('stats')}</CardTitle>
            <CardDescription>
              {t('memberSince', { date: formatLongDate(toDate(user.createdAt), locale as Locale) })}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-5">
              {stats.map((stat) => (
                <div key={stat.key}>
                  <dt className="text-xs text-muted-foreground">{t(stat.key)}</dt>
                  <dd className="mt-1 text-xl font-semibold tabular-nums">{stat.value}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>

        <PasswordForm />

        <SessionList
          sessions={sessions.sessions.map((session) => ({
            id: session.id,
            client: session.client,
            userAgent: session.userAgent,
            ipAddress: session.ipAddress,
            isCurrent: session.isCurrent,
            lastUsedAt: formatDateTime(toDate(session.lastUsedAt), locale as Locale),
            expiresAt: formatDateTime(toDate(session.expiresAt), locale as Locale),
          }))}
        />

        <DangerZone />
      </div>
    </>
  )
}
