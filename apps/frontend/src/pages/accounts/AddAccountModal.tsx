import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import {
  useCreateAccountApiV1HouseholdsHouseholdIdAccountsPost,
  useCreateDebtAnnotationApiV1HouseholdsHouseholdIdAccountsAccountIdDebtPost,
  getListAccountsApiV1HouseholdsHouseholdIdAccountsGetQueryKey,
} from '@/api/generated/accounts/accounts'
import { isLiabilityType } from '@/domain/accounts'
import { ApiError } from '@/api/client'

const ACCOUNT_TYPES = [
  { value: 'checking', label: 'Checking' },
  { value: 'savings', label: 'Savings' },
  { value: 'credit_card', label: 'Credit Card' },
  { value: 'investment', label: 'Investment' },
  { value: 'loan', label: 'Loan' },
  { value: 'line_of_credit', label: 'Line of Credit' },
  { value: 'manual', label: 'Manual' },
] as const

const MIN_PAYMENT_STRATEGIES = [
  { value: 'fixed_amount', label: 'Fixed amount' },
  { value: 'percentage_of_balance', label: 'Percentage of balance' },
  { value: 'from_statement', label: 'From statement' },
] as const

const formSchema = z.object({
  name: z.string().min(1, 'Required').max(255),
  institution: z.string().max(255).optional(),
  account_type: z.enum([
    'checking',
    'savings',
    'credit_card',
    'investment',
    'loan',
    'line_of_credit',
    'manual',
  ]),
  currency: z.string().length(3, 'Must be 3 characters').default('USD'),
  current_balance: z
    .string()
    .regex(/^[+-]?\d*\.?\d*$/, 'Invalid amount')
    .optional(),
  apr_pct: z
    .string()
    .regex(/^\d*\.?\d*$/, 'Invalid APR')
    .optional(),
  minimum_payment_strategy: z
    .enum(['fixed_amount', 'percentage_of_balance', 'from_statement'])
    .optional(),
  statement_day: z.coerce.number().int().min(1).max(31).optional().or(z.literal('')),
  due_day: z.coerce.number().int().min(1).max(31).optional().or(z.literal('')),
})

type FormValues = z.infer<typeof formSchema>

interface AddAccountModalProps {
  householdId: string
  open: boolean
  onClose: () => void
  onAdded?: () => void
}

export function AddAccountModal({ householdId, open, onClose, onAdded }: AddAccountModalProps) {
  const [apiError, setApiError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const createAccount = useCreateAccountApiV1HouseholdsHouseholdIdAccountsPost()
  const createDebtAnnotation =
    useCreateDebtAnnotationApiV1HouseholdsHouseholdIdAccountsAccountIdDebtPost()

  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { account_type: 'checking', currency: 'USD' },
  })

  const accountType = watch('account_type')
  const isDebt = isLiabilityType(accountType)

  const onSubmit = async (values: FormValues) => {
    setApiError(null)
    try {
      const account = await createAccount.mutateAsync({
        householdId,
        data: {
          name: values.name,
          institution: values.institution ?? undefined,
          account_type: values.account_type,
          currency: values.currency,
          current_balance: values.current_balance ?? undefined,
        },
      })

      if (isDebt && values.apr_pct) {
        const aprDecimal = String(parseFloat(values.apr_pct) / 100)
        await createDebtAnnotation.mutateAsync({
          householdId,
          accountId: account.id,
          data: {
            initial_balance: values.current_balance ?? '0',
            initial_apr: aprDecimal,
            effective_from:
              new Date().toISOString().split('T')[0] ?? new Date().toISOString().slice(0, 10),
            minimum_payment_strategy: values.minimum_payment_strategy ?? undefined,
            statement_day:
              typeof values.statement_day === 'number' ? values.statement_day : undefined,
            due_day: typeof values.due_day === 'number' ? values.due_day : undefined,
          },
        })
      }

      await queryClient.invalidateQueries({
        queryKey: getListAccountsApiV1HouseholdsHouseholdIdAccountsGetQueryKey(householdId),
      })

      reset()
      onAdded?.()
      onClose()
    } catch (err) {
      if (err instanceof ApiError) {
        setApiError(err.message)
      } else {
        setApiError('Something went wrong. Try again.')
      }
    }
  }

  if (!open) return null

  return (
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
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 16,
          padding: 24,
          width: '100%',
          maxWidth: 480,
          maxHeight: '90dvh',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-primary)' }}>
            Add account
          </span>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--fg-muted)',
              display: 'flex',
            }}
          >
            <X size={18} />
          </button>
        </div>

        <form
          onSubmit={(e) => void handleSubmit(onSubmit)(e)}
          style={{ display: 'flex', flexDirection: 'column', gap: 14 }}
        >
          <Field label="Account type" error={errors.account_type?.message}>
            <select {...register('account_type')} style={selectStyle}>
              {ACCOUNT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Account name" error={errors.name?.message}>
            <input {...register('name')} placeholder="e.g. Checking ···4821" style={inputStyle} />
          </Field>

          <Field label="Institution" error={errors.institution?.message}>
            <input {...register('institution')} placeholder="e.g. Chase, Ally" style={inputStyle} />
          </Field>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <Field label="Current balance" error={errors.current_balance?.message}>
              <input {...register('current_balance')} placeholder="0.00" style={inputStyle} />
            </Field>
            <Field label="Currency" error={errors.currency?.message}>
              <input
                {...register('currency')}
                placeholder="USD"
                maxLength={3}
                style={{ ...inputStyle, textTransform: 'uppercase' }}
              />
            </Field>
          </div>

          {isDebt && (
            <>
              <div
                style={{
                  height: 1,
                  background: 'var(--border)',
                  margin: '2px 0',
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--fg-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                Debt details
              </span>

              <Field label="APR (%)" error={errors.apr_pct?.message}>
                <input {...register('apr_pct')} placeholder="e.g. 24.99" style={inputStyle} />
              </Field>

              <Field
                label="Minimum payment strategy"
                error={errors.minimum_payment_strategy?.message}
              >
                <select {...register('minimum_payment_strategy')} style={selectStyle}>
                  <option value="">Select…</option>
                  {MIN_PAYMENT_STRATEGIES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </Field>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <Field label="Statement day" error={errors.statement_day?.message}>
                  <input
                    {...register('statement_day')}
                    type="number"
                    min={1}
                    max={31}
                    placeholder="1–31"
                    style={inputStyle}
                  />
                </Field>
                <Field label="Due day" error={errors.due_day?.message}>
                  <input
                    {...register('due_day')}
                    type="number"
                    min={1}
                    max={31}
                    placeholder="1–31"
                    style={inputStyle}
                  />
                </Field>
              </div>
            </>
          )}

          {apiError && (
            <div
              style={{
                fontSize: 12,
                color: 'var(--danger)',
                padding: '8px 12px',
                background: 'color-mix(in oklch, var(--danger) 10%, transparent)',
                borderRadius: 6,
              }}
            >
              {apiError}
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            style={{
              fontSize: 14,
              fontWeight: 500,
              padding: '10px 0',
              borderRadius: 8,
              border: 'none',
              background: isSubmitting ? 'var(--border)' : 'var(--accent)',
              color: isSubmitting ? 'var(--fg-muted)' : 'var(--accent-fg)',
              cursor: isSubmitting ? 'not-allowed' : 'pointer',
              marginTop: 4,
            }}
          >
            {isSubmitting ? 'Adding…' : 'Add account'}
          </button>
        </form>
      </div>
    </div>
  )
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
      <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg-secondary)' }}>{label}</label>
      {children}
      {error && <span style={{ fontSize: 11, color: 'var(--danger)' }}>{error}</span>}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  borderRadius: 7,
  border: '1px solid var(--border)',
  background: 'var(--bg-primary)',
  color: 'var(--fg-primary)',
  fontSize: 13,
  outline: 'none',
  boxSizing: 'border-box',
}

const selectStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  borderRadius: 7,
  border: '1px solid var(--border)',
  background: 'var(--bg-primary)',
  color: 'var(--fg-primary)',
  fontSize: 13,
  outline: 'none',
  cursor: 'pointer',
  boxSizing: 'border-box',
}
