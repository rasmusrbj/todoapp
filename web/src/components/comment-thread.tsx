'use client'

import { faPaperPlane, faPen, faTrash, faXmark } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { useTranslations } from 'next-intl'
import { useActionState, useEffect, useRef, useState, useTransition } from 'react'
import { toast } from 'sonner'

import { createComment, deleteComment, updateComment } from '@/app/actions/tasks'
import { FormError } from '@/components/form-message'
import { SubmitButton } from '@/components/submit-button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { ActionResult } from '@/lib/errors'

type Comment = {
  id: string
  body: string
  edited: boolean
  authorId: string
  authorName: string
  authorAvatar: string
  createdAt: string
}

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  return ((words[0]?.[0] ?? '') + (words.length > 1 ? (words.at(-1)?.[0] ?? '') : '')).toUpperCase()
}

/**
 * The comments on a task.
 *
 * Only the author may edit their own words — not even the list owner, who can delete
 * a comment for moderation but never rewrite it. That is enforced by the API; the UI
 * simply does not offer what would be refused.
 */
export function CommentThread({
  taskId,
  comments,
  viewerId,
  isListOwner,
  canComment,
}: {
  taskId: string
  comments: Comment[]
  viewerId: string
  isListOwner: boolean
  canComment: boolean
}) {
  const t = useTranslations('tasks')
  const app = useTranslations('app')
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [pending, startTransition] = useTransition()
  const [result, action] = useActionState<ActionResult | null, FormData>(createComment, null)
  const formRef = useRef<HTMLFormElement>(null)
  const failure = result && !result.ok ? result : null

  useEffect(() => {
    if (result?.ok) formRef.current?.reset()
  }, [result])

  return (
    <div>
      {comments.length === 0 ? (
        <p className="px-6 py-4 text-sm text-muted-foreground">{t('noComments')}</p>
      ) : (
        <ul className="divide-y divide-border">
          {comments.map((comment) => {
            const isAuthor = comment.authorId === viewerId
            const isEditing = editing === comment.id
            return (
              <li key={comment.id} className="group flex gap-3 px-6 py-4">
                <Avatar className="size-7 shrink-0">
                  {comment.authorAvatar && <AvatarImage src={comment.authorAvatar} alt="" />}
                  <AvatarFallback className="text-[10px]">
                    {initials(comment.authorName)}
                  </AvatarFallback>
                </Avatar>

                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">{comment.authorName}</span> ·{' '}
                    {comment.createdAt}
                    {comment.edited && <span> · {t('commentEdited')}</span>}
                  </p>

                  {isEditing ? (
                    <div className="mt-2 space-y-2">
                      <Textarea
                        value={draft}
                        onChange={(event) => setDraft(event.target.value)}
                        rows={3}
                        autoFocus
                      />
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          disabled={pending || !draft.trim()}
                          className="press"
                          onClick={() =>
                            startTransition(async () => {
                              const outcome = await updateComment(comment.id, taskId, draft)
                              if (outcome.ok) setEditing(null)
                            })
                          }
                        >
                          {app('save')}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="press"
                          onClick={() => setEditing(null)}
                        >
                          <FontAwesomeIcon icon={faXmark} className="h-3.5 w-3.5" />
                          {app('cancel')}
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <p className="mt-1 whitespace-pre-wrap text-sm text-pretty">{comment.body}</p>
                  )}
                </div>

                {!isEditing && (isAuthor || isListOwner) && (
                  <div className="flex shrink-0 gap-1 opacity-0 transition-opacity duration-100 group-hover:opacity-100 focus-within:opacity-100">
                    {isAuthor && (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={app('edit')}
                        className="press-icon text-muted-foreground"
                        onClick={() => {
                          setEditing(comment.id)
                          setDraft(comment.body)
                        }}
                      >
                        <FontAwesomeIcon icon={faPen} className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={app('delete')}
                      disabled={pending}
                      className="press-icon text-muted-foreground hover:text-destructive"
                      onClick={() =>
                        startTransition(async () => {
                          const outcome = await deleteComment(comment.id, taskId)
                          if (outcome.ok) toast.success(t('commentDeleted'))
                        })
                      }
                    >
                      <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {canComment && (
        <form
          ref={formRef}
          action={action}
          className="space-y-2 border-t border-border px-6 py-4"
          noValidate
        >
          <input type="hidden" name="taskId" value={taskId} />
          <Textarea name="body" required rows={2} placeholder={t('commentPlaceholder')} />
          {failure && <FormError failure={failure} />}
          <div className="flex justify-end">
            <SubmitButton size="sm">
              <FontAwesomeIcon icon={faPaperPlane} className="h-3.5 w-3.5" />
              {t('addComment')}
            </SubmitButton>
          </div>
        </form>
      )}
    </div>
  )
}
