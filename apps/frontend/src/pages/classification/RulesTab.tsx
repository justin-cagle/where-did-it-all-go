import { useState } from 'react'
import type { QueryClient } from '@tanstack/react-query'
import { ChevronUp, ChevronDown, Trash2, Plus, AlertTriangle, X } from 'lucide-react'
import type { RuleOut } from '@/api/generated/model/ruleOut'
import type { CategoryOut } from '@/api/generated/model/categoryOut'
import type { TagOut } from '@/api/generated/model/tagOut'
import { RuleMode } from '@/api/generated/model/ruleMode'
import { RuleConditionSchemaField } from '@/api/generated/model/ruleConditionSchemaField'
import { RuleConditionSchemaOperator } from '@/api/generated/model/ruleConditionSchemaOperator'
import { RuleActionSchemaType } from '@/api/generated/model/ruleActionSchemaType'
import type { RuleConditionSchema } from '@/api/generated/model/ruleConditionSchema'
import type { RuleActionSchema } from '@/api/generated/model/ruleActionSchema'
import {
  useCreateRuleApiV1HouseholdsHouseholdIdRulesPost,
  useUpdateRuleApiV1HouseholdsHouseholdIdRulesRuleIdPatch,
  useArchiveRuleApiV1HouseholdsHouseholdIdRulesRuleIdDelete,
  useReorderRulesApiV1HouseholdsHouseholdIdRulesReorderPost,
  useTestRuleApiV1HouseholdsHouseholdIdRulesRuleIdTestPost,
  getListRulesApiV1HouseholdsHouseholdIdRulesGetQueryKey,
} from '@/api/generated/classification/classification'
import { CategorySelect } from '@/components/CategorySelect'

interface Props {
  householdId: string
  rules: RuleOut[]
  categories: CategoryOut[]
  tags: TagOut[]
  qc: QueryClient
}

const FIELD_LABELS: Record<RuleConditionSchemaField, string> = {
  merchant_name: 'Merchant name',
  description: 'Description',
  amount: 'Amount',
  account: 'Account',
  direction: 'Direction',
  transaction_type: 'Transaction type',
}

const OPERATOR_LABELS: Record<RuleConditionSchemaOperator, string> = {
  equals: 'equals',
  contains: 'contains',
  starts_with: 'starts with',
  pattern_match: 'Advanced pattern match (regex)',
  amount_equals: 'equals',
  amount_between: 'between',
}

const FIELD_OPERATORS: Record<RuleConditionSchemaField, RuleConditionSchemaOperator[]> = {
  merchant_name: ['equals', 'contains', 'starts_with', 'pattern_match'],
  description: ['equals', 'contains', 'starts_with', 'pattern_match'],
  amount: ['amount_equals', 'amount_between'],
  account: ['equals'],
  direction: ['equals'],
  transaction_type: ['equals'],
}

const DIRECTION_OPTIONS = ['debit', 'credit']
const TX_TYPE_OPTIONS = ['regular', 'payroll', 'refund', 'transfer', 'fee', 'interest', 'dividend']

interface LocalCondition {
  field: RuleConditionSchemaField
  operator: RuleConditionSchemaOperator
  value: string
  min: string
  max: string
}

interface LocalAction {
  type: RuleActionSchemaType
  category_id: string | null
  tag_id: string | null
}

interface RuleFormState {
  name: string
  mode: RuleMode
  priority: number
  conditions: LocalCondition[]
  actions: LocalAction[]
}

function defaultCondition(): LocalCondition {
  return {
    field: 'merchant_name',
    operator: 'contains',
    value: '',
    min: '',
    max: '',
  }
}

function defaultAction(): LocalAction {
  return { type: 'set_category', category_id: null, tag_id: null }
}

function conditionSummary(cond: unknown): string {
  const c = cond as LocalCondition
  const field = FIELD_LABELS[c.field as RuleConditionSchemaField] ?? c.field
  const op = OPERATOR_LABELS[c.operator as RuleConditionSchemaOperator] ?? c.operator
  if (c.operator === 'amount_between') {
    return `${field} between ${c.min ?? '?'} and ${c.max ?? '?'}`
  }
  return `${field} ${op} "${String(c.value ?? '')}"`
}

function actionSummary(action: unknown, categories: CategoryOut[], tags: TagOut[]): string {
  const a = action as LocalAction
  if (a.type === 'set_category') {
    const cat = categories.find((c) => c.id === a.category_id)
    return `Set category: ${cat?.name ?? 'None'}`
  }
  if (a.type === 'add_tag') {
    const tag = tags.find((t) => t.id === a.tag_id)
    return `Add tag: ${tag?.name ?? 'None'}`
  }
  return a.type
}

interface ConditionRowProps {
  cond: LocalCondition
  index: number
  onChange: (c: LocalCondition) => void
  onRemove: () => void
}

function ConditionRow({ cond, index, onChange, onRemove }: ConditionRowProps) {
  const ops = FIELD_OPERATORS[cond.field] ?? (['equals'] as RuleConditionSchemaOperator[])
  const validOp = ops.includes(cond.operator) ? cond.operator : (ops[0] ?? 'equals')

  function setField(field: RuleConditionSchemaField) {
    const newOps = FIELD_OPERATORS[field] ?? (['equals'] as RuleConditionSchemaOperator[])
    const newOp = newOps[0] ?? 'equals'
    onChange({ ...cond, field, operator: newOp, value: '', min: '', max: '' })
  }

  function setOp(operator: RuleConditionSchemaOperator) {
    onChange({ ...cond, operator })
  }

  const isAmount = cond.field === 'amount'
  const isBetween = validOp === 'amount_between'
  const isSelect = cond.field === 'direction' || cond.field === 'transaction_type'
  const selectOpts = cond.field === 'direction' ? DIRECTION_OPTIONS : TX_TYPE_OPTIONS
  const isPatternMatch = validOp === 'pattern_match'

  return (
    <div
      style={{
        display: 'flex',
        gap: 6,
        alignItems: 'flex-start',
        padding: '8px 0',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <span
        style={{
          fontSize: 11,
          color: 'var(--fg-muted)',
          paddingTop: 8,
          width: 20,
          flexShrink: 0,
          textAlign: 'right',
        }}
      >
        {index + 1}.
      </span>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', flex: 1 }}>
        {/* Field selector */}
        <select
          value={cond.field}
          onChange={(e) => setField(e.target.value as RuleConditionSchemaField)}
          style={selectStyle}
        >
          {Object.entries(FIELD_LABELS).map(([f, label]) => (
            <option key={f} value={f}>
              {label}
            </option>
          ))}
        </select>

        {/* Operator selector */}
        <select
          value={validOp}
          onChange={(e) => setOp(e.target.value as RuleConditionSchemaOperator)}
          style={selectStyle}
        >
          {ops.map((op) => (
            <option key={op} value={op}>
              {OPERATOR_LABELS[op]}
            </option>
          ))}
        </select>

        {/* Value input */}
        {isBetween ? (
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <input
              type="number"
              placeholder="min"
              value={cond.min}
              onChange={(e) => onChange({ ...cond, min: e.target.value })}
              style={{ ...inputStyle, width: 80 }}
            />
            <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>and</span>
            <input
              type="number"
              placeholder="max"
              value={cond.max}
              onChange={(e) => onChange({ ...cond, max: e.target.value })}
              style={{ ...inputStyle, width: 80 }}
            />
          </div>
        ) : isAmount ? (
          <input
            type="number"
            placeholder="amount"
            value={cond.value}
            onChange={(e) => onChange({ ...cond, value: e.target.value })}
            style={{ ...inputStyle, width: 120 }}
          />
        ) : isSelect ? (
          <select
            value={cond.value}
            onChange={(e) => onChange({ ...cond, value: e.target.value })}
            style={selectStyle}
          >
            <option value="">Select...</option>
            {selectOpts.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            placeholder="value"
            value={cond.value}
            onChange={(e) => onChange({ ...cond, value: e.target.value })}
            style={{ ...inputStyle, width: 180 }}
          />
        )}

        {isPatternMatch && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 11,
              color: 'var(--warning)',
            }}
          >
            <AlertTriangle size={11} />
            <span>Use with caution</span>
          </div>
        )}
      </div>

      <button type="button" onClick={onRemove} style={iconBtnStyle}>
        <X size={13} />
      </button>
    </div>
  )
}

interface ActionRowProps {
  action: LocalAction
  index: number
  onChange: (a: LocalAction) => void
  onRemove: () => void
  categories: CategoryOut[]
  tags: TagOut[]
}

function ActionRow({ action, index, onChange, onRemove, categories, tags }: ActionRowProps) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 6,
        alignItems: 'flex-start',
        padding: '8px 0',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <span
        style={{
          fontSize: 11,
          color: 'var(--fg-muted)',
          paddingTop: 8,
          width: 20,
          flexShrink: 0,
          textAlign: 'right',
        }}
      >
        {index + 1}.
      </span>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', flex: 1, alignItems: 'flex-start' }}>
        <select
          value={action.type}
          onChange={(e) =>
            onChange({
              type: e.target.value as RuleActionSchemaType,
              category_id: null,
              tag_id: null,
            })
          }
          style={selectStyle}
        >
          <option value="set_category">Set category</option>
          <option value="add_tag">Add tag</option>
        </select>

        {action.type === 'set_category' && (
          <div style={{ width: 220 }}>
            <CategorySelect
              categories={categories}
              value={action.category_id}
              onChange={(id) => onChange({ ...action, category_id: id })}
              placeholder="Choose category..."
            />
          </div>
        )}

        {action.type === 'add_tag' && (
          <select
            value={action.tag_id ?? ''}
            onChange={(e) => onChange({ ...action, tag_id: e.target.value || null })}
            style={selectStyle}
          >
            <option value="">Choose tag...</option>
            {tags.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        )}
      </div>

      <button type="button" onClick={onRemove} style={iconBtnStyle}>
        <X size={13} />
      </button>
    </div>
  )
}

interface RuleEditorProps {
  householdId: string
  editRule: RuleOut | null
  categories: CategoryOut[]
  tags: TagOut[]
  qc: QueryClient
  onClose: () => void
}

function RuleEditor({ householdId, editRule, categories, tags, qc, onClose }: RuleEditorProps) {
  const [form, setForm] = useState<RuleFormState>(() => {
    if (editRule) {
      return {
        name: editRule.name,
        mode: editRule.mode as RuleMode,
        priority: editRule.priority,
        conditions: (editRule.conditions as unknown[]).map((c) => {
          const cond = c as Partial<LocalCondition>
          return {
            field: (cond.field ?? 'merchant_name') as RuleConditionSchemaField,
            operator: (cond.operator ?? 'contains') as RuleConditionSchemaOperator,
            value: String(cond.value ?? ''),
            min: String(cond.min ?? ''),
            max: String(cond.max ?? ''),
          }
        }),
        actions: (editRule.actions as unknown[]).map((a) => {
          const act = a as Partial<LocalAction>
          return {
            type: (act.type ?? 'set_category') as RuleActionSchemaType,
            category_id: (act.category_id as string | null | undefined) ?? null,
            tag_id: (act.tag_id as string | null | undefined) ?? null,
          }
        }),
      }
    }
    return {
      name: '',
      mode: RuleMode.auto_apply,
      priority: 10,
      conditions: [defaultCondition()],
      actions: [defaultAction()],
    }
  })

  const [testResult, setTestResult] = useState<{
    match_count: number
    sample_count: number
  } | null>(null)
  const [testing, setTesting] = useState(false)

  const create = useCreateRuleApiV1HouseholdsHouseholdIdRulesPost({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey: getListRulesApiV1HouseholdsHouseholdIdRulesGetQueryKey(householdId),
        })
        onClose()
      },
    },
  })

  const update = useUpdateRuleApiV1HouseholdsHouseholdIdRulesRuleIdPatch({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey: getListRulesApiV1HouseholdsHouseholdIdRulesGetQueryKey(householdId),
        })
        onClose()
      },
    },
  })

  const testMutation = useTestRuleApiV1HouseholdsHouseholdIdRulesRuleIdTestPost()

  function buildConditions(): RuleConditionSchema[] {
    return form.conditions.map((c) => {
      const base: RuleConditionSchema = { field: c.field, operator: c.operator }
      if (c.operator === 'amount_between') {
        return { ...base, min: c.min || null, max: c.max || null }
      }
      return { ...base, value: c.value }
    })
  }

  function buildActions(): RuleActionSchema[] {
    return form.actions.map((a) => ({
      type: a.type,
      category_id: a.category_id ?? undefined,
      tag_id: a.tag_id ?? undefined,
    }))
  }

  function submit() {
    if (!form.name.trim()) return
    const payload = {
      name: form.name.trim(),
      mode: form.mode,
      priority: form.priority,
      conditions: buildConditions(),
      actions: buildActions(),
      enabled: true,
    }
    if (editRule) {
      update.mutate({ householdId, ruleId: editRule.id, data: payload })
    } else {
      create.mutate({ householdId, data: payload })
    }
  }

  function runTest() {
    if (!editRule) return
    setTesting(true)
    setTestResult(null)
    testMutation.mutate(
      { householdId, ruleId: editRule.id },
      {
        onSuccess: (res) => {
          setTestResult({ match_count: res.match_count, sample_count: res.sample_count })
          setTesting(false)
        },
        onError: () => setTesting(false),
      }
    )
  }

  const isPending = create.isPending || update.isPending

  return (
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
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 14,
          width: 600,
          maxHeight: '88vh',
          overflowY: 'auto',
          boxShadow: 'var(--shadow)',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
            {editRule ? 'Edit rule' : 'New rule'}
          </h2>
          <button type="button" onClick={onClose} style={iconBtnStyle}>
            <X size={16} />
          </button>
        </div>

        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Basic fields */}
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Rule name</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Netflix subscription"
                style={{ ...inputStyle, width: '100%' }}
              />
            </div>
            <div>
              <label style={labelStyle}>Mode</label>
              <select
                value={form.mode}
                onChange={(e) => setForm({ ...form, mode: e.target.value as RuleMode })}
                style={selectStyle}
              >
                <option value="auto_apply">Auto apply</option>
                <option value="suggest">Suggest</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>Priority</label>
              <input
                type="number"
                min={1}
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
                style={{ ...inputStyle, width: 72 }}
              />
            </div>
          </div>

          {/* Conditions */}
          <div>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--fg-secondary)',
                marginBottom: 4,
              }}
            >
              CONDITIONS (all must match)
            </div>
            {form.conditions.map((cond, i) => (
              <ConditionRow
                key={i}
                cond={cond}
                index={i}
                onChange={(c) =>
                  setForm({ ...form, conditions: form.conditions.map((x, j) => (j === i ? c : x)) })
                }
                onRemove={() =>
                  setForm({ ...form, conditions: form.conditions.filter((_, j) => j !== i) })
                }
              />
            ))}
            <button
              type="button"
              onClick={() =>
                setForm({ ...form, conditions: [...form.conditions, defaultCondition()] })
              }
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                marginTop: 6,
                fontSize: 12,
                color: 'var(--accent)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '2px 0',
              }}
            >
              <Plus size={12} />
              Add condition
            </button>
          </div>

          {/* Actions */}
          <div>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--fg-secondary)',
                marginBottom: 4,
              }}
            >
              ACTIONS
            </div>
            {form.actions.map((action, i) => (
              <ActionRow
                key={i}
                action={action}
                index={i}
                onChange={(a) =>
                  setForm({ ...form, actions: form.actions.map((x, j) => (j === i ? a : x)) })
                }
                onRemove={() =>
                  setForm({ ...form, actions: form.actions.filter((_, j) => j !== i) })
                }
                categories={categories}
                tags={tags}
              />
            ))}
            <button
              type="button"
              onClick={() => setForm({ ...form, actions: [...form.actions, defaultAction()] })}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                marginTop: 6,
                fontSize: 12,
                color: 'var(--accent)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '2px 0',
              }}
            >
              <Plus size={12} />
              Add action
            </button>
          </div>

          {/* Test result */}
          {testResult && (
            <div
              style={{
                padding: '10px 14px',
                background: 'color-mix(in oklch, var(--info) 8%, transparent)',
                border: '1px solid color-mix(in oklch, var(--info) 30%, transparent)',
                borderRadius: 8,
                fontSize: 13,
                color: 'var(--fg-primary)',
              }}
            >
              Rule matched <strong>{testResult.match_count}</strong> transactions out of{' '}
              <strong>{testResult.sample_count}</strong> sampled.
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 20px',
            borderTop: '1px solid var(--border)',
            gap: 8,
          }}
        >
          <div>
            {editRule && (
              <button
                type="button"
                disabled={testing}
                onClick={runTest}
                style={{
                  padding: '7px 14px',
                  fontSize: 12,
                  background: 'none',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: 'var(--fg-secondary)',
                  cursor: testing ? 'not-allowed' : 'pointer',
                  opacity: testing ? 0.6 : 1,
                }}
              >
                {testing ? 'Testing...' : 'Test rule'}
              </button>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" onClick={onClose} style={cancelBtnStyle}>
              Cancel
            </button>
            <button
              type="button"
              disabled={!form.name.trim() || isPending}
              onClick={submit}
              style={{
                padding: '7px 16px',
                fontSize: 13,
                fontWeight: 500,
                background: 'var(--accent)',
                border: 'none',
                borderRadius: 8,
                color: 'var(--accent-fg)',
                cursor: !form.name.trim() || isPending ? 'not-allowed' : 'pointer',
                opacity: !form.name.trim() || isPending ? 0.6 : 1,
              }}
            >
              {isPending ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export function RulesTab({ householdId, rules, categories, tags, qc }: Props) {
  const [editorRule, setEditorRule] = useState<RuleOut | null | 'new'>('new' as never)
  const [editorOpen, setEditorOpen] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [localRules, setLocalRules] = useState<RuleOut[]>([])
  const [dirty, setDirty] = useState(false)

  const sorted = (dirty ? localRules : [...rules]).sort((a, b) => a.priority - b.priority)

  const archive = useArchiveRuleApiV1HouseholdsHouseholdIdRulesRuleIdDelete({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey: getListRulesApiV1HouseholdsHouseholdIdRulesGetQueryKey(householdId),
        })
        setDeleteConfirm(null)
      },
    },
  })

  const reorder = useReorderRulesApiV1HouseholdsHouseholdIdRulesReorderPost({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey: getListRulesApiV1HouseholdsHouseholdIdRulesGetQueryKey(householdId),
        })
        setDirty(false)
      },
    },
  })

  const update = useUpdateRuleApiV1HouseholdsHouseholdIdRulesRuleIdPatch({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey: getListRulesApiV1HouseholdsHouseholdIdRulesGetQueryKey(householdId),
        })
      },
    },
  })

  function move(rule: RuleOut, direction: 'up' | 'down') {
    const current = dirty ? localRules : [...rules].sort((a, b) => a.priority - b.priority)
    const idx = current.findIndex((r) => r.id === rule.id)
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1
    if (swapIdx < 0 || swapIdx >= current.length) return
    const next = [...current]
    const temp = next[idx]
    const swap = next[swapIdx]
    if (!temp || !swap) return
    next[idx] = { ...swap, priority: temp.priority }
    next[swapIdx] = { ...temp, priority: swap.priority }
    setLocalRules(next)
    setDirty(true)
    reorder.mutate({
      householdId,
      data: { items: next.map((r) => ({ rule_id: r.id, priority: r.priority })) },
    })
  }

  function openEditor(rule: RuleOut | null) {
    setEditorRule(rule)
    setEditorOpen(true)
  }

  function closeEditor() {
    setEditorOpen(false)
    setEditorRule(null)
  }

  if (rules.length === 0 && !editorOpen) {
    return (
      <div>
        <div
          style={{
            padding: '40px 20px',
            textAlign: 'center',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            marginBottom: 16,
          }}
        >
          <div style={{ fontSize: 13, color: 'var(--fg-muted)', marginBottom: 12 }}>
            No rules yet — add your first rule to auto-categorize transactions
          </div>
          <button type="button" onClick={() => openEditor(null)} style={accentBtnStyle}>
            <Plus size={13} />
            Add rule
          </button>
        </div>
        {editorOpen && (
          <RuleEditor
            householdId={householdId}
            editRule={
              editorRule instanceof Object && !(editorRule === null)
                ? (editorRule as RuleOut)
                : null
            }
            categories={categories}
            tags={tags}
            qc={qc}
            onClose={closeEditor}
          />
        )}
      </div>
    )
  }

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <button type="button" onClick={() => openEditor(null)} style={accentBtnStyle}>
          <Plus size={13} />
          Add rule
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {sorted.map((rule, i) => {
          const conditions = rule.conditions as unknown[]
          const actions = rule.actions as unknown[]
          return (
            <div
              key={rule.id}
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                borderRadius: 10,
                padding: '12px 14px',
                display: 'flex',
                gap: 10,
                alignItems: 'flex-start',
              }}
            >
              {/* Reorder buttons */}
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                  flexShrink: 0,
                  paddingTop: 2,
                }}
              >
                <button
                  type="button"
                  disabled={i === 0}
                  onClick={() => move(rule, 'up')}
                  style={{ ...iconBtnStyle, opacity: i === 0 ? 0.3 : 1 }}
                >
                  <ChevronUp size={13} />
                </button>
                <button
                  type="button"
                  disabled={i === sorted.length - 1}
                  onClick={() => move(rule, 'down')}
                  style={{ ...iconBtnStyle, opacity: i === sorted.length - 1 ? 0.3 : 1 }}
                >
                  <ChevronDown size={13} />
                </button>
              </div>

              {/* Content */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  {/* Enable toggle */}
                  <button
                    type="button"
                    onClick={() =>
                      update.mutate({
                        householdId,
                        ruleId: rule.id,
                        data: { enabled: !rule.enabled },
                      })
                    }
                    style={{
                      width: 32,
                      height: 18,
                      borderRadius: 9,
                      background: rule.enabled ? 'var(--accent)' : 'var(--border)',
                      border: 'none',
                      cursor: 'pointer',
                      position: 'relative',
                      flexShrink: 0,
                      transition: 'background 0.15s',
                    }}
                  >
                    <span
                      style={{
                        position: 'absolute',
                        top: 2,
                        left: rule.enabled ? 16 : 2,
                        width: 14,
                        height: 14,
                        borderRadius: '50%',
                        background: '#fff',
                        transition: 'left 0.15s',
                      }}
                    />
                  </button>

                  <span
                    style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-primary)', flex: 1 }}
                  >
                    {rule.name}
                  </span>

                  {/* Mode badge */}
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 500,
                      color: 'var(--fg-muted)',
                      background: 'var(--bg-secondary)',
                      border: '1px solid var(--border)',
                      borderRadius: 4,
                      padding: '1px 5px',
                    }}
                  >
                    {rule.mode === 'auto_apply' ? 'auto apply' : 'suggest'}
                  </span>

                  {/* Priority */}
                  <span style={{ fontSize: 11, color: 'var(--fg-muted)' }}>#{rule.priority}</span>

                  {/* Edit/Delete */}
                  <button type="button" onClick={() => openEditor(rule)} style={iconBtnStyle}>
                    <svg
                      width="12"
                      height="12"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    onClick={() => setDeleteConfirm(rule.id)}
                    style={{ ...iconBtnStyle, color: 'var(--danger)' }}
                  >
                    <Trash2 size={12} />
                  </button>
                </div>

                {/* Condition summary */}
                <div style={{ fontSize: 12, color: 'var(--fg-secondary)', lineHeight: 1.5 }}>
                  {conditions.length === 0
                    ? 'No conditions'
                    : conditions.map((c, ci) => <div key={ci}>{conditionSummary(c)}</div>)}
                </div>

                {/* Arrow + actions */}
                <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 4 }}>
                  &rarr;{' '}
                  {actions.length === 0
                    ? 'No actions'
                    : actions.map((a, ai) => (
                        <span key={ai}>
                          {ai > 0 && ', '}
                          {actionSummary(a, categories, tags)}
                        </span>
                      ))}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Rule editor modal */}
      {editorOpen && (
        <RuleEditor
          householdId={householdId}
          editRule={editorRule as RuleOut | null}
          categories={categories}
          tags={tags}
          qc={qc}
          onClose={closeEditor}
        />
      )}

      {/* Delete confirm */}
      {deleteConfirm &&
        (() => {
          const rule = rules.find((r) => r.id === deleteConfirm)
          return (
            <div
              style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0,0,0,0.5)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 300,
              }}
              onClick={() => setDeleteConfirm(null)}
            >
              <div
                onClick={(e) => e.stopPropagation()}
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 12,
                  padding: 24,
                  width: 340,
                  boxShadow: 'var(--shadow)',
                }}
              >
                <h2
                  style={{
                    fontSize: 15,
                    fontWeight: 600,
                    color: 'var(--fg-primary)',
                    margin: '0 0 8px',
                  }}
                >
                  Delete &ldquo;{rule?.name}&rdquo;?
                </h2>
                <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 20px' }}>
                  This rule will no longer run on new transactions.
                </p>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button
                    type="button"
                    onClick={() => setDeleteConfirm(null)}
                    style={cancelBtnStyle}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={archive.isPending}
                    onClick={() => archive.mutate({ householdId, ruleId: deleteConfirm })}
                    style={dangerBtnStyle}
                  >
                    {archive.isPending ? 'Deleting...' : 'Delete'}
                  </button>
                </div>
              </div>
            </div>
          )
        })()}
    </>
  )
}

const iconBtnStyle: React.CSSProperties = {
  padding: 4,
  background: 'none',
  border: 'none',
  color: 'var(--fg-secondary)',
  cursor: 'pointer',
  borderRadius: 4,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
}

const selectStyle: React.CSSProperties = {
  padding: '5px 8px',
  fontSize: 12,
  border: '1px solid var(--border)',
  borderRadius: 6,
  background: 'var(--bg-secondary)',
  color: 'var(--fg-primary)',
  outline: 'none',
  cursor: 'pointer',
}

const inputStyle: React.CSSProperties = {
  padding: '5px 8px',
  fontSize: 12,
  border: '1px solid var(--border)',
  borderRadius: 6,
  background: 'var(--bg-secondary)',
  color: 'var(--fg-primary)',
  outline: 'none',
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 11,
  fontWeight: 600,
  color: 'var(--fg-muted)',
  marginBottom: 4,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
}

const cancelBtnStyle: React.CSSProperties = {
  padding: '7px 14px',
  fontSize: 13,
  background: 'none',
  border: '1px solid var(--border)',
  borderRadius: 8,
  color: 'var(--fg-secondary)',
  cursor: 'pointer',
}

const dangerBtnStyle: React.CSSProperties = {
  padding: '7px 14px',
  fontSize: 13,
  fontWeight: 500,
  background: 'var(--danger)',
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  cursor: 'pointer',
}

const accentBtnStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '7px 14px',
  fontSize: 13,
  fontWeight: 500,
  background: 'var(--accent)',
  border: 'none',
  borderRadius: 8,
  color: 'var(--accent-fg)',
  cursor: 'pointer',
}
