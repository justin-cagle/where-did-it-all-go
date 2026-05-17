import { useState } from 'react'
import { Plus, ChevronDown, ChevronRight, Trash2 } from 'lucide-react'
import {
  useListProvidersApiV1HouseholdsHouseholdIdInsightsProvidersGet,
  useCreateProviderApiV1HouseholdsHouseholdIdInsightsProvidersPost,
  useUpdateProviderApiV1HouseholdsHouseholdIdInsightsProvidersConfigIdPatch,
  useDeleteProviderApiV1HouseholdsHouseholdIdInsightsProvidersConfigIdDelete,
  useGetBudgetApiV1HouseholdsHouseholdIdInsightsBudgetGet,
  useUpdateBudgetApiV1HouseholdsHouseholdIdInsightsBudgetPatch,
} from '@/api/generated/insights/insights'
import { useHousehold } from '@/hooks/use-household'
import { formatAmount } from '@/lib/format-amount'
import { useQueryClient } from '@tanstack/react-query'
import type { ProviderConfigOut } from '@/api/generated/model/providerConfigOut'

const PROVIDER_TYPES = ['local_ollama', 'local_llamacpp', 'anthropic', 'openai', 'disabled']
const LOCAL_TYPES = new Set(['local_ollama', 'local_llamacpp'])

const AI_DATA_SHARING_OPTIONS = [
  {
    value: 'disabled',
    label: 'Disabled',
    description: 'No data sent to AI',
  },
  {
    value: 'generalizations_only',
    label: 'Generalizations only',
    description: 'Category names and patterns only',
  },
  {
    value: 'aggregates_only',
    label: 'Aggregates only',
    description: 'Category totals, no transaction detail',
  },
  {
    value: 'redacted',
    label: 'Redacted',
    description: 'Transaction structure, merchants hashed',
  },
  {
    value: 'full',
    label: 'Full',
    description: 'Full data (local providers only)',
  },
]

const OVERAGE_OPTIONS = [
  { value: 'block', label: 'Block' },
  { value: 'warn_and_continue', label: 'Warn and continue' },
  { value: 'silent', label: 'Silent' },
]

function ProviderRow({
  provider,
  householdId,
  onDeleted,
}: {
  provider: ProviderConfigOut
  householdId: string
  onDeleted: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [modelName, setModelName] = useState(provider.model_name ?? '')
  const [baseUrl, setBaseUrl] = useState(provider.base_url ?? '')
  const [sharing, setSharing] = useState(provider.ai_data_sharing)
  const [enabled, setEnabled] = useState(provider.enabled)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const update = useUpdateProviderApiV1HouseholdsHouseholdIdInsightsProvidersConfigIdPatch()
  const del = useDeleteProviderApiV1HouseholdsHouseholdIdInsightsProvidersConfigIdDelete()
  const qc = useQueryClient()

  const isLocal = LOCAL_TYPES.has(provider.provider)
  const statusColor = enabled ? 'var(--success)' : 'var(--fg-muted)'

  const handleSave = async () => {
    setSaving(true)
    try {
      await update.mutateAsync({
        householdId,
        configId: provider.id,
        data: {
          model_name: modelName || null,
          base_url: isLocal ? baseUrl || null : undefined,
          ai_data_sharing: sharing,
          enabled,
        },
      })
      await qc.invalidateQueries({
        queryKey: [`/api/v1/households/${householdId}/insights/providers`],
      })
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    await del.mutateAsync({ householdId, configId: provider.id })
    onDeleted()
  }

  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        overflow: 'hidden',
      }}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          width: '100%',
          padding: '12px 14px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontFamily: 'var(--font-sans)',
          textAlign: 'left',
        }}
      >
        {expanded ? (
          <ChevronDown size={14} style={{ color: 'var(--fg-muted)', flexShrink: 0 }} />
        ) : (
          <ChevronRight size={14} style={{ color: 'var(--fg-muted)', flexShrink: 0 }} />
        )}
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: statusColor,
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)', flex: 1 }}>
          {provider.provider.replace(/_/g, ' ')}
        </span>
        <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
          {provider.ai_data_sharing.replace(/_/g, ' ')}
        </span>
      </button>

      {expanded && (
        <div
          style={{
            padding: '0 14px 14px',
            borderTop: '1px solid var(--border)',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          <div style={{ paddingTop: 12 }} />

          {isLocal && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Base URL</label>
              <input
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="http://localhost:11434"
                style={{
                  padding: '7px 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'var(--bg-secondary)',
                  color: 'var(--fg-primary)',
                  fontSize: 13,
                  outline: 'none',
                }}
              />
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Model name</label>
            <input
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder="e.g. llama3, gpt-4o, claude-3-opus"
              style={{
                padding: '7px 10px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-secondary)',
                color: 'var(--fg-primary)',
                fontSize: 13,
                outline: 'none',
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Data sharing</label>
            {AI_DATA_SHARING_OPTIONS.filter((o) => isLocal || o.value !== 'full').map((opt) => (
              <label
                key={opt.value}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 8,
                  cursor: 'pointer',
                  padding: '6px 8px',
                  borderRadius: 6,
                  background:
                    sharing === opt.value
                      ? 'color-mix(in oklch, var(--accent) 8%, transparent)'
                      : 'transparent',
                  border: `1px solid ${sharing === opt.value ? 'color-mix(in oklch, var(--accent) 25%, transparent)' : 'transparent'}`,
                }}
              >
                <input
                  type="radio"
                  name={`sharing-${provider.id}`}
                  value={opt.value}
                  checked={sharing === opt.value}
                  onChange={() => setSharing(opt.value)}
                  style={{ marginTop: 1, flexShrink: 0 }}
                />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
                    {opt.label}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{opt.description}</div>
                </div>
              </label>
            ))}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                cursor: 'pointer',
                fontSize: 13,
                color: 'var(--fg-secondary)',
              }}
            >
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                style={{ width: 14, height: 14 }}
              />
              Enabled
            </label>

            <div style={{ display: 'flex', gap: 6 }}>
              {confirmDelete ? (
                <>
                  <button
                    type="button"
                    onClick={() => void handleDelete()}
                    style={{
                      padding: '5px 12px',
                      fontSize: 12,
                      background: 'var(--danger)',
                      color: 'white',
                      border: 'none',
                      borderRadius: 6,
                      cursor: 'pointer',
                      fontFamily: 'var(--font-sans)',
                    }}
                  >
                    Confirm delete
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(false)}
                    style={{
                      padding: '5px 12px',
                      fontSize: 12,
                      background: 'none',
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      cursor: 'pointer',
                      color: 'var(--fg-muted)',
                      fontFamily: 'var(--font-sans)',
                    }}
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => void handleSave()}
                    disabled={saving}
                    style={{
                      padding: '5px 14px',
                      fontSize: 12,
                      background: 'var(--accent)',
                      color: 'var(--accent-fg)',
                      border: 'none',
                      borderRadius: 6,
                      cursor: 'pointer',
                      fontFamily: 'var(--font-sans)',
                    }}
                  >
                    {saving ? 'Saving...' : 'Save'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(true)}
                    style={{
                      padding: '5px 8px',
                      fontSize: 12,
                      background: 'none',
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      cursor: 'pointer',
                      color: 'var(--danger)',
                      display: 'flex',
                      alignItems: 'center',
                    }}
                  >
                    <Trash2 size={13} />
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function AddProviderModal({
  householdId,
  onClose,
  onAdded,
}: {
  householdId: string
  onClose: () => void
  onAdded: () => void
}) {
  const [providerType, setProviderType] = useState('local_ollama')
  const [modelName, setModelName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [sharing, setSharing] = useState('generalizations_only')
  const [saving, setSaving] = useState(false)

  const create = useCreateProviderApiV1HouseholdsHouseholdIdInsightsProvidersPost()
  const isLocal = LOCAL_TYPES.has(providerType)

  const handleSave = async () => {
    setSaving(true)
    try {
      await create.mutateAsync({
        householdId,
        data: {
          provider: providerType,
          model_name: modelName || null,
          base_url: isLocal ? baseUrl || null : undefined,
          ai_data_sharing: sharing,
          enabled: true,
        },
      })
      onAdded()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        backdropFilter: 'blur(2px)',
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 480,
          maxWidth: '100%',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderTop: '2px solid var(--accent)',
          borderRadius: 14,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '88vh',
        }}
      >
        <div
          style={{
            padding: '18px 22px 14px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)' }}>
            Add AI provider
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'none',
              border: '1px solid var(--border)',
              borderRadius: 6,
              width: 26,
              height: 26,
              cursor: 'pointer',
              color: 'var(--fg-muted)',
              fontSize: 14,
            }}
          >
            &times;
          </button>
        </div>

        <div
          style={{
            padding: '16px 22px',
            overflowY: 'auto',
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Provider type</label>
            <select
              value={providerType}
              onChange={(e) => setProviderType(e.target.value)}
              style={{
                padding: '8px 10px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-secondary)',
                color: 'var(--fg-primary)',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              {PROVIDER_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>

          {isLocal && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Base URL</label>
              <input
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="http://localhost:11434"
                style={{
                  padding: '8px 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'var(--bg-secondary)',
                  color: 'var(--fg-primary)',
                  fontSize: 13,
                  outline: 'none',
                }}
              />
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Model name</label>
            <input
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder="e.g. llama3, gpt-4o, claude-opus-4-7"
              style={{
                padding: '8px 10px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-secondary)',
                color: 'var(--fg-primary)',
                fontSize: 13,
                outline: 'none',
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Data sharing</label>
            <select
              value={sharing}
              onChange={(e) => setSharing(e.target.value)}
              style={{
                padding: '8px 10px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-secondary)',
                color: 'var(--fg-primary)',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              {AI_DATA_SHARING_OPTIONS.filter((o) => isLocal || o.value !== 'full').map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label} — {opt.description}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div
          style={{
            padding: '12px 22px',
            borderTop: '1px solid var(--border)',
            background: 'var(--bg-secondary)',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 8,
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: '7px 16px',
              background: 'none',
              border: '1px solid var(--border)',
              borderRadius: 8,
              fontSize: 13,
              color: 'var(--fg-secondary)',
              cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            style={{
              padding: '7px 16px',
              background: 'var(--accent)',
              color: 'var(--accent-fg)',
              border: 'none',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 500,
              cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
            }}
          >
            {saving ? 'Adding...' : 'Add provider'}
          </button>
        </div>
      </div>
    </div>
  )
}

function TokenBudgetSection({ householdId, currency }: { householdId: string; currency: string }) {
  const { data: budget, refetch } = useGetBudgetApiV1HouseholdsHouseholdIdInsightsBudgetGet(
    householdId,
    { query: { enabled: !!householdId } }
  )
  const update = useUpdateBudgetApiV1HouseholdsHouseholdIdInsightsBudgetPatch()

  const [tokenLimit, setTokenLimit] = useState('')
  const [costLimit, setCostLimit] = useState('')
  const [overage, setOverage] = useState('block')
  const [loaded, setLoaded] = useState(false)
  const [saving, setSaving] = useState(false)

  if (budget && !loaded) {
    setTokenLimit(budget.token_limit != null ? String(budget.token_limit) : '')
    setCostLimit(budget.cost_limit != null ? String(budget.cost_limit) : '')
    setOverage(budget.overage_behavior)
    setLoaded(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await update.mutateAsync({
        householdId,
        data: {
          token_limit: tokenLimit ? parseInt(tokenLimit, 10) : null,
          cost_limit: costLimit || null,
          overage_behavior: overage,
        },
      })
      await refetch()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>Token budget</div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
            Token limit / month (blank = unlimited)
          </label>
          <input
            value={tokenLimit}
            onChange={(e) => setTokenLimit(e.target.value)}
            placeholder="e.g. 100000"
            type="number"
            style={{
              padding: '8px 10px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--bg-secondary)',
              color: 'var(--fg-primary)',
              fontSize: 13,
              outline: 'none',
            }}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
            Cost limit / month {currency} (blank = unlimited)
          </label>
          <input
            value={costLimit}
            onChange={(e) => setCostLimit(e.target.value)}
            placeholder="e.g. 5.00"
            type="number"
            step="0.01"
            style={{
              padding: '8px 10px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--bg-secondary)',
              color: 'var(--fg-primary)',
              fontSize: 13,
              outline: 'none',
            }}
          />
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>On overage</label>
        <div style={{ display: 'flex', gap: 6 }}>
          {OVERAGE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setOverage(opt.value)}
              style={{
                padding: '5px 12px',
                fontSize: 12,
                borderRadius: 6,
                border: `1px solid ${overage === opt.value ? 'var(--accent)' : 'var(--border)'}`,
                background:
                  overage === opt.value
                    ? 'color-mix(in oklch, var(--accent) 12%, transparent)'
                    : 'none',
                color: overage === opt.value ? 'var(--accent)' : 'var(--fg-muted)',
                cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {budget && (
        <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
          This month:{' '}
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--fg-primary)' }}>
            {budget.tokens_used.toLocaleString()} tokens /{' '}
            {formatAmount(parseFloat(budget.cost_used), { currency })}
          </span>
        </div>
      )}

      <div>
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={saving}
          style={{
            padding: '7px 16px',
            background: 'var(--accent)',
            color: 'var(--accent-fg)',
            border: 'none',
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 500,
            cursor: 'pointer',
            fontFamily: 'var(--font-sans)',
          }}
        >
          {saving ? 'Saving...' : 'Save budget'}
        </button>
      </div>
    </div>
  )
}

export function InsightsSettingsPage() {
  const { household, householdId } = useHousehold()
  const hid = householdId ?? ''
  const [showAdd, setShowAdd] = useState(false)
  const qc = useQueryClient()

  const { data: providers = [], refetch } =
    useListProvidersApiV1HouseholdsHouseholdIdInsightsProvidersGet(hid, {
      query: { enabled: !!hid },
    })

  const handleAdded = async () => {
    setShowAdd(false)
    await refetch()
  }

  const handleDeleted = async () => {
    await qc.invalidateQueries({
      queryKey: [`/api/v1/households/${hid}/insights/providers`],
    })
  }

  const currency = household?.home_currency ?? 'USD'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 640 }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
        AI Insights Settings
      </h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>Providers</div>
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 12px',
              background: 'var(--accent)',
              color: 'var(--accent-fg)',
              border: 'none',
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 500,
              cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
            }}
          >
            <Plus size={13} />
            Add provider
          </button>
        </div>

        {(providers as ProviderConfigOut[]).length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>
            No providers configured. Add one to enable AI insights.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {(providers as ProviderConfigOut[]).map((p) => (
              <ProviderRow key={p.id} provider={p} householdId={hid} onDeleted={handleDeleted} />
            ))}
          </div>
        )}
      </div>

      <div
        style={{
          paddingTop: 20,
          borderTop: '1px solid var(--border)',
        }}
      >
        <TokenBudgetSection householdId={hid} currency={currency} />
      </div>

      {showAdd && (
        <AddProviderModal
          householdId={hid}
          onClose={() => setShowAdd(false)}
          onAdded={handleAdded}
        />
      )}
    </div>
  )
}
