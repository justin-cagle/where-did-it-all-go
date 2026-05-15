import { RouterProvider } from 'react-router-dom'
import { ThemeProvider } from '@/providers/ThemeProvider'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { router } from '@/router'

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <RouterProvider router={router} />
      </ThemeProvider>
    </ErrorBoundary>
  )
}
