import { useQueryClient } from '@tanstack/react-query'
import { Merge, X } from 'lucide-react'
import {
  useListDedupCandidatesApiV1HouseholdsHouseholdIdTransactionsDedupCandidatesGet,
  useResolveDedupCandidateApiV1HouseholdsHouseholdIdTransactionsDedupCandidatesLogIdResolvePost,
  getListDedupCandidatesApiV1HouseholdsHouseholdIdTransactionsDedupCandidatesGetQueryKey,
} from '@/api/generated/transactions/transactions'
import type { DeduplicationLogOut } from '@/api/generated/model/deduplicationLogOut'
import { DedupResolveRequestResolution } from '@/api/generated/model/dedupResolveRequestResolution'

interface Props {
  householdId: string
  open: boolean
  onClose: () => void
}

export function DedupQueue({ householdId, open, onClose }: Props) {
  const qc = useQueryClient()

  const { data: candidates, isLoading } =
    useListDedupCandidatesApiV1HouseholdsHouseholdIdTransactionsDedupCandidatesGet(householdId, {
      query: { enabled: open },
    })

  const { mutateAsync: resolve } =
    useResolveDedupCandidateApiV1HouseholdsHouseholdIdTransactionsDedupCandidatesLogIdResolvePost()

  async function handleResolve(logId: string, resolution: 'merged' | 'rejected') {
    await resolve({
      householdId,
      logId,
      data: { resolution: DedupResolveRequestResolution[resolution] },
    })
    await qc.invalidateQueries({
      queryKey:
        getListDedupCandidatesApiV1HouseholdsHouseholdIdTransactionsDedupCandidatesGetQueryKey(
          householdId
        ),
    })
  }

  if (!open) return null

  return (
    <>
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 200 }}
      />
      <div
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 201,
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 16,
          width: 600,
          maxWidth: 'calc(100vw - 32px)',
          maxHeight: '80vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '20px 24px',
            borderBottom: '1px solid var(--border)',
            flexShrink: 0,
          }}
        >
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-primary)' }}>
              Review duplicates
            </div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
              {candidates
                ? `${candidates.length} pair${candidates.length !== 1 ? 's' : ''} to review`
                : ''}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--fg-muted)',
              cursor: 'pointer',
              padding: 4,
            }}
          >
            <X size={16} />
          </button>
        </div>

        <div
          style={{
            overflowY: 'auto',
            flex: 1,
            padding: '16px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          {isLoading && (
            <div
              style={{
                padding: '32px 0',
                textAlign: 'center' as const,
                color: 'var(--fg-muted)',
                fontSize: 13,
              }}
            >
              Loading...
            </div>
          )}

          {!isLoading && (!candidates || candidates.length === 0) && (
            <div
              style={{
                padding: '48px 0',
                textAlign: 'center' as const,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
                alignItems: 'center',
              }}
            >
              <div style={{ fontSize: 32 }}>&#10003;</div>
              <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-primary)' }}>
                No duplicates to review
              </div>
              <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>
                All transactions look unique.
              </div>
            </div>
          )}

          {candidates?.map((pair) => (
            <DedupPairCard key={pair.id} pair={pair} onResolve={handleResolve} />
          ))}
        </div>
      </div>
    </>
  )
}

function DedupPairCard({
  pair,
  onResolve,
}: {
  pair: DeduplicationLogOut
  onResolve: (id: string, resolution: 'merged' | 'rejected') => Promise<void>
}) {
  const confidence = Math.round(parseFloat(pair.confidence) * 100)
  const isHighConfidence = confidence >= 90

  return (
    <div
      style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--fg-muted)',
            textTransform: 'uppercase' as const,
            letterSpacing: '0.06em',
          }}
        >
          Possible duplicate
        </div>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: 99,
            background: isHighConfidence
              ? 'color-mix(in oklch, var(--danger) 15%, transparent)'
              : 'color-mix(in oklch, var(--warning) 15%, transparent)',
            color: isHighConfidence ? 'var(--danger)' : 'var(--warning)',
          }}
        >
          {confidence}% match
        </span>
      </div>

      <div style={{ fontSize: 12, color: 'var(--fg-secondary)', lineHeight: 1.5 }}>
        {pair.match_reason}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <TxIdCard label="Transaction A" txId={pair.candidate_a_id} />
        <TxIdCard label="Transaction B" txId={pair.candidate_b_id} />
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          type="button"
          onClick={() => void onResolve(pair.id, 'merged')}
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            padding: '8px',
            borderRadius: 8,
            border: 'none',
            background: 'var(--danger)',
            color: '#fff',
            fontSize: 12,
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          <Merge size={12} /> Merge into one
        </button>
        <button
          type="button"
          onClick={() => void onResolve(pair.id, 'rejected')}
          style={{
            flex: 1,
            padding: '8px',
            borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'none',
            color: 'var(--fg-secondary)',
            fontSize: 12,
            cursor: 'pointer',
          }}
        >
          Keep both
        </button>
      </div>
    </div>
  )
}

function TxIdCard({ label, txId }: { label: string; txId: string }) {
  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 8,
        padding: '10px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: 'var(--fg-muted)',
          fontWeight: 600,
          textTransform: 'uppercase' as const,
          letterSpacing: '0.06em',
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 11, color: 'var(--fg-secondary)', fontFamily: 'var(--font-mono)' }}>
        {txId.slice(0, 12)}...
      </div>
    </div>
  )
}
