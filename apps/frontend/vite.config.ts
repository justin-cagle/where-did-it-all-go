import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'node:path'
import pkg from './package.json'

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
            // Auth routes: network-first (security-sensitive — never serve stale session data)
            urlPattern: /^\/api\/v1\/auth\//i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'auth-api-cache',
              networkTimeoutSeconds: 5,
            },
          },
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
        start_url: '/',
        theme_color: '#4f70f0',
        background_color: '#0a0a0a',
        display: 'standalone',
        icons: [
          { src: '/logo.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      '/api': {
        target: process.env['VITE_BACKEND_URL'] ?? 'http://localhost:8111',
        changeOrigin: true,
        cookieDomainRewrite: '',
      },
    },
  },
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
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
