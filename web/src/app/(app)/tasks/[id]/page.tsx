import { faClock, faRepeat, faUser } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { getLocale, getTranslations } from 'next-intl/server'

import { ActivityFeed } from '@/components/activity-feed'
import { CommentThread } from '@/components/comment-thread'
import { DueDate } from '@/components/due-date'
import { ColorDot, LabelChip, PriorityBadge, StatusBadge } from '@/components/enum-badge'
import { PageHeader } from '@/components/page-header'
import { StatusToggle } from '@/components/status-toggle'
import { SubtaskList } from '@/components/subtask-list'
import { TaskActions } from '@/components/task-actions'
import { TaskAssignee } from '@/components/task-assignee'
import { TaskLabelPicker } from '@/components/task-label-picker'
import { TaskMove } from '@/components/task-move'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { listClient, taskClient, userClient } from '@/lib/api'
import { canComment, canWrite, RecurrenceFrequency } from '@/lib/enums'
import { isUnauthenticated } from '@/lib/errors'
import type { Locale } from '@/i18n/config'
import {
  formatDateTime,
  formatMinutes,
  toDateInputValue,
  toDate,
  toTimeInputValue,
} from '@/lib/format'

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>
}): Promise<Metadata> {
  const { id } = await params
  try {
    const { task } = await taskClient.getTask({ id })
    return { title: task?.title }
  } catch {
    return { title: (await getTranslations('tasks'))('title') }
  }
}

export default async function TaskDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const [t, app, locale] = await Promise.all([
    getTranslations('tasks'),
    getTranslations('app'),
    getLocale(),
  ])

  let task
  try {
    const response = await taskClient.getTask({ id })
    task = response.task
  } catch (error) {
    if (isUnauthenticated(error)) throw error
    notFound()
  }
  if (!task?.list) notFound()

  // The task carries only a list *reference*, so the full list is needed for the
  // caller's role, its labels, and the people who can be assigned.
  const [listResponse, comments, activity, me, allLists] = await Promise.all([
    listClient.getList({ id: task.list.id }),
    taskClient.listComments({ taskId: id, page: { limit: 50 } }),
    taskClient.listActivity({ page: { limit: 15 }, taskId: id }),
    userClient.getCurrentUser({}),
    listClient.listLists({ page: { limit: 60 } }),
  ])

  const list = listResponse.list
  const mayEdit = list ? canWrite(list.viewerRole) : false
  const mayComment = list ? canComment(list.viewerRole) : false
  const writableLists = allLists.lists
    .filter((candidate) => !candidate.archived && canWrite(candidate.viewerRole))
    .map((candidate) => ({ id: candidate.id, name: candidate.name, color: candidate.color }))
  const repeats =
    task.recurrence !== undefined &&
    task.recurrence.frequency !== RecurrenceFrequency.NONE &&
    task.recurrence.frequency !== RecurrenceFrequency.UNSPECIFIED

  const dueDate = toDate(task.dueAt)

  return (
    <>
      <PageHeader
        title={task.title}
        description={task.description || undefined}
        action={
          <TaskActions
            task={{
              id: task.id,
              listId: task.list.id,
              title: task.title,
              description: task.description,
              status: task.status,
              priority: task.priority,
              assigneeId: task.assignee?.id,
              labelIds: task.labels.map((label) => label.id),
              dueDate: toDateInputValue(dueDate),
              dueTime: task.dueHasTime ? toTimeInputValue(dueDate) : '',
              startsAt: toDateInputValue(toDate(task.startsAt)),
              estimateMinutes: task.estimateMinutes,
              recurrenceFrequency: task.recurrence?.frequency ?? RecurrenceFrequency.NONE,
              recurrenceInterval: task.recurrence?.interval ?? 1,
            }}
            lists={
              list
                ? [
                    {
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
                    },
                  ]
                : []
            }
            canEdit={mayEdit}
            returnTo={`/lists/${task.list.id}`}
          />
        }
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
        <div className="space-y-6">
          <Card className="rounded-xl">
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <StatusToggle taskId={task.id} status={task.status} disabled={!mayEdit} />
                <StatusBadge status={task.status} />
                <PriorityBadge priority={task.priority} />
                <DueDate dueAt={task.dueAt} hasTime={task.dueHasTime} overdue={task.overdue} />
              </div>

              {task.labels.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {task.labels.map((label) => (
                    <LabelChip key={label.id} name={label.name} color={label.color} />
                  ))}
                </div>
              )}

              {mayEdit && list && list.labels.length > 0 && (
                <TaskLabelPicker
                  taskId={task.id}
                  selected={task.labels.map((label) => label.id)}
                  labels={list.labels.map((label) => ({
                    id: label.id,
                    name: label.name,
                    color: label.color,
                  }))}
                />
              )}
            </CardContent>
          </Card>

          <Card className="rounded-xl py-0">
            <CardHeader className="border-b border-border py-4">
              <CardTitle className="text-sm">
                {t('subtasks')}
                {task.subtaskCount > 0 && (
                  <span className="ml-2 font-normal text-muted-foreground tabular-nums">
                    {t('subtaskProgress', {
                      done: task.completedSubtaskCount,
                      total: task.subtaskCount,
                    })}
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <SubtaskList
                taskId={task.id}
                subtasks={task.subtasks.map((subtask) => ({
                  id: subtask.id,
                  title: subtask.title,
                  completed: subtask.completed,
                }))}
                canEdit={mayEdit}
              />
            </CardContent>
          </Card>

          <Card className="rounded-xl py-0">
            <CardHeader className="border-b border-border py-4">
              <CardTitle className="text-sm">
                {t('comments')}
                {task.commentCount > 0 && (
                  <span className="ml-2 font-normal text-muted-foreground tabular-nums">
                    {task.commentCount}
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <CommentThread
                taskId={task.id}
                viewerId={me.user?.id ?? ''}
                isListOwner={list ? list.viewerRole === 1 : false}
                canComment={mayComment}
                comments={comments.comments.map((comment) => ({
                  id: comment.id,
                  body: comment.body,
                  edited: comment.edited,
                  authorId: comment.author?.id ?? '',
                  authorName: comment.author?.displayName ?? '—',
                  authorAvatar: comment.author?.avatarUrl ?? '',
                  createdAt: formatDateTime(toDate(comment.createdAt), locale as Locale),
                }))}
              />
            </CardContent>
          </Card>
        </div>

        {/* The facts pane: everything that is metadata rather than content. */}
        <aside className="space-y-4">
          <Card className="rounded-xl">
            <CardContent className="space-y-4 text-sm">
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-muted-foreground">{t('list')}</p>
                <Link
                  href={`/lists/${task.list.id}`}
                  className="press inline-flex items-center gap-2 font-medium underline-offset-4 hover:underline"
                >
                  <ColorDot color={task.list.color} />
                  {task.list.name}
                </Link>
              </div>

              {mayEdit && writableLists.length > 1 && (
                <TaskMove
                  taskId={task.id}
                  currentListId={task.list.id}
                  lists={writableLists}
                />
              )}

              <Separator />

              <div className="space-y-1.5">
                <p className="text-xs font-medium text-muted-foreground">{t('assignee')}</p>
                <TaskAssignee
                  taskId={task.id}
                  assigneeId={task.assignee?.id}
                  assigneeName={task.assignee?.displayName}
                  viewerId={me.user?.id ?? ''}
                  members={
                    list
                      ? list.members
                          .filter((member) => canWrite(member.role))
                          .map((member) => ({
                            id: member.user?.id ?? '',
                            displayName: member.user?.displayName ?? '',
                          }))
                      : []
                  }
                  canEdit={mayEdit}
                />
              </div>

              {task.estimateMinutes > 0 && (
                <>
                  <Separator />
                  <div className="space-y-1.5">
                    <p className="text-xs font-medium text-muted-foreground">{t('estimate')}</p>
                    <p className="inline-flex items-center gap-2 tabular-nums">
                      <FontAwesomeIcon icon={faClock} className="h-3.5 w-3.5 text-muted-foreground" />
                      {formatMinutes(task.estimateMinutes, locale as Locale)}
                    </p>
                  </div>
                </>
              )}

              {repeats && (
                <>
                  <Separator />
                  <div className="space-y-1.5">
                    <p className="text-xs font-medium text-muted-foreground">{t('repeat')}</p>
                    <p className="inline-flex items-center gap-2">
                      <FontAwesomeIcon icon={faRepeat} className="h-3.5 w-3.5 text-muted-foreground" />
                      {(await getTranslations('enums.recurrence'))(
                        `RECURRENCE_FREQUENCY_${
                          ['UNSPECIFIED', 'NONE', 'DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'][
                            task.recurrence?.frequency ?? 0
                          ]
                        }`,
                      )}
                      {(task.recurrence?.interval ?? 1) > 1 && (
                        <span className="text-muted-foreground tabular-nums">
                          · {t('repeatEvery')} {task.recurrence?.interval}
                        </span>
                      )}
                    </p>
                  </div>
                </>
              )}

              <Separator />

              <div className="space-y-1.5 text-xs text-muted-foreground">
                {task.createdBy && (
                  <p className="inline-flex items-center gap-1.5">
                    <FontAwesomeIcon icon={faUser} className="h-3 w-3" />
                    {t('createdBy', { name: task.createdBy.displayName })}
                  </p>
                )}
                <p>{t('createdAt', { date: formatDateTime(toDate(task.createdAt), locale as Locale) })}</p>
                {task.completedBy && (
                  <p>{t('completedBy', { name: task.completedBy.displayName })}</p>
                )}
              </div>
            </CardContent>
          </Card>

          <div>
            <h2 className="mb-2 text-sm font-semibold">
              {(await getTranslations('activity'))('title')}
            </h2>
            <ActivityFeed
              activities={activity.activities}
              emptyMessage={(await getTranslations('activity'))('empty')}
              showList={false}
            />
          </div>
        </aside>
      </div>

      <p className="sr-only">{app('back')}</p>
    </>
  )
}
