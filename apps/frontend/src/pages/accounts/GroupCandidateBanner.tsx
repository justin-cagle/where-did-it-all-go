import { useState } from 'react'
import { AlertTriangle, X, Check, XCircle } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useCreateAccountGroupApiV1HouseholdsHouseholdIdAccountsGroupsPost,
  getListAccountsApiV1HouseholdsHouseholdIdAccountsGetQueryKey,
  getListAccountGroupsApiV1HouseholdsHouseholdIdAccountsGroupsGetQueryKey,
  getFindGroupCandidatesApiV1HouseholdsHouseholdIdAccountsGroupsCandidatesGetQueryKey,
} from '@/api/generated/accounts/accounts'
import type { GroupCandidateOut } from '@/api/generated/model/groupCandidateOut'
import type { AccountOut } from '@/api/generated/model/accountOut'

interface GroupCandidateBannerProps {
  householdId: string
  candidates: GroupCandidateOut[]
  accounts: AccountOut[]
}

export function GroupCandidateBanner({
  householdId,
  candidates,
  accounts,
}: GroupCandidateBannerProps) {
  const [dismissed, setDismissed] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [dismissedPairs, setDismissedPairs] = useState<Set<string>>(new Set())
  const [merging, setMerging] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const createGroup = useCreateAccountGroupApiV1HouseholdsHouseholdIdAccountsGroupsPost()

  const activeCandidates = candidates.filter(
    (c) => !dismissedPairs.has(`${c.account_a_id}:${c.account_b_id}`)
  )

  if (dismissed || activeCandidates.length === 0) return null

  const accountName = (id: string) => {
    const a = accounts.find((acc) => acc.id === id)
    return a ? `${a.institution ? `${a.institution} — ` : ''}${a.name}` : id
  }

  const handleMerge = async (candidate: GroupCandidateOut) => {
    const key = `${candidate.account_a_id}:${candidate.account_b_id}`
    setMerging(key)
    setError(null)
    try {
      await createGroup.mutateAsync({
        householdId,
        data: {
          name: `${accountName(candidate.account_a_id)} (group)`,
          member_account_ids: [candidate.account_a_id, candidate.account_b_id],
        },
      })
      setDismissedPairs((prev) => new Set(prev).add(key))
      await queryClient.invalidateQueries({
        queryKey: getListAccountsApiV1HouseholdsHouseholdIdAccountsGetQueryKey(householdId),
      })
      await queryClient.invalidateQueries({
        queryKey:
          getListAccountGroupsApiV1HouseholdsHouseholdIdAccountsGroupsGetQueryKey(householdId),
      })
      await queryClient.invalidateQueries({
        queryKey:
          getFindGroupCandidatesApiV1HouseholdsHouseholdIdAccountsGroupsCandidatesGetQueryKey(
            householdId
          ),
      })
    } catch {
      setError('Merge failed. Try again.')
    } finally {
      setMerging(null)
    }
  }

  const handleDismissPair = (candidate: GroupCandidateOut) => {
    setDismissedPairs((prev) =>
      new Set(prev).add(`${candidate.account_a_id}:${candidate.account_b_id}`)
    )
  }

  return (
    <>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 14px',
          borderRadius: 10,
          background: 'color-mix(in oklch, var(--warning) 12%, transparent)',
          border: '1px solid color-mix(in oklch, var(--warning) 35%, transparent)',
          cursor: 'pointer',
        }}
        onClick={() => setShowModal(true)}
      >
        <AlertTriangle size={14} style={{ color: 'var(--warning)', flexShrink: 0 }} />
        <span style={{ flex: 1, fontSize: 13, color: 'var(--fg-primary)' }}>
          {activeCandidates.length === 1
            ? '1 account may be a duplicate — review'
            : `${activeCandidates.length} accounts may be duplicates — review`}
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation()
            setDismissed(true)
          }}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--fg-muted)',
            padding: 2,
            display: 'flex',
          }}
          aria-label="Dismiss"
        >
          <X size={14} />
        </button>
      </div>

      {showModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 50,
            padding: 24,
          }}
          onClick={() => setShowModal(false)}
        >
          <div
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: 16,
              padding: 24,
              width: '100%',
              maxWidth: 480,
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)' }}>
                Possible duplicates
              </span>
              <button
                onClick={() => setShowModal(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--fg-muted)',
                  display: 'flex',
                }}
              >
                <X size={16} />
              </button>
            </div>

            {error && (
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--danger)',
                  padding: '6px 10px',
                  background: 'color-mix(in oklch, var(--danger) 10%, transparent)',
                  borderRadius: 6,
                }}
              >
                {error}
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {activeCandidates.map((c) => {
                const key = `${c.account_a_id}:${c.account_b_id}`
                const isMerging = merging === key
                return (
                  <div
                    key={key}
                    style={{
                      border: '1px solid var(--border)',
                      borderRadius: 10,
                      padding: '12px 14px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                    }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                      <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Account A</span>
                      <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
                        {accountName(c.account_a_id)}
                      </span>
                    </div>
                    <div style={{ height: 1, background: 'var(--border)' }} />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                      <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Account B</span>
                      <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
                        {accountName(c.account_b_id)}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>{c.reason}</div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        onClick={() => void handleMerge(c)}
                        disabled={isMerging}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 5,
                          fontSize: 12,
                          fontWeight: 500,
                          padding: '6px 12px',
                          borderRadius: 6,
                          border: 'none',
                          background: isMerging ? 'var(--border)' : 'var(--accent)',
                          color: isMerging ? 'var(--fg-muted)' : 'var(--accent-fg)',
                          cursor: isMerging ? 'not-allowed' : 'pointer',
                        }}
                      >
                        <Check size={12} />
                        {isMerging ? 'Merging…' : 'Merge'}
                      </button>
                      <button
                        onClick={() => handleDismissPair(c)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 5,
                          fontSize: 12,
                          fontWeight: 500,
                          padding: '6px 12px',
                          borderRadius: 6,
                          border: '1px solid var(--border)',
                          background: 'transparent',
                          color: 'var(--fg-secondary)',
                          cursor: 'pointer',
                        }}
                      >
                        <XCircle size={12} /> Dismiss
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
