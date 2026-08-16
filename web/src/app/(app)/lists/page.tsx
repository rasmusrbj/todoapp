import { faBoxArchive, faListUl } from '@fortawesome/pro-regular-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import type { Metadata } from 'next'
import Link from 'next/link'
import { getTranslations } from 'next-intl/server'

import { ListCard } from '@/components/list-card'
import { ListDialog } from '@/components/list-dialog'
import { ListReorder } from '@/components/list-reorder'
import { PageHeader } from '@/components/page-header'
import { Button } from '@/components/ui/button'
import { ListSortField, SortDirection } from '@/gen/todo/v1/enums_pb'
import { listClient } from '@/lib/api'
import { isOwner } from '@/lib/enums'

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('lists')
  return { title: t('title') }
}

export default async function ListsPage({
  searchParams,
}: {
  searchParams: Promise<{ archived?: string; q?: string }>
}) {
  const { archived, q } = await searchParams
  const showArchived = archived === '1'
  const t = await getTranslations('lists')

  const response = await listClient.listLists({
    page: { limit: 60 },
    query: q ?? '',
    includeArchived: showArchived,
    sortField: ListSortField.POSITION,
    sortDirection: SortDirection.ASC,
  })

  // `ReorderLists` only repositions rows the caller owns, so only those are offered.
  const ownedLists = response.lists.filter((list) => isOwner(list.viewerRole))

  return (
    <>
      <PageHeader
        title={t('title')}
        description={t('subtitle')}
        action={
          <>
            {/* Reordering applies to the lists you own, which is what the API allows. */}
            <ListReorder
              lists={ownedLists.map((list) => ({
                id: list.id,
                name: list.name,
                color: list.color,
              }))}
            />
            <Button asChild variant="outline" size="sm" className="press">
              <Link href={showArchived ? '/lists' : '/lists?archived=1'}>
                <FontAwesomeIcon icon={faBoxArchive} className="h-3.5 w-3.5" />
                {showArchived ? t('title') : t('showArchived')}
              </Link>
            </Button>
            <ListDialog />
          </>
        }
      />

      {response.lists.length === 0 ? (
        <div className="flex flex-col items-center gap-5 rounded-xl border border-dashed border-border bg-card px-6 py-20 text-center">
          <span className="flex size-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <FontAwesomeIcon icon={faListUl} className="h-6 w-6" />
          </span>
          <div className="space-y-1.5">
            <p className="text-lg font-semibold tracking-tight">
              {q ? t('emptyFiltered') : t('empty')}
            </p>
            {!q && (
              <p className="text-[15px] text-muted-foreground">{t('createSubtitle')}</p>
            )}
          </div>
          {!q && (
            <ListDialog
              trigger={<Button className="press">{t('emptyAction')}</Button>}
            />
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {response.lists.map((list) => (
            <ListCard key={list.id} list={list} />
          ))}
        </div>
      )}
    </>
  )
}
