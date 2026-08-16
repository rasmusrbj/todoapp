import type { Metadata } from 'next'
import { getLocale, getTranslations } from 'next-intl/server'

import { PageHeader } from '@/components/page-header'
import { UserCreateDialog } from '@/components/admin/user-create-dialog'
import { UserTable } from '@/components/admin/user-table'
import { SortDirection, UserSortField } from '@/gen/todo/v1/enums_pb'
import type { Locale } from '@/i18n/config'
import { userClient } from '@/lib/api'
import { formatDateTime, toDate } from '@/lib/format'

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('admin')
  return { title: t('title') }
}

/**
 * The admin account listing.
 *
 * Not defended in the UI: the layout only shows the link to an admin, and every RPC
 * on this page requires the role server-side. A non-admin who typed the URL gets a
 * `PERMISSION_DENIED` from the API, which is the only check that matters.
 */
export default async function AdminUsersPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>
}) {
  const { q } = await searchParams
  const [t, locale] = await Promise.all([getTranslations('admin'), getLocale()])

  const [response, me] = await Promise.all([
    userClient.listUsers({
      page: { limit: 100 },
      query: q ?? '',
      sortField: UserSortField.CREATED_AT,
      sortDirection: SortDirection.DESC,
    }),
    userClient.getCurrentUser({}),
  ])

  return (
    <>
      <PageHeader title={t('title')} description={t('subtitle')} action={<UserCreateDialog />} />

      <UserTable
        users={response.users.map((user) => ({
          id: user.id,
          displayName: user.displayName,
          email: user.email,
          avatarUrl: user.avatarUrl,
          role: user.role,
          status: user.status,
          emailVerified: user.emailVerified,
          ownedListCount: user.stats?.ownedListCount ?? 0,
          openTaskCount: user.stats?.openTaskCount ?? 0,
          overdueTaskCount: user.stats?.overdueTaskCount ?? 0,
          lastSeenAt: user.lastSeenAt
            ? formatDateTime(toDate(user.lastSeenAt), locale as Locale)
            : '',
        }))}
        viewerId={me.user?.id ?? ''}
      />
    </>
  )
}
