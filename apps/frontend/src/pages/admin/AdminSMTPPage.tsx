import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  useGetSmtpApiV1AdminSmtpGet,
  getGetSmtpApiV1AdminSmtpGetQueryKey,
  useUpsertSmtpApiV1AdminSmtpPost,
  useDeleteSmtpApiV1AdminSmtpDelete,
  useTestSmtpApiV1AdminSmtpTestPost,
} from '@/api/generated/admin/admin'
import { StepUpModal } from '@/components/admin/StepUpModal'

const A = {
  bg: '#0a0f1a',
  bgRaised: '#111827',
  border: '#1f2937',
  fg: '#f9fafb',
  fgMuted: '#6b7280',
  accent: '#3b82f6',
  danger: '#ef4444',
  success: '#10b981',
}

const TLS_MODES = [
  { value: 'ssl', label: 'SSL/TLS', description: 'Implicit TLS (port 465)' },
  { value: 'starttls', label: 'STARTTLS', description: 'Upgrade to TLS (port 587)' },
  { value: 'none', label: 'None', description: 'No encryption (not recommended)' },
] as const

type TlsMode = 'ssl' | 'starttls' | 'none'

const smtpSchema = z.object({
  host: z.string().min(1, 'Required'),
  port: z.coerce.number().default(587),
  username: z.string().min(1, 'Required'),
  password: z.string().min(1, 'Required'),
  from_address: z.string().email('Valid email required'),
  tls_mode: z.enum(['ssl', 'starttls', 'none']).default('ssl'),
})
type SMTPFormData = z.infer<typeof smtpSchema>

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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 12, color: A.fgMuted }}>{label}</label>
      {children}
      {error && <span style={{ fontSize: 12, color: A.danger }}>{error}</span>}
    </div>
  )
}

const inputStyle = {
  padding: '7px 10px',
  borderRadius: 6,
  fontSize: 13,
  background: A.bg,
  border: `1px solid ${A.border}`,
  color: A.fg,
  outline: 'none',
}

export function AdminSMTPPage() {
  const qc = useQueryClient()
  const [stepUpFor, setStepUpFor] = useState<'save' | 'delete' | null>(null)
  const [pendingData, setPendingData] = useState<SMTPFormData | null>(null)
  const [showPassword, setShowPassword] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; detail: string | null } | null>(
    null
  )
  const [testing, setTesting] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(false)

  const { data: smtp } = useGetSmtpApiV1AdminSmtpGet()
  const upsert = useUpsertSmtpApiV1AdminSmtpPost()
  const deleteSMTP = useDeleteSmtpApiV1AdminSmtpDelete()
  const testSMTP = useTestSmtpApiV1AdminSmtpTestPost()

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SMTPFormData>({
    resolver: zodResolver(smtpSchema),
    defaultValues: {
      host: smtp?.host ?? '',
      port: smtp?.port ?? 587,
      username: smtp?.username ?? '',
      password: '',
      from_address: smtp?.from_address ?? '',
      tls_mode: (smtp?.tls_mode as TlsMode | undefined) ?? 'ssl',
    },
  })

  function invalidate() {
    void qc.invalidateQueries({ queryKey: getGetSmtpApiV1AdminSmtpGetQueryKey() })
  }

  async function doSave(data: SMTPFormData) {
    await upsert.mutateAsync({ data })
    invalidate()
  }

  async function doDelete() {
    await deleteSMTP.mutateAsync()
    setDeleteConfirm(false)
    invalidate()
  }

  async function doTest() {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await testSMTP.mutateAsync()
      setTestResult({ success: result.success, detail: result.error_detail ?? null })
      invalidate()
    } catch {
      setTestResult({ success: false, detail: 'Request failed' })
    } finally {
      setTesting(false)
    }
  }

  const isConfigured = smtp?.smtp_configured ?? false

  return (
    <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 600 }}>
      {stepUpFor === 'save' && pendingData && (
        <StepUpModal
          onSuccess={async () => {
            const d = pendingData
            setStepUpFor(null)
            setPendingData(null)
            await doSave(d)
          }}
          onCancel={() => {
            setStepUpFor(null)
            setPendingData(null)
          }}
        />
      )}
      {stepUpFor === 'delete' && (
        <StepUpModal
          onSuccess={async () => {
            setStepUpFor(null)
            await doDelete()
          }}
          onCancel={() => setStepUpFor(null)}
        />
      )}
      {deleteConfirm && (
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
        >
          <div
            style={{
              background: A.bgRaised,
              border: `1px solid ${A.border}`,
              borderRadius: 10,
              padding: 24,
              width: 380,
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 600, color: A.fg }}>Delete SMTP config</div>
            <div style={{ fontSize: 13, color: A.fgMuted }}>
              This will disable email delivery. Environment variable config will be used as fallback
              if set.
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setDeleteConfirm(false)}
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
                onClick={() => {
                  setDeleteConfirm(false)
                  setStepUpFor('delete')
                }}
                style={{
                  padding: '7px 14px',
                  borderRadius: 6,
                  background: A.danger,
                  border: 'none',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: A.fg, margin: 0 }}>SMTP</h1>
        <p style={{ fontSize: 13, color: A.fgMuted, margin: '4px 0 0' }}>
          Email delivery configuration
        </p>
      </div>

      {/* Current config status */}
      <div
        style={{
          background: A.bgRaised,
          border: `1px solid ${A.border}`,
          borderRadius: 10,
          padding: '18px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}
      >
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: A.fgMuted,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}
        >
          Current Status
        </div>
        {isConfigured ? (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, color: A.fgMuted }}>Host</span>
              <span style={{ fontSize: 13, color: A.fg }}>
                {smtp?.host}:{smtp?.port}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, color: A.fgMuted }}>From</span>
              <span style={{ fontSize: 13, color: A.fg }}>{smtp?.from_address}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, color: A.fgMuted }}>Username</span>
              <span style={{ fontSize: 13, color: A.fg }}>{smtp?.username}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, color: A.fgMuted }}>TLS mode</span>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  padding: '1px 6px',
                  borderRadius: 99,
                  background:
                    smtp?.tls_mode === 'none' ? `rgba(239,68,68,0.15)` : `rgba(16,185,129,0.15)`,
                  color: smtp?.tls_mode === 'none' ? A.danger : A.success,
                }}
              >
                {smtp?.tls_mode === 'ssl'
                  ? 'SSL/TLS'
                  : smtp?.tls_mode === 'starttls'
                    ? 'STARTTLS'
                    : 'None'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, color: A.fgMuted }}>Last test</span>
              <span
                style={{
                  fontSize: 12,
                  color:
                    smtp?.last_test_success === true
                      ? A.success
                      : smtp?.last_test_success === false
                        ? A.danger
                        : A.fgMuted,
                }}
              >
                {smtp?.last_test_success === true
                  ? 'Passed'
                  : smtp?.last_test_success === false
                    ? 'Failed'
                    : 'Not tested'}
              </span>
            </div>
          </>
        ) : (
          <div style={{ fontSize: 13, color: A.fgMuted }}>
            Email delivery is not configured. Without SMTP, invitation links must be shared
            manually. Admin notifications will only appear in the admin panel.
          </div>
        )}
      </div>

      {/* Test email */}
      {isConfigured && (
        <div
          style={{
            background: A.bgRaised,
            border: `1px solid ${A.border}`,
            borderRadius: 10,
            padding: '18px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: A.fgMuted,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            Test Email
          </div>
          <button
            onClick={doTest}
            disabled={testing}
            style={{
              alignSelf: 'flex-start',
              padding: '7px 14px',
              borderRadius: 6,
              background: A.accent,
              border: 'none',
              color: '#fff',
              fontSize: 13,
              fontWeight: 500,
              cursor: testing ? 'not-allowed' : 'pointer',
              opacity: testing ? 0.6 : 1,
            }}
          >
            {testing ? 'Sending...' : 'Send test email to admin address'}
          </button>
          {testResult && (
            <div style={{ fontSize: 13, color: testResult.success ? A.success : A.danger }}>
              {testResult.success
                ? 'Test email sent successfully'
                : `Failed: ${testResult.detail ?? 'Unknown error'}`}
            </div>
          )}
        </div>
      )}

      {/* Config form */}
      <form
        onSubmit={handleSubmit((data) => {
          setPendingData(data)
          setStepUpFor('save')
        })}
        style={{
          background: A.bgRaised,
          border: `1px solid ${A.border}`,
          borderRadius: 10,
          padding: '18px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
        }}
      >
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: A.fgMuted,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}
        >
          Configuration
        </div>
        <Field label="Host" error={errors.host?.message}>
          <input {...register('host')} style={inputStyle} placeholder="smtp.example.com" />
        </Field>
        <Field label="Port" error={errors.port?.message}>
          <input {...register('port')} type="number" style={{ ...inputStyle, width: 100 }} />
        </Field>
        <Field label="Username" error={errors.username?.message}>
          <input {...register('username')} style={inputStyle} />
        </Field>
        <Field label="Password" error={errors.password?.message}>
          <div style={{ position: 'relative' }}>
            <input
              {...register('password')}
              type={showPassword ? 'text' : 'password'}
              style={{ ...inputStyle, width: '100%', paddingRight: 64 }}
            />
            <button
              type="button"
              onClick={() => setShowPassword((p) => !p)}
              style={{
                position: 'absolute',
                right: 8,
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'transparent',
                border: 'none',
                color: A.fgMuted,
                fontSize: 11,
                cursor: 'pointer',
              }}
            >
              {showPassword ? 'Hide' : 'Show'}
            </button>
          </div>
        </Field>
        <Field label="From address" error={errors.from_address?.message}>
          <input
            {...register('from_address')}
            type="email"
            style={inputStyle}
            placeholder="noreply@example.com"
          />
        </Field>
        <Field label="TLS mode">
          <div style={{ display: 'flex', gap: 6 }}>
            {TLS_MODES.map((mode) => (
              <label
                key={mode.value}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                  flex: 1,
                  padding: '8px 10px',
                  borderRadius: 6,
                  border: `1px solid ${A.border}`,
                  cursor: 'pointer',
                  fontSize: 12,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <input
                    {...register('tls_mode')}
                    type="radio"
                    value={mode.value}
                    style={{ accentColor: A.accent }}
                  />
                  <span style={{ color: A.fg, fontWeight: 500 }}>{mode.label}</span>
                </div>
                <span style={{ color: A.fgMuted, paddingLeft: 18 }}>{mode.description}</span>
              </label>
            ))}
          </div>
        </Field>
        <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
          <button
            type="submit"
            style={{
              padding: '7px 16px',
              borderRadius: 6,
              background: A.accent,
              border: 'none',
              color: '#fff',
              fontSize: 13,
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            Save
          </button>
          {isConfigured && (
            <button
              type="button"
              onClick={() => setDeleteConfirm(true)}
              style={{
                padding: '7px 14px',
                borderRadius: 6,
                background: 'transparent',
                border: `1px solid ${A.danger}`,
                color: A.danger,
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              Delete config
            </button>
          )}
        </div>
      </form>
    </div>
  )
}
