import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Pencil } from 'lucide-react'
import { useListAccountsApiV1HouseholdsHouseholdIdAccountsGet } from '@/api/generated/accounts/accounts'
import {
  useListPlansApiV1HouseholdsHouseholdIdDebtPlansGet,
  useGetSummaryApiV1HouseholdsHouseholdIdDebtPlansPlanIdSummaryGet,
} from '@/api/generated/default/default'
import { useHousehold } from '@/hooks/use-household'
import { formatAmount } from '@/lib/format-amount'
import { isLiabilityType } from '@/domain/accounts'
import type { AccountOut } from '@/api/generated/model/accountOut'
import type { DebtPlanOut } from '@/api/generated/model/debtPlanOut'
import { DebtPlanSetupModal } from './DebtPlanSetupModal'

function methodLabel(method: string): string {
  const map: Record<string, string> = {
    avalanche: 'Avalanche',
    snowball: 'Snowball',
    custom: 'Custom',
    none: 'Track only',
  }
  return map[method] ?? method
}

function Badge({ label, color = 'var(--fg-muted)' }: { label: string; color?: string }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 8px',
        borderRadius: 99,
        fontSize: 11,
        fontWeight: 500,
        background: `color-mix(in oklch, ${color} 15%, transparent)`,
        color,
        border: `1px solid color-mix(in oklch, ${color} 30%, transparent)`,
      }}
    >
      {label}
    </span>
  )
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Unknown'
  const parts = dateStr.split('-')
  const y = parseInt(parts[0] ?? '2000', 10)
  const m = parseInt(parts[1] ?? '1', 10)
  const d = parseInt(parts[2] ?? '1', 10)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', {
    month: 'short',
    year: 'numeric',
  })
}

function DebtAccountCard({ account, plan }: { account: AccountOut; plan: DebtPlanOut | null }) {
  const balance = parseFloat(account.current_balance)
  const absBalance = Math.abs(balance)

  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '16px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>
            {account.name}
          </div>
          {account.institution && (
            <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{account.institution}</div>
          )}
        </div>
        <span
          style={{
            fontSize: 11,
            color: 'var(--fg-muted)',
            background: 'var(--bg-secondary)',
            padding: '2px 8px',
            borderRadius: 4,
            flexShrink: 0,
          }}
        >
          {account.account_type}
        </span>
      </div>

      <div
        style={{
          fontSize: 24,
          fontWeight: 700,
          fontFamily: "'Geist Mono', monospace",
          color: 'var(--danger)',
          letterSpacing: '-0.02em',
        }}
      >
        {formatAmount(absBalance, { currency: account.currency })}
      </div>

      {/* Progress bar: shows proportion of balance relative to itself (placeholder visual) */}
      <div
        style={{
          height: 6,
          borderRadius: 99,
          background: 'color-mix(in oklch, var(--danger) 20%, var(--border))',
        }}
      >
        <div
          style={{
            height: '100%',
            width: '100%',
            borderRadius: 99,
            background: 'var(--danger)',
            opacity: 0.6,
          }}
        />
      </div>

      {plan && (
        <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
          Part of {methodLabel(plan.method)} plan
        </div>
      )}
    </div>
  )
}

function SummaryHeader({
  accounts,
  plan,
  householdId,
}: {
  accounts: AccountOut[]
  plan: DebtPlanOut | null
  householdId: string
}) {
  const totalDebt = accounts.reduce((s, a) => s + Math.abs(parseFloat(a.current_balance)), 0)

  const { data: summary } = useGetSummaryApiV1HouseholdsHouseholdIdDebtPlansPlanIdSummaryGet(
    householdId,
    plan?.id ?? '',
    { query: { enabled: !!plan?.id && !!householdId } }
  )

  const currency = accounts[0]?.currency ?? 'USD'

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
        gap: 12,
        padding: '16px 18px',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 12,
      }}
    >
      <div>
        <div
          style={{
            fontSize: 11,
            color: 'var(--fg-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            marginBottom: 4,
          }}
        >
          Total debt
        </div>
        <div
          style={{
            fontSize: 22,
            fontWeight: 700,
            fontFamily: "'Geist Mono', monospace",
            color: 'var(--danger)',
            letterSpacing: '-0.02em',
          }}
        >
          {formatAmount(totalDebt, { currency })}
        </div>
      </div>

      {plan && (
        <div>
          <div
            style={{
              fontSize: 11,
              color: 'var(--fg-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              marginBottom: 4,
            }}
          >
            Plan
          </div>
          <Badge label={methodLabel(plan.method)} color="var(--accent)" />
        </div>
      )}

      {summary && (
        <>
          <div>
            <div
              style={{
                fontSize: 11,
                color: 'var(--fg-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                marginBottom: 4,
              }}
            >
              Payoff date
            </div>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)' }}>
              {formatDate(summary.payoff_date)}
            </div>
          </div>
          <div>
            <div
              style={{
                fontSize: 11,
                color: 'var(--fg-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                marginBottom: 4,
              }}
            >
              Interest savings
            </div>
            <div
              style={{
                fontSize: 15,
                fontWeight: 600,
                color: 'var(--success)',
                fontFamily: "'Geist Mono', monospace",
              }}
            >
              {formatAmount(summary.interest_savings_vs_minimums, { currency: summary.currency })}
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>vs minimums only</div>
          </div>
        </>
      )}
    </div>
  )
}

export function DebtsPage() {
  const { householdId } = useHousehold()
  const navigate = useNavigate()
  const [showSetup, setShowSetup] = useState(false)

  const hid = householdId ?? ''

  const { data: allAccounts = [], isLoading: accountsLoading } =
    useListAccountsApiV1HouseholdsHouseholdIdAccountsGet(hid, undefined, {
      query: { enabled: !!hid },
    })

  const liabilityAccounts = allAccounts.filter((a) => isLiabilityType(a.account_type))

  const { data: plans = [], isLoading: plansLoading } =
    useListPlansApiV1HouseholdsHouseholdIdDebtPlansGet(hid, {
      query: { enabled: !!hid },
    })

  const activePlan = plans[0] ?? null
  const isLoading = accountsLoading || plansLoading

  if (!householdId) {
    return <div style={{ padding: 32, color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div
        style={{
          padding: '16px 24px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <h1
          style={{
            fontSize: 22,
            fontWeight: 600,
            color: 'var(--fg-primary)',
            margin: 0,
            letterSpacing: '-0.01em',
          }}
        >
          Debts
        </h1>
        {activePlan ? (
          <button
            type="button"
            onClick={() => navigate(`/debts/plan/${activePlan.id}`)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '7px 14px',
              background: 'none',
              color: 'var(--accent)',
              border: '1px solid var(--accent)',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            <Pencil size={13} />
            View plan
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setShowSetup(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '7px 14px',
              background: 'var(--accent)',
              color: 'var(--accent-fg)',
              border: 'none',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            <Plus size={14} />
            Create debt plan
          </button>
        )}
      </div>

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        {isLoading ? (
          <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>
        ) : liabilityAccounts.length === 0 ? (
          <div
            style={{
              color: 'var(--fg-muted)',
              fontSize: 13,
              padding: '40px 0',
              textAlign: 'center' as const,
            }}
          >
            No liability accounts found. Add a credit card, loan, or line of credit account to track
            debts.
          </div>
        ) : (
          <>
            <SummaryHeader accounts={liabilityAccounts} plan={activePlan} householdId={hid} />

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                gap: 12,
              }}
            >
              {liabilityAccounts.map((acct) => (
                <DebtAccountCard key={acct.id} account={acct} plan={activePlan} />
              ))}
            </div>
          </>
        )}
      </div>

      {showSetup && (
        <DebtPlanSetupModal
          householdId={hid}
          liabilityAccounts={liabilityAccounts}
          onClose={() => setShowSetup(false)}
          onCreated={(id) => {
            setShowSetup(false)
            navigate(`/debts/plan/${id}`)
          }}
        />
      )}
    </div>
  )
}
