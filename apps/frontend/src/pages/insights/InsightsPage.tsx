import { useEffect, useRef, useState } from 'react'
import { Send, Loader, Sparkles, CheckCircle, XCircle, AlertTriangle, Settings } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { useAuthStore } from '@/store'
import {
  useListProvidersApiV1HouseholdsHouseholdIdInsightsProvidersGet,
  useAskApiV1HouseholdsHouseholdIdInsightsAskPost,
  useTriggerGenerateApiV1HouseholdsHouseholdIdInsightsGeneratePost,
  useGetBudgetApiV1HouseholdsHouseholdIdInsightsBudgetGet,
  useTestProviderApiV1HouseholdsHouseholdIdInsightsProvidersConfigIdTestPost,
} from '@/api/generated/insights/insights'
import {
  useListRecommendationsApiV1HouseholdsHouseholdIdRecommendationsGet,
  useAcceptRecommendationApiV1HouseholdsHouseholdIdRecommendationsRecommendationIdAcceptPost,
  useRejectRecommendationApiV1HouseholdsHouseholdIdRecommendationsRecommendationIdRejectPost,
} from '@/api/generated/recommendations/recommendations'
import { useHousehold } from '@/hooks/use-household'
import { formatAmount } from '@/lib/format-amount'
import { useQueryClient } from '@tanstack/react-query'
import { RecommendationSource } from '@/api/generated/model/recommendationSource'
import { RecommendationStatus } from '@/api/generated/model/recommendationStatus'
import type { ProviderConfigOut } from '@/api/generated/model/providerConfigOut'
import type { RecommendationOut } from '@/api/generated/model/recommendationOut'
import type { AskResponse } from '@/api/generated/model/askResponse'
import { NavLink } from 'react-router-dom'

const ADMIN_AI_LINK = '/admin/ai'

interface QAItem {
  id: string
  question: string
  response: AskResponse | null
  error: string | null
  errorType: string | null
  loading: boolean
}

type ProviderStatus =
  | { state: 'untested' }
  | { state: 'testing' }
  | { state: 'connected'; modelName: string }
  | { state: 'unreachable'; error: string }

function providerStatusColor(s: ProviderStatus) {
  if (s.state === 'connected') return 'var(--success)'
  if (s.state === 'unreachable') return 'var(--danger)'
  if (s.state === 'testing') return 'var(--warning)'
  return 'var(--fg-muted)'
}

function ProviderChip({
  provider,
  householdId,
}: {
  provider: ProviderConfigOut
  householdId: string
}) {
  const [status, setStatus] = useState<ProviderStatus>({ state: 'untested' })
  const testMutation = useTestProviderApiV1HouseholdsHouseholdIdInsightsProvidersConfigIdTestPost()

  const runTest = async () => {
    setStatus({ state: 'testing' })
    try {
      const result = await testMutation.mutateAsync({ householdId, configId: provider.id })
      if (result.available) {
        setStatus({ state: 'connected', modelName: result.model_name ?? '' })
      } else {
        setStatus({ state: 'unreachable', error: result.error ?? 'Unreachable' })
      }
    } catch {
      setStatus({ state: 'unreachable', error: 'Test failed' })
    }
  }

  useEffect(() => {
    if (provider.enabled) {
      void runTest()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider.id])

  const dotColor = providerStatusColor(status)
  const label = provider.provider.replace(/_/g, ' ')

  return (
    <button
      type="button"
      onClick={() => void runTest()}
      title="Click to test connection"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 5,
        padding: '3px 10px',
        borderRadius: 99,
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border)',
        fontSize: 12,
        cursor: 'pointer',
        fontFamily: 'var(--font-sans)',
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: dotColor,
          flexShrink: 0,
        }}
      />
      <span style={{ color: 'var(--fg-secondary)' }}>{label}</span>
      {status.state === 'connected' && status.modelName && (
        <span style={{ color: 'var(--fg-muted)', fontSize: 11 }}>{status.modelName}</span>
      )}
      {status.state === 'testing' && (
        <Loader
          size={10}
          style={{ animation: 'spin 1s linear infinite', color: 'var(--warning)' }}
        />
      )}
      {status.state === 'unreachable' && (
        <span
          style={{
            fontSize: 11,
            color: 'var(--danger)',
            maxWidth: 140,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={status.error}
        >
          {status.error}
        </span>
      )}
    </button>
  )
}

function ProviderStatusBar({
  providers,
  householdId,
}: {
  providers: ProviderConfigOut[]
  householdId: string
}) {
  if (providers.length === 0) return null

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
      <span style={{ fontSize: 12, color: 'var(--fg-muted)', marginRight: 4 }}>Providers:</span>
      {providers.map((p) => (
        <ProviderChip key={p.id} provider={p} householdId={householdId} />
      ))}
      <NavLink
        to={ADMIN_AI_LINK}
        style={{
          fontSize: 12,
          color: 'var(--accent)',
          textDecoration: 'none',
          marginLeft: 4,
        }}
      >
        Configure
      </NavLink>
    </div>
  )
}

function QAErrorMessage({ errorType, error }: { errorType: string | null; error: string | null }) {
  const isAdmin = useAuthStore((s) => s.currentUser?.is_app_admin ?? false)
  if (!error && !errorType) return null

  const adminLink = isAdmin ? (
    <>
      {' '}
      Check your provider configuration in{' '}
      <NavLink to={ADMIN_AI_LINK} style={{ color: 'var(--accent)', textDecoration: 'underline' }}>
        Admin &rarr; AI
      </NavLink>
      .
    </>
  ) : null

  if (errorType === 'no_provider' || (error && error.includes('no_provider'))) {
    return (
      <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 6 }}>
        No AI provider is available.{adminLink}
      </div>
    )
  }

  if (errorType === 'budget_exceeded' || (error && error.includes('budget_exceeded'))) {
    return (
      <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 6 }}>
        Monthly token budget reached.{adminLink}
      </div>
    )
  }

  if (errorType === 'disabled' || (error && error.includes('disabled'))) {
    return (
      <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 6 }}>
        AI insights are disabled.{adminLink}
      </div>
    )
  }

  return (
    <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 6 }}>
      {error ?? 'Something went wrong. Try again.'}
    </div>
  )
}

function QAHistory({
  items,
  onClear,
  onRetry,
}: {
  items: QAItem[]
  onClear: () => void
  onRetry: (question: string) => void
}) {
  if (items.length === 0) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--fg-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}
        >
          History
        </div>
        <button
          type="button"
          onClick={onClear}
          style={{
            fontSize: 11,
            color: 'var(--fg-muted)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontFamily: 'var(--font-sans)',
          }}
        >
          Clear
        </button>
      </div>
      {[...items].reverse().map((item) => (
        <div
          key={item.id}
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              padding: '12px 16px',
              background: 'var(--bg-secondary)',
              borderBottom: '1px solid var(--border)',
              fontSize: 13,
              fontWeight: 500,
              color: 'var(--fg-primary)',
            }}
          >
            {item.question}
          </div>
          <div style={{ padding: '12px 16px' }}>
            {item.loading ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  color: 'var(--fg-muted)',
                  fontSize: 13,
                }}
              >
                <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} />
                Thinking...
              </div>
            ) : item.error ? (
              <div>
                <QAErrorMessage errorType={item.errorType} error={item.error} />
                {(!item.errorType ||
                  (item.errorType !== 'budget_exceeded' && item.errorType !== 'disabled')) && (
                  <button
                    type="button"
                    onClick={() => onRetry(item.question)}
                    style={{
                      marginTop: 8,
                      padding: '4px 10px',
                      fontSize: 11,
                      background: 'none',
                      border: '1px solid var(--border)',
                      borderRadius: 5,
                      cursor: 'pointer',
                      color: 'var(--fg-secondary)',
                      fontFamily: 'var(--font-sans)',
                    }}
                  >
                    Retry
                  </button>
                )}
              </div>
            ) : item.response ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div
                  style={{
                    fontSize: 13,
                    color: 'var(--fg-primary)',
                    lineHeight: 1.6,
                  }}
                >
                  <ReactMarkdown>{String(item.response.answer ?? '')}</ReactMarkdown>
                </div>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginTop: 4,
                  }}
                >
                  {item.response.provider_used && (
                    <span style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
                      via {String(item.response.provider_used)}
                    </span>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  )
}

function AskSection({ householdId }: { householdId: string }) {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<QAItem[]>([])
  const [inlineError, setInlineError] = useState<{ msg: string; type: string | null } | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const longWaitRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [showLongWait, setShowLongWait] = useState(false)
  const qc = useQueryClient()

  const ask = useAskApiV1HouseholdsHouseholdIdInsightsAskPost()

  const handleSubmit = async (q?: string) => {
    const text = (q ?? question).trim()
    if (!text) return

    setInlineError(null)
    setShowLongWait(false)

    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    if (longWaitRef.current) clearTimeout(longWaitRef.current)

    const id = Math.random().toString(36).slice(2, 10)
    const item: QAItem = {
      id,
      question: text,
      response: null,
      error: null,
      errorType: null,
      loading: true,
    }

    const conversationHistory = history
      .filter((x) => x.response?.answer)
      .flatMap((x) => [
        { role: 'user' as const, content: x.question },
        { role: 'assistant' as const, content: String(x.response?.answer ?? '') },
      ])

    setHistory((prev) => [...prev, item])
    if (!q) setQuestion('')

    longWaitRef.current = setTimeout(() => {
      setShowLongWait(true)
    }, 60000)

    try {
      const res = await ask.mutateAsync({
        householdId,
        data: { question: text, history: conversationHistory },
      })

      if (longWaitRef.current) clearTimeout(longWaitRef.current)
      setShowLongWait(false)

      if (res.reason && !res.answer) {
        const reasonError = res.reason
        setHistory((prev) =>
          prev.map((x) =>
            x.id === id ? { ...x, error: reasonError, errorType: reasonError, loading: false } : x
          )
        )
      } else {
        setHistory((prev) =>
          prev.map((x) => (x.id === id ? { ...x, response: res, loading: false } : x))
        )
        void qc.invalidateQueries({
          queryKey: [`/api/v1/households/${householdId}/insights/budget`],
        })
        textareaRef.current?.focus()
      }
    } catch (err) {
      if (longWaitRef.current) clearTimeout(longWaitRef.current)
      setShowLongWait(false)
      const msg = err instanceof Error ? err.message : 'Something went wrong. Try again.'
      setHistory((prev) =>
        prev.map((x) => (x.id === id ? { ...x, error: msg, errorType: null, loading: false } : x))
      )
    }
  }

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      if (longWaitRef.current) clearTimeout(longWaitRef.current)
    }
  }, [])

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSubmit()
    }
  }

  const isInFlight = ask.isPending

  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 14,
        overflow: 'hidden',
      }}
    >
      <div style={{ padding: '18px 20px 0' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 12,
          }}
        >
          <Sparkles size={16} style={{ color: 'var(--accent)' }} />
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>
            Ask about your finances
          </div>
        </div>
        <div
          style={{
            display: 'flex',
            gap: 8,
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            borderRadius: 10,
            padding: '10px 12px',
            alignItems: 'flex-end',
          }}
        >
          <textarea
            ref={textareaRef}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask anything about your finances..."
            rows={2}
            disabled={isInFlight}
            style={{
              flex: 1,
              background: 'none',
              border: 'none',
              outline: 'none',
              resize: 'none',
              fontSize: 13,
              color: 'var(--fg-primary)',
              fontFamily: 'var(--font-sans)',
              lineHeight: 1.5,
              opacity: isInFlight ? 0.6 : 1,
            }}
          />
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={!question.trim() || isInFlight}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 4,
              padding: '0 10px',
              height: 34,
              background: question.trim() && !isInFlight ? 'var(--accent)' : 'var(--border)',
              border: 'none',
              borderRadius: 8,
              cursor: question.trim() && !isInFlight ? 'pointer' : 'default',
              color: question.trim() && !isInFlight ? 'var(--accent-fg)' : 'var(--fg-muted)',
              flexShrink: 0,
              transition: 'background 0.15s',
              fontSize: 12,
              fontFamily: 'var(--font-sans)',
            }}
          >
            {isInFlight ? (
              <>
                <Loader size={13} style={{ animation: 'spin 1s linear infinite' }} />
                Thinking...
              </>
            ) : (
              <Send size={14} />
            )}
          </button>
        </div>

        {showLongWait && (
          <div
            style={{
              marginTop: 8,
              padding: '6px 10px',
              background: 'color-mix(in oklch, var(--warning) 8%, transparent)',
              border: '1px solid color-mix(in oklch, var(--warning) 25%, transparent)',
              borderRadius: 6,
              fontSize: 11,
              color: 'var(--warning)',
            }}
          >
            This is taking longer than expected. The model may be loading.
          </div>
        )}

        {inlineError && (
          <div style={{ marginTop: 8 }}>
            <QAErrorMessage errorType={inlineError.type} error={inlineError.msg} />
          </div>
        )}
      </div>

      {history.length > 0 && (
        <div style={{ padding: '16px 20px' }}>
          <QAHistory
            items={history}
            onClear={() => setHistory([])}
            onRetry={(q) => void handleSubmit(q)}
          />
        </div>
      )}
    </div>
  )
}

const INSIGHT_CATEGORY_LABELS: Record<string, string> = {
  anomaly: 'Anomaly',
  pattern: 'Pattern',
  rationale: 'Rationale',
  forecast: 'Forecast',
  categorization: 'Categorization',
}

const INSIGHT_CATEGORY_COLORS: Record<string, string> = {
  anomaly: 'var(--danger)',
  pattern: 'var(--accent)',
  rationale: 'var(--info)',
  forecast: 'var(--success)',
  categorization: 'var(--warning)',
}

function InsightCard({
  rec,
  householdId,
  onResolved,
}: {
  rec: RecommendationOut
  householdId: string
  onResolved: () => void
}) {
  const accept =
    useAcceptRecommendationApiV1HouseholdsHouseholdIdRecommendationsRecommendationIdAcceptPost()
  const reject =
    useRejectRecommendationApiV1HouseholdsHouseholdIdRecommendationsRecommendationIdRejectPost()

  const handleAccept = async () => {
    await accept.mutateAsync({ householdId, recommendationId: rec.id })
    onResolved()
  }

  const handleReject = async () => {
    await reject.mutateAsync({ householdId, recommendationId: rec.id })
    onResolved()
  }

  const confidence = rec.confidence != null ? parseFloat(String(rec.confidence)) : null
  const category = rec.target_subsystem ?? 'insight'
  const catColor = INSIGHT_CATEGORY_COLORS[category] ?? 'var(--accent)'
  const catLabel = INSIGHT_CATEGORY_LABELS[category] ?? category

  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '16px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 8,
          justifyContent: 'space-between',
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '2px 8px',
            borderRadius: 99,
            fontSize: 11,
            fontWeight: 500,
            background: `color-mix(in oklch, ${catColor} 15%, transparent)`,
            color: catColor,
            border: `1px solid color-mix(in oklch, ${catColor} 30%, transparent)`,
          }}
        >
          {catLabel}
        </span>
      </div>

      <div style={{ fontSize: 13, color: 'var(--fg-primary)', lineHeight: 1.55 }}>
        {rec.rationale_text}
      </div>

      {confidence != null && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 11,
              color: 'var(--fg-muted)',
            }}
          >
            <span>Confidence</span>
            <span>{Math.round(confidence * 100)}%</span>
          </div>
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
                width: `${Math.round(confidence * 100)}%`,
                borderRadius: 99,
                background: 'var(--accent)',
              }}
            />
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 6 }}>
        <button
          type="button"
          onClick={() => void handleAccept()}
          disabled={accept.isPending}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '5px 12px',
            background: 'color-mix(in oklch, var(--success) 15%, transparent)',
            border: '1px solid color-mix(in oklch, var(--success) 30%, transparent)',
            borderRadius: 6,
            fontSize: 12,
            color: 'var(--success)',
            cursor: 'pointer',
            fontFamily: 'var(--font-sans)',
          }}
        >
          <CheckCircle size={12} />
          Accept
        </button>
        <button
          type="button"
          onClick={() => void handleReject()}
          disabled={reject.isPending}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '5px 12px',
            background: 'none',
            border: '1px solid var(--border)',
            borderRadius: 6,
            fontSize: 12,
            color: 'var(--fg-muted)',
            cursor: 'pointer',
            fontFamily: 'var(--font-sans)',
          }}
        >
          <XCircle size={12} />
          Dismiss
        </button>
      </div>
    </div>
  )
}

function TokenBudgetWidget({
  householdId,
  currency,
  isAdmin,
}: {
  householdId: string
  currency: string
  isAdmin: boolean
}) {
  const { data: budget } = useGetBudgetApiV1HouseholdsHouseholdIdInsightsBudgetGet(householdId, {
    query: { enabled: !!householdId },
  })

  if (!budget) return null

  const tokenLimit = budget.token_limit != null ? Number(budget.token_limit) : null
  const costLimit = budget.cost_limit != null ? parseFloat(String(budget.cost_limit)) : null
  const tokensUsed = budget.tokens_used
  const costUsed = parseFloat(budget.cost_used)
  const tokenPct = tokenLimit ? Math.min(100, (tokensUsed / tokenLimit) * 100) : null

  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '16px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-primary)' }}>
          Token budget
        </div>
        {isAdmin && (
          <NavLink
            to={ADMIN_AI_LINK}
            style={{ fontSize: 12, color: 'var(--accent)', textDecoration: 'none' }}
          >
            Edit limits
          </NavLink>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 12,
              color: 'var(--fg-muted)',
            }}
          >
            <span>Tokens this month</span>
            {tokenLimit != null ? (
              <span style={{ fontFamily: 'var(--font-mono)' }}>
                {tokensUsed.toLocaleString()} / {tokenLimit.toLocaleString()}
              </span>
            ) : (
              <span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>
                  {tokensUsed.toLocaleString()}
                </span>
                <span style={{ fontStyle: 'italic', marginLeft: 4 }}>/ No limit</span>
              </span>
            )}
          </div>
          {tokenLimit != null && (
            <div
              style={{
                height: 6,
                borderRadius: 99,
                background: 'var(--border)',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${tokenPct ?? 0}%`,
                  borderRadius: 99,
                  background:
                    (tokenPct ?? 0) > 90
                      ? 'var(--danger)'
                      : (tokenPct ?? 0) > 70
                        ? 'var(--warning)'
                        : 'var(--accent)',
                }}
              />
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Cost used</div>
            <div
              style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--fg-primary)' }}
            >
              {formatAmount(costUsed, { currency, fractionDigits: 4 })}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Cost limit</div>
            {costLimit != null ? (
              <div
                style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--fg-primary)' }}
              >
                {formatAmount(costLimit, { currency })}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: 'var(--fg-muted)', fontStyle: 'italic' }}>
                No limit
              </div>
            )}
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>On overage</div>
            <div style={{ fontSize: 12, color: 'var(--fg-secondary)' }}>
              {budget.overage_behavior.replace(/_/g, ' ')}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function GenerateSection({ householdId, recCount }: { householdId: string; recCount: number }) {
  const generate = useTriggerGenerateApiV1HouseholdsHouseholdIdInsightsGeneratePost()
  const [disabledUntil, setDisabledUntil] = useState<number | null>(null)
  const [generateError, setGenerateError] = useState<string | null>(null)

  const isDisabled = generate.isPending || (disabledUntil !== null && Date.now() < disabledUntil)

  const handleGenerate = async () => {
    setGenerateError(null)
    try {
      await generate.mutateAsync({ householdId })
      setDisabledUntil(Date.now() + 60000)
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : 'Failed to start generation')
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div>
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: 'var(--fg-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            Generated Insights
          </div>
          {recCount > 0 && (
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
              {recCount} pending
            </div>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
          <button
            type="button"
            onClick={() => void handleGenerate()}
            disabled={isDisabled}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 14px',
              background: 'none',
              border: '1px solid var(--border)',
              borderRadius: 8,
              fontSize: 12,
              color: 'var(--fg-secondary)',
              cursor: isDisabled ? 'default' : 'pointer',
              fontFamily: 'var(--font-sans)',
              opacity: isDisabled ? 0.5 : 1,
            }}
          >
            {generate.isPending ? (
              <Loader size={13} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <Sparkles size={13} />
            )}
            Generate insights
          </button>
        </div>
      </div>

      {generate.isSuccess && (
        <div
          style={{
            padding: '10px 14px',
            background: 'color-mix(in oklch, var(--success) 10%, transparent)',
            border: '1px solid color-mix(in oklch, var(--success) 30%, transparent)',
            borderRadius: 8,
            fontSize: 12,
            color: 'var(--success)',
          }}
        >
          Generating insights &mdash; check back in a few minutes.
        </div>
      )}

      {generateError && (
        <div
          style={{
            padding: '10px 14px',
            background: 'color-mix(in oklch, var(--danger) 8%, transparent)',
            border: '1px solid color-mix(in oklch, var(--danger) 25%, transparent)',
            borderRadius: 8,
            fontSize: 12,
            color: 'var(--danger)',
          }}
        >
          {generateError}
        </div>
      )}
    </div>
  )
}

export function InsightsPage() {
  const { household, householdId } = useHousehold()
  const hid = householdId ?? ''
  const qc = useQueryClient()
  const isAdmin = useAuthStore((s) => s.currentUser?.is_app_admin ?? false)

  const { data: providers = [] } = useListProvidersApiV1HouseholdsHouseholdIdInsightsProvidersGet(
    hid,
    { query: { enabled: !!hid } }
  )

  const { data: aiRecs = [] } = useListRecommendationsApiV1HouseholdsHouseholdIdRecommendationsGet(
    hid,
    {
      source: RecommendationSource.ai_insights,
      status: RecommendationStatus.pending,
    },
    { query: { enabled: !!hid } }
  )

  const handleResolved = () => {
    void qc.invalidateQueries({
      queryKey: [`/api/v1/households/${hid}/recommendations`],
    })
  }

  const hasNoProviders = (providers as ProviderConfigOut[]).length === 0
  const allDisabled = (providers as ProviderConfigOut[]).every((p) => !p.enabled)
  const currency = household?.home_currency ?? 'USD'

  if (!householdId) {
    return <div style={{ padding: 32, color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>
  }

  if (hasNoProviders) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div
          style={{
            padding: '16px 24px',
            borderBottom: '1px solid var(--border)',
            flexShrink: 0,
          }}
        >
          <h1
            style={{
              fontSize: 22,
              fontWeight: 600,
              color: 'var(--fg-primary)',
              margin: 0,
              letterSpacing: '-0.01em',
            }}
          >
            AI Insights
          </h1>
        </div>
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 12,
            padding: '80px 24px',
            textAlign: 'center',
          }}
        >
          <AlertTriangle size={32} style={{ color: 'var(--fg-muted)' }} />
          <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--fg-secondary)' }}>
            No AI provider configured
          </div>
          <div style={{ fontSize: 13, color: 'var(--fg-muted)', maxWidth: 360 }}>
            {isAdmin
              ? 'Add an AI provider in Admin → AI to get started.'
              : 'Contact your instance administrator to configure an AI provider.'}
          </div>
          {isAdmin && (
            <NavLink
              to={ADMIN_AI_LINK}
              style={{
                marginTop: 8,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 18px',
                background: 'var(--accent)',
                color: 'var(--accent-fg)',
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 500,
                textDecoration: 'none',
              }}
            >
              <Settings size={14} />
              Go to Admin &rarr; AI
            </NavLink>
          )}
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div
        style={{
          padding: '16px 24px',
          borderBottom: '1px solid var(--border)',
          flexShrink: 0,
        }}
      >
        <h1
          style={{
            fontSize: 22,
            fontWeight: 600,
            color: 'var(--fg-primary)',
            margin: 0,
            letterSpacing: '-0.01em',
          }}
        >
          AI Insights
        </h1>
      </div>

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 24,
        }}
      >
        <ProviderStatusBar providers={providers as ProviderConfigOut[]} householdId={hid} />

        {allDisabled && (
          <div
            style={{
              padding: '12px 16px',
              background: 'color-mix(in oklch, var(--warning) 8%, transparent)',
              border: '1px solid color-mix(in oklch, var(--warning) 25%, transparent)',
              borderRadius: 10,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              fontSize: 13,
            }}
          >
            <AlertTriangle size={14} style={{ color: 'var(--warning)', flexShrink: 0 }} />
            <span style={{ color: 'var(--fg-secondary)', flex: 1 }}>
              AI is unavailable &mdash; all providers are disabled.
            </span>
            {isAdmin && (
              <NavLink
                to={ADMIN_AI_LINK}
                style={{
                  fontSize: 12,
                  color: 'var(--accent)',
                  textDecoration: 'none',
                  flexShrink: 0,
                }}
              >
                Admin &rarr; AI
              </NavLink>
            )}
          </div>
        )}

        <AskSection householdId={hid} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <GenerateSection householdId={hid} recCount={(aiRecs as RecommendationOut[]).length} />

          {(aiRecs as RecommendationOut[]).length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--fg-muted)', padding: '12px 0' }}>
              No pending insights. Click &ldquo;Generate insights&rdquo; to analyze your finances.
            </div>
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
                gap: 12,
              }}
            >
              {(aiRecs as RecommendationOut[]).map((rec) => (
                <InsightCard key={rec.id} rec={rec} householdId={hid} onResolved={handleResolved} />
              ))}
            </div>
          )}
        </div>

        <TokenBudgetWidget householdId={hid} currency={currency} isAdmin={isAdmin} />
      </div>
    </div>
  )
}
