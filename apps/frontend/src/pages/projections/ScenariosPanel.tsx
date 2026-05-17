import { useState } from 'react'
import { Plus, Trash2, Play, Save } from 'lucide-react'
import {
  useListScenariosApiV1HouseholdsHouseholdIdProjectionsScenariosGet,
  useCreateScenarioApiV1HouseholdsHouseholdIdProjectionsScenariosPost,
  useRunScenarioApiV1HouseholdsHouseholdIdProjectionsScenariosScenarioIdRunPost,
  useArchiveScenarioApiV1HouseholdsHouseholdIdProjectionsScenariosScenarioIdDelete,
  useUpdateScenarioApiV1HouseholdsHouseholdIdProjectionsScenariosScenarioIdPatch,
} from '@/api/generated/default/default'
import { useQueryClient } from '@tanstack/react-query'
import type { ScenarioOut } from '@/api/generated/model/scenarioOut'
import type { ScenarioOverride } from '@/api/generated/model/scenarioOverride'

const OVERRIDE_TYPES = [
  { value: 'add_recurrence', label: 'Add recurrence' },
  { value: 'remove_recurrence', label: 'Remove recurrence' },
  { value: 'change_income', label: 'Change income' },
  { value: 'change_extra_debt_payment', label: 'Extra debt payment' },
  { value: 'change_goal_contribution', label: 'Goal contribution' },
  { value: 'change_account_balance', label: 'Account balance' },
] as const

type OverrideType = (typeof OVERRIDE_TYPES)[number]['value']

interface Override {
  id: string
  type: OverrideType
  description: string
  raw: ScenarioOverride
}

function generateId(): string {
  return Math.random().toString(36).slice(2, 10)
}

function OverridePill({ override, onRemove }: { override: Override; onRemove: () => void }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '5px 10px',
        background: 'color-mix(in oklch, var(--accent) 10%, transparent)',
        border: '1px solid color-mix(in oklch, var(--accent) 25%, transparent)',
        borderRadius: 99,
        fontSize: 12,
      }}
    >
      <span style={{ color: 'var(--fg-primary)' }}>{override.description}</span>
      <button
        type="button"
        onClick={onRemove}
        style={{
          background: 'none',
          border: 'none',
          padding: 0,
          cursor: 'pointer',
          color: 'var(--fg-muted)',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        &times;
      </button>
    </div>
  )
}

function AddOverrideForm({ onAdd }: { onAdd: (o: Override) => void }) {
  const [type, setType] = useState<OverrideType>('add_recurrence')
  const [name, setName] = useState('')
  const [amount, setAmount] = useState('')

  const handleAdd = () => {
    if (!amount && type !== 'remove_recurrence') return
    const desc = `${OVERRIDE_TYPES.find((t) => t.value === type)?.label ?? type}${name ? `: ${name}` : ''}${amount ? ` $${amount}` : ''}`
    onAdd({
      id: generateId(),
      type,
      description: desc,
      raw: { type, ...(amount ? { amount } : {}) },
    })
    setName('')
    setAmount('')
  }

  return (
    <div
      style={{
        display: 'flex',
        gap: 8,
        padding: '12px',
        background: 'var(--bg-secondary)',
        borderRadius: 8,
        flexWrap: 'wrap',
        alignItems: 'flex-end',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <label style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Type</label>
        <select
          value={type}
          onChange={(e) => setType(e.target.value as OverrideType)}
          style={{
            padding: '6px 8px',
            borderRadius: 6,
            border: '1px solid var(--border)',
            background: 'var(--bg-elevated)',
            color: 'var(--fg-primary)',
            fontSize: 12,
            cursor: 'pointer',
          }}
        >
          {OVERRIDE_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <label style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Name (optional)</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Car payment"
          style={{
            padding: '6px 8px',
            borderRadius: 6,
            border: '1px solid var(--border)',
            background: 'var(--bg-elevated)',
            color: 'var(--fg-primary)',
            fontSize: 12,
            width: 140,
          }}
        />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <label style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Amount</label>
        <input
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="0.00"
          type="number"
          style={{
            padding: '6px 8px',
            borderRadius: 6,
            border: '1px solid var(--border)',
            background: 'var(--bg-elevated)',
            color: 'var(--fg-primary)',
            fontSize: 12,
            width: 100,
          }}
        />
      </div>
      <button
        type="button"
        onClick={handleAdd}
        style={{
          padding: '6px 14px',
          background: 'var(--accent)',
          color: 'var(--accent-fg)',
          border: 'none',
          borderRadius: 6,
          fontSize: 12,
          fontWeight: 500,
          cursor: 'pointer',
          fontFamily: 'var(--font-sans)',
        }}
      >
        Add
      </button>
    </div>
  )
}

function ScenarioBuilderModal({
  householdId,
  onClose,
  onCreated,
}: {
  householdId: string
  onClose: () => void
  onCreated: (id: string) => void
}) {
  const [name, setName] = useState('')
  const [overrides, setOverrides] = useState<Override[]>([])
  const [save, setSave] = useState(false)

  const create = useCreateScenarioApiV1HouseholdsHouseholdIdProjectionsScenariosPost()
  const run = useRunScenarioApiV1HouseholdsHouseholdIdProjectionsScenariosScenarioIdRunPost()

  const handleRun = async () => {
    const payload = {
      name: name || null,
      overrides: overrides.map((o) => o.raw),
      saved: save,
    }
    const scenario = await create.mutateAsync({ householdId, data: payload })
    await run.mutateAsync({ householdId, scenarioId: scenario.id, data: {} })
    onCreated(scenario.id)
  }

  const isLoading = create.isPending || run.isPending

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
          width: 520,
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
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)' }}>
              New scenario
            </div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
              What-if analysis with custom overrides
            </div>
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
            gap: 16,
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
              Scenario name (optional)
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Unsaved scenario"
              style={{
                padding: '8px 10px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-secondary)',
                color: 'var(--fg-primary)',
                fontSize: 13,
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-muted)' }}>
              Overrides {overrides.length > 0 && `(${overrides.length})`}
            </div>
            {overrides.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {overrides.map((o) => (
                  <OverridePill
                    key={o.id}
                    override={o}
                    onRemove={() => setOverrides((prev) => prev.filter((x) => x.id !== o.id))}
                  />
                ))}
              </div>
            )}
            <AddOverrideForm onAdd={(o) => setOverrides((prev) => [...prev, o])} />
          </div>

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
              checked={save}
              onChange={(e) => setSave(e.target.checked)}
              style={{ width: 14, height: 14 }}
            />
            Save this scenario
          </label>
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
            onClick={handleRun}
            disabled={isLoading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '7px 16px',
              background: 'var(--accent)',
              color: 'var(--accent-fg)',
              border: 'none',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 500,
              cursor: isLoading ? 'not-allowed' : 'pointer',
              opacity: isLoading ? 0.7 : 1,
              fontFamily: 'var(--font-sans)',
            }}
          >
            <Play size={13} />
            {isLoading ? 'Running...' : 'Run scenario'}
          </button>
        </div>
      </div>
    </div>
  )
}

function ScenarioCard({
  scenario,
  householdId,
  onDelete,
  onRun,
}: {
  scenario: ScenarioOut
  householdId: string
  onDelete: () => void
  onRun: () => void
}) {
  const [saving, setSaving] = useState(false)
  const update = useUpdateScenarioApiV1HouseholdsHouseholdIdProjectionsScenariosScenarioIdPatch()

  const toggleSave = async () => {
    setSaving(true)
    try {
      await update.mutateAsync({
        householdId,
        scenarioId: scenario.id,
        data: { saved: !scenario.saved },
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '16px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 8,
        }}
      >
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>
            {scenario.name ?? 'Unsaved scenario'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
            {new Date(scenario.created_at).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
            {scenario.saved && (
              <span
                style={{
                  marginLeft: 8,
                  padding: '1px 6px',
                  borderRadius: 99,
                  background: 'color-mix(in oklch, var(--success) 15%, transparent)',
                  color: 'var(--success)',
                  fontSize: 10,
                  fontWeight: 600,
                }}
              >
                Saved
              </span>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
          <button
            type="button"
            onClick={onRun}
            title="Run scenario"
            style={{
              padding: '5px 8px',
              background: 'none',
              border: '1px solid var(--border)',
              borderRadius: 6,
              cursor: 'pointer',
              color: 'var(--fg-muted)',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <Play size={12} />
          </button>
          <button
            type="button"
            onClick={toggleSave}
            disabled={saving}
            title={scenario.saved ? 'Unsave' : 'Save'}
            style={{
              padding: '5px 8px',
              background: 'none',
              border: `1px solid ${scenario.saved ? 'var(--success)' : 'var(--border)'}`,
              borderRadius: 6,
              cursor: 'pointer',
              color: scenario.saved ? 'var(--success)' : 'var(--fg-muted)',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <Save size={12} />
          </button>
          <button
            type="button"
            onClick={onDelete}
            title="Delete"
            style={{
              padding: '5px 8px',
              background: 'none',
              border: '1px solid var(--border)',
              borderRadius: 6,
              cursor: 'pointer',
              color: 'var(--danger)',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>
      <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
        {(scenario.overrides as unknown[]).length} override
        {(scenario.overrides as unknown[]).length !== 1 ? 's' : ''}
      </div>
    </div>
  )
}

export function ScenariosPanel({ householdId }: { householdId: string }) {
  const [showBuilder, setShowBuilder] = useState(false)
  const qc = useQueryClient()

  const { data: scenarios = [], isLoading } =
    useListScenariosApiV1HouseholdsHouseholdIdProjectionsScenariosGet(householdId, {
      query: { enabled: !!householdId },
    })

  const archive = useArchiveScenarioApiV1HouseholdsHouseholdIdProjectionsScenariosScenarioIdDelete()
  const run = useRunScenarioApiV1HouseholdsHouseholdIdProjectionsScenariosScenarioIdRunPost()

  const handleDelete = async (scenarioId: string) => {
    await archive.mutateAsync({ householdId, scenarioId })
    await qc.invalidateQueries({
      queryKey: [`/api/v1/households/${householdId}/projections/scenarios`],
    })
  }

  const handleRun = async (scenarioId: string) => {
    await run.mutateAsync({ householdId, scenarioId, data: {} })
  }

  const handleCreated = async () => {
    setShowBuilder(false)
    await qc.invalidateQueries({
      queryKey: [`/api/v1/households/${householdId}/projections/scenarios`],
    })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>Scenarios</div>
          <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
            What-if analysis with custom overrides
          </div>
        </div>
        <button
          type="button"
          onClick={() => setShowBuilder(true)}
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
            fontFamily: 'var(--font-sans)',
          }}
        >
          <Plus size={14} />
          New scenario
        </button>
      </div>

      {isLoading ? (
        <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>
      ) : (scenarios as ScenarioOut[]).length === 0 ? (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 12,
            padding: '60px 24px',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--fg-secondary)' }}>
            No scenarios yet
          </div>
          <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>
            Create a what-if scenario to see how changes affect your projections
          </div>
          <button
            type="button"
            onClick={() => setShowBuilder(true)}
            style={{
              marginTop: 8,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 18px',
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
            <Plus size={14} />
            New scenario
          </button>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: 12,
          }}
        >
          {(scenarios as ScenarioOut[]).map((s) => (
            <ScenarioCard
              key={s.id}
              scenario={s}
              householdId={householdId}
              onDelete={() => handleDelete(s.id)}
              onRun={() => handleRun(s.id)}
            />
          ))}
        </div>
      )}

      {showBuilder && (
        <ScenarioBuilderModal
          householdId={householdId}
          onClose={() => setShowBuilder(false)}
          onCreated={handleCreated}
        />
      )}
    </div>
  )
}
