/**
 * Shared Playwright fixtures — authenticated browser context + typed API helpers.
 *
 * Each test file imports `test` and `expect` from here instead of @playwright/test
 * to get the authenticated context automatically.
 */
import { test as base, expect } from '@playwright/test'
import * as fs from 'fs'
import { AUTH_STATE_FILE, TEST_CREDENTIALS_FILE } from './global-setup'

interface TestCredentials {
  email: string
  password: string
  householdId: string
  apiUrl: string
}

function loadCredentials(): TestCredentials {
  return JSON.parse(fs.readFileSync(TEST_CREDENTIALS_FILE, 'utf8')) as TestCredentials
}

export interface TestFixtures {
  credentials: TestCredentials
  apiPost: (path: string, body: unknown) => Promise<unknown>
}

export const test = base.extend<TestFixtures>({
  storageState: AUTH_STATE_FILE,

  credentials: async ({}, use) => {
    await use(loadCredentials())
  },

  apiPost: async ({ request, credentials }, use) => {
    const helper = async (path: string, body: unknown): Promise<unknown> => {
      const res = await request.post(`${credentials.apiUrl}/api/v1${path}`, { data: body })
      if (!res.ok()) {
        throw new Error(`POST ${path} failed: ${res.status()} ${await res.text()}`)
      }
      return res.json()
    }
    await use(helper)
  },
})

export { expect }
