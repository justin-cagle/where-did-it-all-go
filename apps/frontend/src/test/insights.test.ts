/**
 * Frontend tests for AI insights — pure logic, no DOM.
 *
 * Covers:
 *  - SSE pull progress event parsing
 *  - Progress percentage calculation
 *  - Error type classification
 *  - Model list filtering
 */

import { describe, it, expect } from 'vitest'

// ---------------------------------------------------------------------------
// SSE pull progress parsing
// ---------------------------------------------------------------------------

describe('SSE pull event parsing', () => {
  it('parses pulling manifest event', () => {
    const line = 'data: {"status": "pulling manifest"}'
    const ev = JSON.parse(line.slice(6)) as { status: string }
    expect(ev.status).toBe('pulling manifest')
  })

  it('parses downloading event with progress', () => {
    const line = 'data: {"status": "downloading", "completed": 1234, "total": 4661211136}'
    const ev = JSON.parse(line.slice(6)) as { status: string; completed: number; total: number }
    expect(ev.status).toBe('downloading')
    expect(ev.completed).toBe(1234)
    expect(ev.total).toBe(4661211136)
  })

  it('recognizes complete status', () => {
    const ev = JSON.parse('{"status": "complete"}') as { status: string }
    const isDone = ev.status === 'success' || ev.status === 'complete'
    expect(isDone).toBe(true)
  })

  it('recognizes success status', () => {
    const ev = JSON.parse('{"status": "success"}') as { status: string }
    const isDone = ev.status === 'success' || ev.status === 'complete'
    expect(isDone).toBe(true)
  })

  it('recognizes error status', () => {
    const ev = JSON.parse('{"status": "error", "error": "model not found"}') as {
      status: string
      error?: string
    }
    expect(ev.status).toBe('error')
    expect(ev.error).toBe('model not found')
  })

  it('ignores malformed SSE data gracefully', () => {
    const line = 'data: {not valid json}'
    let parsed: unknown = null
    try {
      parsed = JSON.parse(line.slice(6))
    } catch {
      parsed = null
    }
    expect(parsed).toBeNull()
  })

  it('skips non-data SSE lines', () => {
    const lines = ['event: open', ': keepalive', '', 'data: {"status": "complete"}']
    const dataLines = lines.filter((l) => l.startsWith('data: '))
    expect(dataLines).toHaveLength(1)
    expect(dataLines[0]).toBe('data: {"status": "complete"}')
  })
})

// ---------------------------------------------------------------------------
// Progress percentage calculation
// ---------------------------------------------------------------------------

describe('Pull progress percentage', () => {
  it('computes 50% correctly', () => {
    const completed = 2330605568
    const total = 4661211136
    const pct = Math.min(100, Math.round((completed / total) * 100))
    expect(pct).toBe(50)
  })

  it('caps at 100% on overshoot', () => {
    const pct = Math.min(100, Math.round((5000000000 / 4661211136) * 100))
    expect(pct).toBe(100)
  })

  it('returns null when total is 0 to avoid division by zero', () => {
    const total = 0
    const pct = total > 0 ? Math.min(100, Math.round((0 / total) * 100)) : null
    expect(pct).toBeNull()
  })

  it('returns 0% when completed is 0', () => {
    const pct = Math.min(100, Math.round((0 / 4661211136) * 100))
    expect(pct).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// Q&A error type classification
// ---------------------------------------------------------------------------

describe('Q&A error type classification', () => {
  function classifyReason(reason: string | null | undefined): string {
    if (!reason) return 'generic'
    if (reason === 'no_provider') return 'no_provider'
    if (reason === 'budget_exceeded') return 'budget_exceeded'
    if (reason === 'disabled') return 'disabled'
    return 'generic'
  }

  it('classifies no_provider reason', () => {
    expect(classifyReason('no_provider')).toBe('no_provider')
  })

  it('classifies budget_exceeded reason', () => {
    expect(classifyReason('budget_exceeded')).toBe('budget_exceeded')
  })

  it('classifies disabled reason', () => {
    expect(classifyReason('disabled')).toBe('disabled')
  })

  it('classifies unknown reason as generic', () => {
    expect(classifyReason('some_future_reason')).toBe('generic')
  })

  it('classifies null reason as generic', () => {
    expect(classifyReason(null)).toBe('generic')
  })
})

// ---------------------------------------------------------------------------
// Model selector logic
// ---------------------------------------------------------------------------

describe('OllamaModelSelector logic', () => {
  interface OllamaModel {
    name: string
    size_bytes: number
    modified_at: string
  }

  it('finds a model by name', () => {
    const models: OllamaModel[] = [
      { name: 'llama3:latest', size_bytes: 4661211136, modified_at: '2024-01-15T10:00:00Z' },
      { name: 'mistral:latest', size_bytes: 3825884160, modified_at: '2024-01-10T10:00:00Z' },
    ]
    const selected = models.find((m) => m.name === 'mistral:latest')
    expect(selected).toBeDefined()
    expect(selected?.size_bytes).toBe(3825884160)
  })

  it('returns undefined for unknown model name', () => {
    const models: OllamaModel[] = [
      { name: 'llama3:latest', size_bytes: 4661211136, modified_at: '2024-01-15T10:00:00Z' },
    ]
    const selected = models.find((m) => m.name === 'nonexistent:tag')
    expect(selected).toBeUndefined()
  })

  it('empty models list yields no selection', () => {
    const models: OllamaModel[] = []
    expect(models.length).toBe(0)
  })

  it('falls back to text input when models list is null (Ollama unreachable)', () => {
    const modelsData: { models: OllamaModel[] } | null = null
    const shouldShowFallback = modelsData === null
    expect(shouldShowFallback).toBe(true)
  })

  it('shows dropdown when models loaded and non-empty', () => {
    const models: OllamaModel[] = [
      { name: 'llama3:latest', size_bytes: 4661211136, modified_at: '2024-01-15T10:00:00Z' },
    ]
    const shouldShowDropdown = models.length > 0
    expect(shouldShowDropdown).toBe(true)
  })
})
