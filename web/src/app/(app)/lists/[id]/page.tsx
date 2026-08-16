import { faSquareCheck } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { getTranslations } from 'next-intl/server'

import { ActivityFeed } from '@/components/activity-feed'
import { ColorDot, VisibilityBadge } from '@/components/enum-badge'
import { LabelManager } from '@/components/label-manager'
import { ListActions } from '@/components/list-actions'
import { MemberManager } from '@/components/member-manager'
import { PageHeader, SectionHeader } from '@/components/page-header'
import { QuickAdd } from '@/components/quick-add'
import { TaskDialog } from '@/components/task-dialog'
import { TaskRow } from '@/components/task-row'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SortDirection, TaskSortField } from '@/gen/todo/v1/enums_pb'
import { listClient, taskClient, userClient } from '@/lib/api'
import { canWrite, isOwner } from '@/lib/enums'
import { isUnauthenticated } from '@/lib/errors'

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>
}): Promise<Metadata> {
  const { id } = await params
  try {
    const { list } = await listClient.getList({ id })
    return { title: list?.name }
  } catch {
    return { title: (await getTranslations('lists'))('title') }
  }
}

export default async function ListDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const [t, tasksT] = await Promise.all([getTranslations('lists'), getTranslations('tasks')])

  let list
  try {
    const response = await listClient.getList({ id })
    list = response.list
  } catch (error) {
    if (isUnauthenticated(error)) throw error
    // A list that does not exist and one the reader may not see are the same thing
    // here, exactly as the API reports them.
    notFound()
  }
  if (!list) notFound()

  const [tasks, activity, me] = await Promise.all([
    taskClient.listTasks({
      page: { limit: 100 },
      listIds: [id],
      sortField: TaskSortField.POSITION,
      sortDirection: SortDirection.ASC,
    }),
    taskClient.listActivity({ page: { limit: 15 }, listId: id }),
    userClient.getCurrentUser({}),
  ])

  const mayEdit = canWrite(list.viewerRole)
  const mayAdminister = isOwner(list.viewerRole)
  const stats = list.stats

  const dialogList = {
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
  }

  const open = tasks.tasks.filter((task) => !task.completedAt)
  const done = tasks.tasks.filter((task) => task.completedAt)

  return (
    <>
      <PageHeader
        title={list.name}
        description={list.description || t('ownedBy', { name: list.owner?.displayName ?? '' })}
        action={
          <>
            {mayEdit && <TaskDialog lists={[dialogList]} defaultListId={list.id} />}
            <ListActions
              list={{
                id: list.id,
                name: list.name,
                description: list.description,
                color: list.color,
                visibility: list.visibility,
                archived: list.archived,
              }}
              viewerId={me.user?.id ?? ''}
              canEdit={mayEdit}
              canAdminister={mayAdminister}
              isMember={list.viewerRole !== 0}
            />
          </>
        }
      />

      {/* The list at a glance: how far along, and anything that needs attention. */}
      <div className="mb-8 rounded-xl border border-border bg-card p-6">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
          <div className="flex items-center gap-2.5">
            <ColorDot color={list.color} className="size-3" />
            <VisibilityBadge visibility={list.visibility} />
          </div>
          {(stats?.overdueTaskCount ?? 0) > 0 && (
            <span className="rounded-full border border-red-200 bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700 tabular-nums dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
              {t('overdueCount', { count: stats?.overdueTaskCount ?? 0 })}
            </span>
          )}
        </div>

        <div className="mt-5 space-y-2.5">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-3xl font-semibold leading-none tabular-nums">
              {stats?.completionPercent ?? 0}%
            </span>
            <span className="text-sm text-muted-foreground tabular-nums">
              {t('openTasksOf', {
                open: stats?.openTaskCount ?? 0,
                total: stats?.totalTaskCount ?? 0,
              })}
            </span>
          </div>
          <Progress value={stats?.completionPercent ?? 0} className="h-2" />
        </div>
      </div>

      {mayEdit && (
        <div className="mb-8">
          <QuickAdd
            lists={[dialogList]}
            defaultListId={list.id}
            user={
              me.user
                ? { displayName: me.user.displayName, avatarUrl: me.user.avatarUrl }
                : undefined
            }
          />
        </div>
      )}

      <Tabs defaultValue="tasks">
        <TabsList className="h-10 rounded-xl p-1">
          <TabsTrigger value="tasks" className="press rounded-lg px-4">
            {tasksT('title')}
          </TabsTrigger>
          <TabsTrigger value="members" className="press rounded-lg px-4">
            {t('members')}
          </TabsTrigger>
          <TabsTrigger value="labels" className="press rounded-lg px-4">
            {t('labels')}
          </TabsTrigger>
          <TabsTrigger value="activity" className="press rounded-lg px-4">
            {(await getTranslations('activity'))('title')}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="tasks" className="mt-6 space-y-8">
          {tasks.tasks.length === 0 ? (
            <div className="flex flex-col items-center gap-5 rounded-xl border border-dashed border-border bg-card px-6 py-20 text-center">
              <span className="flex size-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
                <FontAwesomeIcon icon={faSquareCheck} className="h-6 w-6" />
              </span>
              <p className="text-lg font-semibold tracking-tight">{tasksT('empty')}</p>
              {mayEdit && <TaskDialog lists={[dialogList]} defaultListId={list.id} />}
            </div>
          ) : (
            <>
              <ul className="overflow-hidden rounded-xl border border-border bg-card">
                {open.map((task) => (
                  <TaskRow key={task.id} task={task} showList={false} canEdit={mayEdit} />
                ))}
              </ul>

              {done.length > 0 && (
                <div>
                  <SectionHeader
                    title={(await getTranslations('enums.taskStatus'))('TASK_STATUS_DONE')}
                    count={done.length}
                  />
                  <ul className="overflow-hidden rounded-xl border border-border bg-card">
                    {done.map((task) => (
                      <TaskRow key={task.id} task={task} showList={false} canEdit={mayEdit} />
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </TabsContent>

        <TabsContent value="members" className="mt-6">
          <MemberManager
            listId={list.id}
            listName={list.name}
            members={list.members.map((member) => ({
              userId: member.user?.id ?? '',
              displayName: member.user?.displayName ?? '',
              email: member.user?.email ?? '',
              avatarUrl: member.user?.avatarUrl ?? '',
              role: member.role,
              invitedBy: member.invitedBy?.displayName,
            }))}
            viewerId={me.user?.id ?? ''}
            canAdminister={mayAdminister}
          />
        </TabsContent>

        <TabsContent value="labels" className="mt-6">
          <LabelManager
            listId={list.id}
            labels={list.labels.map((label) => ({
              id: label.id,
              name: label.name,
              color: label.color,
            }))}
            canEdit={mayEdit}
          />
        </TabsContent>

        <TabsContent value="activity" className="mt-6">
          <ActivityFeed
            activities={activity.activities}
            emptyMessage={(await getTranslations('activity'))('empty')}
            showList={false}
          />
        </TabsContent>
      </Tabs>
    </>
  )
}
