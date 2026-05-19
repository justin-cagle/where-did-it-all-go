import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeft, Info, CheckCircle2 } from 'lucide-react'
import { useHousehold } from '@/hooks/use-household'
import {
  useUploadFileApiV1HouseholdsHouseholdIdIngestUploadPost,
  useGetCsvMappingApiV1HouseholdsHouseholdIdIngestCsvMappingsInstitutionNameGet,
  useUpsertCsvMappingApiV1HouseholdsHouseholdIdIngestCsvMappingsPost,
} from '@/api/generated/ingest/ingest'
import { useListAccountsApiV1HouseholdsHouseholdIdAccountsGet } from '@/api/generated/accounts/accounts'
import type { AccountOut } from '@/api/generated/model/accountOut'
import type { BodyUploadFileApiV1HouseholdsHouseholdIdIngestUploadPost } from '@/api/generated/model/bodyUploadFileApiV1HouseholdsHouseholdIdIngestUploadPost'

const DATE_FORMATS = [
  { value: '%Y-%m-%d', label: 'YYYY-MM-DD' },
  { value: '%m/%d/%Y', label: 'MM/DD/YYYY' },
  { value: '%d/%m/%Y', label: 'DD/MM/YYYY' },
  { value: '%m-%d-%Y', label: 'MM-DD-YYYY' },
  { value: '%d-%m-%Y', label: 'DD-MM-YYYY' },
  { value: '%m/%d/%y', label: 'MM/DD/YY' },
]

const AMOUNT_CONVENTIONS = [
  { value: 'positive_is_debit', label: 'Positive = debit (most banks)' },
  { value: 'positive_is_credit', label: 'Positive = credit' },
]

const REQUIRED_COLS = ['date', 'amount', 'description'] as const
const OPTIONAL_COLS = ['merchant', 'currency'] as const

function parseCSVHeaders(text: string): string[] {
  const first = text.split('\n')[0] ?? ''
  if (!first.trim()) return []
  const cols: string[] = []
  let cur = ''
  let inQ = false
  for (const ch of first) {
    if (ch === '"') {
      inQ = !inQ
    } else if (ch === ',' && !inQ) {
      cols.push(cur.trim())
      cur = ''
    } else {
      cur += ch
    }
  }
  cols.push(cur.trim())
  return cols
}

function AccountSelect({
  accounts,
  value,
  onChange,
}: {
  accounts: AccountOut[]
  value: string
  onChange: (v: string) => void
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        fontSize: 13,
        padding: '8px 12px',
        borderRadius: 8,
        border: `1px solid ${value ? 'var(--border)' : 'var(--danger)'}`,
        background: 'var(--bg-secondary)',
        color: 'var(--fg-primary)',
        cursor: 'pointer',
        width: '100%',
      }}
    >
      <option value="">Select account...</option>
      {accounts.map((a) => (
        <option key={a.id} value={a.id}>
          {a.name}
          {a.institution ? ` — ${a.institution}` : ''}
        </option>
      ))}
    </select>
  )
}

function OFXFlow({
  file,
  accounts,
  householdId,
  onDone,
}: {
  file: File
  accounts: AccountOut[]
  householdId: string
  onDone: (jobId: string) => void
}) {
  const [accountId, setAccountId] = useState('')
  const uploadMut = useUploadFileApiV1HouseholdsHouseholdIdIngestUploadPost()

  function handleUpload() {
    if (!accountId) return
    uploadMut.mutate(
      {
        householdId,
        data: {
          file: file as unknown as BodyUploadFileApiV1HouseholdsHouseholdIdIngestUploadPost['file'],
        },
        params: { account_id: accountId, source: 'ofx_upload' },
      },
      {
        onSuccess: (res) => {
          onDone(res.import_job_id)
        },
      }
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div
        style={{
          padding: '10px 14px',
          background: 'var(--bg-secondary)',
          borderRadius: 8,
          fontSize: 12,
          color: 'var(--fg-muted)',
          display: 'flex',
          alignItems: 'flex-start',
          gap: 8,
        }}
      >
        <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
        OFX/QFX files contain account and transaction data. Select which account to import into.
      </div>

      <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
          Import into account
        </span>
        <AccountSelect accounts={accounts} value={accountId} onChange={setAccountId} />
      </label>

      {uploadMut.isError && (
        <div
          style={{
            fontSize: 13,
            padding: '10px 14px',
            borderRadius: 8,
            background: 'color-mix(in oklch, var(--danger) 10%, transparent)',
            border: '1px solid color-mix(in oklch, var(--danger) 30%, transparent)',
            color: 'var(--danger)',
          }}
        >
          Upload failed. Check the file format and try again.
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={handleUpload}
          disabled={!accountId || uploadMut.isPending}
          style={{
            fontSize: 13,
            fontWeight: 600,
            padding: '8px 22px',
            borderRadius: 8,
            background: 'var(--accent)',
            color: 'var(--accent-fg)',
            border: 'none',
            cursor: !accountId || uploadMut.isPending ? 'not-allowed' : 'pointer',
            opacity: !accountId || uploadMut.isPending ? 0.6 : 1,
          }}
        >
          {uploadMut.isPending ? 'Uploading...' : 'Import'}
        </button>
      </div>
    </div>
  )
}

function CSVFlow({
  file,
  accounts,
  householdId,
  onDone,
}: {
  file: File
  accounts: AccountOut[]
  householdId: string
  onDone: (jobId: string) => void
}) {
  const [accountId, setAccountId] = useState('')
  const [institutionName, setInstitutionName] = useState('')
  const [csvHeaders, setCsvHeaders] = useState<string[]>([])
  const [colMap, setColMap] = useState<Record<string, string>>({
    date: '',
    amount: '',
    description: '',
    merchant: '',
    currency: '',
  })
  const [dateFormat, setDateFormat] = useState('%Y-%m-%d')
  const [amountConvention, setAmountConvention] = useState('positive_is_debit')
  const [savedMappingApplied, setSavedMappingApplied] = useState(false)
  const [lookupName, setLookupName] = useState('')

  useEffect(() => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const text = (e.target?.result as string) ?? ''
      setCsvHeaders(parseCSVHeaders(text))
    }
    reader.readAsText(file.slice(0, 4096))
  }, [file])

  useEffect(() => {
    const timer = setTimeout(() => {
      if (institutionName.trim().length >= 3) {
        setLookupName(institutionName.trim())
      } else {
        setLookupName('')
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [institutionName])

  const { data: savedMapping } =
    useGetCsvMappingApiV1HouseholdsHouseholdIdIngestCsvMappingsInstitutionNameGet(
      householdId,
      lookupName,
      { query: { enabled: !!householdId && lookupName.length >= 3 } }
    )

  const upsertMut = useUpsertCsvMappingApiV1HouseholdsHouseholdIdIngestCsvMappingsPost()
  const uploadMut = useUploadFileApiV1HouseholdsHouseholdIdIngestUploadPost()

  function applySavedMapping() {
    if (!savedMapping) return
    const cm = (savedMapping.column_map ?? {}) as Record<string, string>
    setColMap((prev) => ({ ...prev, ...cm }))
    if (savedMapping.date_format) setDateFormat(savedMapping.date_format)
    if (savedMapping.amount_convention) setAmountConvention(savedMapping.amount_convention)
    setSavedMappingApplied(true)
  }

  const requiredFilled = REQUIRED_COLS.every((k) => colMap[k]?.trim())
  const canUpload = !!accountId && requiredFilled

  function handleUpload() {
    if (!canUpload) return

    const csvConfig = {
      column_mapping: {
        date: colMap.date,
        amount: colMap.amount,
        description: colMap.description,
        ...(colMap.merchant ? { merchant: colMap.merchant } : {}),
        ...(colMap.currency ? { currency: colMap.currency } : {}),
      },
      date_format: dateFormat,
      amount_sign: amountConvention,
      default_currency: 'USD',
    }

    const doUpload = () => {
      uploadMut.mutate(
        {
          householdId,
          data: {
            file: file as unknown as BodyUploadFileApiV1HouseholdsHouseholdIdIngestUploadPost['file'],
          },
          params: {
            account_id: accountId,
            source: 'csv_upload',
            csv_config: JSON.stringify(csvConfig),
          },
        },
        {
          onSuccess: (res) => {
            onDone(res.import_job_id)
          },
        }
      )
    }

    if (institutionName.trim()) {
      upsertMut.mutate(
        {
          householdId,
          data: {
            institution_name: institutionName.trim(),
            column_map: csvConfig.column_mapping as Record<string, unknown>,
            date_format: dateFormat,
            amount_convention: amountConvention,
          },
        },
        { onSuccess: doUpload, onError: doUpload }
      )
    } else {
      doUpload()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
          Import into account
        </span>
        <AccountSelect accounts={accounts} value={accountId} onChange={setAccountId} />
      </label>

      <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
          Institution name{' '}
          <span style={{ fontWeight: 400, color: 'var(--fg-muted)', fontSize: 12 }}>
            (optional — saves your column mapping for next time)
          </span>
        </span>
        <input
          type="text"
          value={institutionName}
          onChange={(e) => {
            setInstitutionName(e.target.value)
            setSavedMappingApplied(false)
          }}
          placeholder="e.g. Chase, Wells Fargo"
          style={{
            fontSize: 13,
            padding: '8px 12px',
            borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'var(--bg-secondary)',
            color: 'var(--fg-primary)',
          }}
        />
      </label>

      {savedMapping && !savedMappingApplied && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            padding: '10px 14px',
            background: 'color-mix(in oklch, var(--accent) 8%, transparent)',
            border: '1px solid color-mix(in oklch, var(--accent) 25%, transparent)',
            borderRadius: 8,
            fontSize: 13,
          }}
        >
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--fg-primary)' }}
          >
            <CheckCircle2 size={14} style={{ color: 'var(--accent)' }} />
            Saved mapping found for {savedMapping.institution_name}
          </div>
          <button
            onClick={applySavedMapping}
            style={{
              fontSize: 12,
              fontWeight: 600,
              padding: '4px 12px',
              borderRadius: 6,
              background: 'var(--accent)',
              color: 'var(--accent-fg)',
              border: 'none',
              cursor: 'pointer',
              flexShrink: 0,
            }}
          >
            Use it
          </button>
        </div>
      )}

      {savedMappingApplied && (
        <div
          style={{
            padding: '8px 12px',
            background: 'color-mix(in oklch, var(--success) 8%, transparent)',
            border: '1px solid color-mix(in oklch, var(--success) 25%, transparent)',
            borderRadius: 8,
            fontSize: 12,
            color: 'var(--fg-muted)',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <CheckCircle2 size={13} style={{ color: 'var(--success)' }} />
          Saved mapping applied
        </div>
      )}

      {csvHeaders.length > 0 && (
        <div>
          <div
            style={{
              fontSize: 13,
              fontWeight: 500,
              color: 'var(--fg-primary)',
              marginBottom: 12,
            }}
          >
            Column mapping
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {([...REQUIRED_COLS, ...OPTIONAL_COLS] as string[]).map((field) => (
              <div key={field} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: 'var(--fg-primary)',
                    width: 90,
                    flexShrink: 0,
                  }}
                >
                  {field.charAt(0).toUpperCase() + field.slice(1)}
                  {(REQUIRED_COLS as readonly string[]).includes(field) && (
                    <span style={{ color: 'var(--danger)' }}> *</span>
                  )}
                </span>
                <select
                  value={colMap[field] ?? ''}
                  onChange={(e) => setColMap((prev) => ({ ...prev, [field]: e.target.value }))}
                  style={{
                    flex: 1,
                    fontSize: 12,
                    padding: '6px 10px',
                    borderRadius: 6,
                    border: `1px solid ${(REQUIRED_COLS as readonly string[]).includes(field) && !colMap[field] ? 'var(--danger)' : 'var(--border)'}`,
                    background: 'var(--bg-secondary)',
                    color: 'var(--fg-primary)',
                    cursor: 'pointer',
                  }}
                >
                  <option value="">
                    {(REQUIRED_COLS as readonly string[]).includes(field)
                      ? 'Select column...'
                      : '— optional —'}
                  </option>
                  {csvHeaders.map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </div>
      )}

      {csvHeaders.length === 0 && (
        <div
          style={{
            padding: '10px 14px',
            background: 'color-mix(in oklch, var(--warning) 8%, transparent)',
            border: '1px solid color-mix(in oklch, var(--warning) 25%, transparent)',
            borderRadius: 8,
            fontSize: 12,
            color: 'var(--fg-muted)',
          }}
        >
          Could not read CSV headers. Make sure the file has a header row.
        </div>
      )}

      <div style={{ display: 'flex', gap: 16 }}>
        <label style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
            Date format
          </span>
          <select
            value={dateFormat}
            onChange={(e) => setDateFormat(e.target.value)}
            style={{
              fontSize: 12,
              padding: '7px 10px',
              borderRadius: 7,
              border: '1px solid var(--border)',
              background: 'var(--bg-secondary)',
              color: 'var(--fg-primary)',
              cursor: 'pointer',
            }}
          >
            {DATE_FORMATS.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}>
            Amount sign
          </span>
          <select
            value={amountConvention}
            onChange={(e) => setAmountConvention(e.target.value)}
            style={{
              fontSize: 12,
              padding: '7px 10px',
              borderRadius: 7,
              border: '1px solid var(--border)',
              background: 'var(--bg-secondary)',
              color: 'var(--fg-primary)',
              cursor: 'pointer',
            }}
          >
            {AMOUNT_CONVENTIONS.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {uploadMut.isError && (
        <div
          style={{
            fontSize: 13,
            padding: '10px 14px',
            borderRadius: 8,
            background: 'color-mix(in oklch, var(--danger) 10%, transparent)',
            border: '1px solid color-mix(in oklch, var(--danger) 30%, transparent)',
            color: 'var(--danger)',
          }}
        >
          Upload failed. Check your column mapping and try again.
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={handleUpload}
          disabled={!canUpload || uploadMut.isPending || upsertMut.isPending}
          style={{
            fontSize: 13,
            fontWeight: 600,
            padding: '8px 22px',
            borderRadius: 8,
            background: 'var(--accent)',
            color: 'var(--accent-fg)',
            border: 'none',
            cursor:
              !canUpload || uploadMut.isPending || upsertMut.isPending ? 'not-allowed' : 'pointer',
            opacity: !canUpload || uploadMut.isPending || upsertMut.isPending ? 0.6 : 1,
          }}
        >
          {uploadMut.isPending || upsertMut.isPending ? 'Uploading...' : 'Import'}
        </button>
      </div>
    </div>
  )
}

export function FileUploadPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { householdId } = useHousehold()

  const file = (location.state as { file?: File } | null)?.file ?? null

  const { data: accounts } = useListAccountsApiV1HouseholdsHouseholdIdAccountsGet(
    householdId ?? '',
    undefined,
    { query: { enabled: !!householdId } }
  )

  if (!file) {
    void navigate('/settings/ingest', { replace: true })
    return null
  }

  if (!householdId) return null

  const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
  const isCSV = ext === 'csv'
  const isOFX = ext === 'ofx' || ext === 'qfx'

  if (!isCSV && !isOFX) {
    return (
      <div style={{ maxWidth: 560, margin: '0 auto', padding: '32px 24px' }}>
        <button
          onClick={() => void navigate('/settings/ingest')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 13,
            color: 'var(--fg-muted)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '0 0 20px',
            marginBottom: 4,
          }}
        >
          <ArrowLeft size={14} /> Connected Accounts
        </button>
        <div
          style={{
            padding: '32px 24px',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            textAlign: 'center' as const,
            color: 'var(--fg-muted)',
            fontSize: 14,
          }}
        >
          File format not recognized. Only OFX, QFX, and CSV files are supported.
        </div>
      </div>
    )
  }

  function handleDone(jobId: string) {
    void navigate(`/settings/ingest/upload/${jobId}`)
  }

  return (
    <div style={{ maxWidth: 560, margin: '0 auto', padding: '32px 24px' }}>
      <button
        onClick={() => void navigate('/settings/ingest')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 13,
          color: 'var(--fg-muted)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '0 0 20px',
          marginBottom: 4,
        }}
      >
        <ArrowLeft size={14} /> Connected Accounts
      </button>

      <h1
        style={{
          fontSize: 20,
          fontWeight: 600,
          color: 'var(--fg-primary)',
          margin: '0 0 4px',
          letterSpacing: '-0.01em',
        }}
      >
        Import {isCSV ? 'CSV' : 'OFX/QFX'}
      </h1>
      <p
        style={{
          fontSize: 13,
          color: 'var(--fg-muted)',
          margin: '0 0 24px',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap' as const,
        }}
      >
        {file.name}
      </p>

      {isOFX && (
        <OFXFlow
          file={file}
          accounts={accounts ?? []}
          householdId={householdId}
          onDone={handleDone}
        />
      )}

      {isCSV && (
        <CSVFlow
          file={file}
          accounts={accounts ?? []}
          householdId={householdId}
          onDone={handleDone}
        />
      )}
    </div>
  )
}
