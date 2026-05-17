import { useState, useMemo } from 'react'
import { ChevronLeft, ChevronRight, X, AlertTriangle } from 'lucide-react'
import {
  useGetCalendarEventsApiV1HouseholdsHouseholdIdProjectionsCalendarEventsGet,
  useListBreachesApiV1HouseholdsHouseholdIdProjectionsBreachesGet,
} from '@/api/generated/default/default'
import { useListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGet } from '@/api/generated/transactions/transactions'
import { useHousehold } from '@/hooks/use-household'
import { formatAmount } from '@/lib/format-amount'
import { TransactionState } from '@/api/generated/model/transactionState'
import { ProjectedEventType } from '@/api/generated/model/projectedEventType'
import { ProjectedConfidence } from '@/api/generated/model/projectedConfidence'
import type { TransactionOut } from '@/api/generated/model/transactionOut'
import type { ProjectedEventOut } from '@/api/generated/model/projectedEventOut'
import type { ProjectionBreachEventOut } from '@/api/generated/model/projectionBreachEventOut'

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function padDate(n: number): string {
  return String(n).padStart(2, '0')
}

function dateStr(year: number, month: number, day: number): string {
  return `${year}-${padDate(month + 1)}-${padDate(day)}`
}

function todayStr(): string {
  const d = new Date()
  return dateStr(d.getFullYear(), d.getMonth(), d.getDate())
}

function formatMonthYear(year: number, month: number): string {
  return new Date(year, month, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
}

function formatFullDate(dateStr: string): string {
  const parts = dateStr.split('-')
  const y = parseInt(parts[0] ?? '2000', 10)
  const m = parseInt(parts[1] ?? '1', 10)
  const d = parseInt(parts[2] ?? '1', 10)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
}

function confidenceOpacity(confidence: string): number {
  if (confidence === ProjectedConfidence.high) return 1
  if (confidence === ProjectedConfidence.medium) return 0.7
  return 0.4
}

function projectedEventColor(type: string): string {
  if (type === ProjectedEventType.income) return 'var(--success)'
  if (type === ProjectedEventType.debt_payment) return 'var(--danger)'
  if (type === ProjectedEventType.balance_breach) return 'var(--warning)'
  return 'var(--fg-muted)'
}

function projectedEventLabel(event: ProjectedEventOut): string {
  if (event.description) return event.description
  if (event.event_type === ProjectedEventType.income) return 'Projected income'
  if (event.event_type === ProjectedEventType.debt_payment) return 'Debt payment'
  if (event.event_type === ProjectedEventType.recurrence) return 'Recurring'
  if (event.event_type === ProjectedEventType.budget_spend) return 'Budget spend'
  if (event.event_type === ProjectedEventType.balance_breach) return 'Balance warning'
  return event.event_type
}

function txDisplayAmount(tx: TransactionOut): number {
  const raw = parseFloat(tx.amount)
  return tx.direction === 'credit' ? raw : -raw
}

interface DayEvents {
  transactions: TransactionOut[]
  projected: ProjectedEventOut[]
}

function EventPill({
  label,
  color,
  dashed = false,
  opacity = 1,
  icon,
}: {
  label: string
  color: string
  dashed?: boolean
  opacity?: number
  icon?: React.ReactNode
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 3,
        padding: '1px 5px',
        borderRadius: 4,
        fontSize: 10,
        fontWeight: 500,
        color,
        background: dashed ? 'transparent' : `color-mix(in oklch, ${color} 15%, transparent)`,
        border: dashed
          ? `1px dashed ${color}`
          : `1px solid color-mix(in oklch, ${color} 30%, transparent)`,
        opacity,
        overflow: 'hidden',
        whiteSpace: 'nowrap' as const,
        textOverflow: 'ellipsis',
        maxWidth: '100%',
      }}
    >
      {icon && <span style={{ flexShrink: 0, display: 'flex' }}>{icon}</span>}
      <span
        style={{
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap' as const,
        }}
      >
        {label}
      </span>
    </div>
  )
}

function DayCell({
  day,
  isToday,
  isCurrentMonth,
  events,
  projectedLoading,
  isSelected,
  onClick,
}: {
  day: string
  isToday: boolean
  isCurrentMonth: boolean
  events: DayEvents
  projectedLoading: boolean
  isSelected: boolean
  onClick: () => void
}) {
  const dayNum = parseInt(day.split('-')[2] ?? '1', 10)
  const allEvents = [...events.transactions, ...events.projected]
  const maxVisible = 3
  const overflow = allEvents.length > maxVisible ? allEvents.length - maxVisible : 0

  const visibleTxs = events.transactions.slice(0, Math.min(events.transactions.length, maxVisible))
  const visibleProj = events.projected.slice(0, Math.max(0, maxVisible - visibleTxs.length))

  return (
    <div
      onClick={onClick}
      style={{
        minHeight: 80,
        padding: '6px 8px',
        borderRight: '1px solid var(--border)',
        borderBottom: '1px solid var(--border)',
        background: isSelected
          ? 'color-mix(in oklch, var(--accent) 8%, var(--bg-primary))'
          : isCurrentMonth
            ? 'var(--bg-primary)'
            : 'var(--bg-secondary)',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        gap: 3,
        transition: 'background 0.1s',
        position: 'relative' as const,
        overflow: 'hidden',
      }}
      onMouseEnter={(e) => {
        if (!isSelected)
          (e.currentTarget as HTMLDivElement).style.background =
            'color-mix(in oklch, var(--fg-primary) 3%, var(--bg-primary))'
      }}
      onMouseLeave={(e) => {
        if (!isSelected)
          (e.currentTarget as HTMLDivElement).style.background = isCurrentMonth
            ? 'var(--bg-primary)'
            : 'var(--bg-secondary)'
      }}
    >
      <div
        style={{
          width: 22,
          height: 22,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: '50%',
          fontSize: 12,
          fontWeight: isToday ? 700 : 400,
          color: isToday
            ? 'var(--accent-fg)'
            : isCurrentMonth
              ? 'var(--fg-primary)'
              : 'var(--fg-muted)',
          background: isToday ? 'var(--accent)' : 'transparent',
          flexShrink: 0,
        }}
      >
        {dayNum}
      </div>

      {visibleTxs.map((tx) => (
        <EventPill
          key={tx.id}
          label={tx.merchant_name ?? tx.description}
          color="var(--accent)"
          opacity={1}
        />
      ))}

      {!projectedLoading &&
        visibleProj.map((ev) => {
          const color = projectedEventColor(ev.event_type)
          const opacity = confidenceOpacity(ev.confidence)
          const dashed =
            ev.event_type === ProjectedEventType.recurrence ||
            ev.event_type === ProjectedEventType.budget_spend
          const hasWarningIcon = ev.event_type === ProjectedEventType.balance_breach
          return (
            <EventPill
              key={ev.id}
              label={projectedEventLabel(ev)}
              color={color}
              dashed={dashed}
              opacity={opacity}
              icon={hasWarningIcon ? <AlertTriangle size={8} /> : undefined}
            />
          )
        })}

      {projectedLoading && events.projected.length === 0 && (
        <div style={{ display: 'flex', gap: 3, marginTop: 2 }}>
          {[0, 1].map((i) => (
            <div
              key={i}
              style={{
                width: 24,
                height: 6,
                borderRadius: 99,
                background: 'var(--border)',
              }}
            />
          ))}
        </div>
      )}

      {overflow > 0 && (
        <div style={{ fontSize: 10, color: 'var(--fg-muted)', marginTop: 1 }}>+{overflow} more</div>
      )}
    </div>
  )
}

function DayDetailSheet({
  day,
  events,
  onClose,
}: {
  day: string
  events: DayEvents
  onClose: () => void
}) {
  const hasAny = events.transactions.length > 0 || events.projected.length > 0

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 80,
        display: 'flex',
        justifyContent: 'flex-end',
        pointerEvents: 'none',
      }}
    >
      <div style={{ flex: 1, pointerEvents: 'auto' }} onClick={onClose} />
      <div
        style={{
          width: 360,
          maxWidth: '90vw',
          height: '100%',
          background: 'var(--bg-elevated)',
          borderLeft: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '-8px 0 24px rgba(0,0,0,0.12)',
          pointerEvents: 'auto',
        }}
      >
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>
              {formatFullDate(day)}
            </div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
              {events.transactions.length} posted, {events.projected.length} projected
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              width: 28,
              height: 28,
              border: '1px solid var(--border)',
              background: 'transparent',
              borderRadius: 6,
              color: 'var(--fg-muted)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 0,
            }}
          >
            <X size={13} />
          </button>
        </div>

        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '12px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: 0,
          }}
        >
          {!hasAny && (
            <div
              style={{
                fontSize: 13,
                color: 'var(--fg-muted)',
                padding: '24px 0',
                textAlign: 'center' as const,
              }}
            >
              No events
            </div>
          )}

          {events.transactions.length > 0 && (
            <>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--fg-muted)',
                  textTransform: 'uppercase' as const,
                  letterSpacing: '0.06em',
                  padding: '8px 0 6px',
                }}
              >
                Posted
              </div>
              {events.transactions.map((tx) => {
                const amount = txDisplayAmount(tx)
                return (
                  <div
                    key={tx.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-start',
                      gap: 10,
                      padding: '9px 0',
                      borderBottom: '1px solid var(--border)',
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 500,
                          color: 'var(--fg-primary)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap' as const,
                        }}
                      >
                        {tx.merchant_name ?? tx.description}
                      </div>
                      {tx.merchant_name && tx.description !== tx.merchant_name && (
                        <div
                          style={{
                            fontSize: 11,
                            color: 'var(--fg-muted)',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap' as const,
                          }}
                        >
                          {tx.description}
                        </div>
                      )}
                    </div>
                    <div
                      style={{
                        fontSize: 14,
                        fontWeight: 600,
                        fontFamily: "'Geist Mono', monospace",
                        color: amount >= 0 ? 'var(--success)' : 'var(--fg-primary)',
                        flexShrink: 0,
                      }}
                    >
                      {amount >= 0 ? '+' : ''}
                      {formatAmount(amount, { currency: tx.currency })}
                    </div>
                  </div>
                )
              })}
            </>
          )}

          {events.projected.length > 0 && (
            <>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--fg-muted)',
                  textTransform: 'uppercase' as const,
                  letterSpacing: '0.06em',
                  padding: '12px 0 6px',
                }}
              >
                Projected
              </div>
              {events.projected.map((ev) => {
                const color = projectedEventColor(ev.event_type)
                const opacity = confidenceOpacity(ev.confidence)
                const amount = parseFloat(ev.amount)
                return (
                  <div
                    key={ev.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-start',
                      gap: 10,
                      padding: '9px 0',
                      borderBottom: '1px solid var(--border)',
                      opacity,
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 500,
                          color: 'var(--fg-primary)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap' as const,
                        }}
                      >
                        {projectedEventLabel(ev)}
                      </div>
                      <div style={{ display: 'flex', gap: 5, marginTop: 3 }}>
                        <span
                          style={{
                            fontSize: 10,
                            padding: '1px 5px',
                            borderRadius: 4,
                            background: `color-mix(in oklch, ${color} 15%, transparent)`,
                            color,
                            border: `1px solid color-mix(in oklch, ${color} 30%, transparent)`,
                          }}
                        >
                          {ev.confidence}
                        </span>
                      </div>
                    </div>
                    <div
                      style={{
                        fontSize: 14,
                        fontWeight: 600,
                        fontFamily: "'Geist Mono', monospace",
                        color: ev.direction === 'credit' ? 'var(--success)' : 'var(--fg-primary)',
                        flexShrink: 0,
                      }}
                    >
                      {ev.direction === 'credit' ? '+' : '-'}
                      {formatAmount(amount, { currency: ev.currency })}
                    </div>
                  </div>
                )
              })}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function BreachBanner({
  breaches,
  onDismiss,
  onDateClick,
}: {
  breaches: ProjectionBreachEventOut[]
  onDismiss: () => void
  onDateClick: (date: string) => void
}) {
  const first = breaches[0]
  if (!first) return null

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '10px 16px',
        background: `color-mix(in oklch, var(--warning) 12%, var(--bg-elevated))`,
        border: '1px solid color-mix(in oklch, var(--warning) 35%, transparent)',
        borderRadius: 8,
        margin: '0 24px',
      }}
    >
      <AlertTriangle size={14} style={{ color: 'var(--warning)', flexShrink: 0 }} />
      <div style={{ flex: 1, fontSize: 13, color: 'var(--fg-primary)' }}>
        <span style={{ fontWeight: 600, color: 'var(--warning)' }}>
          Projected balance breach on {first.breach_date}
        </span>
        {first.description && (
          <span style={{ color: 'var(--fg-muted)' }}> — {first.description}</span>
        )}
        {breaches.length > 1 && (
          <span style={{ color: 'var(--fg-muted)' }}> (+{breaches.length - 1} more)</span>
        )}
      </div>
      <button
        type="button"
        onClick={() => onDateClick(first.breach_date)}
        style={{
          fontSize: 12,
          padding: '4px 10px',
          borderRadius: 6,
          border: '1px solid color-mix(in oklch, var(--warning) 50%, transparent)',
          background: 'transparent',
          color: 'var(--warning)',
          cursor: 'pointer',
          flexShrink: 0,
        }}
      >
        View
      </button>
      <button
        type="button"
        onClick={onDismiss}
        style={{
          width: 22,
          height: 22,
          border: 'none',
          background: 'transparent',
          color: 'var(--fg-muted)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 0,
          flexShrink: 0,
        }}
      >
        <X size={12} />
      </button>
    </div>
  )
}

export function CalendarPage() {
  const { householdId } = useHousehold()
  const hid = householdId ?? ''

  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth())
  const [weekMode, setWeekMode] = useState(false)
  const [selectedDay, setSelectedDay] = useState<string | null>(null)
  const [breachDismissed, setBreachDismissed] = useState(false)

  const monthStart = `${year}-${padDate(month + 1)}-01`
  const lastDay = new Date(year, month + 1, 0).getDate()
  const monthEnd = `${year}-${padDate(month + 1)}-${padDate(lastDay)}`

  const { data: postedTxs = [], isLoading: txLoading } =
    useListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGet(
      hid,
      { state: TransactionState.posted, date_from: monthStart, date_to: monthEnd },
      { query: { enabled: !!hid } }
    )

  const { data: projectedEvents = [], isLoading: projLoading } =
    useGetCalendarEventsApiV1HouseholdsHouseholdIdProjectionsCalendarEventsGet(
      hid,
      { from: monthStart, to: monthEnd },
      { query: { enabled: !!hid } }
    )

  const { data: breaches = [] } = useListBreachesApiV1HouseholdsHouseholdIdProjectionsBreachesGet(
    hid,
    {},
    { query: { enabled: !!hid } }
  )

  const upcomingBreaches = breaches.filter((b) => {
    const d = new Date(b.breach_date)
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() + 30)
    return d <= cutoff && d >= today
  })

  const eventsByDay = useMemo(() => {
    const map = new Map<string, DayEvents>()
    for (const tx of postedTxs) {
      const key = tx.posted_date
      const existing = map.get(key) ?? { transactions: [], projected: [] }
      existing.transactions.push(tx)
      map.set(key, existing)
    }
    for (const ev of projectedEvents) {
      const key = ev.event_date
      const existing = map.get(key) ?? { transactions: [], projected: [] }
      existing.projected.push(ev)
      map.set(key, existing)
    }
    return map
  }, [postedTxs, projectedEvents])

  function prevMonth() {
    if (month === 0) {
      setMonth(11)
      setYear((y) => y - 1)
    } else setMonth((m) => m - 1)
  }

  function nextMonth() {
    if (month === 11) {
      setMonth(0)
      setYear((y) => y + 1)
    } else setMonth((m) => m + 1)
  }

  function goToday() {
    setYear(today.getFullYear())
    setMonth(today.getMonth())
  }

  const todayKey = todayStr()

  const firstDayOfMonth = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const daysInPrevMonth = new Date(year, month, 0).getDate()

  type CalCell = { date: string; currentMonth: boolean }

  function buildMonthCells(): CalCell[] {
    const cells: CalCell[] = []
    for (let i = firstDayOfMonth - 1; i >= 0; i--) {
      const d = daysInPrevMonth - i
      const prevM = month === 0 ? 11 : month - 1
      const prevY = month === 0 ? year - 1 : year
      cells.push({ date: dateStr(prevY, prevM, d), currentMonth: false })
    }
    for (let d = 1; d <= daysInMonth; d++) {
      cells.push({ date: dateStr(year, month, d), currentMonth: true })
    }
    const remaining = 42 - cells.length
    const nextM = month === 11 ? 0 : month + 1
    const nextY = month === 11 ? year + 1 : year
    for (let d = 1; d <= remaining; d++) {
      cells.push({ date: dateStr(nextY, nextM, d), currentMonth: false })
    }
    return cells
  }

  function buildWeekCells(): CalCell[] {
    const cells: CalCell[] = []
    const base = new Date()
    const dow = base.getDay()
    base.setDate(base.getDate() - dow)
    for (let i = 0; i < 7; i++) {
      const d = new Date(base)
      d.setDate(base.getDate() + i)
      cells.push({
        date: dateStr(d.getFullYear(), d.getMonth(), d.getDate()),
        currentMonth: d.getMonth() === month,
      })
    }
    return cells
  }

  const cells = weekMode ? buildWeekCells() : buildMonthCells()

  const selectedDayEvents = selectedDay
    ? (eventsByDay.get(selectedDay) ?? { transactions: [], projected: [] })
    : null

  const postedDebits = postedTxs
    .filter((tx) => tx.direction === 'debit')
    .reduce((s, tx) => s + parseFloat(tx.amount), 0)
  const postedCredits = postedTxs
    .filter((tx) => tx.direction === 'credit')
    .reduce((s, tx) => s + parseFloat(tx.amount), 0)

  if (!householdId) {
    return <div style={{ padding: 32, color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div
        style={{
          padding: '12px 24px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            type="button"
            onClick={prevMonth}
            style={{
              width: 30,
              height: 30,
              border: '1px solid var(--border)',
              background: 'none',
              borderRadius: 7,
              color: 'var(--fg-secondary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 0,
            }}
          >
            <ChevronLeft size={15} />
          </button>

          <h1
            style={{
              fontSize: 18,
              fontWeight: 600,
              color: 'var(--fg-primary)',
              margin: 0,
              letterSpacing: '-0.01em',
              minWidth: 160,
              textAlign: 'center' as const,
            }}
          >
            {formatMonthYear(year, month)}
          </h1>

          <button
            type="button"
            onClick={nextMonth}
            style={{
              width: 30,
              height: 30,
              border: '1px solid var(--border)',
              background: 'none',
              borderRadius: 7,
              color: 'var(--fg-secondary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 0,
            }}
          >
            <ChevronRight size={15} />
          </button>

          <button
            type="button"
            onClick={goToday}
            style={{
              padding: '5px 12px',
              border: '1px solid var(--border)',
              background: 'none',
              borderRadius: 7,
              color: 'var(--fg-secondary)',
              cursor: 'pointer',
              fontSize: 12,
              marginLeft: 4,
            }}
          >
            Today
          </button>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div
            style={{
              display: 'flex',
              borderRadius: 7,
              border: '1px solid var(--border)',
              overflow: 'hidden',
            }}
          >
            {[
              { label: 'Month', val: false },
              { label: 'Week', val: true },
            ].map((opt) => (
              <button
                key={opt.label}
                type="button"
                onClick={() => setWeekMode(opt.val)}
                style={{
                  padding: '5px 12px',
                  fontSize: 12,
                  border: 'none',
                  cursor: 'pointer',
                  background:
                    weekMode === opt.val
                      ? `color-mix(in oklch, var(--accent) 15%, transparent)`
                      : 'transparent',
                  color: weekMode === opt.val ? 'var(--accent)' : 'var(--fg-muted)',
                  fontWeight: weekMode === opt.val ? 600 : 400,
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Breach banner */}
      {upcomingBreaches.length > 0 && !breachDismissed && (
        <div style={{ padding: '10px 0 0' }}>
          <BreachBanner
            breaches={upcomingBreaches}
            onDismiss={() => setBreachDismissed(true)}
            onDateClick={(d) => {
              setYear(parseInt(d.split('-')[0] ?? '2000', 10))
              setMonth(parseInt(d.split('-')[1] ?? '1', 10) - 1)
              setSelectedDay(d)
            }}
          />
        </div>
      )}

      {/* Calendar grid */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Weekday headers */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(7, 1fr)',
            borderBottom: '1px solid var(--border)',
            borderTop: '1px solid var(--border)',
            flexShrink: 0,
          }}
        >
          {WEEKDAYS.map((w) => (
            <div
              key={w}
              style={{
                padding: '6px 8px',
                fontSize: 11,
                fontWeight: 600,
                color: 'var(--fg-muted)',
                textTransform: 'uppercase' as const,
                letterSpacing: '0.05em',
                textAlign: 'center' as const,
                borderRight: '1px solid var(--border)',
              }}
            >
              {w}
            </div>
          ))}
        </div>

        {/* Day cells */}
        <div
          style={{
            flex: 1,
            display: 'grid',
            gridTemplateColumns: 'repeat(7, 1fr)',
            gridAutoRows: weekMode ? '1fr' : 'minmax(80px, 1fr)',
            overflowY: 'auto',
            borderLeft: '1px solid var(--border)',
          }}
        >
          {cells.map((cell) => (
            <DayCell
              key={cell.date}
              day={cell.date}
              isToday={cell.date === todayKey}
              isCurrentMonth={cell.currentMonth}
              events={eventsByDay.get(cell.date) ?? { transactions: [], projected: [] }}
              projectedLoading={projLoading}
              isSelected={cell.date === selectedDay}
              onClick={() => setSelectedDay(cell.date === selectedDay ? null : cell.date)}
            />
          ))}
        </div>
      </div>

      {/* Month summary footer */}
      {!txLoading && (
        <div
          style={{
            padding: '10px 24px',
            borderTop: '1px solid var(--border)',
            display: 'flex',
            gap: 24,
            alignItems: 'center',
            fontSize: 12,
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <span style={{ color: 'var(--fg-muted)' }}>Posted spending:</span>
            <span
              style={{
                fontFamily: "'Geist Mono', monospace",
                fontWeight: 600,
                color: 'var(--danger)',
              }}
            >
              {formatAmount(postedDebits)}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <span style={{ color: 'var(--fg-muted)' }}>Posted income:</span>
            <span
              style={{
                fontFamily: "'Geist Mono', monospace",
                fontWeight: 600,
                color: 'var(--success)',
              }}
            >
              {formatAmount(postedCredits)}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
            <div
              style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)' }}
            />
            <span style={{ color: 'var(--fg-muted)' }}>Posted</span>
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                border: '1.5px dashed var(--fg-muted)',
                background: 'transparent',
              }}
            />
            <span style={{ color: 'var(--fg-muted)' }}>Projected</span>
          </div>
        </div>
      )}

      {/* Day detail side sheet */}
      {selectedDay && selectedDayEvents && (
        <DayDetailSheet
          day={selectedDay}
          events={selectedDayEvents}
          onClose={() => setSelectedDay(null)}
        />
      )}
    </div>
  )
}
