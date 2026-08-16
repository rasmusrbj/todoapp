import type { Metadata } from 'next'
import { getTranslations } from 'next-intl/server'

import { ActivityFeed } from '@/components/activity-feed'
import { PageHeader } from '@/components/page-header'
import { taskClient } from '@/lib/api'

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('activity')
  return { title: t('title') }
}

export default async function ActivityPage({
  searchParams,
}: {
  searchParams: Promise<{ list?: string }>
}) {
  const { list } = await searchParams
  const t = await getTranslations('activity')

  const response = await taskClient.listActivity({
    page: { limit: 50 },
    listId: list,
  })

  return (
    <>
      <PageHeader title={t('title')} description={t('subtitle')} />
      <ActivityFeed activities={response.activities} emptyMessage={t('empty')} />
      {response.page?.totalCount ? (
        <p className="mt-4 text-center text-sm text-muted-foreground tabular-nums">
          {response.page.totalCount}
        </p>
      ) : null}
    </>
  )
}
