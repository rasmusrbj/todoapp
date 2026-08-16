/**
 * The heading block every screen opens with.
 *
 * A confident title, one line of context, and room on the right for the primary
 * action. The title carries the screen on its own, so it gets the largest type step
 * in the app — everything below it can then stay at `text-sm` without the page
 * reading flat.
 */
export function PageHeader({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: React.ReactNode
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 space-y-1">
        <h1 className="title-page">{title}</h1>
        {description && (
          <p className="text-[15px] text-muted-foreground text-pretty">{description}</p>
        )}
      </div>
      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </div>
  )
}

/**
 * A heading for a block within a page, with an optional count and trailing action.
 *
 * The count sits next to the label rather than in a badge: at these sizes a pill adds
 * a box without adding information.
 */
export function SectionHeader({
  title,
  count,
  action,
  className,
}: {
  title: string
  count?: number
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div className={`mb-4 flex items-center justify-between gap-4 ${className ?? ''}`}>
      <h2 className="title-section">
        {title}
        {count !== undefined && count > 0 && (
          <span className="ml-2 font-normal text-muted-foreground tabular-nums">{count}</span>
        )}
      </h2>
      {action}
    </div>
  )
}
