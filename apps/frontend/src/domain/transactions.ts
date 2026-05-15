import type { TransactionOut } from '@/api/generated/model/transactionOut'

export type DateGroup = {
  label: string
  date: string
  transactions: TransactionOut[]
}

export type VirtualRow =
  | { kind: 'header'; label: string; date: string }
  | { kind: 'tx'; tx: TransactionOut }

export const TX_ROW_HEIGHT = 57
export const TX_HEADER_HEIGHT = 36

function localDateStr(offset = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function formatDateLabel(dateStr: string): string {
  const parts = dateStr.split('-')
  const y = parseInt(parts[0] ?? '2000', 10)
  const m = parseInt(parts[1] ?? '1', 10)
  const day = parseInt(parts[2] ?? '1', 10)
  const d = new Date(y, m - 1, day)
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
}

export function groupByDate(transactions: TransactionOut[]): DateGroup[] {
  const today = localDateStr(0)
  const yesterday = localDateStr(-1)

  const map = new Map<string, TransactionOut[]>()
  for (const tx of transactions) {
    const date = tx.posted_date
    const existing = map.get(date)
    if (existing) existing.push(tx)
    else map.set(date, [tx])
  }

  const sorted = Array.from(map.entries()).sort(([a], [b]) => b.localeCompare(a))

  return sorted.map(([date, txs]) => {
    let label: string
    if (date === today) label = 'Today'
    else if (date === yesterday) label = 'Yesterday'
    else label = formatDateLabel(date)
    return { label, date, transactions: txs }
  })
}

export function buildVirtualRows(groups: DateGroup[]): VirtualRow[] {
  const rows: VirtualRow[] = []
  for (const group of groups) {
    rows.push({ kind: 'header', label: group.label, date: group.date })
    for (const tx of group.transactions) {
      rows.push({ kind: 'tx', tx })
    }
  }
  return rows
}

const CAT_PALETTE = [
  '#6366f1',
  '#ec4899',
  '#f59e0b',
  '#10b981',
  '#3b82f6',
  '#8b5cf6',
  '#ef4444',
  '#14b8a6',
  '#f97316',
  '#06b6d4',
]

export function categoryColor(colorHex: string | null | undefined, name?: string): string {
  if (colorHex) return colorHex
  if (!name) return CAT_PALETTE[0] ?? '#6366f1'
  let h = 5381
  for (let i = 0; i < name.length; i++) h = (h * 33 + name.charCodeAt(i)) & 0x7fffffff
  return CAT_PALETTE[h % CAT_PALETTE.length] ?? '#6366f1'
}

export function txDisplayAmount(tx: TransactionOut): number {
  const raw = parseFloat(tx.amount)
  return tx.direction === 'credit' ? raw : -raw
}
