import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { customInstance, ApiError } from '@/api/client'

type VisibilityMode =
  | 'fully_shared'
  | 'separate_with_joint_view'
  | 'role_based'
  | 'admin_controlled'

const VISIBILITY_OPTIONS: { value: VisibilityMode; label: string; description: string }[] = [
  {
    value: 'fully_shared',
    label: 'Fully shared',
    description: 'All members see all accounts and transactions.',
  },
  {
    value: 'separate_with_joint_view',
    label: 'Separate with joint view',
    description: 'Members have private views; a shared view aggregates everything.',
  },
  {
    value: 'role_based',
    label: 'Role-based',
    description: 'Visibility is controlled by the roles you assign to each member.',
  },
  {
    value: 'admin_controlled',
    label: 'Admin controlled',
    description: 'You explicitly grant access to each member.',
  },
]

const step1Schema = z.object({
  name: z.string().min(1, 'Household name is required').max(100),
  visibility_mode: z.enum([
    'fully_shared',
    'separate_with_joint_view',
    'role_based',
    'admin_controlled',
  ]),
})
type Step1Fields = z.infer<typeof step1Schema>

interface HouseholdResponse {
  id: string
  name: string
}

export function OnboardingPage() {
  const [step, setStep] = useState(1)
  const [householdId, setHouseholdId] = useState<string | null>(null)
  const [inviteEmail, setInviteEmail] = useState('')
  const [invites, setInvites] = useState<string[]>([])
  const [inviteError, setInviteError] = useState('')
  const [isInviting, setIsInviting] = useState(false)
  const navigate = useNavigate()

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<Step1Fields>({
    resolver: zodResolver(step1Schema),
    defaultValues: { visibility_mode: 'fully_shared' },
  })

  const selectedMode = watch('visibility_mode')

  const onStep1Submit = async (data: Step1Fields) => {
    try {
      const household = await customInstance<HouseholdResponse>({
        url: '/api/v1/households',
        method: 'POST',
        data: { name: data.name, visibility_mode: data.visibility_mode },
      })
      setHouseholdId(household.id)
      setStep(2)
    } catch {
      // step-level error not shown since no root error field here
    }
  }

  const addInvite = async () => {
    if (!inviteEmail.trim() || !householdId) return
    setIsInviting(true)
    setInviteError('')
    try {
      await customInstance({
        url: `/api/v1/households/${householdId}/members/invite`,
        method: 'POST',
        data: { email: inviteEmail.trim() },
      })
      setInvites((prev) => [...prev, inviteEmail.trim()])
      setInviteEmail('')
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setInviteError('No account found for that email.')
      } else {
        setInviteError('Failed to send invite. Try again.')
      }
    } finally {
      setIsInviting(false)
    }
  }

  const handleFinish = () => navigate('/dashboard', { replace: true })

  return (
    <div
      style={{
        minHeight: '100dvh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
        background: 'var(--bg-primary)',
      }}
    >
      <div
        style={{ width: '100%', maxWidth: 480, display: 'flex', flexDirection: 'column', gap: 32 }}
      >
        {/* Header */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: 'var(--accent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <span
                style={{
                  color: 'var(--accent-fg)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 16,
                  fontWeight: 600,
                }}
              >
                $
              </span>
            </div>
            <span
              style={{
                fontFamily: 'var(--font-sans)',
                fontSize: 18,
                fontWeight: 600,
                color: 'var(--fg-primary)',
              }}
            >
              wdiag
            </span>
          </div>

          {/* Step indicator */}
          <div style={{ display: 'flex', gap: 6 }}>
            {[1, 2, 3].map((s) => (
              <div
                key={s}
                style={{
                  height: 4,
                  flex: 1,
                  borderRadius: 99,
                  background: s <= step ? 'var(--accent)' : 'var(--border)',
                  transition: 'background 0.3s',
                }}
              />
            ))}
          </div>
        </div>

        {/* Card */}
        <div
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 16,
            padding: '28px 28px',
            boxShadow: 'var(--shadow)',
          }}
        >
          {step === 1 && (
            <form
              onSubmit={handleSubmit(onStep1Submit)}
              noValidate
              style={{ display: 'flex', flexDirection: 'column', gap: 20 }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <h2
                  style={{ fontSize: 20, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}
                >
                  Create your household
                </h2>
                <p style={{ fontSize: 13, color: 'var(--fg-muted)', margin: 0 }}>
                  A household groups all your financial data in one place.
                </p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-secondary)' }}>
                  Household name
                </label>
                <input
                  {...register('name')}
                  type="text"
                  placeholder="Home, Smith Family, My Finances..."
                  style={{
                    height: 40,
                    padding: '0 12px',
                    borderRadius: 8,
                    border: `1px solid ${errors.name ? 'var(--danger)' : 'var(--border)'}`,
                    background: 'var(--bg-primary)',
                    color: 'var(--fg-primary)',
                    fontSize: 14,
                    fontFamily: 'var(--font-sans)',
                    outline: 'none',
                    width: '100%',
                  }}
                />
                {errors.name && (
                  <p style={{ fontSize: 12, color: 'var(--danger)', margin: 0 }}>
                    {errors.name.message}
                  </p>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-secondary)' }}>
                  Visibility mode
                </label>
                {VISIBILITY_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    style={{
                      display: 'flex',
                      gap: 12,
                      padding: '12px 14px',
                      borderRadius: 10,
                      border: `1px solid ${selectedMode === opt.value ? 'var(--accent)' : 'var(--border)'}`,
                      background:
                        selectedMode === opt.value
                          ? 'color-mix(in oklch, var(--accent) 8%, transparent)'
                          : 'transparent',
                      cursor: 'pointer',
                      transition: 'border-color 0.15s, background 0.15s',
                    }}
                  >
                    <input
                      type="radio"
                      {...register('visibility_mode')}
                      value={opt.value}
                      checked={selectedMode === opt.value}
                      onChange={() => setValue('visibility_mode', opt.value)}
                      style={{ marginTop: 2, accentColor: 'var(--accent)', flexShrink: 0 }}
                    />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
                        {opt.label}
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
                        {opt.description}
                      </span>
                    </div>
                  </label>
                ))}
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                style={{
                  height: 40,
                  borderRadius: 8,
                  border: 'none',
                  background: 'var(--accent)',
                  color: 'var(--accent-fg)',
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontFamily: 'var(--font-sans)',
                  opacity: isSubmitting ? 0.6 : 1,
                }}
              >
                {isSubmitting ? 'Creating...' : 'Continue'}
              </button>
            </form>
          )}

          {step === 2 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <h2
                  style={{ fontSize: 20, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}
                >
                  Invite members
                </h2>
                <p style={{ fontSize: 13, color: 'var(--fg-muted)', margin: 0 }}>
                  You can skip this — invite people anytime from Settings.
                </p>
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      void addInvite()
                    }
                  }}
                  placeholder="email@example.com"
                  style={{
                    flex: 1,
                    height: 40,
                    padding: '0 12px',
                    borderRadius: 8,
                    border: '1px solid var(--border)',
                    background: 'var(--bg-primary)',
                    color: 'var(--fg-primary)',
                    fontSize: 14,
                    fontFamily: 'var(--font-sans)',
                    outline: 'none',
                  }}
                />
                <button
                  type="button"
                  onClick={() => void addInvite()}
                  disabled={isInviting || !inviteEmail.trim()}
                  style={{
                    height: 40,
                    padding: '0 16px',
                    borderRadius: 8,
                    border: 'none',
                    background: 'var(--bg-secondary)',
                    color: 'var(--fg-secondary)',
                    fontSize: 13,
                    fontWeight: 500,
                    cursor: 'pointer',
                    fontFamily: 'var(--font-sans)',
                  }}
                >
                  {isInviting ? '...' : 'Invite'}
                </button>
              </div>

              {inviteError && (
                <p style={{ fontSize: 12, color: 'var(--danger)', margin: 0 }}>{inviteError}</p>
              )}

              {invites.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {invites.map((email) => (
                    <div
                      key={email}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: '8px 12px',
                        borderRadius: 8,
                        background: 'var(--bg-secondary)',
                        fontSize: 13,
                      }}
                    >
                      <div
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          background: 'var(--success)',
                          flexShrink: 0,
                        }}
                      />
                      <span style={{ color: 'var(--fg-secondary)' }}>Invite sent to</span>
                      <span style={{ color: 'var(--fg-primary)', fontWeight: 500 }}>{email}</span>
                    </div>
                  ))}
                </div>
              )}

              <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                <button
                  type="button"
                  onClick={() => setStep(3)}
                  style={{
                    flex: 1,
                    height: 40,
                    borderRadius: 8,
                    border: '1px solid var(--border)',
                    background: 'transparent',
                    color: 'var(--fg-secondary)',
                    fontSize: 14,
                    cursor: 'pointer',
                    fontFamily: 'var(--font-sans)',
                  }}
                >
                  Skip
                </button>
                <button
                  type="button"
                  onClick={() => setStep(3)}
                  style={{
                    flex: 1,
                    height: 40,
                    borderRadius: 8,
                    border: 'none',
                    background: 'var(--accent)',
                    color: 'var(--accent-fg)',
                    fontSize: 14,
                    fontWeight: 600,
                    cursor: 'pointer',
                    fontFamily: 'var(--font-sans)',
                  }}
                >
                  Continue
                </button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <h2
                  style={{ fontSize: 20, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}
                >
                  You're all set!
                </h2>
                <p style={{ fontSize: 13, color: 'var(--fg-muted)', margin: 0 }}>
                  Your household is ready. Start by adding your accounts.
                </p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[
                  { label: 'Household created', done: true },
                  {
                    label: `${invites.length} member${invites.length !== 1 ? 's' : ''} invited`,
                    done: invites.length > 0,
                  },
                ].map(({ label, done }) => (
                  <div
                    key={label}
                    style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13 }}
                  >
                    <div
                      style={{
                        width: 20,
                        height: 20,
                        borderRadius: '50%',
                        background: done ? 'var(--success)' : 'var(--border)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      {done && (
                        <svg
                          width="10"
                          height="10"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="white"
                          strokeWidth="3"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      )}
                    </div>
                    <span style={{ color: done ? 'var(--fg-primary)' : 'var(--fg-muted)' }}>
                      {label}
                    </span>
                  </div>
                ))}
              </div>

              <button
                type="button"
                onClick={handleFinish}
                style={{
                  height: 44,
                  borderRadius: 8,
                  border: 'none',
                  background: 'var(--accent)',
                  color: 'var(--accent-fg)',
                  fontSize: 15,
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontFamily: 'var(--font-sans)',
                }}
              >
                Go to Dashboard
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
