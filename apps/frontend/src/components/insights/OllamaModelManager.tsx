import { useState } from 'react'
import { ExternalLink, Loader, Trash2, X } from 'lucide-react'
import {
  useListOllamaModelsApiV1HouseholdsHouseholdIdInsightsProvidersOllamaModelsGet,
  useDeleteOllamaModelApiV1HouseholdsHouseholdIdInsightsProvidersOllamaModelsModelNameDelete,
} from '@/api/generated/insights/insights'
import { formatBytes } from '@/lib/format'
import { useQueryClient } from '@tanstack/react-query'
import type { OllamaModelOut } from '@/api/generated/model/ollamaModelOut'

interface PullEvent {
  status: string
  completed?: number
  total?: number
  error?: string
}

interface PullState {
  active: boolean
  statusText: string
  completed: number
  total: number
  error: string | null
  done: boolean
}

function relativetime(iso: string): string {
  try {
    const ms = Date.now() - new Date(iso).getTime()
    const days = Math.floor(ms / 86400000)
    if (days === 0) return 'today'
    if (days === 1) return 'yesterday'
    if (days < 30) return `${days}d ago`
    const months = Math.floor(days / 30)
    if (months < 12) return `${months}mo ago`
    return `${Math.floor(months / 12)}y ago`
  } catch {
    return ''
  }
}

export function OllamaModelManager({
  householdId,
  onClose,
  onModelSelected,
}: {
  householdId: string
  onClose: () => void
  onModelSelected?: (name: string) => void
}) {
  const qc = useQueryClient()
  const [pullName, setPullName] = useState('')
  const [pull, setPull] = useState<PullState>({
    active: false,
    statusText: '',
    completed: 0,
    total: 0,
    error: null,
    done: false,
  })
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const modelsQueryKey = [
    `/api/v1/households/${householdId}/insights/providers/ollama/models`,
  ] as const

  const { data: modelsData, isLoading: modelsLoading } =
    useListOllamaModelsApiV1HouseholdsHouseholdIdInsightsProvidersOllamaModelsGet(householdId, {
      query: { enabled: !!householdId },
    })

  const deleteModel =
    useDeleteOllamaModelApiV1HouseholdsHouseholdIdInsightsProvidersOllamaModelsModelNameDelete()

  const models: OllamaModelOut[] = modelsData?.models ?? []

  const handlePullSSE = async () => {
    const name = pullName.trim()
    if (!name || pull.active) return

    setPull({
      active: true,
      statusText: 'Starting...',
      completed: 0,
      total: 0,
      error: null,
      done: false,
    })

    try {
      const resp = await fetch(`/api/v1/households/${householdId}/insights/providers/ollama/pull`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_name: name }),
      })
      if (!resp.ok || !resp.body) {
        setPull((p) => ({ ...p, active: false, error: `Server error ${resp.status}` }))
        return
      }
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          let ev: PullEvent
          try {
            ev = JSON.parse(line.slice(6)) as PullEvent
          } catch {
            continue
          }
          if (ev.status === 'error') {
            setPull((p) => ({ ...p, active: false, error: ev.error ?? 'Unknown error' }))
            return
          }
          const isDone = ev.status === 'success' || ev.status === 'complete'
          setPull((p) => ({
            ...p,
            statusText: ev.status,
            completed: ev.completed ?? p.completed,
            total: ev.total ?? p.total,
            done: isDone,
            active: !isDone,
          }))
          if (isDone) {
            void qc.invalidateQueries({ queryKey: modelsQueryKey })
            setPullName('')
            return
          }
        }
      }
    } catch (err) {
      setPull((p) => ({
        ...p,
        active: false,
        error: err instanceof Error ? err.message : 'Failed',
      }))
    }
  }

  const handleDelete = async (name: string) => {
    await deleteModel.mutateAsync({ householdId, modelName: encodeURIComponent(name) })
    setDeleteConfirm(null)
    await qc.invalidateQueries({ queryKey: modelsQueryKey })
  }

  const pullPct =
    pull.total > 0 ? Math.min(100, Math.round((pull.completed / pull.total) * 100)) : null

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 60,
        display: 'flex',
        alignItems: 'stretch',
        justifyContent: 'flex-end',
      }}
    >
      <div
        onClick={onClose}
        style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.35)' }}
      />
      <div
        style={{
          position: 'relative',
          width: 480,
          maxWidth: '100vw',
          height: '100%',
          background: 'var(--bg-primary)',
          borderLeft: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          overflowY: 'auto',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '20px 22px 14px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            flexShrink: 0,
          }}
        >
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-primary)' }}>
              Ollama Models
            </div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
              Models installed on your Ollama instance
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'none',
              border: '1px solid var(--border)',
              borderRadius: 6,
              width: 28,
              height: 28,
              cursor: 'pointer',
              color: 'var(--fg-muted)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={14} />
          </button>
        </div>

        {/* Installed models */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px 22px',
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {modelsLoading ? (
              <div
                style={{
                  display: 'flex',
                  gap: 8,
                  alignItems: 'center',
                  color: 'var(--fg-muted)',
                  fontSize: 13,
                }}
              >
                <Loader size={13} style={{ animation: 'spin 1s linear infinite' }} />
                Loading models...
              </div>
            ) : models.length === 0 ? (
              <div style={{ fontSize: 13, color: 'var(--fg-muted)', padding: '8px 0' }}>
                No models installed yet.
              </div>
            ) : (
              models.map((m) => (
                <div
                  key={m.name}
                  style={{
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border)',
                    borderRadius: 10,
                    padding: '12px 14px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 500,
                        color: 'var(--fg-primary)',
                        fontFamily: 'var(--font-mono)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {m.name}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 2 }}>
                      {formatBytes(m.size_bytes)}
                      {m.modified_at ? ` · ${relativetime(m.modified_at)}` : ''}
                    </div>
                  </div>
                  {onModelSelected && (
                    <button
                      type="button"
                      onClick={() => {
                        onModelSelected(m.name)
                        onClose()
                      }}
                      style={{
                        padding: '4px 10px',
                        fontSize: 11,
                        background: 'color-mix(in oklch, var(--accent) 12%, transparent)',
                        border: '1px solid color-mix(in oklch, var(--accent) 30%, transparent)',
                        borderRadius: 6,
                        color: 'var(--accent)',
                        cursor: 'pointer',
                        fontFamily: 'var(--font-sans)',
                        flexShrink: 0,
                      }}
                    >
                      Use
                    </button>
                  )}
                  {deleteConfirm === m.name ? (
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                      <span style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
                        Free {formatBytes(m.size_bytes)}?
                      </span>
                      <button
                        type="button"
                        onClick={() => void handleDelete(m.name)}
                        disabled={deleteModel.isPending}
                        style={{
                          padding: '3px 8px',
                          fontSize: 11,
                          background: 'var(--danger)',
                          color: 'white',
                          border: 'none',
                          borderRadius: 5,
                          cursor: 'pointer',
                          fontFamily: 'var(--font-sans)',
                        }}
                      >
                        Remove
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeleteConfirm(null)}
                        style={{
                          padding: '3px 8px',
                          fontSize: 11,
                          background: 'none',
                          border: '1px solid var(--border)',
                          borderRadius: 5,
                          cursor: 'pointer',
                          color: 'var(--fg-muted)',
                          fontFamily: 'var(--font-sans)',
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setDeleteConfirm(m.name)}
                      style={{
                        background: 'none',
                        border: '1px solid var(--border)',
                        borderRadius: 6,
                        width: 26,
                        height: 26,
                        cursor: 'pointer',
                        color: 'var(--danger)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      <Trash2 size={12} />
                    </button>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Pull new model */}
          <div
            style={{
              paddingTop: 16,
              borderTop: '1px solid var(--border)',
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-primary)' }}>
              Pull new model
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                value={pullName}
                onChange={(e) => setPullName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void handlePullSSE()
                }}
                placeholder="e.g. llama3, mistral, phi3:mini"
                disabled={pull.active}
                style={{
                  flex: 1,
                  padding: '8px 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'var(--bg-secondary)',
                  color: 'var(--fg-primary)',
                  fontSize: 13,
                  outline: 'none',
                  opacity: pull.active ? 0.6 : 1,
                }}
              />
              <button
                type="button"
                onClick={() => void handlePullSSE()}
                disabled={!pullName.trim() || pull.active}
                style={{
                  padding: '8px 16px',
                  background: 'var(--accent)',
                  color: 'var(--accent-fg)',
                  border: 'none',
                  borderRadius: 8,
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: !pullName.trim() || pull.active ? 'default' : 'pointer',
                  opacity: !pullName.trim() || pull.active ? 0.5 : 1,
                  fontFamily: 'var(--font-sans)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  flexShrink: 0,
                }}
              >
                {pull.active && (
                  <Loader size={13} style={{ animation: 'spin 1s linear infinite' }} />
                )}
                Pull model
              </button>
            </div>

            <a
              href="https://ollama.com/library"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                fontSize: 12,
                color: 'var(--accent)',
                textDecoration: 'none',
              }}
            >
              <ExternalLink size={11} />
              Browse models at ollama.com/library
            </a>

            {/* Pull progress */}
            {(pull.active || pull.done || pull.error) && (
              <div
                style={{
                  padding: '12px 14px',
                  background: pull.error
                    ? 'color-mix(in oklch, var(--danger) 8%, transparent)'
                    : pull.done
                      ? 'color-mix(in oklch, var(--success) 8%, transparent)'
                      : 'var(--bg-secondary)',
                  border: `1px solid ${pull.error ? 'color-mix(in oklch, var(--danger) 25%, transparent)' : pull.done ? 'color-mix(in oklch, var(--success) 25%, transparent)' : 'var(--border)'}`,
                  borderRadius: 8,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                }}
              >
                {pull.error ? (
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-start',
                      gap: 8,
                    }}
                  >
                    <span style={{ fontSize: 12, color: 'var(--danger)' }}>{pull.error}</span>
                    <button
                      type="button"
                      onClick={() => void handlePullSSE()}
                      style={{
                        padding: '3px 8px',
                        fontSize: 11,
                        background: 'none',
                        border: '1px solid var(--border)',
                        borderRadius: 5,
                        cursor: 'pointer',
                        color: 'var(--fg-secondary)',
                        fontFamily: 'var(--font-sans)',
                        flexShrink: 0,
                      }}
                    >
                      Retry
                    </button>
                  </div>
                ) : pull.done ? (
                  <span style={{ fontSize: 12, color: 'var(--success)' }}>
                    Model pulled successfully
                  </span>
                ) : (
                  <>
                    <span style={{ fontSize: 12, color: 'var(--fg-secondary)' }}>
                      {pull.statusText === 'downloading' || (pull.total > 0 && pull.completed > 0)
                        ? `Downloading ${pullPct ?? 0}% (${formatBytes(pull.completed)} / ${formatBytes(pull.total)})`
                        : pull.statusText
                          ? pull.statusText.charAt(0).toUpperCase() +
                            pull.statusText.slice(1) +
                            '...'
                          : 'Working...'}
                    </span>
                    {pull.total > 0 && (
                      <div
                        style={{
                          height: 4,
                          borderRadius: 99,
                          background: 'var(--border)',
                          overflow: 'hidden',
                        }}
                      >
                        <div
                          style={{
                            height: '100%',
                            width: `${pullPct ?? 0}%`,
                            borderRadius: 99,
                            background: 'var(--accent)',
                            transition: 'width 0.3s ease',
                          }}
                        />
                      </div>
                    )}
                    <span style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
                      Close this panel to navigate away. The pull will continue in the background.
                    </span>
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '12px 22px',
            borderTop: '1px solid var(--border)',
            flexShrink: 0,
          }}
        >
          <a
            href="https://ollama.com/library"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 12,
              color: 'var(--fg-muted)',
              textDecoration: 'none',
            }}
          >
            <ExternalLink size={11} />
            Browse available models at ollama.com/library
          </a>
        </div>
      </div>
    </div>
  )
}
