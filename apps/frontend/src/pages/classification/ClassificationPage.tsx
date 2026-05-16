import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useListCategoriesApiV1HouseholdsHouseholdIdCategoriesGet,
  useListTagsApiV1HouseholdsHouseholdIdTagsGet,
  useListRulesApiV1HouseholdsHouseholdIdRulesGet,
  useListIncomeSourcesApiV1HouseholdsHouseholdIdIncomeSourcesGet,
  useReclassifyAllApiV1HouseholdsHouseholdIdReclassifyAllPost,
} from '@/api/generated/classification/classification'
import { useListMembersApiV1HouseholdsHouseholdIdMembersGet } from '@/api/generated/households/households'
import { useListAccountsApiV1HouseholdsHouseholdIdAccountsGet } from '@/api/generated/accounts/accounts'
import { useHousehold } from '@/hooks/use-household'
import { CategoriesTab } from './CategoriesTab'
import { TagsTab } from './TagsTab'
import { RulesTab } from './RulesTab'
import { IncomeSourcesTab } from './IncomeSourcesTab'

type Tab = 'categories' | 'tags' | 'rules' | 'income-sources'

const TABS: { id: Tab; label: string }[] = [
  { id: 'categories', label: 'Categories' },
  { id: 'tags', label: 'Tags' },
  { id: 'rules', label: 'Rules' },
  { id: 'income-sources', label: 'Income Sources' },
]

export function ClassificationPage() {
  const { householdId } = useHousehold()
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('categories')
  const [confirmReclassify, setConfirmReclassify] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const hid = householdId ?? ''

  const { data: categories = [], isLoading: catsLoading } =
    useListCategoriesApiV1HouseholdsHouseholdIdCategoriesGet(hid, {
      query: { enabled: !!hid },
    })

  const { data: tags = [], isLoading: tagsLoading } = useListTagsApiV1HouseholdsHouseholdIdTagsGet(
    hid,
    {
      query: { enabled: !!hid },
    }
  )

  const { data: rules = [], isLoading: rulesLoading } =
    useListRulesApiV1HouseholdsHouseholdIdRulesGet(hid, {
      query: { enabled: !!hid },
    })

  const { data: incomeSources = [], isLoading: incomeLoading } =
    useListIncomeSourcesApiV1HouseholdsHouseholdIdIncomeSourcesGet(hid, {
      query: { enabled: !!hid },
    })

  const { data: members = [] } = useListMembersApiV1HouseholdsHouseholdIdMembersGet(hid, {
    query: { enabled: !!hid },
  })

  const { data: accounts = [] } = useListAccountsApiV1HouseholdsHouseholdIdAccountsGet(
    hid,
    undefined,
    {
      query: { enabled: !!hid },
    }
  )

  const reclassifyAll = useReclassifyAllApiV1HouseholdsHouseholdIdReclassifyAllPost({
    mutation: {
      onSuccess: (data) => {
        showToast(`Reclassification started (job ${data.job_id})`)
        setConfirmReclassify(false)
      },
      onError: () => {
        showToast('Reclassification failed. Try again.')
        setConfirmReclassify(false)
      },
    },
  })

  function showToast(msg: string) {
    if (toastTimer.current) clearTimeout(toastTimer.current)
    setToast(msg)
    toastTimer.current = setTimeout(() => setToast(null), 4000)
  }

  const loading = catsLoading || tagsLoading || rulesLoading || incomeLoading

  if (!householdId) {
    return <div style={{ padding: 32, color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        gap: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '16px 24px 0',
          flexShrink: 0,
        }}
      >
        <h1
          style={{
            fontSize: 22,
            fontWeight: 600,
            color: 'var(--fg-primary)',
            margin: '0 0 16px',
            letterSpacing: '-0.01em',
          }}
        >
          Classification
        </h1>

        {/* Tab bar */}
        <div
          style={{
            display: 'flex',
            gap: 2,
            borderBottom: '1px solid var(--border)',
          }}
        >
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              style={{
                padding: '8px 16px',
                fontSize: 13,
                fontWeight: tab === t.id ? 600 : 400,
                color: tab === t.id ? 'var(--accent)' : 'var(--fg-secondary)',
                background: 'none',
                border: 'none',
                borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
                marginBottom: -1,
                cursor: 'pointer',
                transition: 'color 0.15s, border-color 0.15s',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, padding: '20px 24px' }}>
        {loading ? (
          <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>
        ) : tab === 'categories' ? (
          <CategoriesTab householdId={hid} categories={categories} qc={qc} />
        ) : tab === 'tags' ? (
          <TagsTab householdId={hid} tags={tags} qc={qc} />
        ) : tab === 'rules' ? (
          <RulesTab householdId={hid} rules={rules} categories={categories} tags={tags} qc={qc} />
        ) : (
          <IncomeSourcesTab
            householdId={hid}
            incomeSources={incomeSources}
            members={members}
            accounts={accounts}
            qc={qc}
          />
        )}

        {/* Reclassify all section */}
        <div
          style={{
            marginTop: 40,
            paddingTop: 20,
            borderTop: '1px solid var(--border)',
          }}
        >
          <div style={{ fontSize: 13, color: 'var(--fg-secondary)', marginBottom: 8 }}>
            Re-run the classification pipeline on all transactions. Manually categorized
            transactions will not be changed.
          </div>
          <button
            type="button"
            onClick={() => setConfirmReclassify(true)}
            style={{
              padding: '7px 14px',
              fontSize: 13,
              fontWeight: 500,
              color: 'var(--fg-primary)',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              cursor: 'pointer',
            }}
          >
            Reclassify all transactions
          </button>
        </div>
      </div>

      {/* Confirm reclassify dialog */}
      {confirmReclassify && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 200,
          }}
          onClick={() => setConfirmReclassify(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: 24,
              width: 380,
              boxShadow: 'var(--shadow)',
            }}
          >
            <h2
              style={{
                fontSize: 16,
                fontWeight: 600,
                color: 'var(--fg-primary)',
                margin: '0 0 8px',
              }}
            >
              Reclassify all transactions?
            </h2>
            <p
              style={{
                fontSize: 13,
                color: 'var(--fg-secondary)',
                margin: '0 0 20px',
                lineHeight: 1.5,
              }}
            >
              This will re-run the classification pipeline on all transactions. Manually categorized
              transactions will not be changed.
            </p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setConfirmReclassify(false)}
                style={{
                  padding: '7px 14px',
                  fontSize: 13,
                  background: 'none',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: 'var(--fg-secondary)',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={reclassifyAll.isPending}
                onClick={() => reclassifyAll.mutate({ householdId: hid })}
                style={{
                  padding: '7px 14px',
                  fontSize: 13,
                  fontWeight: 500,
                  background: 'var(--accent)',
                  border: 'none',
                  borderRadius: 8,
                  color: 'var(--accent-fg)',
                  cursor: reclassifyAll.isPending ? 'not-allowed' : 'pointer',
                  opacity: reclassifyAll.isPending ? 0.7 : 1,
                }}
              >
                {reclassifyAll.isPending ? 'Starting...' : 'Reclassify'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            background: 'var(--fg-primary)',
            color: 'var(--bg-primary)',
            padding: '10px 16px',
            borderRadius: 8,
            fontSize: 13,
            zIndex: 300,
            boxShadow: 'var(--shadow)',
          }}
        >
          {toast}
        </div>
      )}
    </div>
  )
}
