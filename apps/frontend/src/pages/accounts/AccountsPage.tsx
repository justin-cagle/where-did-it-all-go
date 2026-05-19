import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { useHousehold } from '@/hooks/use-household'
import { useQueryClient } from '@tanstack/react-query'
import {
  useListAccountsApiV1HouseholdsHouseholdIdAccountsGet,
  useFindGroupCandidatesApiV1HouseholdsHouseholdIdAccountsGroupsCandidatesGet,
  getGetAccountApiV1HouseholdsHouseholdIdAccountsAccountIdGetQueryOptions,
} from '@/api/generated/accounts/accounts'
import { useGetHouseholdApiV1HouseholdsHouseholdIdGet } from '@/api/generated/households/households'
import { useListSyncConfigsApiV1HouseholdsHouseholdIdIngestSyncConfigsGet } from '@/api/generated/ingest/ingest'
import type { AccountOut } from '@/api/generated/model/accountOut'
import type { SyncConfigOut } from '@/api/generated/model/syncConfigOut'
import { useAuthStore } from '@/store'
import { fmt } from '@/lib/format'
import type { PrivacyMode } from '@/lib/format'
import {
  groupAccounts,
  calcNetWorth,
  groupTotal,
  isLiabilityType,
  accountTypeLabel,
} from '@/domain/accounts'
import type { AccountGroupConfig } from '@/domain/accounts'
import { AddAccountModal } from './AddAccountModal'
import { GroupCandidateBanner } from './GroupCandidateBanner'

const SYNC_STATUS_CFG: Record<string, { color: string; label: string }> = {
  active: { color: 'var(--success)', label: 'Syncing' },
  warning: { color: 'var(--warning)', label: 'Warning' },
  rate_limited: { color: 'oklch(62% 0.18 42)', label: 'Paused' },
  error: { color: 'var(--danger)', label: 'Error' },
  disabled: { color: 'var(--fg-muted)', label: 'Disabled' },
}
const DEFAULT_SYNC_CFG = { color: 'var(--fg-muted)', label: 'Unknown' }

function SyncStatusBadge({ status }: { status: string }) {
  const navigate = useNavigate()
  const cfg = SYNC_STATUS_CFG[status] ?? DEFAULT_SYNC_CFG
  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        void navigate('/settings/ingest')
      }}
      title={`Sync status: ${cfg.label} — click to manage`}
      style={{
        fontSize: 10,
        fontWeight: 600,
        padding: '2px 7px',
        borderRadius: 99,
        background: `color-mix(in oklch, ${cfg.color} 14%, transparent)`,
        color: cfg.color,
        border: 'none',
        cursor: 'pointer',
        letterSpacing: '0.03em',
        flexShrink: 0,
      }}
    >
      {cfg.label}
    </button>
  )
}

function TypeBadge({ type }: { type: string }) {
  const isLiab = isLiabilityType(type)
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 600,
        padding: '2px 7px',
        borderRadius: 99,
        background: isLiab
          ? 'color-mix(in oklch, var(--danger) 14%, transparent)'
          : 'color-mix(in oklch, var(--accent) 14%, transparent)',
        color: isLiab ? 'var(--danger)' : 'var(--accent)',
        letterSpacing: '0.04em',
        textTransform: 'uppercase' as const,
        whiteSpace: 'nowrap' as const,
        flexShrink: 0,
      }}
    >
      {accountTypeLabel(type)}
    </span>
  )
}

function AccountCard({
  account,
  householdId,
  syncConfigs,
  homeCurrency,
}: {
  account: AccountOut
  householdId: string
  syncConfigs: SyncConfigOut[]
  homeCurrency: string
}) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const privacyMode = useAuthStore((s) => s.privacyMode)
  const balance = parseFloat(account.current_balance)
  const isLiab = isLiabilityType(account.account_type)
  const syncConfig = account.authoritative_sync_config_id
    ? syncConfigs.find((c) => c.id === account.authoritative_sync_config_id)
    : undefined

  function handleMouseEnter() {
    hoverTimer.current = setTimeout(() => {
      void qc.prefetchQuery(
        getGetAccountApiV1HouseholdsHouseholdIdAccountsAccountIdGetQueryOptions(
          householdId,
          account.id
        )
      )
    }, 300)
  }

  function handleMouseLeave() {
    if (hoverTimer.current) clearTimeout(hoverTimer.current)
  }

  return (
    <div
      onClick={() => void navigate(`/accounts/${account.id}`)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter') void navigate(`/accounts/${account.id}`)
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '16px 18px',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 8,
        }}
      >
        <div style={{ minWidth: 0 }}>
          {account.institution && (
            <div
              style={{
                fontSize: 11,
                color: 'var(--fg-muted)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {account.institution}
            </div>
          )}
          <div
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: 'var(--fg-primary)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {account.name}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          {syncConfig && syncConfig.status !== 'active' && (
            <SyncStatusBadge status={syncConfig.status} />
          )}
          {account.currency !== homeCurrency && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                padding: '2px 7px',
                borderRadius: 99,
                background: 'color-mix(in oklch, var(--warning, #f59e0b) 14%, transparent)',
                color: '#f59e0b',
                letterSpacing: '0.04em',
                fontFamily: 'var(--font-mono)',
                flexShrink: 0,
              }}
            >
              {account.currency}
            </span>
          )}
          <TypeBadge type={account.account_type} />
        </div>
      </div>
      <span
        style={{
          fontSize: 20,
          fontWeight: 700,
          fontFamily: 'var(--font-mono)',
          letterSpacing: '-0.02em',
          color: isLiab ? 'var(--danger)' : 'var(--fg-primary)',
        }}
      >
        {fmt(balance, privacyMode, account.currency)}
      </span>
    </div>
  )
}

function AccountGroupSection({
  config,
  accounts,
  privacyMode,
  householdId,
  syncConfigs,
  homeCurrency,
}: {
  config: AccountGroupConfig
  accounts: AccountOut[]
  privacyMode: PrivacyMode
  householdId: string
  syncConfigs: SyncConfigOut[]
  homeCurrency: string
}) {
  const total = groupTotal(accounts)
  const isLiab = config.types.some((t) => isLiabilityType(t))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          padding: '0 2px',
        }}
      >
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--fg-muted)',
            textTransform: 'uppercase' as const,
            letterSpacing: '0.06em',
          }}
        >
          {config.label}
        </span>
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            fontFamily: 'var(--font-mono)',
            color: isLiab ? 'var(--danger)' : 'var(--fg-primary)',
          }}
        >
          {fmt(total, privacyMode)}
        </span>
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 10,
        }}
      >
        {accounts.map((a) => (
          <AccountCard
            key={a.id}
            account={a}
            householdId={householdId}
            syncConfigs={syncConfigs}
            homeCurrency={homeCurrency}
          />
        ))}
      </div>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        height: 88,
        opacity: 0.6,
      }}
    />
  )
}

function PageHeader({
  netWorth,
  privacyMode,
  onAdd,
  isApproximate = false,
}: {
  netWorth: number
  privacyMode: PrivacyMode
  onAdd: () => void
  isApproximate?: boolean
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: 16,
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
          Accounts
        </h1>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 4 }}>
          <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Net worth</span>
          <span
            style={{
              fontSize: 22,
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '-0.02em',
              color: netWorth >= 0 ? 'var(--fg-primary)' : 'var(--danger)',
            }}
          >
            {fmt(netWorth, { privacyMode, isApproximate })}
          </span>
        </div>
      </div>
      <button
        onClick={onAdd}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 13,
          fontWeight: 500,
          padding: '8px 16px',
          borderRadius: 8,
          background: 'var(--accent)',
          color: 'var(--accent-fg)',
          border: 'none',
          cursor: 'pointer',
          whiteSpace: 'nowrap' as const,
          flexShrink: 0,
        }}
      >
        <Plus size={13} /> Add account
      </button>
    </div>
  )
}

export function AccountsPage() {
  const { householdId, isLoading: householdLoading } = useHousehold()
  const privacyMode = useAuthStore((s) => s.privacyMode)
  const [showAddModal, setShowAddModal] = useState(false)

  const { data: household } = useGetHouseholdApiV1HouseholdsHouseholdIdGet(householdId ?? '', {
    query: { enabled: !!householdId },
  })
  const homeCurrency = household?.home_currency ?? 'USD'

  const {
    data: accounts,
    isLoading: accountsLoading,
    isError,
    refetch,
  } = useListAccountsApiV1HouseholdsHouseholdIdAccountsGet(householdId ?? '', undefined, {
    query: { enabled: !!householdId },
  })

  const { data: syncConfigs } = useListSyncConfigsApiV1HouseholdsHouseholdIdIngestSyncConfigsGet(
    householdId ?? '',
    {
      query: { enabled: !!householdId, staleTime: 60_000 },
    }
  )

  const { data: candidates } =
    useFindGroupCandidatesApiV1HouseholdsHouseholdIdAccountsGroupsCandidatesGet(householdId ?? '', {
      query: { enabled: !!householdId },
    })

  const isLoading = householdLoading || accountsLoading
  const netWorth = accounts ? calcNetWorth(accounts) : 0
  const grouped = accounts ? groupAccounts(accounts) : []
  const hasApproxFx = accounts ? accounts.some((a) => a.currency !== homeCurrency) : false

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <PageHeader
          netWorth={0}
          privacyMode={privacyMode}
          onAdd={() => setShowAddModal(true)}
          isApproximate={false}
        />
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 10,
          }}
        >
          {[1, 2, 3, 4].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
          padding: '48px 0',
        }}
      >
        <span style={{ color: 'var(--fg-muted)', fontSize: 14 }}>Failed to load accounts.</span>
        <button
          onClick={() => void refetch()}
          style={{
            fontSize: 13,
            padding: '7px 16px',
            borderRadius: 8,
            background: 'var(--accent)',
            color: 'var(--accent-fg)',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          Retry
        </button>
      </div>
    )
  }

  if (!accounts || accounts.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <PageHeader
          netWorth={0}
          privacyMode={privacyMode}
          onAdd={() => setShowAddModal(true)}
          isApproximate={false}
        />
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 16,
            padding: '64px 0',
          }}
        >
          <div style={{ fontSize: 48 }}>&#127968;</div>
          <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg-primary)' }}>
            Add your first account
          </div>
          <div
            style={{
              fontSize: 14,
              color: 'var(--fg-muted)',
              textAlign: 'center' as const,
              maxWidth: 320,
            }}
          >
            Connect banks, credit cards, investments, or track manual balances for net worth.
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 14,
              fontWeight: 500,
              padding: '9px 20px',
              borderRadius: 8,
              background: 'var(--accent)',
              color: 'var(--accent-fg)',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            <Plus size={14} /> Add account
          </button>
        </div>
        {householdId && (
          <AddAccountModal
            householdId={householdId}
            open={showAddModal}
            onClose={() => setShowAddModal(false)}
            defaultCurrency={homeCurrency}
          />
        )}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <PageHeader
        netWorth={netWorth}
        privacyMode={privacyMode}
        onAdd={() => setShowAddModal(true)}
        isApproximate={hasApproxFx}
      />

      {candidates && candidates.length > 0 && householdId && (
        <GroupCandidateBanner
          householdId={householdId}
          candidates={candidates}
          accounts={accounts}
        />
      )}

      {grouped.map(({ config, accounts: groupAccs }) => (
        <AccountGroupSection
          key={config.label}
          config={config}
          accounts={groupAccs}
          privacyMode={privacyMode}
          householdId={householdId ?? ''}
          syncConfigs={syncConfigs ?? []}
          homeCurrency={homeCurrency}
        />
      ))}

      {householdId && (
        <AddAccountModal
          householdId={householdId}
          open={showAddModal}
          onClose={() => setShowAddModal(false)}
          defaultCurrency={homeCurrency}
        />
      )}
    </div>
  )
}
