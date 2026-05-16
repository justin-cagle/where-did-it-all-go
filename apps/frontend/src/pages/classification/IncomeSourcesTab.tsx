import { useState } from 'react'
import type { QueryClient } from '@tanstack/react-query'
import { Plus, Archive, Pencil, X } from 'lucide-react'
import type { IncomeSourceOut } from '@/api/generated/model/incomeSourceOut'
import type { MembershipOut } from '@/api/generated/model/membershipOut'
import type { AccountOut } from '@/api/generated/model/accountOut'
import { IncomeSourceSubType } from '@/api/generated/model/incomeSourceSubType'
import { VariabilityModel } from '@/api/generated/model/variabilityModel'
import {
  useCreateIncomeSourceApiV1HouseholdsHouseholdIdIncomeSourcesPost,
  useUpdateIncomeSourceApiV1HouseholdsHouseholdIdIncomeSourcesSourceIdPatch,
  useArchiveIncomeSourceApiV1HouseholdsHouseholdIdIncomeSourcesSourceIdDelete,
  getListIncomeSourcesApiV1HouseholdsHouseholdIdIncomeSourcesGetQueryKey,
} from '@/api/generated/classification/classification'
import { fmt } from '@/lib/format'

interface Props {
  householdId: string
  incomeSources: IncomeSourceOut[]
  members: MembershipOut[]
  accounts: AccountOut[]
  qc: QueryClient
}

const SUB_TYPE_LABELS: Record<string, string> = {
  payroll: 'Payroll',
  bonus: 'Bonus',
  rsu: 'RSU',
  reimbursement: 'Reimbursement',
}

const VARIABILITY_LABELS: Record<string, string> = {
  fixed: 'Fixed',
  range: 'Range',
  historical_distribution: 'Historical',
}

interface IncomeSourceFormState {
  employer_name: string
  sub_type: string
  expected_amount_min: string
  expected_amount_max: string
  currency: string
  attributed_to_user_id: string
  expected_cadence: string
  variability_model: string
  account_id: string
}

function defaultForm(members: MembershipOut[]): IncomeSourceFormState {
  return {
    employer_name: '',
    sub_type: IncomeSourceSubType.payroll,
    expected_amount_min: '',
    expected_amount_max: '',
    currency: 'USD',
    attributed_to_user_id: members[0]?.user_id ?? '',
    expected_cadence: '',
    variability_model: VariabilityModel.fixed,
    account_id: '',
  }
}

interface ModalProps {
  householdId: string
  source: IncomeSourceOut | null
  members: MembershipOut[]
  accounts: AccountOut[]
  qc: QueryClient
  onClose: () => void
}

function IncomeSourceModal({ householdId, source, members, accounts, qc, onClose }: ModalProps) {
  const [form, setForm] = useState<IncomeSourceFormState>(() => {
    if (source) {
      return {
        employer_name: source.employer_name,
        sub_type: source.sub_type,
        expected_amount_min: source.expected_amount_min,
        expected_amount_max: source.expected_amount_max,
        currency: source.currency,
        attributed_to_user_id: source.attributed_to_user_id,
        expected_cadence: source.expected_cadence ?? '',
        variability_model: source.variability_model,
        account_id: source.account_id ?? '',
      }
    }
    return defaultForm(members)
  })

  const create = useCreateIncomeSourceApiV1HouseholdsHouseholdIdIncomeSourcesPost({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey:
            getListIncomeSourcesApiV1HouseholdsHouseholdIdIncomeSourcesGetQueryKey(householdId),
        })
        onClose()
      },
    },
  })

  const update = useUpdateIncomeSourceApiV1HouseholdsHouseholdIdIncomeSourcesSourceIdPatch({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey:
            getListIncomeSourcesApiV1HouseholdsHouseholdIdIncomeSourcesGetQueryKey(householdId),
        })
        onClose()
      },
    },
  })

  const isPending = create.isPending || update.isPending

  function submit() {
    if (!form.employer_name.trim() || !form.attributed_to_user_id) return
    const payload = {
      employer_name: form.employer_name.trim(),
      sub_type: form.sub_type as (typeof IncomeSourceSubType)[keyof typeof IncomeSourceSubType],
      expected_amount_min: form.expected_amount_min || '0',
      expected_amount_max: form.expected_amount_max || '0',
      currency: form.currency || 'USD',
      attributed_to_user_id: form.attributed_to_user_id,
      expected_cadence: form.expected_cadence || undefined,
      variability_model:
        form.variability_model as (typeof VariabilityModel)[keyof typeof VariabilityModel],
      account_id: form.account_id || undefined,
    }
    if (source) {
      update.mutate({ householdId, sourceId: source.id, data: payload })
    } else {
      create.mutate({ householdId, data: payload })
    }
  }

  function field(label: string, content: React.ReactNode) {
    return (
      <div>
        <label style={labelStyle}>{label}</label>
        {content}
      </div>
    )
  }

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
          width: 500,
          maxHeight: '88vh',
          overflowY: 'auto',
          boxShadow: 'var(--shadow)',
        }}
      >
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
            {source ? 'Edit income source' : 'Add income source'}
          </h2>
          <button type="button" onClick={onClose} style={iconBtnStyle}>
            <X size={16} />
          </button>
        </div>

        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {field(
            'Employer name *',
            <input
              value={form.employer_name}
              onChange={(e) => setForm({ ...form, employer_name: e.target.value })}
              placeholder="e.g. Acme Corp"
              style={{ ...inputStyle, width: '100%' }}
            />
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {field(
              'Type',
              <select
                value={form.sub_type}
                onChange={(e) => setForm({ ...form, sub_type: e.target.value })}
                style={{ ...selectStyle, width: '100%' }}
              >
                {Object.entries(SUB_TYPE_LABELS).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            )}

            {field(
              'Variability',
              <select
                value={form.variability_model}
                onChange={(e) => setForm({ ...form, variability_model: e.target.value })}
                style={{ ...selectStyle, width: '100%' }}
              >
                {Object.entries(VARIABILITY_LABELS).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 80px', gap: 8 }}>
            {field(
              'Min amount',
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.expected_amount_min}
                onChange={(e) => setForm({ ...form, expected_amount_min: e.target.value })}
                placeholder="0.00"
                style={{ ...inputStyle, width: '100%' }}
              />
            )}
            {field(
              'Max amount',
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.expected_amount_max}
                onChange={(e) => setForm({ ...form, expected_amount_max: e.target.value })}
                placeholder="0.00"
                style={{ ...inputStyle, width: '100%' }}
              />
            )}
            {field(
              'Currency',
              <input
                value={form.currency}
                onChange={(e) =>
                  setForm({ ...form, currency: e.target.value.toUpperCase().slice(0, 3) })
                }
                maxLength={3}
                placeholder="USD"
                style={{ ...inputStyle, width: '100%' }}
              />
            )}
          </div>

          {field(
            'Attributed to',
            <select
              value={form.attributed_to_user_id}
              onChange={(e) => setForm({ ...form, attributed_to_user_id: e.target.value })}
              style={{ ...selectStyle, width: '100%' }}
            >
              <option value="">Select member...</option>
              {members.map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.user.display_name || m.user.email}
                </option>
              ))}
            </select>
          )}

          {field(
            'Expected cadence',
            <input
              value={form.expected_cadence}
              onChange={(e) => setForm({ ...form, expected_cadence: e.target.value })}
              placeholder="e.g. bi-weekly, monthly"
              style={{ ...inputStyle, width: '100%' }}
            />
          )}

          {field(
            'Deposit account (optional)',
            <select
              value={form.account_id}
              onChange={(e) => setForm({ ...form, account_id: e.target.value })}
              style={{ ...selectStyle, width: '100%' }}
            >
              <option value="">Any account</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                  {a.institution ? ` — ${String(a.institution)}` : ''}
                </option>
              ))}
            </select>
          )}
        </div>

        <div
          style={{
            display: 'flex',
            gap: 8,
            justifyContent: 'flex-end',
            padding: '12px 20px',
            borderTop: '1px solid var(--border)',
          }}
        >
          <button type="button" onClick={onClose} style={cancelBtnStyle}>
            Cancel
          </button>
          <button
            type="button"
            disabled={!form.employer_name.trim() || !form.attributed_to_user_id || isPending}
            onClick={submit}
            style={{
              padding: '7px 16px',
              fontSize: 13,
              fontWeight: 500,
              background: 'var(--accent)',
              border: 'none',
              borderRadius: 8,
              color: 'var(--accent-fg)',
              cursor:
                !form.employer_name.trim() || !form.attributed_to_user_id || isPending
                  ? 'not-allowed'
                  : 'pointer',
              opacity:
                !form.employer_name.trim() || !form.attributed_to_user_id || isPending ? 0.6 : 1,
            }}
          >
            {isPending ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

export function IncomeSourcesTab({ householdId, incomeSources, members, accounts, qc }: Props) {
  const [modalSource, setModalSource] = useState<IncomeSourceOut | null | 'new'>('new' as never)
  const [modalOpen, setModalOpen] = useState(false)
  const [archiveConfirm, setArchiveConfirm] = useState<string | null>(null)

  const archive = useArchiveIncomeSourceApiV1HouseholdsHouseholdIdIncomeSourcesSourceIdDelete({
    mutation: {
      onSuccess: () => {
        void qc.invalidateQueries({
          queryKey:
            getListIncomeSourcesApiV1HouseholdsHouseholdIdIncomeSourcesGetQueryKey(householdId),
        })
        setArchiveConfirm(null)
      },
    },
  })

  function memberName(userId: string): string {
    const m = members.find((m) => m.user_id === userId)
    return m?.user.display_name || m?.user.email || 'Unknown'
  }

  function openAdd() {
    setModalSource(null)
    setModalOpen(true)
  }

  function openEdit(source: IncomeSourceOut) {
    setModalSource(source)
    setModalOpen(true)
  }

  function closeModal() {
    setModalOpen(false)
    setModalSource(null)
  }

  if (incomeSources.length === 0) {
    return (
      <>
        <div
          style={{
            padding: '40px 20px',
            textAlign: 'center',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 12,
          }}
        >
          <div style={{ fontSize: 13, color: 'var(--fg-muted)', marginBottom: 12 }}>
            Add an income source to improve payroll detection
          </div>
          <button type="button" onClick={openAdd} style={accentBtnStyle}>
            <Plus size={13} />
            Add income source
          </button>
        </div>
        {modalOpen && (
          <IncomeSourceModal
            householdId={householdId}
            source={modalSource as IncomeSourceOut | null}
            members={members}
            accounts={accounts}
            qc={qc}
            onClose={closeModal}
          />
        )}
      </>
    )
  }

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <button type="button" onClick={openAdd} style={accentBtnStyle}>
          <Plus size={13} />
          Add income source
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {incomeSources.map((src) => {
          const minAmt = parseFloat(src.expected_amount_min)
          const maxAmt = parseFloat(src.expected_amount_max)
          const sameAmt = Math.abs(minAmt - maxAmt) < 0.01

          return (
            <div
              key={src.id}
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                borderRadius: 10,
                padding: '14px 16px',
                display: 'flex',
                gap: 12,
                alignItems: 'flex-start',
              }}
            >
              {/* Color rail */}
              <div
                style={{
                  width: 3,
                  alignSelf: 'stretch',
                  borderRadius: 2,
                  background: 'var(--success)',
                  flexShrink: 0,
                }}
              />

              <div style={{ flex: 1, minWidth: 0 }}>
                {/* Top row */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span
                    style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)', flex: 1 }}
                  >
                    {src.employer_name}
                  </span>

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
                    {SUB_TYPE_LABELS[src.sub_type] ?? src.sub_type}
                  </span>
                </div>

                {/* Meta row */}
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '4px 16px',
                    fontSize: 12,
                    color: 'var(--fg-secondary)',
                  }}
                >
                  <span>
                    {sameAmt
                      ? fmt(minAmt, 'off', src.currency)
                      : `${fmt(minAmt, 'off', src.currency)} – ${fmt(maxAmt, 'off', src.currency)}`}{' '}
                    {src.currency}
                  </span>
                  <span style={{ color: 'var(--fg-muted)' }}>
                    {memberName(src.attributed_to_user_id)}
                  </span>
                  {src.expected_cadence && (
                    <span style={{ color: 'var(--fg-muted)' }}>{src.expected_cadence}</span>
                  )}
                  <span style={{ color: 'var(--fg-muted)' }}>
                    {VARIABILITY_LABELS[src.variability_model] ?? src.variability_model}
                  </span>
                </div>
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                <button type="button" onClick={() => openEdit(src)} style={iconBtnStyle}>
                  <Pencil size={13} />
                </button>
                <button
                  type="button"
                  onClick={() => setArchiveConfirm(src.id)}
                  style={{ ...iconBtnStyle, color: 'var(--fg-muted)' }}
                >
                  <Archive size={13} />
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {/* Add/Edit modal */}
      {modalOpen && (
        <IncomeSourceModal
          householdId={householdId}
          source={modalSource as IncomeSourceOut | null}
          members={members}
          accounts={accounts}
          qc={qc}
          onClose={closeModal}
        />
      )}

      {/* Archive confirm */}
      {archiveConfirm &&
        (() => {
          const src = incomeSources.find((s) => s.id === archiveConfirm)
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
              onClick={() => setArchiveConfirm(null)}
            >
              <div
                onClick={(e) => e.stopPropagation()}
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 12,
                  padding: 24,
                  width: 360,
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
                  Archive &ldquo;{src?.employer_name}&rdquo;?
                </h2>
                <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 20px' }}>
                  This income source will no longer be used for payroll matching.
                </p>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button
                    type="button"
                    onClick={() => setArchiveConfirm(null)}
                    style={cancelBtnStyle}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={archive.isPending}
                    onClick={() => archive.mutate({ householdId, sourceId: archiveConfirm })}
                    style={dangerBtnStyle}
                  >
                    {archive.isPending ? 'Archiving...' : 'Archive'}
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

const inputStyle: React.CSSProperties = {
  padding: '7px 10px',
  fontSize: 13,
  border: '1px solid var(--border)',
  borderRadius: 8,
  background: 'var(--bg-secondary)',
  color: 'var(--fg-primary)',
  outline: 'none',
}

const selectStyle: React.CSSProperties = {
  padding: '7px 10px',
  fontSize: 13,
  border: '1px solid var(--border)',
  borderRadius: 8,
  background: 'var(--bg-secondary)',
  color: 'var(--fg-primary)',
  outline: 'none',
  cursor: 'pointer',
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
