import {
  faCalendarCheck,
  faCircleCheck,
  faClipboardList,
  faTriangleExclamation,
} from '@fortawesome/pro-regular-svg-icons'
import type { Metadata } from 'next'
import Link from 'next/link'
import { getTranslations } from 'next-intl/server'
import { timestampFromDate } from '@bufbuild/protobuf/wkt'

import { ActivityFeed } from '@/components/activity-feed'
import { ListCard } from '@/components/list-card'
import { PageHeader, SectionHeader } from '@/components/page-header'
import { QuickAdd } from '@/components/quick-add'
import { StatCard } from '@/components/stat-card'
import { TaskRow } from '@/components/task-row'
import { Button } from '@/components/ui/button'
import { SortDirection, TaskSortField } from '@/gen/todo/v1/enums_pb'
import { listClient, taskClient, userClient } from '@/lib/api'
import { canWrite, openStatuses } from '@/lib/enums'

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('nav')
  return { title: t('dashboard') }
}

/** Midnight tonight, in the reader's own timezone. */
function endOfToday(): Date {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59)
}

/** Midnight this morning, in the reader's own timezone. */
function startOfToday(): Date {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0)
}

export default async function DashboardPage() {
  const [t, nav, lists_] = await Promise.all([
    getTranslations('dashboard'),
    getTranslations('nav'),
    getTranslations('lists'),
  ])

  // Five independent reads, issued together rather than in sequence: the page is only
  // as slow as its slowest query instead of the sum of all five.
  const [me, lists, dueToday, overdue, activity] = await Promise.all([
    userClient.getCurrentUser({}),
    listClient.listLists({ page: { limit: 6 }, sortField: 1, sortDirection: SortDirection.ASC }),
    taskClient.listTasks({
      page: { limit: 5 },
      statuses: [...openStatuses],
      // Bounded at both ends: without the lower bound "due today" also matches
      // everything overdue, and the same task turns up in both columns below.
      dueAfter: timestampFromDate(startOfToday()),
      dueBefore: timestampFromDate(endOfToday()),
      sortField: TaskSortField.DUE_AT,
      sortDirection: SortDirection.ASC,
    }),
    taskClient.listTasks({
      page: { limit: 5 },
      overdueOnly: true,
      sortField: TaskSortField.DUE_AT,
      sortDirection: SortDirection.ASC,
    }),
    taskClient.listActivity({ page: { limit: 6 } }),
  ])

  const user = me.user
  const stats = user?.stats
  const firstName = user?.displayName.split(' ')[0] ?? ''
  const writableLists = lists.lists.filter((list) => !list.archived && canWrite(list.viewerRole))

  return (
    <>
      <PageHeader title={t('greeting', { name: firstName })} description={t('subtitle')} />

      {/* The shape of the day in four numbers, before anything asks to be read. */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard
          label={t('openTasks')}
          value={stats?.openTaskCount ?? 0}
          icon={faClipboardList}
          href="/tasks?filter=open"
        />
        <StatCard
          label={t('dueToday')}
          value={dueToday.page?.totalCount ?? 0}
          icon={faCalendarCheck}
          href="/tasks"
        />
        <StatCard
          label={t('overdue')}
          value={stats?.overdueTaskCount ?? 0}
          icon={faTriangleExclamation}
          href="/tasks?filter=overdue"
          tone={(stats?.overdueTaskCount ?? 0) > 0 ? 'alert' : 'neutral'}
        />
        <StatCard
          label={t('completed')}
          value={stats?.completedTaskCount ?? 0}
          icon={faCircleCheck}
          href="/tasks?filter=done"
          tone="positive"
        />
      </div>

      {writableLists.length > 0 && user && (
        <div className="mb-8">
          <QuickAdd
            lists={writableLists.map((list) => ({
              id: list.id,
              name: list.name,
              color: list.color,
            }))}
            user={{ displayName: user.displayName, avatarUrl: user.avatarUrl }}
          />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <SectionHeader
            title={t('dueToday')}
            count={dueToday.page?.totalCount}
            action={
              <Button asChild variant="ghost" size="sm" className="press -mr-2">
                <Link href="/tasks">{t('viewAll')}</Link>
              </Button>
            }
          />
          {dueToday.tasks.length === 0 ? (
            <p className="rounded-xl border border-border bg-card px-5 py-8 text-center text-sm text-muted-foreground">
              {t('nothingDueToday')}
            </p>
          ) : (
            <ul className="overflow-hidden rounded-xl border border-border bg-card">
              {dueToday.tasks.map((task) => (
                <TaskRow key={task.id} task={task} />
              ))}
            </ul>
          )}
        </section>

        <section>
          <SectionHeader
            title={t('overdue')}
            count={overdue.page?.totalCount}
            action={
              <Button asChild variant="ghost" size="sm" className="press -mr-2">
                <Link href="/tasks?filter=overdue">{t('viewAll')}</Link>
              </Button>
            }
          />
          {overdue.tasks.length === 0 ? (
            <p className="rounded-xl border border-border bg-card px-5 py-8 text-center text-sm text-muted-foreground">
              {t('nothingOverdue')}
            </p>
          ) : (
            <ul className="overflow-hidden rounded-xl border border-border bg-card">
              {overdue.tasks.map((task) => (
                <TaskRow key={task.id} task={task} />
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="mt-10">
        <SectionHeader
          title={t('yourLists')}
          count={lists.page?.totalCount}
          action={
            <Button asChild variant="ghost" size="sm" className="press -mr-2">
              <Link href="/lists">{nav('lists')}</Link>
            </Button>
          }
        />
        {lists.lists.length === 0 ? (
          <p className="rounded-xl border border-border bg-card px-5 py-8 text-center text-sm text-muted-foreground">
            {lists_('empty')}
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {lists.lists.map((list) => (
              <ListCard key={list.id} list={list} />
            ))}
          </div>
        )}
      </section>

      <section className="mt-10">
        <SectionHeader
          title={t('recentActivity')}
          action={
            <Button asChild variant="ghost" size="sm" className="press -mr-2">
              <Link href="/activity">{t('viewAll')}</Link>
            </Button>
          }
        />
        <ActivityFeed activities={activity.activities} emptyMessage={t('noActivity')} />
      </section>
    </>
  )
}
