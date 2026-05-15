import { Component } from 'react'
import type { ReactNode, ErrorInfo } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (import.meta.env.DEV) {
      console.error('[ErrorBoundary]', error, info)
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: '100dvh',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 16,
            padding: 24,
            background: 'var(--bg-primary)',
            color: 'var(--fg-primary)',
            fontFamily: 'var(--font-sans)',
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 12,
              background: 'color-mix(in oklch, var(--danger) 12%, transparent)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 24,
            }}
          >
            !
          </div>
          <div style={{ textAlign: 'center', maxWidth: 400 }}>
            <p style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>Something went wrong</p>
            <p style={{ fontSize: 13, color: 'var(--fg-muted)', marginBottom: 24 }}>
              An unexpected error occurred. Reload to try again.
            </p>
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: '8px 20px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-elevated)',
                color: 'var(--fg-primary)',
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
              }}
            >
              Reload page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
