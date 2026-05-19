import { useState, useMemo } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, RefreshCw, AlertCircle } from 'lucide-react'
import { useHousehold } from '@/hooks/use-household'
import {
  usePreviewSimplefinAccountsApiV1HouseholdsHouseholdIdIngestSyncConfigsConfigIdPreviewGet,
  useSaveAccountMappingApiV1HouseholdsHouseholdIdIngestSyncConfigsConfigIdMappingPost,
  useListSyncConfigsApiV1HouseholdsHouseholdIdIngestSyncConfigsGet,
} from '@/api/generated/ingest/ingest'
import { useListAccountsApiV1HouseholdsHouseholdIdAccountsGet } from '@/api/generated/accounts/accounts'
import type { SimplefinAccountPreview } from '@/api/generated/model/simplefinAccountPreview'
import type { AccountOut } from '@/api/generated/model/accountOut'
import type { MappingDecision } from '@/api/generated/model/mappingDecision'

type RowAction = 'create' | 'map' | 'ignore'

interface RowState {
  action: RowAction
  newName: string
  newType: string
  newCurrency: string
  mapToAccountId: string
}

const ACCOUNT_TYPES = [
  { value: 'checking', label: 'Checking' },
  { value: 'savings', label: 'Savings' },
  { value: 'credit_card', label: 'Credit Card' },
  { value: 'investment', label: 'Investment' },
  { value: 'loan', label: 'Loan' },
  { value: 'mortgage', label: 'Mortgage' },
  { value: 'other_asset', label: 'Other Asset' },
  { value: 'other_liability', label: 'Other Liability' },
]

function rowValid(s: RowState): boolean {
  if (s.action === 'create') return s.newName.trim().length > 0
  if (s.action === 'map') return s.mapToAccountId.length > 0
  return true
}

function AccountRow({
  preview,
  state,
  accounts,
  onChange,
}: {
  preview: SimplefinAccountPreview
  state: RowState
  accounts: AccountOut[]
  onChange: (s: RowState) => void
}) {
  return (
    <div
      style={{
        padding: '14px 16px',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 12,
          flexWrap: 'wrap' as const,
        }}
      >
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>
            {preview.account_name}
            {preview.account_number_last4 && (
              <span
                style={{ fontWeight: 400, color: 'var(--fg-muted)', marginLeft: 6, fontSize: 13 }}
              >
                &middot;&middot;&middot;{preview.account_number_last4}
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
            {preview.balance} {preview.currency} &middot; suggested:{' '}
            {ACCOUNT_TYPES.find((t) => t.value === preview.suggested_type)?.label ??
              preview.suggested_type}
          </div>
        </div>
        <select
          value={state.action}
          onChange={(e) => {
            const action = e.target.value as RowAction
            onChange({ ...state, action })
          }}
          style={{
            fontSize: 12,
            padding: '5px 8px',
            borderRadius: 6,
            border: '1px solid var(--border)',
            background: 'var(--bg-secondary)',
            color: 'var(--fg-primary)',
            cursor: 'pointer',
            flexShrink: 0,
          }}
        >
          <option value="create">Create new account</option>
          <option value="map">Map to existing</option>
          <option value="ignore">Ignore</option>
        </select>
      </div>

      {state.action === 'create' && (
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            type="text"
            value={state.newName}
            onChange={(e) => onChange({ ...state, newName: e.target.value })}
            placeholder="Account name"
            style={{
              flex: 1,
              fontSize: 12,
              padding: '6px 10px',
              borderRadius: 6,
              border: `1px solid ${state.newName.trim() ? 'var(--border)' : 'var(--danger)'}`,
              background: 'var(--bg-secondary)',
              color: 'var(--fg-primary)',
              minWidth: 0,
            }}
          />
          <select
            value={state.newType}
            onChange={(e) => onChange({ ...state, newType: e.target.value })}
            style={{
              fontSize: 12,
              padding: '6px 8px',
              borderRadius: 6,
              border: '1px solid var(--border)',
              background: 'var(--bg-secondary)',
              color: 'var(--fg-primary)',
              cursor: 'pointer',
              flexShrink: 0,
            }}
          >
            {ACCOUNT_TYPES.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      )}

      {state.action === 'map' && (
        <select
          value={state.mapToAccountId}
          onChange={(e) => onChange({ ...state, mapToAccountId: e.target.value })}
          style={{
            fontSize: 12,
            padding: '6px 10px',
            borderRadius: 6,
            border: `1px solid ${state.mapToAccountId ? 'var(--border)' : 'var(--danger)'}`,
            background: 'var(--bg-secondary)',
            color: 'var(--fg-primary)',
            cursor: 'pointer',
            width: '100%',
          }}
        >
          <option value="">Select an existing account...</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
              {a.institution ? ` (${a.institution})` : ''}
            </option>
          ))}
        </select>
      )}
    </div>
  )
}

function SkeletonRow() {
  return (
    <div
      style={{
        height: 72,
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        opacity: 0.6,
      }}
    />
  )
}

export function AccountMappingPage() {
  const navigate = useNavigate()
  const { syncConfigId } = useParams<{ syncConfigId: string }>()
  const [searchParams] = useSearchParams()
  const isWizard = searchParams.get('wizard') === 'true'
  const { householdId } = useHousehold()

  const [rowState, setRowState] = useState<Record<string, RowState>>({})

  const {
    data: preview,
    isLoading: previewLoading,
    isError: previewError,
    refetch,
  } = usePreviewSimplefinAccountsApiV1HouseholdsHouseholdIdIngestSyncConfigsConfigIdPreviewGet(
    householdId ?? '',
    syncConfigId ?? '',
    { query: { enabled: !!householdId && !!syncConfigId, staleTime: 300_000 } }
  )

  const { data: allConfigs } = useListSyncConfigsApiV1HouseholdsHouseholdIdIngestSyncConfigsGet(
    householdId ?? '',
    {
      query: { enabled: !!householdId },
    }
  )

  const { data: existingAccounts } = useListAccountsApiV1HouseholdsHouseholdIdAccountsGet(
    householdId ?? '',
    undefined,
    {
      query: { enabled: !!householdId },
    }
  )

  const saveMut =
    useSaveAccountMappingApiV1HouseholdsHouseholdIdIngestSyncConfigsConfigIdMappingPost()

  const configLabel =
    allConfigs?.find((c) => c.id === syncConfigId)?.label ?? 'SimpleFIN Connection'

  const grouped = useMemo(() => {
    if (!preview) return []
    const map = new Map<string, SimplefinAccountPreview[]>()
    for (const acc of preview) {
      const key = acc.institution_name
      if (!map.has(key)) map.set(key, [])
      const bucket = map.get(key)
      if (bucket) bucket.push(acc)
    }
    return [...map.entries()]
  }, [preview])

  function getRow(acc: SimplefinAccountPreview): RowState {
    return (
      rowState[acc.simplefin_account_id] ?? {
        action: 'create',
        newName: acc.account_name,
        newType: acc.suggested_type,
        newCurrency: acc.currency,
        mapToAccountId: '',
      }
    )
  }

  const canSave = !!preview && preview.length > 0 && preview.every((acc) => rowValid(getRow(acc)))

  function handleSave() {
    if (!householdId || !syncConfigId || !preview || !canSave) return
    const decisions: MappingDecision[] = preview.map((acc) => {
      const s = getRow(acc)
      if (s.action === 'create') {
        return {
          simplefin_account_id: acc.simplefin_account_id,
          action: 'create' as const,
          authoritative: true,
          new_account: { name: s.newName.trim(), type: s.newType, currency: s.newCurrency },
        }
      } else if (s.action === 'map') {
        return {
          simplefin_account_id: acc.simplefin_account_id,
          action: 'map' as const,
          system_account_id: s.mapToAccountId,
          authoritative: true,
        }
      } else {
        return {
          simplefin_account_id: acc.simplefin_account_id,
          action: 'ignore' as const,
        }
      }
    })

    saveMut.mutate(
      { householdId, configId: syncConfigId, data: decisions },
      {
        onSuccess: (result) => {
          if (isWizard) {
            const params = new URLSearchParams({
              done: 'true',
              label: configLabel,
              created: String(result.accounts_created),
              mapped: String(result.accounts_mapped),
            })
            void navigate(`/settings/ingest/connect?${params.toString()}`)
          } else {
            void navigate('/settings/ingest')
          }
        },
      }
    )
  }

  const backTo = isWizard ? undefined : '/settings/ingest'

  return (
    <div style={{ maxWidth: 640, margin: '0 auto', padding: '32px 24px' }}>
      <button
        onClick={() => void navigate(backTo ?? '/settings/ingest')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 13,
          color: 'var(--fg-muted)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '0 0 20px',
          marginBottom: 4,
        }}
      >
        <ArrowLeft size={14} /> {isWizard ? 'Cancel' : 'Connected Accounts'}
      </button>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 12,
          marginBottom: 24,
        }}
      >
        <div>
          <h1
            style={{
              fontSize: 20,
              fontWeight: 600,
              color: 'var(--fg-primary)',
              margin: '0 0 4px',
              letterSpacing: '-0.01em',
            }}
          >
            Map accounts
          </h1>
          <p style={{ fontSize: 13, color: 'var(--fg-muted)', margin: 0 }}>
            {configLabel} &mdash; choose what to do with each bank account
          </p>
        </div>
        {previewError && (
          <button
            onClick={() => void refetch()}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              padding: '6px 12px',
              borderRadius: 7,
              border: '1px solid var(--border)',
              background: 'var(--bg-secondary)',
              color: 'var(--fg-primary)',
              cursor: 'pointer',
            }}
          >
            <RefreshCw size={12} /> Retry
          </button>
        )}
      </div>

      {previewLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div
            style={{
              height: 24,
              width: 120,
              background: 'var(--bg-elevated)',
              borderRadius: 6,
              opacity: 0.6,
            }}
          />
          {[1, 2, 3].map((i) => (
            <SkeletonRow key={i} />
          ))}
        </div>
      )}

      {previewError && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 10,
            padding: '40px 24px',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            textAlign: 'center' as const,
          }}
        >
          <AlertCircle size={24} style={{ color: 'var(--danger)' }} />
          <div style={{ fontSize: 14, color: 'var(--fg-primary)', fontWeight: 500 }}>
            Could not fetch accounts from SimpleFIN
          </div>
          <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
            SimpleFIN may be temporarily unavailable. Try again in a moment.
          </div>
        </div>
      )}

      {!previewLoading && !previewError && preview && preview.length === 0 && (
        <div
          style={{
            padding: '40px 24px',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            textAlign: 'center' as const,
            color: 'var(--fg-muted)',
            fontSize: 14,
          }}
        >
          No accounts found in this SimpleFIN connection.
        </div>
      )}

      {!previewLoading && !previewError && preview && preview.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
          {grouped.map(([institution, accounts]) => (
            <div key={institution}>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--fg-muted)',
                  textTransform: 'uppercase' as const,
                  letterSpacing: '0.06em',
                  marginBottom: 10,
                }}
              >
                {institution}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {accounts.map((acc) => (
                  <AccountRow
                    key={acc.simplefin_account_id}
                    preview={acc}
                    state={getRow(acc)}
                    accounts={existingAccounts ?? []}
                    onChange={(s) =>
                      setRowState((prev) => ({
                        ...prev,
                        [acc.simplefin_account_id]: s,
                      }))
                    }
                  />
                ))}
              </div>
            </div>
          ))}

          {saveMut.isError && (
            <div
              style={{
                fontSize: 13,
                padding: '10px 14px',
                borderRadius: 8,
                background: 'color-mix(in oklch, var(--danger) 10%, transparent)',
                border: '1px solid color-mix(in oklch, var(--danger) 30%, transparent)',
                color: 'var(--danger)',
              }}
            >
              Failed to save mapping. Please try again.
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, paddingTop: 4 }}>
            <button
              onClick={() => void navigate(isWizard ? '/settings/ingest' : '/settings/ingest')}
              style={{
                fontSize: 13,
                padding: '8px 18px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-secondary)',
                color: 'var(--fg-primary)',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!canSave || saveMut.isPending}
              style={{
                fontSize: 13,
                fontWeight: 600,
                padding: '8px 20px',
                borderRadius: 8,
                background: 'var(--accent)',
                color: 'var(--accent-fg)',
                border: 'none',
                cursor: !canSave || saveMut.isPending ? 'not-allowed' : 'pointer',
                opacity: !canSave || saveMut.isPending ? 0.6 : 1,
              }}
            >
              {saveMut.isPending ? 'Saving...' : 'Save mapping'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
