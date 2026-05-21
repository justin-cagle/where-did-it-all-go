import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, useLocation } from 'react-router-dom'
import QRCode from 'qrcode'
import { useAuthStore } from '@/store'
import {
  useTotpSetupApiV1AuthTotpSetupPost,
  useTotpConfirmApiV1AuthTotpConfirmPost,
} from '@/api/generated/households/households'
import { getMeApiV1AuthMeGetQueryKey } from '@/api/generated/households/households'
import { useQueryClient } from '@tanstack/react-query'
import { AuthLayout } from './LoginPage'

const schema = z.object({
  code: z.string().length(6, 'Enter the 6-digit code').regex(/^\d+$/, 'Digits only'),
})
type Fields = z.infer<typeof schema>

export function TotpSetupPage() {
  const { currentUser, setUser } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const qc = useQueryClient()
  const returnTo: string =
    (location.state as { returnTo?: string } | null)?.returnTo ?? '/onboarding'

  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null)
  const [secret, setSecret] = useState<string | null>(null)
  const [loadError, setLoadError] = useState('')

  const setupMutation = useTotpSetupApiV1AuthTotpSetupPost()
  const confirmMutation = useTotpConfirmApiV1AuthTotpConfirmPost()

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({ resolver: zodResolver(schema) })

  useEffect(() => {
    setupMutation
      .mutateAsync()
      .then(async (data) => {
        setSecret(data.secret)
        const url = await QRCode.toDataURL(data.provisioning_uri, { width: 160, margin: 1 })
        setQrDataUrl(url)
      })
      .catch(() => setLoadError('Failed to load QR code. Reload to retry.'))
    // run once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onSubmit = async (data: Fields) => {
    try {
      await confirmMutation.mutateAsync({ data: { totp_code: data.code } })
      if (currentUser) {
        setUser({ ...currentUser, totp_enabled: true })
      }
      await qc.invalidateQueries({ queryKey: getMeApiV1AuthMeGetQueryKey() })
      navigate(returnTo, { replace: true })
    } catch {
      setError('code', { message: 'Invalid code. Try again.' })
    }
  }

  return (
    <AuthLayout>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
          Set up two-factor auth
        </h1>
        <p style={{ fontSize: 13, color: 'var(--fg-muted)', margin: 0 }}>
          Scan this QR code with your authenticator app, then enter the 6-digit code.
        </p>
      </div>

      {loadError && <p style={{ fontSize: 13, color: 'var(--danger)', margin: 0 }}>{loadError}</p>}

      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          padding: 20,
          background: 'var(--bg-secondary)',
          borderRadius: 12,
          border: '1px solid var(--border)',
        }}
      >
        {qrDataUrl ? (
          <img
            src={qrDataUrl}
            alt="TOTP QR code"
            width={160}
            height={160}
            style={{ display: 'block' }}
          />
        ) : !loadError ? (
          <div
            style={{
              width: 160,
              height: 160,
              background: 'var(--border)',
              borderRadius: 8,
              animation: 'pulse 1.5s ease-in-out infinite',
            }}
          />
        ) : null}
      </div>

      {secret && (
        <p
          style={{
            fontSize: 11,
            color: 'var(--fg-muted)',
            margin: 0,
            wordBreak: 'break-all',
            textAlign: 'center',
          }}
        >
          Manual key: <span style={{ fontFamily: 'var(--font-mono)' }}>{secret}</span>
        </p>
      )}

      <form
        onSubmit={handleSubmit(onSubmit)}
        noValidate
        style={{ display: 'flex', flexDirection: 'column', gap: 16 }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-secondary)' }}>
            Verification code
          </label>
          <input
            {...register('code')}
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            placeholder="000000"
            style={{
              height: 48,
              padding: '0 16px',
              borderRadius: 8,
              border: `1px solid ${errors.code ? 'var(--danger)' : 'var(--border)'}`,
              background: 'var(--bg-primary)',
              color: 'var(--fg-primary)',
              fontSize: 24,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.3em',
              textAlign: 'center',
              outline: 'none',
              width: '100%',
            }}
          />
          {errors.code && (
            <p style={{ fontSize: 12, color: 'var(--danger)', margin: 0 }}>{errors.code.message}</p>
          )}
        </div>

        {errors.root && (
          <p style={{ fontSize: 13, color: 'var(--danger)', margin: 0 }}>{errors.root.message}</p>
        )}

        <button
          type="submit"
          disabled={isSubmitting || !qrDataUrl}
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
            opacity: isSubmitting || !qrDataUrl ? 0.6 : 1,
          }}
        >
          {isSubmitting ? 'Verifying...' : 'Verify and enable'}
        </button>
      </form>
    </AuthLayout>
  )
}
