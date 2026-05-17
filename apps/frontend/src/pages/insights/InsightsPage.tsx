import { useState, useRef } from 'react'
import { Send, Loader, Sparkles, CheckCircle, XCircle, AlertTriangle, Settings } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import {
  useListProvidersApiV1HouseholdsHouseholdIdInsightsProvidersGet,
  useAskApiV1HouseholdsHouseholdIdInsightsAskPost,
  useTriggerGenerateApiV1HouseholdsHouseholdIdInsightsGeneratePost,
  useGetBudgetApiV1HouseholdsHouseholdIdInsightsBudgetGet,
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

interface QAItem {
  id: string
  question: string
  response: AskResponse | null
  error: string | null
  loading: boolean
}

function ProviderStatusBar({ providers }: { providers: ProviderConfigOut[] }) {
  if (providers.length === 0) return null

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
      <span style={{ fontSize: 12, color: 'var(--fg-muted)', marginRight: 4 }}>Providers:</span>
      {providers.map((p) => {
        const dotColor = p.enabled ? 'var(--success)' : 'var(--fg-muted)'
        const label = p.provider.replace(/_/g, ' ')
        return (
          <div
            key={p.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '3px 10px',
              borderRadius: 99,
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              fontSize: 12,
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
          </div>
        )
      })}
      <NavLink
        to="/settings/insights"
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

function QAHistory({ items, onClear }: { items: QAItem[]; onClear: () => void }) {
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
              <div style={{ fontSize: 13, color: 'var(--danger)' }}>{item.error}</div>
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
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const ask = useAskApiV1HouseholdsHouseholdIdInsightsAskPost()

  const handleSubmit = async () => {
    const q = question.trim()
    if (!q) return

    const id = Math.random().toString(36).slice(2, 10)
    const item: QAItem = { id, question: q, response: null, error: null, loading: true }
    setHistory((prev) => [...prev, item])
    setQuestion('')

    try {
      const res = await ask.mutateAsync({ householdId, data: { question: q } })
      setHistory((prev) =>
        prev.map((x) => (x.id === id ? { ...x, response: res, loading: false } : x))
      )
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Something went wrong'
      setHistory((prev) =>
        prev.map((x) => (x.id === id ? { ...x, error: msg, loading: false } : x))
      )
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSubmit()
    }
  }

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
            }}
          />
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={!question.trim() || ask.isPending}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 34,
              height: 34,
              background: question.trim() ? 'var(--accent)' : 'var(--border)',
              border: 'none',
              borderRadius: 8,
              cursor: question.trim() ? 'pointer' : 'default',
              color: question.trim() ? 'var(--accent-fg)' : 'var(--fg-muted)',
              flexShrink: 0,
              transition: 'background 0.15s',
            }}
          >
            {ask.isPending ? <Loader size={14} /> : <Send size={14} />}
          </button>
        </div>
      </div>

      {history.length > 0 && (
        <div style={{ padding: '16px 20px' }}>
          <QAHistory items={history} onClear={() => setHistory([])} />
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

function TokenBudgetWidget({ householdId, currency }: { householdId: string; currency: string }) {
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
        <NavLink
          to="/settings/insights"
          style={{ fontSize: 12, color: 'var(--accent)', textDecoration: 'none' }}
        >
          Edit limits
        </NavLink>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {tokenLimit != null && (
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
              <span style={{ fontFamily: 'var(--font-mono)' }}>
                {tokensUsed.toLocaleString()} / {tokenLimit.toLocaleString()}
              </span>
            </div>
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
          </div>
        )}

        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Cost used</div>
            <div
              style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--fg-primary)' }}
            >
              {formatAmount(costUsed, { currency })}
            </div>
          </div>
          {costLimit != null && (
            <div>
              <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Cost limit</div>
              <div
                style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--fg-primary)' }}
              >
                {formatAmount(costLimit, { currency })}
              </div>
            </div>
          )}
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

export function InsightsPage() {
  const { household, householdId } = useHousehold()
  const hid = householdId ?? ''
  const qc = useQueryClient()

  const { data: providers = [] } = useListProvidersApiV1HouseholdsHouseholdIdInsightsProvidersGet(
    hid,
    { query: { enabled: !!hid } }
  )

  const { data: aiRecs = [], refetch: refetchRecs } =
    useListRecommendationsApiV1HouseholdsHouseholdIdRecommendationsGet(
      hid,
      {
        source: RecommendationSource.ai_insights,
        status: RecommendationStatus.pending,
      },
      { query: { enabled: !!hid } }
    )

  const generate = useTriggerGenerateApiV1HouseholdsHouseholdIdInsightsGeneratePost()

  const handleGenerate = async () => {
    await generate.mutateAsync({ householdId: hid })
    void refetchRecs()
  }

  const handleResolved = () => {
    void qc.invalidateQueries({
      queryKey: [`/api/v1/households/${hid}/recommendations`],
    })
  }

  const hasNoProviders = providers.length === 0
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
            Connect a local or cloud AI provider to get started with insights, Q&A, and more.
          </div>
          <NavLink
            to="/settings/insights"
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
            Configure provider
          </NavLink>
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
        <ProviderStatusBar providers={providers as ProviderConfigOut[]} />

        <AskSection householdId={hid} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
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
              {(aiRecs as RecommendationOut[]).length > 0 && (
                <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
                  {(aiRecs as RecommendationOut[]).length} pending
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={() => void handleGenerate()}
              disabled={generate.isPending}
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
                cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
                opacity: generate.isPending ? 0.6 : 1,
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
              Generation queued — insights will appear shortly.
            </div>
          )}

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

        <TokenBudgetWidget householdId={hid} currency={currency} />
      </div>
    </div>
  )
}
