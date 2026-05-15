import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { X } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import type { AccountOut } from '@/api/generated/model/accountOut'
import { useCreateTransactionApiV1HouseholdsHouseholdIdAccountsAccountIdTransactionsPost } from '@/api/generated/transactions/transactions'
import { getListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGetQueryKey } from '@/api/generated/transactions/transactions'

const schema = z.object({
  account_id: z.string().min(1, 'Account required'),
  amount: z
    .string()
    .min(1, 'Amount required')
    .refine((v) => !isNaN(parseFloat(v)) && parseFloat(v) > 0, 'Must be positive'),
  direction: z.enum(['debit', 'credit']),
  description: z.string().min(1, 'Description required'),
  merchant_name: z.string().optional(),
  posted_date: z.string().min(1, 'Date required'),
  currency: z.string().default('USD'),
})

type FormData = z.infer<typeof schema>

interface Props {
  householdId: string
  accounts: AccountOut[]
  open: boolean
  onClose: () => void
}

export function AddTransactionModal({ householdId, accounts, open, onClose }: Props) {
  const qc = useQueryClient()

  const today = new Date()
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      direction: 'debit',
      posted_date: todayStr,
      currency: 'USD',
    },
  })

  const { mutateAsync } =
    useCreateTransactionApiV1HouseholdsHouseholdIdAccountsAccountIdTransactionsPost()

  useEffect(() => {
    if (!open) reset()
  }, [open, reset])

  if (!open) return null

  async function onSubmit(data: FormData) {
    await mutateAsync({
      householdId,
      accountId: data.account_id,
      data: {
        amount: data.amount,
        currency: data.currency,
        direction: data.direction,
        description: data.description,
        merchant_name: data.merchant_name ?? undefined,
        posted_date: data.posted_date,
        occurred_at: `${data.posted_date}T00:00:00Z`,
        state: 'posted',
        transaction_type: 'regular',
      },
    })
    await qc.invalidateQueries({
      queryKey:
        getListTransactionsCrossAccountApiV1HouseholdsHouseholdIdTransactionsGetQueryKey(
          householdId
        ),
    })
    onClose()
  }

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.5)',
          zIndex: 200,
        }}
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
          padding: '24px',
          width: 440,
          maxWidth: 'calc(100vw - 32px)',
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-primary)' }}>
            Add transaction
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

        <form
          onSubmit={(e) => void handleSubmit(onSubmit)(e)}
          style={{ display: 'flex', flexDirection: 'column', gap: 14 }}
        >
          <Field label="Account" error={errors.account_id?.message}>
            <select {...register('account_id')} style={inputStyle}>
              <option value="">Select account...</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </Field>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10 }}>
            <Field label="Amount" error={errors.amount?.message}>
              <input
                {...register('amount')}
                type="number"
                step="0.01"
                min="0.01"
                placeholder="0.00"
                style={inputStyle}
              />
            </Field>
            <Field label="Direction" error={errors.direction?.message}>
              <select {...register('direction')} style={inputStyle}>
                <option value="debit">Debit (expense)</option>
                <option value="credit">Credit (income)</option>
              </select>
            </Field>
          </div>

          <Field label="Description" error={errors.description?.message}>
            <input
              {...register('description')}
              placeholder="What was this for?"
              style={inputStyle}
            />
          </Field>

          <Field label="Merchant name (optional)" error={errors.merchant_name?.message}>
            <input
              {...register('merchant_name')}
              placeholder="e.g. Whole Foods"
              style={inputStyle}
            />
          </Field>

          <Field label="Date" error={errors.posted_date?.message}>
            <input {...register('posted_date')} type="date" style={inputStyle} />
          </Field>

          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                flex: 1,
                padding: '9px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'none',
                color: 'var(--fg-secondary)',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              style={{
                flex: 1,
                padding: '9px',
                borderRadius: 8,
                border: 'none',
                background: 'var(--accent)',
                color: 'var(--accent-fg)',
                fontSize: 13,
                fontWeight: 500,
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                opacity: isSubmitting ? 0.7 : 1,
              }}
            >
              {isSubmitting ? 'Saving...' : 'Add transaction'}
            </button>
          </div>
        </form>
      </div>
    </>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'var(--bg-primary)',
  color: 'var(--fg-primary)',
  fontSize: 13,
  outline: 'none',
  boxSizing: 'border-box',
}

function Field({
  label,
  error,
  children,
}: {
  label: string
  error?: string
  children: React.ReactNode
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-muted)' }}>{label}</label>
      {children}
      {error && <span style={{ fontSize: 11, color: 'var(--danger)' }}>{error}</span>}
    </div>
  )
}
