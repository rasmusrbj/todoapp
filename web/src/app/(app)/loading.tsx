import { Skeleton } from '@/components/ui/skeleton'

/**
 * The loading state for every signed-in route.
 *
 * A skeleton in the shape of a page header plus a few rows, rather than a spinner: the
 * layout does not jump when the real content lands, which is the whole point of showing
 * something. It matches the common case — a title, a strip of counters, and a list.
 *
 * The shell around it is already rendered, so the sidebar and top bar stay interactive
 * while this is on screen.
 */
export default function Loading() {
  return (
    <div aria-busy="true" aria-live="polite">
      <div className="mb-8 space-y-2">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-5 w-72" />
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-[86px] rounded-xl" />
        ))}
      </div>

      <div className="space-y-4">
        <Skeleton className="h-16 rounded-xl" />
        <div className="overflow-hidden rounded-xl border border-border">
          {Array.from({ length: 5 }, (_, index) => (
            <div
              key={index}
              className="flex items-start gap-3.5 border-b border-border px-5 py-4 last:border-b-0"
            >
              <Skeleton className="size-5 shrink-0 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
