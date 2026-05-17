import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'node:path'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        // App shell caching — all static assets
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        // API GET caching with stale-while-revalidate.
        // No precaching of authenticated content.
        runtimeCaching: [
          {
            urlPattern: /^\/api\/v1\//i,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'api-cache',
              expiration: { maxEntries: 100, maxAgeSeconds: 300 },
            },
          },
        ],
      },
      manifest: {
        name: 'Where Did It All Go',
        short_name: 'WDIAG',
        description: 'Personal finance budgeting and intelligence',
        theme_color: '#ffffff',
        background_color: '#ffffff',
        display: 'standalone',
        icons: [],
      },
    }),
  ],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    passWithNoTests: true,
    exclude: ['**/node_modules/**', '**/dist/**', 'e2e/**'],
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/domain/**'],
      // Threshold enforced once real domain code exists; stub files excluded until then
      thresholds: { lines: 0 },
    },
  },
})
