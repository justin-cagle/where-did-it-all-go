import { describe, it, expect } from 'vitest'
import {
  groupByDate,
  buildVirtualRows,
  formatTransactionDate,
  offsetDateStr,
} from '@/domain/transactions'
import type { TransactionOut } from '@/api/generated/model/transactionOut'

function makeTx(overrides: Partial<TransactionOut> = {}): TransactionOut {
  return {
    id: 'tx-1',
    household_id: 'hh-1',
    account_id: 'acc-1',
    amount: '100.00',
    currency: 'USD',
    direction: 'debit',
    transaction_type: 'purchase',
    state: 'posted',
    posted_date: '2026-05-23',
    pending_date: null,
    occurred_at: '2026-05-23T12:00:00Z',
    description: 'Test merchant',
    merchant_name: null,
    note: null,
    external_id: null,
    recurrence_id: null,
    manually_categorized: false,
    transfer_peer_id: null,
    refund_peer_id: null,
    fx_rate: null,
    fx_rate_date: null,
    fx_rate_source: '',
    home_currency_amount: null,
    home_currency: null,
    created_at: '2026-05-23T12:00:00Z',
    updated_at: '2026-05-23T12:00:00Z',
    ...overrides,
  }
}

describe('formatTransactionDate', () => {
  it('formats a valid date string', () => {
    expect(formatTransactionDate('2026-05-23')).toBe('May 23')
  })

  it('returns empty string for null', () => {
    expect(formatTransactionDate(null)).toBe('')
  })

  it('returns empty string for undefined', () => {
    expect(formatTransactionDate(undefined)).toBe('')
  })

  it('returns empty string for empty string', () => {
    expect(formatTransactionDate('')).toBe('')
  })
})

describe('offsetDateStr', () => {
  it('adds positive days', () => {
    expect(offsetDateStr('2026-05-20', 3)).toBe('2026-05-23')
  })

  it('subtracts negative days', () => {
    expect(offsetDateStr('2026-05-23', -7)).toBe('2026-05-16')
  })

  it('handles null by falling back to today', () => {
    const result = offsetDateStr(null, 0)
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('handles undefined by falling back to today', () => {
    const result = offsetDateStr(undefined, 7)
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('wraps month boundary', () => {
    expect(offsetDateStr('2026-05-31', 1)).toBe('2026-06-01')
  })

  it('wraps year boundary', () => {
    expect(offsetDateStr('2026-12-31', 1)).toBe('2027-01-01')
  })
})

describe('groupByDate', () => {
  it('groups transactions by posted_date', () => {
    const txs = [
      makeTx({ id: 'tx-1', posted_date: '2026-05-23' }),
      makeTx({ id: 'tx-2', posted_date: '2026-05-22' }),
      makeTx({ id: 'tx-3', posted_date: '2026-05-23' }),
    ]
    const groups = groupByDate(txs)
    expect(groups).toHaveLength(2)
    expect(groups[0]?.date).toBe('2026-05-23')
    expect(groups[0]?.transactions).toHaveLength(2)
    expect(groups[1]?.date).toBe('2026-05-22')
  })

  it('sorts groups descending by date', () => {
    const txs = [
      makeTx({ id: 'tx-1', posted_date: '2026-05-20' }),
      makeTx({ id: 'tx-2', posted_date: '2026-05-22' }),
      makeTx({ id: 'tx-3', posted_date: '2026-05-21' }),
    ]
    const groups = groupByDate(txs)
    expect(groups.map((g) => g.date)).toEqual(['2026-05-22', '2026-05-21', '2026-05-20'])
  })

  it('does not throw when posted_date is null (pending transaction)', () => {
    const pendingTx = makeTx({
      id: 'tx-pending',
      // Simulate runtime null despite TS type saying string
      posted_date: null as unknown as string,
      occurred_at: '2026-05-23T10:00:00Z',
    })
    expect(() => groupByDate([pendingTx])).not.toThrow()
  })

  it('falls back to occurred_at date for pending transactions', () => {
    const pendingTx = makeTx({
      id: 'tx-pending',
      posted_date: null as unknown as string,
      occurred_at: '2026-05-21T10:00:00Z',
    })
    const groups = groupByDate([pendingTx])
    expect(groups).toHaveLength(1)
    expect(groups[0]?.date).toBe('2026-05-21')
  })

  it('handles empty array', () => {
    expect(groupByDate([])).toEqual([])
  })

  it('does not throw when sorting mix of null and non-null posted_dates', () => {
    const txs = [
      makeTx({ id: 'tx-1', posted_date: '2026-05-23' }),
      makeTx({
        id: 'tx-2',
        posted_date: null as unknown as string,
        occurred_at: '2026-05-20T00:00:00Z',
      }),
      makeTx({ id: 'tx-3', posted_date: '2026-05-22' }),
    ]
    expect(() => groupByDate(txs)).not.toThrow()
  })
})

describe('buildVirtualRows', () => {
  it('inserts header before each group', () => {
    const txs = [
      makeTx({ id: 'tx-1', posted_date: '2026-05-23' }),
      makeTx({ id: 'tx-2', posted_date: '2026-05-22' }),
    ]
    const groups = groupByDate(txs)
    const rows = buildVirtualRows(groups)
    expect(rows[0]).toMatchObject({ kind: 'header' })
    expect(rows[1]).toMatchObject({ kind: 'tx' })
    expect(rows[2]).toMatchObject({ kind: 'header' })
    expect(rows[3]).toMatchObject({ kind: 'tx' })
  })

  it('produces correct total row count', () => {
    const txs = [
      makeTx({ id: 'tx-1', posted_date: '2026-05-23' }),
      makeTx({ id: 'tx-2', posted_date: '2026-05-23' }),
      makeTx({ id: 'tx-3', posted_date: '2026-05-22' }),
    ]
    const rows = buildVirtualRows(groupByDate(txs))
    // 2 headers + 3 tx rows
    expect(rows).toHaveLength(5)
  })
})
