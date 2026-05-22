import { useEffect, useState } from 'react'
import { Plus, ChevronDown, ChevronRight, Trash2, Wifi, Loader, ExternalLink } from 'lucide-react'
import {
  useListProvidersApiV1HouseholdsHouseholdIdInsightsProvidersGet,
  useCreateProviderApiV1HouseholdsHouseholdIdInsightsProvidersPost,
  useUpdateProviderApiV1HouseholdsHouseholdIdInsightsProvidersConfigIdPatch,
  useDeleteProviderApiV1HouseholdsHouseholdIdInsightsProvidersConfigIdDelete,
  useGetBudgetApiV1HouseholdsHouseholdIdInsightsBudgetGet,
  useUpdateBudgetApiV1HouseholdsHouseholdIdInsightsBudgetPatch,
  useTestProviderApiV1HouseholdsHouseholdIdInsightsProvidersConfigIdTestPost,
  useListOllamaModelsApiV1HouseholdsHouseholdIdInsightsProvidersOllamaModelsGet,
} from '@/api/generated/insights/insights'
import { useHousehold } from '@/hooks/use-household'
import { formatAmount } from '@/lib/format-amount'
import { useQueryClient } from '@tanstack/react-query'
import type { ProviderConfigOut } from '@/api/generated/model/providerConfigOut'
import type { OllamaModelOut } from '@/api/generated/model/ollamaModelOut'
import { OllamaModelManager } from '@/components/insights/OllamaModelManager'

const PROVIDER_TYPES = ['local_ollama', 'local_llamacpp', 'anthropic', 'openai', 'disabled']
const LOCAL_TYPES = new Set(['local_ollama', 'local_llamacpp'])
const REMOTE_TYPES = new Set(['anthropic', 'openai'])

const ANTHROPIC_MODELS = [
  { value: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5' },
  { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
  { value: 'claude-opus-4-7', label: 'Claude Opus 4.7' },
]

const OPENAI_MODELS = [
  { value: 'gpt-4o-mini', label: 'GPT-4o mini' },
  { value: 'gpt-4o', label: 'GPT-4o' },
]

function remoteModelOptions(providerType: string) {
  if (providerType === 'anthropic') return ANTHROPIC_MODELS
  if (providerType === 'openai') return OPENAI_MODELS
  return null
}

const AI_DATA_SHARING_OPTIONS = [
  { value: 'disabled', label: 'Disabled', description: 'No data sent to AI' },
  {
    value: 'generalizations_only',
    label: 'Generalizations only',
    description: 'Category names and patterns only',
  },
  {
    value: 'aggregates_only',
    label: 'Aggregates only',
    description: 'Category totals, no transaction detail',
  },
  {
    value: 'redacted',
    label: 'Redacted',
    description: 'Transaction structure, merchants hashed',
  },
  { value: 'full', label: 'Full', description: 'Full data (local providers only)' },
]

const OVERAGE_OPTIONS = [
  { value: 'block', label: 'Block' },
  { value: 'warn_and_continue', label: 'Warn and continue' },
  { value: 'silent', label: 'Silent' },
]

type ConnectionStatus =
  | { state: 'untested' }
  | { state: 'testing' }
  | { state: 'connected'; modelName: string }
  | { state: 'unreachable'; error: string }

function StatusDot({ status }: { status: ConnectionStatus }) {
  const color =
    status.state === 'connected'
      ? 'var(--success)'
      : status.state === 'unreachable'
        ? 'var(--danger)'
        : status.state === 'testing'
          ? 'var(--warning)'
          : 'var(--fg-muted)'

  return (
    <span
      style={{
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: color,
        flexShrink: 0,
        display: 'inline-block',
      }}
    />
  )
}

function ConnectionStatusLabel({ status }: { status: ConnectionStatus }) {
  if (status.state === 'untested')
    return <span style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Not tested</span>
  if (status.state === 'testing')
    return <span style={{ fontSize: 11, color: 'var(--warning)' }}>Testing...</span>
  if (status.state === 'connected')
    return (
      <span style={{ fontSize: 11, color: 'var(--success)' }}>
        Connected
        {status.modelName && (
          <span style={{ color: 'var(--fg-muted)', marginLeft: 4 }}>{status.modelName}</span>
        )}
      </span>
    )
  return (
    <span style={{ fontSize: 11, color: 'var(--danger)' }}>
      Unreachable &mdash;{' '}
      <span
        style={{
          color: 'var(--fg-muted)',
          maxWidth: 200,
          display: 'inline-block',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          verticalAlign: 'bottom',
          whiteSpace: 'nowrap',
        }}
        title={status.error}
      >
        {status.error}
      </span>
    </span>
  )
}

function OllamaModelSelector({
  householdId,
  modelName,
  onChange,
  onManage,
}: {
  householdId: string
  modelName: string
  onChange: (v: string) => void
  onManage: () => void
}) {
  const { data: modelsData, isLoading } =
    useListOllamaModelsApiV1HouseholdsHouseholdIdInsightsProvidersOllamaModelsGet(householdId, {
      query: { enabled: !!householdId },
    })

  const models: OllamaModelOut[] = modelsData?.models ?? []

  if (isLoading) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 12,
          color: 'var(--fg-muted)',
        }}
      >
        <Loader size={12} style={{ animation: 'spin 1s linear infinite' }} />
        Loading models...
      </div>
    )
  }

  if (models.length === 0 && modelsData) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
          No models installed yet.{' '}
          <button
            type="button"
            onClick={onManage}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--accent)',
              cursor: 'pointer',
              fontSize: 12,
              padding: 0,
              fontFamily: 'var(--font-sans)',
            }}
          >
            Pull a model
          </button>
        </div>
        <input
          value={modelName}
          onChange={(e) => onChange(e.target.value)}
          placeholder="or enter model name manually"
          style={inputStyle}
        />
      </div>
    )
  }

  if (!modelsData) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
          Ollama unreachable — enter model name manually
        </div>
        <input
          value={modelName}
          onChange={(e) => onChange(e.target.value)}
          placeholder="e.g. llama3, mistral"
          style={inputStyle}
        />
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <select
        value={modelName}
        onChange={(e) => onChange(e.target.value)}
        style={{
          padding: '7px 10px',
          borderRadius: 8,
          border: '1px solid var(--border)',
          background: 'var(--bg-secondary)',
          color: 'var(--fg-primary)',
          fontSize: 13,
          cursor: 'pointer',
        }}
      >
        <option value="">— select a model —</option>
        {models.map((m) => (
          <option key={m.name} value={m.name}>
            {m.name}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={onManage}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 11,
          color: 'var(--accent)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: 0,
          fontFamily: 'var(--font-sans)',
        }}
      >
        <ExternalLink size={10} />
        Manage models
      </button>
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  padding: '7px 10px',
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'var(--bg-secondary)',
  color: 'var(--fg-primary)',
  fontSize: 13,
  outline: 'none',
}

function ProviderRow({
  provider,
  householdId,
  onDeleted,
}: {
  provider: ProviderConfigOut
  householdId: string
  onDeleted: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [modelName, setModelName] = useState(provider.model_name ?? '')
  const [baseUrl, setBaseUrl] = useState(provider.base_url ?? '')
  const [sharing, setSharing] = useState(provider.ai_data_sharing)
  const [enabled, setEnabled] = useState(provider.enabled)
  const [apiKey, setApiKey] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [connStatus, setConnStatus] = useState<ConnectionStatus>({ state: 'untested' })
  const [showModelManager, setShowModelManager] = useState(false)

  const update = useUpdateProviderApiV1HouseholdsHouseholdIdInsightsProvidersConfigIdPatch()
  const del = useDeleteProviderApiV1HouseholdsHouseholdIdInsightsProvidersConfigIdDelete()
  const testMutation = useTestProviderApiV1HouseholdsHouseholdIdInsightsProvidersConfigIdTestPost()
  const qc = useQueryClient()

  const isLocal = LOCAL_TYPES.has(provider.provider)
  const isRemote = REMOTE_TYPES.has(provider.provider)
  const isOllama = provider.provider === 'local_ollama'
  const isDisabled = provider.provider === 'disabled'
  const remoteModels = remoteModelOptions(provider.provider)

  const runTest = async () => {
    setConnStatus({ state: 'testing' })
    try {
      const result = await testMutation.mutateAsync({
        householdId,
        configId: provider.id,
      })
      if (result.available) {
        setConnStatus({ state: 'connected', modelName: result.model_name ?? '' })
      } else {
        setConnStatus({ state: 'unreachable', error: result.error ?? 'Unknown error' })
      }
    } catch {
      setConnStatus({ state: 'unreachable', error: 'Test request failed' })
    }
  }

  useEffect(() => {
    if (provider.enabled) {
      void runTest()
    }
    // run once on mount for enabled providers
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    try {
      await update.mutateAsync({
        householdId,
        configId: provider.id,
        data: {
          model_name: modelName || null,
          base_url: isLocal ? baseUrl || null : undefined,
          ai_data_sharing: sharing,
          enabled,
          ...(isRemote && apiKey.trim() ? { credentials: { api_key: apiKey.trim() } } : {}),
        },
      })
      await qc.invalidateQueries({
        queryKey: [`/api/v1/households/${householdId}/insights/providers`],
      })
      if (apiKey) setApiKey('')
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
      void runTest()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await del.mutateAsync({ householdId, configId: provider.id })
      onDeleted()
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <div
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 10,
          overflow: 'hidden',
        }}
      >
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            width: '100%',
            padding: '12px 14px',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontFamily: 'var(--font-sans)',
            textAlign: 'left',
          }}
        >
          {expanded ? (
            <ChevronDown size={14} style={{ color: 'var(--fg-muted)', flexShrink: 0 }} />
          ) : (
            <ChevronRight size={14} style={{ color: 'var(--fg-muted)', flexShrink: 0 }} />
          )}
          <StatusDot status={connStatus} />
          <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)', flex: 1 }}>
            {provider.provider.replace(/_/g, ' ')}
          </span>
          <ConnectionStatusLabel status={connStatus} />
        </button>

        {expanded && (
          <div
            style={{
              padding: '0 14px 14px',
              borderTop: '1px solid var(--border)',
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
            }}
          >
            <div style={{ paddingTop: 12 }} />

            {!isDisabled && (
              <>
                {/* Connection test bar */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '8px 10px',
                    background: 'var(--bg-secondary)',
                    borderRadius: 8,
                    border: '1px solid var(--border)',
                  }}
                >
                  <StatusDot status={connStatus} />
                  <span style={{ flex: 1, fontSize: 12 }}>
                    <ConnectionStatusLabel status={connStatus} />
                  </span>
                  <button
                    type="button"
                    onClick={() => void runTest()}
                    disabled={connStatus.state === 'testing'}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      padding: '3px 8px',
                      fontSize: 11,
                      background: 'none',
                      border: '1px solid var(--border)',
                      borderRadius: 5,
                      cursor: 'pointer',
                      color: 'var(--fg-secondary)',
                      fontFamily: 'var(--font-sans)',
                      opacity: connStatus.state === 'testing' ? 0.5 : 1,
                    }}
                  >
                    {connStatus.state === 'testing' ? (
                      <Loader size={11} style={{ animation: 'spin 1s linear infinite' }} />
                    ) : (
                      <Wifi size={11} />
                    )}
                    Test connection
                  </button>
                </div>

                {isLocal && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Base URL</label>
                    <input
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      placeholder="http://localhost:11434"
                      style={inputStyle}
                    />
                  </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Model</label>
                  {isOllama ? (
                    <OllamaModelSelector
                      householdId={householdId}
                      modelName={modelName}
                      onChange={setModelName}
                      onManage={() => setShowModelManager(true)}
                    />
                  ) : remoteModels ? (
                    <select
                      value={modelName}
                      onChange={(e) => setModelName(e.target.value)}
                      style={{
                        padding: '7px 10px',
                        borderRadius: 8,
                        border: '1px solid var(--border)',
                        background: 'var(--bg-secondary)',
                        color: 'var(--fg-primary)',
                        fontSize: 13,
                        cursor: 'pointer',
                      }}
                    >
                      <option value="">— select a model —</option>
                      {remoteModels.map((m) => (
                        <option key={m.value} value={m.value}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      value={modelName}
                      onChange={(e) => setModelName(e.target.value)}
                      placeholder="e.g. mistral-7b-v0.1"
                      style={inputStyle}
                    />
                  )}
                </div>

                {isRemote && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>API key</label>
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="Leave blank to keep existing key"
                      autoComplete="off"
                      style={inputStyle}
                    />
                  </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Data sharing</label>
                  {AI_DATA_SHARING_OPTIONS.filter((o) => isLocal || o.value !== 'full').map(
                    (opt) => (
                      <label
                        key={opt.value}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 8,
                          cursor: 'pointer',
                          padding: '6px 8px',
                          borderRadius: 6,
                          background:
                            sharing === opt.value
                              ? 'color-mix(in oklch, var(--accent) 8%, transparent)'
                              : 'transparent',
                          border: `1px solid ${sharing === opt.value ? 'color-mix(in oklch, var(--accent) 25%, transparent)' : 'transparent'}`,
                        }}
                      >
                        <input
                          type="radio"
                          name={`sharing-${provider.id}`}
                          value={opt.value}
                          checked={sharing === opt.value}
                          onChange={() => setSharing(opt.value)}
                          style={{ marginTop: 1, flexShrink: 0 }}
                        />
                        <div>
                          <div
                            style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-primary)' }}
                          >
                            {opt.label}
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
                            {opt.description}
                          </div>
                        </div>
                      </label>
                    )
                  )}
                </div>
              </>
            )}

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
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
                  checked={enabled}
                  onChange={(e) => setEnabled(e.target.checked)}
                  style={{ width: 14, height: 14 }}
                />
                Enabled
              </label>

              <div style={{ display: 'flex', gap: 6 }}>
                {confirmDelete ? (
                  <>
                    <button
                      type="button"
                      onClick={() => void handleDelete()}
                      disabled={deleting}
                      style={{
                        padding: '5px 12px',
                        fontSize: 12,
                        background: 'var(--danger)',
                        color: 'white',
                        border: 'none',
                        borderRadius: 6,
                        cursor: 'pointer',
                        fontFamily: 'var(--font-sans)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      {deleting && (
                        <Loader size={11} style={{ animation: 'spin 1s linear infinite' }} />
                      )}
                      Confirm delete
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmDelete(false)}
                      style={{
                        padding: '5px 12px',
                        fontSize: 12,
                        background: 'none',
                        border: '1px solid var(--border)',
                        borderRadius: 6,
                        cursor: 'pointer',
                        color: 'var(--fg-muted)',
                        fontFamily: 'var(--font-sans)',
                      }}
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => void handleSave()}
                      disabled={saving}
                      style={{
                        padding: '5px 14px',
                        fontSize: 12,
                        background: 'var(--accent)',
                        color: 'var(--accent-fg)',
                        border: 'none',
                        borderRadius: 6,
                        cursor: 'pointer',
                        fontFamily: 'var(--font-sans)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      {saving && (
                        <Loader size={11} style={{ animation: 'spin 1s linear infinite' }} />
                      )}
                      {saving ? 'Saving...' : saveSuccess ? 'Saved' : 'Save'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmDelete(true)}
                      style={{
                        padding: '5px 8px',
                        fontSize: 12,
                        background: 'none',
                        border: '1px solid var(--border)',
                        borderRadius: 6,
                        cursor: 'pointer',
                        color: 'var(--danger)',
                        display: 'flex',
                        alignItems: 'center',
                      }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </>
                )}
              </div>
            </div>

            {saveError && (
              <div
                style={{
                  padding: '8px 10px',
                  background: 'color-mix(in oklch, var(--danger) 8%, transparent)',
                  border: '1px solid color-mix(in oklch, var(--danger) 25%, transparent)',
                  borderRadius: 6,
                  fontSize: 12,
                  color: 'var(--danger)',
                }}
              >
                {saveError}
              </div>
            )}
          </div>
        )}
      </div>
      {showModelManager && (
        <OllamaModelManager
          householdId={householdId}
          onClose={() => setShowModelManager(false)}
          onModelSelected={(name) => setModelName(name)}
        />
      )}
    </>
  )
}

function AddProviderModal({
  householdId,
  onClose,
  onAdded,
}: {
  householdId: string
  onClose: () => void
  onAdded: () => void
}) {
  const [providerType, setProviderType] = useState('local_ollama')
  const [modelName, setModelName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [sharing, setSharing] = useState('generalizations_only')
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [showModelManager, setShowModelManager] = useState(false)

  const create = useCreateProviderApiV1HouseholdsHouseholdIdInsightsProvidersPost()
  const isLocal = LOCAL_TYPES.has(providerType)
  const isRemote = REMOTE_TYPES.has(providerType)
  const isOllama = providerType === 'local_ollama'
  const isDisabledType = providerType === 'disabled'
  const remoteModels = remoteModelOptions(providerType)

  const handleTypeChange = (t: string) => {
    setProviderType(t)
    setModelName('')
    setApiKey('')
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      await create.mutateAsync({
        householdId,
        data: {
          provider: providerType,
          model_name: modelName || null,
          base_url: isLocal ? baseUrl || null : undefined,
          ai_data_sharing: sharing,
          enabled: true,
          ...(isRemote && apiKey.trim() ? { credentials: { api_key: apiKey.trim() } } : {}),
        },
      })
      onAdded()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to add provider')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
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
            width: 480,
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
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)' }}>
              Add AI provider
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
              gap: 14,
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Provider type</label>
              <select
                value={providerType}
                onChange={(e) => handleTypeChange(e.target.value)}
                style={{
                  padding: '8px 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'var(--bg-secondary)',
                  color: 'var(--fg-primary)',
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                {PROVIDER_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.replace(/_/g, ' ')}
                  </option>
                ))}
              </select>
            </div>

            {!isDisabledType && (
              <>
                {isLocal && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Base URL</label>
                    <input
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      placeholder="http://localhost:11434"
                      style={{
                        padding: '8px 10px',
                        borderRadius: 8,
                        border: '1px solid var(--border)',
                        background: 'var(--bg-secondary)',
                        color: 'var(--fg-primary)',
                        fontSize: 13,
                        outline: 'none',
                      }}
                    />
                  </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Model</label>
                  {isOllama && baseUrl ? (
                    <OllamaModelSelector
                      householdId={householdId}
                      modelName={modelName}
                      onChange={setModelName}
                      onManage={() => setShowModelManager(true)}
                    />
                  ) : remoteModels ? (
                    <select
                      value={modelName}
                      onChange={(e) => setModelName(e.target.value)}
                      style={{
                        padding: '8px 10px',
                        borderRadius: 8,
                        border: '1px solid var(--border)',
                        background: 'var(--bg-secondary)',
                        color: 'var(--fg-primary)',
                        fontSize: 13,
                        cursor: 'pointer',
                      }}
                    >
                      <option value="">— select a model —</option>
                      {remoteModels.map((m) => (
                        <option key={m.value} value={m.value}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      value={modelName}
                      onChange={(e) => setModelName(e.target.value)}
                      placeholder={
                        providerType === 'local_llamacpp' ? 'e.g. mistral-7b-v0.1' : 'e.g. llama3'
                      }
                      style={{
                        padding: '8px 10px',
                        borderRadius: 8,
                        border: '1px solid var(--border)',
                        background: 'var(--bg-secondary)',
                        color: 'var(--fg-primary)',
                        fontSize: 13,
                        outline: 'none',
                      }}
                    />
                  )}
                </div>

                {isRemote && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>API key</label>
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder={providerType === 'anthropic' ? 'sk-ant-...' : 'sk-...'}
                      autoComplete="off"
                      style={{
                        padding: '8px 10px',
                        borderRadius: 8,
                        border: '1px solid var(--border)',
                        background: 'var(--bg-secondary)',
                        color: 'var(--fg-primary)',
                        fontSize: 13,
                        outline: 'none',
                      }}
                    />
                  </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Data sharing</label>
                  <select
                    value={sharing}
                    onChange={(e) => setSharing(e.target.value)}
                    style={{
                      padding: '8px 10px',
                      borderRadius: 8,
                      border: '1px solid var(--border)',
                      background: 'var(--bg-secondary)',
                      color: 'var(--fg-primary)',
                      fontSize: 13,
                      cursor: 'pointer',
                    }}
                  >
                    {AI_DATA_SHARING_OPTIONS.filter((o) => isLocal || o.value !== 'full').map(
                      (opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label} — {opt.description}
                        </option>
                      )
                    )}
                  </select>
                </div>
              </>
            )}

            {saveError && (
              <div
                style={{
                  padding: '8px 10px',
                  background: 'color-mix(in oklch, var(--danger) 8%, transparent)',
                  border: '1px solid color-mix(in oklch, var(--danger) 25%, transparent)',
                  borderRadius: 6,
                  fontSize: 12,
                  color: 'var(--danger)',
                }}
              >
                {saveError}
              </div>
            )}
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
              onClick={() => void handleSave()}
              disabled={saving}
              style={{
                padding: '7px 16px',
                background: 'var(--accent)',
                color: 'var(--accent-fg)',
                border: 'none',
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              {saving && <Loader size={13} style={{ animation: 'spin 1s linear infinite' }} />}
              {saving ? 'Adding...' : 'Add provider'}
            </button>
          </div>
        </div>
      </div>
      {showModelManager && (
        <OllamaModelManager
          householdId={householdId}
          onClose={() => setShowModelManager(false)}
          onModelSelected={(name) => setModelName(name)}
        />
      )}
    </>
  )
}

function TokenBudgetSection({ householdId, currency }: { householdId: string; currency: string }) {
  const { data: budget, refetch } = useGetBudgetApiV1HouseholdsHouseholdIdInsightsBudgetGet(
    householdId,
    { query: { enabled: !!householdId } }
  )
  const update = useUpdateBudgetApiV1HouseholdsHouseholdIdInsightsBudgetPatch()

  const [tokenLimit, setTokenLimit] = useState('')
  const [costLimit, setCostLimit] = useState('')
  const [overage, setOverage] = useState('block')
  const [loaded, setLoaded] = useState(false)
  const [saving, setSaving] = useState(false)

  if (budget && !loaded) {
    setTokenLimit(budget.token_limit != null ? String(budget.token_limit) : '')
    setCostLimit(budget.cost_limit != null ? String(budget.cost_limit) : '')
    setOverage(budget.overage_behavior)
    setLoaded(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await update.mutateAsync({
        householdId,
        data: {
          token_limit: tokenLimit ? parseInt(tokenLimit, 10) : null,
          cost_limit: costLimit || null,
          overage_behavior: overage,
        },
      })
      await refetch()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>Token budget</div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
            Token limit / month (blank = unlimited)
          </label>
          <input
            value={tokenLimit}
            onChange={(e) => setTokenLimit(e.target.value)}
            placeholder="e.g. 100000"
            type="number"
            style={{
              padding: '8px 10px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--bg-secondary)',
              color: 'var(--fg-primary)',
              fontSize: 13,
              outline: 'none',
            }}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
            Cost limit / month {currency} (blank = unlimited)
          </label>
          <input
            value={costLimit}
            onChange={(e) => setCostLimit(e.target.value)}
            placeholder="e.g. 5.00"
            type="number"
            step="0.01"
            style={{
              padding: '8px 10px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--bg-secondary)',
              color: 'var(--fg-primary)',
              fontSize: 13,
              outline: 'none',
            }}
          />
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <label style={{ fontSize: 12, color: 'var(--fg-muted)' }}>On overage</label>
        <div style={{ display: 'flex', gap: 6 }}>
          {OVERAGE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setOverage(opt.value)}
              style={{
                padding: '5px 12px',
                fontSize: 12,
                borderRadius: 6,
                border: `1px solid ${overage === opt.value ? 'var(--accent)' : 'var(--border)'}`,
                background:
                  overage === opt.value
                    ? 'color-mix(in oklch, var(--accent) 12%, transparent)'
                    : 'none',
                color: overage === opt.value ? 'var(--accent)' : 'var(--fg-muted)',
                cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {budget && (
        <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
          This month:{' '}
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--fg-primary)' }}>
            {budget.tokens_used.toLocaleString()} tokens /{' '}
            {formatAmount(parseFloat(budget.cost_used), { currency, fractionDigits: 4 })}
          </span>
        </div>
      )}

      <div>
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={saving}
          style={{
            padding: '7px 16px',
            background: 'var(--accent)',
            color: 'var(--accent-fg)',
            border: 'none',
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 500,
            cursor: 'pointer',
            fontFamily: 'var(--font-sans)',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          {saving && <Loader size={13} style={{ animation: 'spin 1s linear infinite' }} />}
          {saving ? 'Saving...' : 'Save budget'}
        </button>
      </div>
    </div>
  )
}

export function InsightsSettingsPage() {
  const { household, householdId } = useHousehold()
  const hid = householdId ?? ''
  const [showAdd, setShowAdd] = useState(false)
  const qc = useQueryClient()

  const { data: providers = [], refetch } =
    useListProvidersApiV1HouseholdsHouseholdIdInsightsProvidersGet(hid, {
      query: { enabled: !!hid },
    })

  const handleAdded = async () => {
    setShowAdd(false)
    await refetch()
  }

  const handleDeleted = async () => {
    await qc.invalidateQueries({
      queryKey: [`/api/v1/households/${hid}/insights/providers`],
    })
  }

  const currency = household?.home_currency ?? 'USD'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 640 }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg-primary)', margin: 0 }}>
        AI Insights Settings
      </h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>Providers</div>
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 12px',
              background: 'var(--accent)',
              color: 'var(--accent-fg)',
              border: 'none',
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 500,
              cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
            }}
          >
            <Plus size={13} />
            Add provider
          </button>
        </div>

        {(providers as ProviderConfigOut[]).length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>
            No providers configured. Add one to enable AI insights.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {(providers as ProviderConfigOut[]).map((p) => (
              <ProviderRow key={p.id} provider={p} householdId={hid} onDeleted={handleDeleted} />
            ))}
          </div>
        )}
      </div>

      <div
        style={{
          paddingTop: 20,
          borderTop: '1px solid var(--border)',
        }}
      >
        <TokenBudgetSection householdId={hid} currency={currency} />
      </div>

      {showAdd && (
        <AddProviderModal
          householdId={hid}
          onClose={() => setShowAdd(false)}
          onAdded={handleAdded}
        />
      )}
    </div>
  )
}
