import { faSquareCheck } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import type { Metadata } from 'next'
import { getTranslations } from 'next-intl/server'

import { PageHeader } from '@/components/page-header'
import { StatusCounts, TaskFilters } from '@/components/task-filters'
import { TaskDialog } from '@/components/task-dialog'
import { TaskRow } from '@/components/task-row'
import { TaskSelectionProvider } from '@/components/task-selection'
import { SortDirection, TaskStatusSchema } from '@/gen/todo/v1/enums_pb'
import { listClient, taskClient, userClient } from '@/lib/api'
import { canWrite, openStatuses, realValues, TaskStatus, valueName } from '@/lib/enums'

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('tasks')
  return { title: t('title') }
}

export default async function TasksPage({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string
    filter?: string
    mine?: string
    unassigned?: string
    sort?: string
    list?: string
  }>
}) {
  const params = await searchParams
  const [t, statusLabels] = await Promise.all([
    getTranslations('tasks'),
    getTranslations('enums.taskStatus'),
  ])

  const me = await userClient.getCurrentUser({})

  // The filter chips map onto API fields rather than being interpreted client-side, so
  // the server does the work and pagination stays correct.
  const statuses =
    params.filter === 'open'
      ? [...openStatuses]
      : params.filter === 'done'
        ? [TaskStatus.DONE]
        : []

  const [response, lists] = await Promise.all([
    taskClient.listTasks({
      page: { limit: 50 },
      query: params.q ?? '',
      statuses,
      overdueOnly: params.filter === 'overdue',
      assigneeIds: params.mine === '1' && me.user ? [me.user.id] : [],
      unassignedOnly: params.unassigned === '1',
      listIds: params.list ? [params.list] : [],
      sortField: Number(params.sort) || 1,
      sortDirection: params.sort === '4' ? SortDirection.ASC : SortDirection.DESC,
    }),
    listClient.listLists({ page: { limit: 60 } }),
  ])

  const writableLists = lists.lists
    .filter((list) => !list.archived && canWrite(list.viewerRole))
    .map((list) => ({
      id: list.id,
      name: list.name,
      color: list.color,
      members: list.members
        .filter((member) => canWrite(member.role))
        .map((member) => ({
          id: member.user?.id ?? '',
          displayName: member.user?.displayName ?? '',
        })),
      labels: list.labels.map((label) => ({
        id: label.id,
        name: label.name,
        color: label.color,
      })),
    }))

  // Localized status names, keyed by the PostgreSQL label the API returns in
  // `statusCounts` — derived from the descriptor, never hand-written.
  const countLabels = Object.fromEntries(
    realValues(TaskStatusSchema).map((value) => {
      const name = valueName(TaskStatusSchema, value)
      return [name.replace('TASK_STATUS_', '').toLowerCase(), statusLabels(name)]
    }),
  )

  const filtered = Boolean(params.q || params.filter || params.mine || params.unassigned)

  return (
    <>
      <PageHeader
        title={t('title')}
        description={t('subtitle')}
        action={writableLists.length > 0 ? <TaskDialog lists={writableLists} /> : undefined}
      />

      <TaskFilters className="mb-4" />

      {Object.keys(response.statusCounts).length > 0 && (
        <div className="mb-4">
          <StatusCounts counts={response.statusCounts} labels={countLabels} />
        </div>
      )}

      {response.tasks.length === 0 ? (
        <div className="flex flex-col items-center gap-5 rounded-xl border border-dashed border-border bg-card px-6 py-20 text-center">
          <span className="flex size-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <FontAwesomeIcon icon={faSquareCheck} className="h-6 w-6" />
          </span>
          <p className="text-lg font-semibold tracking-tight">
            {filtered ? t('emptyFiltered') : t('empty')}
          </p>
          {!filtered && writableLists.length > 0 && <TaskDialog lists={writableLists} />}
        </div>
      ) : (
        <TaskSelectionProvider>
          <ul className="overflow-hidden rounded-xl border border-border bg-card">
            {response.tasks.map((task) => (
              <TaskRow key={task.id} task={task} selectable />
            ))}
          </ul>
        </TaskSelectionProvider>
      )}

      {response.page?.hasMore && (
        <p className="mt-4 text-center text-sm text-muted-foreground">
          {t('title')}: {response.page.totalCount}
        </p>
      )}
    </>
  )
}
