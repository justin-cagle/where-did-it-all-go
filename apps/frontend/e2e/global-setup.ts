/**
 * Playwright global setup — creates a test household and stores the auth
 * state file so individual test files can reuse the session.
 *
 * Run once before all tests. Individual tests create their own data and
 * never depend on state from other tests.
 */
import { chromium, type FullConfig } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'

const API_URL = process.env.PLAYWRIGHT_API_URL ?? 'http://localhost:8000'
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173'

const TEST_EMAIL = `e2e-${Date.now()}@test.invalid`
const TEST_PASSWORD = 'E2eTestPass!1' // pragma: allowlist secret
const TEST_DISPLAY_NAME = 'E2E Test User'

export const AUTH_STATE_FILE = path.join(__dirname, '.auth-state.json')
export const TEST_CREDENTIALS_FILE = path.join(__dirname, '.test-credentials.json')

async function createTestUser(apiUrl: string): Promise<void> {
  const res = await fetch(`${apiUrl}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: TEST_EMAIL,
      display_name: TEST_DISPLAY_NAME,
      password: TEST_PASSWORD,
    }),
  })
  if (!res.ok && res.status !== 409) {
    throw new Error(`Failed to register test user: ${res.status} ${await res.text()}`)
  }
}

async function createTestHousehold(apiUrl: string, cookies: string): Promise<string> {
  const res = await fetch(`${apiUrl}/api/v1/households`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Cookie: cookies,
    },
    body: JSON.stringify({
      name: 'E2E Test Household',
      home_currency: 'USD',
    }),
  })
  if (!res.ok) {
    throw new Error(`Failed to create household: ${res.status} ${await res.text()}`)
  }
  const data = (await res.json()) as { id: string }
  return data.id
}

export default async function globalSetup(_config: FullConfig): Promise<void> {
  await createTestUser(API_URL)

  const browser = await chromium.launch()
  const context = await browser.newContext({ baseURL: BASE_URL })
  const page = await context.newPage()

  await page.goto('/login')
  await page.getByLabel(/email/i).fill(TEST_EMAIL)
  await page.getByLabel(/password/i).fill(TEST_PASSWORD)
  await page.getByRole('button', { name: /sign in|log in/i }).click()
  await page.waitForURL(/\/(dashboard|onboarding|households)/)

  const cookieJar = await context.cookies()
  const cookieHeader = cookieJar.map((c) => `${c.name}=${c.value}`).join('; ')

  const householdId = await createTestHousehold(API_URL, cookieHeader)

  await context.storageState({ path: AUTH_STATE_FILE })
  await browser.close()

  fs.writeFileSync(
    TEST_CREDENTIALS_FILE,
    JSON.stringify({
      email: TEST_EMAIL,
      password: TEST_PASSWORD,
      householdId,
      apiUrl: API_URL,
    }),
    'utf8'
  )
}
