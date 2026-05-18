import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { customInstance, ApiError } from '@/api/client'

const A = {
  bg: '#0a0f1a',
  bgRaised: '#111827',
  border: '#1f2937',
  fg: '#f9fafb',
  fgMuted: '#6b7280',
  accent: '#3b82f6',
  danger: '#ef4444',
}

const schema = z.object({
  password: z.string().min(1, 'Required'),
})
type FormData = z.infer<typeof schema>

interface StepUpModalProps {
  onSuccess: () => void
  onCancel: () => void
}

export function StepUpModal({ onSuccess, onCancel }: StepUpModalProps) {
  const [error, setError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  async function onSubmit(data: FormData) {
    setError(null)
    try {
      await customInstance({
        url: '/api/v1/auth/step-up',
        method: 'POST',
        data: { password: data.password },
      })
      onSuccess()
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Step-up failed')
      }
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={onCancel}
    >
      <div
        style={{
          background: A.bgRaised,
          border: `1px solid ${A.border}`,
          borderRadius: 10,
          padding: 24,
          width: 360,
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div>
          <div style={{ fontSize: 15, fontWeight: 600, color: A.fg }}>Confirm your identity</div>
          <div style={{ fontSize: 13, color: A.fgMuted, marginTop: 4 }}>
            Enter your password to continue this admin action.
          </div>
        </div>
        <form
          onSubmit={handleSubmit(onSubmit)}
          style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, color: A.fgMuted }}>Password</label>
            <input
              type="password"
              autoFocus
              {...register('password')}
              style={{
                background: A.bg,
                border: `1px solid ${errors.password ? A.danger : A.border}`,
                borderRadius: 6,
                padding: '8px 10px',
                color: A.fg,
                fontSize: 14,
                outline: 'none',
              }}
            />
            {errors.password && (
              <span style={{ fontSize: 12, color: A.danger }}>{errors.password.message}</span>
            )}
          </div>
          {error && <div style={{ fontSize: 13, color: A.danger }}>{error}</div>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button
              type="button"
              onClick={onCancel}
              style={{
                padding: '7px 14px',
                borderRadius: 6,
                background: 'transparent',
                border: `1px solid ${A.border}`,
                color: A.fgMuted,
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
                padding: '7px 14px',
                borderRadius: 6,
                background: A.accent,
                border: 'none',
                color: '#fff',
                fontSize: 13,
                fontWeight: 500,
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                opacity: isSubmitting ? 0.6 : 1,
              }}
            >
              {isSubmitting ? 'Verifying...' : 'Confirm'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
