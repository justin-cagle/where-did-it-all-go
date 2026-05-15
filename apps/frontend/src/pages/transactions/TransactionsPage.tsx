import { useRef, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { Plus, Inbox, RefreshCw, SlidersHorizontal, X } from 'lucide-react'
import { useListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGet } from '@/api/generated/transactions/transactions'
import { useListAccountsApiV1HouseholdsHouseholdIdAccountsGet } from '@/api/generated/accounts/accounts'
import type { TransactionOut } from '@/api/generated/model/transactionOut'
import { useHousehold } from '@/hooks/use-household'
import { useAuthStore } from '@/store'
import { fmt } from '@/lib/format'
import type { PrivacyMode } from '@/lib/format'
import {
  groupByDate,
  buildVirtualRows,
  txDisplayAmount,
  categoryColor,
  TX_ROW_HEIGHT,
  TX_HEADER_HEIGHT,
} from '@/domain/transactions'
import type { VirtualRow } from '@/domain/transactions'
import { TransactionDetail } from './TransactionDetail'
import { AddTransactionModal } from './AddTransactionModal'
import { DedupQueue } from './DedupQueue'
import { useDedupCount } from './useDedupCount'

type StateFilter = '' | 'pending' | 'posted' | 'reconciled'
type DirFilter = '' | 'debit' | 'credit'

interface Filters {
  dateFrom: string
  dateTo: string
  accountIds: string[]
  state: StateFilter
  direction: DirFilter
  categorySearch: string
}

const DEFAULT_FILTERS: Filters = {
  dateFrom: '',
  dateTo: '',
  accountIds: [],
  state: '',
  direction: '',
  categorySearch: '',
}

function hasActiveFilters(f: Filters) {
  return (
    f.dateFrom !== '' ||
    f.dateTo !== '' ||
    f.accountIds.length > 0 ||
    f.state !== '' ||
    f.direction !== '' ||
    f.categorySearch !== ''
  )
}

export function TransactionsPage() {
  const { householdId } = useHousehold()
  const privacyMode = useAuthStore((s) => s.privacyMode)

  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [selectedTxId, setSelectedTxId] = useState<string | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [showDedupQueue, setShowDedupQueue] = useState(false)

  const listRef = useRef<HTMLDivElement>(null)

  const apiParams = {
    state: (filters.state || null) as 'pending' | 'posted' | 'reconciled' | null,
    direction: (filters.direction || null) as 'debit' | 'credit' | null,
    date_from: filters.dateFrom || null,
    date_to: filters.dateTo || null,
  }

  const {
    data: rawTxs,
    isLoading,
    isError,
    refetch,
  } = useListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGet(
    householdId ?? '',
    apiParams,
    { query: { enabled: !!householdId } }
  )

  const { data: accounts = [] } = useListAccountsApiV1HouseholdsHouseholdIdAccountsGet(
    householdId ?? '',
    undefined,
    { query: { enabled: !!householdId } }
  )

  const dedupCount = useDedupCount(householdId)

  const transactions: TransactionOut[] = (rawTxs ?? []).filter((tx) => {
    if (filters.accountIds.length > 0 && !filters.accountIds.includes(tx.account_id)) return false
    if (filters.categorySearch) {
      const name = (tx.merchant_name ?? tx.description).toLowerCase()
      if (!name.includes(filters.categorySearch.toLowerCase())) return false
    }
    return true
  })

  const groups = groupByDate(transactions)
  const virtualRows = buildVirtualRows(groups)

  const virtualizer = useVirtualizer({
    count: virtualRows.length,
    getScrollElement: () => listRef.current,
    estimateSize: (i) => {
      const row = virtualRows[i]
      return row?.kind === 'header' ? TX_HEADER_HEIGHT : TX_ROW_HEIGHT
    },
    overscan: 8,
  })

  const active = hasActiveFilters(filters)

  function clearFilters() {
    setFilters(DEFAULT_FILTERS)
  }

  if (!householdId) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Page header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 16,
          flexShrink: 0,
          marginBottom: 16,
        }}
      >
        <div>
          <h1
            style={{
              fontSize: 22,
              fontWeight: 600,
              color: 'var(--fg-primary)',
              margin: 0,
              letterSpacing: '-0.01em',
            }}
          >
            Transactions
          </h1>
          {rawTxs && (
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
              {transactions.length} transaction{transactions.length !== 1 ? 's' : ''}
              {active ? ' (filtered)' : ''}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          {dedupCount > 0 && (
            <button
              type="button"
              onClick={() => setShowDedupQueue(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 12px',
                borderRadius: 8,
                border: '1px solid color-mix(in oklch, var(--warning) 40%, transparent)',
                background: 'color-mix(in oklch, var(--warning) 10%, transparent)',
                color: 'var(--warning)',
                fontSize: 12,
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              <Inbox size={12} />
              {dedupCount} duplicate{dedupCount !== 1 ? 's' : ''}
            </button>
          )}
          <button
            type="button"
            onClick={() => setFiltersOpen((o) => !o)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '7px 12px',
              borderRadius: 8,
              border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
              background: active ? 'color-mix(in oklch, var(--accent) 10%, transparent)' : 'none',
              color: active ? 'var(--accent)' : 'var(--fg-secondary)',
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            <SlidersHorizontal size={12} />
            Filters
            {active && (
              <span
                style={{
                  background: 'var(--accent)',
                  color: 'var(--accent-fg)',
                  borderRadius: 99,
                  fontSize: 10,
                  fontWeight: 700,
                  padding: '1px 5px',
                }}
              >
                {
                  [
                    filters.dateFrom || filters.dateTo,
                    filters.accountIds.length > 0,
                    filters.state,
                    filters.direction,
                    filters.categorySearch,
                  ].filter(Boolean).length
                }
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '7px 14px',
              borderRadius: 8,
              border: 'none',
              background: 'var(--accent)',
              color: 'var(--accent-fg)',
              fontSize: 13,
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            <Plus size={13} /> Add
          </button>
        </div>
      </div>

      {/* Filter bar */}
      {filtersOpen && (
        <div
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            padding: '14px 16px',
            marginBottom: 12,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            flexShrink: 0,
          }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
              gap: 10,
            }}
          >
            <FilterField label="Date from">
              <input
                type="date"
                value={filters.dateFrom}
                onChange={(e) => setFilters((f) => ({ ...f, dateFrom: e.target.value }))}
                style={filterInputStyle}
              />
            </FilterField>

            <FilterField label="Date to">
              <input
                type="date"
                value={filters.dateTo}
                onChange={(e) => setFilters((f) => ({ ...f, dateTo: e.target.value }))}
                style={filterInputStyle}
              />
            </FilterField>

            <FilterField label="State">
              <select
                value={filters.state}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, state: e.target.value as StateFilter }))
                }
                style={filterInputStyle}
              >
                <option value="">All states</option>
                <option value="pending">Pending</option>
                <option value="posted">Posted</option>
                <option value="reconciled">Reconciled</option>
              </select>
            </FilterField>

            <FilterField label="Direction">
              <select
                value={filters.direction}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, direction: e.target.value as DirFilter }))
                }
                style={filterInputStyle}
              >
                <option value="">All directions</option>
                <option value="debit">Debit (expenses)</option>
                <option value="credit">Credit (income)</option>
              </select>
            </FilterField>

            <FilterField label="Category search">
              <input
                type="text"
                value={filters.categorySearch}
                onChange={(e) => setFilters((f) => ({ ...f, categorySearch: e.target.value }))}
                placeholder="Search merchant or description..."
                style={filterInputStyle}
              />
            </FilterField>
          </div>

          {/* Account multi-select */}
          {accounts.length > 0 && (
            <FilterField label="Accounts">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {accounts.map((a) => {
                  const checked = filters.accountIds.includes(a.id)
                  return (
                    <button
                      key={a.id}
                      type="button"
                      onClick={() =>
                        setFilters((f) => ({
                          ...f,
                          accountIds: checked
                            ? f.accountIds.filter((id) => id !== a.id)
                            : [...f.accountIds, a.id],
                        }))
                      }
                      style={{
                        padding: '4px 10px',
                        borderRadius: 99,
                        border: `1px solid ${checked ? 'var(--accent)' : 'var(--border)'}`,
                        background: checked
                          ? 'color-mix(in oklch, var(--accent) 12%, transparent)'
                          : 'none',
                        color: checked ? 'var(--accent)' : 'var(--fg-muted)',
                        fontSize: 11,
                        fontWeight: checked ? 500 : 400,
                        cursor: 'pointer',
                      }}
                    >
                      {a.name}
                    </button>
                  )
                })}
              </div>
            </FilterField>
          )}

          {active && (
            <button
              type="button"
              onClick={clearFilters}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                alignSelf: 'flex-end',
                padding: '5px 10px',
                borderRadius: 6,
                border: '1px solid var(--border)',
                background: 'none',
                color: 'var(--fg-muted)',
                fontSize: 11,
                cursor: 'pointer',
              }}
            >
              <X size={10} /> Clear all filters
            </button>
          )}
        </div>
      )}

      {/* Virtual list */}
      <div ref={listRef} style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {isLoading && <SkeletonRows />}

        {isError && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 12,
              padding: '48px 0',
            }}
          >
            <span style={{ fontSize: 14, color: 'var(--fg-muted)' }}>
              Failed to load transactions.
            </span>
            <button
              type="button"
              onClick={() => void refetch()}
              style={{
                padding: '7px 16px',
                borderRadius: 8,
                border: 'none',
                background: 'var(--accent)',
                color: 'var(--accent-fg)',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              Retry
            </button>
          </div>
        )}

        {!isLoading && !isError && virtualRows.length === 0 && (
          <EmptyState filtered={active} onClearFilters={clearFilters} />
        )}

        {!isLoading && !isError && virtualRows.length > 0 && (
          <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
            {virtualizer.getVirtualItems().map((vItem) => {
              const row = virtualRows[vItem.index] as VirtualRow
              return (
                <div
                  key={vItem.key}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    transform: `translateY(${vItem.start}px)`,
                    height: vItem.size,
                  }}
                >
                  {row.kind === 'header' ? (
                    <DateHeader label={row.label} />
                  ) : (
                    <TxRowItem
                      tx={row.tx}
                      privacyMode={privacyMode}
                      selected={selectedTxId === row.tx.id}
                      onSelect={() => setSelectedTxId(row.tx.id)}
                    />
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Detail sheet */}
      <TransactionDetail
        householdId={householdId}
        transactionId={selectedTxId}
        onClose={() => setSelectedTxId(null)}
        onOpenTransaction={(id) => setSelectedTxId(id)}
      />

      {/* Modals */}
      <AddTransactionModal
        householdId={householdId}
        accounts={accounts}
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
      />

      <DedupQueue
        householdId={householdId}
        open={showDedupQueue}
        onClose={() => setShowDedupQueue(false)}
      />
    </div>
  )
}

function DateHeader({ label }: { label: string }) {
  return (
    <div
      style={{
        height: TX_HEADER_HEIGHT,
        display: 'flex',
        alignItems: 'flex-end',
        paddingBottom: 6,
        fontSize: 11,
        fontWeight: 600,
        color: 'var(--fg-muted)',
        textTransform: 'uppercase' as const,
        letterSpacing: '0.07em',
      }}
    >
      {label}
    </div>
  )
}

function TxRowItem({
  tx,
  privacyMode,
  selected,
  onSelect,
}: {
  tx: TransactionOut
  privacyMode: PrivacyMode
  selected: boolean
  onSelect: () => void
}) {
  const isIncome = tx.direction === 'credit'
  const displayAmt = txDisplayAmount(tx)
  const name = tx.merchant_name ?? tx.description
  const color = categoryColor(null, name)

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onSelect()
      }}
      style={{
        height: TX_ROW_HEIGHT,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        paddingLeft: selected ? 14 : 0,
        borderBottom: '1px solid var(--border)',
        borderLeft: `2px solid ${selected ? 'var(--accent)' : 'transparent'}`,
        background: selected ? 'color-mix(in oklch, var(--accent) 6%, transparent)' : 'transparent',
        cursor: 'pointer',
        transition: 'all 0.12s',
      }}
    >
      {/* Category icon */}
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          flexShrink: 0,
          background: `color-mix(in oklch, ${color} 18%, transparent)`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
      </div>

      {/* Name + meta */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: 'var(--fg-primary)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {name}
        </div>
        <div
          style={{
            fontSize: 11,
            color: 'var(--fg-muted)',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            marginTop: 1,
          }}
        >
          {tx.state === 'pending' && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                padding: '1px 5px',
                borderRadius: 99,
                background: 'color-mix(in oklch, var(--warning) 15%, transparent)',
                color: 'var(--warning)',
              }}
            >
              Pending
            </span>
          )}
          {tx.recurrence_id && <RefreshCw size={10} style={{ color: 'var(--accent)' }} />}
          <span>{tx.posted_date}</span>
        </div>
      </div>

      {/* Amount */}
      <div
        style={{
          fontSize: 13,
          fontWeight: 500,
          fontFamily: 'var(--font-mono)',
          color: isIncome ? 'var(--success)' : 'var(--fg-primary)',
          flexShrink: 0,
          paddingRight: 2,
        }}
      >
        {isIncome ? '+' : ''}
        {fmt(displayAmt, privacyMode, tx.currency)}
      </div>
    </div>
  )
}

function SkeletonRows() {
  return (
    <div>
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          style={{
            height: TX_ROW_HEIGHT,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            borderBottom: '1px solid var(--border)',
          }}
        >
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: 'var(--border)',
              opacity: 0.5,
              flexShrink: 0,
            }}
          />
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div
              style={{
                height: 12,
                width: '40%',
                borderRadius: 4,
                background: 'var(--border)',
                opacity: 0.6,
              }}
            />
            <div
              style={{
                height: 10,
                width: '25%',
                borderRadius: 4,
                background: 'var(--border)',
                opacity: 0.4,
              }}
            />
          </div>
          <div
            style={{
              width: 60,
              height: 12,
              borderRadius: 4,
              background: 'var(--border)',
              opacity: 0.5,
            }}
          />
        </div>
      ))}
    </div>
  )
}

function EmptyState({
  filtered,
  onClearFilters,
}: {
  filtered: boolean
  onClearFilters: () => void
}) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 14,
        padding: '64px 0',
        textAlign: 'center' as const,
      }}
    >
      <div style={{ fontSize: 40 }}>{filtered ? '&#128269;' : '&#128184;'}</div>
      <div style={{ fontSize: 17, fontWeight: 600, color: 'var(--fg-primary)' }}>
        {filtered ? 'No transactions match your filters' : 'No transactions yet'}
      </div>
      <div
        style={{
          fontSize: 13,
          color: 'var(--fg-muted)',
          maxWidth: 320,
          lineHeight: 1.6,
        }}
      >
        {filtered
          ? 'Try adjusting or clearing your filters to see more results.'
          : 'Import a file or connect an account to get started.'}
      </div>
      {filtered && (
        <button
          type="button"
          onClick={onClearFilters}
          style={{
            padding: '8px 18px',
            borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'none',
            color: 'var(--fg-secondary)',
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          Clear filters
        </button>
      )}
    </div>
  )
}

function FilterField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <label style={{ fontSize: 11, fontWeight: 500, color: 'var(--fg-muted)' }}>{label}</label>
      {children}
    </div>
  )
}

const filterInputStyle: React.CSSProperties = {
  width: '100%',
  padding: '7px 10px',
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'var(--bg-primary)',
  color: 'var(--fg-primary)',
  fontSize: 13,
  outline: 'none',
  boxSizing: 'border-box',
}
