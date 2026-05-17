/**
 * Auth critical-path E2E tests.
 *
 * These tests use fresh browser contexts (no stored auth state) so they
 * can test the full login/register flow.
 */
import { test, expect } from '@playwright/test'
import * as fs from 'fs'
import { TEST_CREDENTIALS_FILE } from './global-setup'

interface Credentials {
  email: string
  password: string
}

function getCredentials(): Credentials {
  return JSON.parse(fs.readFileSync(TEST_CREDENTIALS_FILE, 'utf8')) as Credentials
}

test.describe('Auth flows', () => {
  test('register new user redirects to onboarding or dashboard', async ({ page }) => {
    const email = `reg-${Date.now()}@test.invalid`
    await page.goto('/register')
    await page.getByLabel(/email/i).fill(email)
    await page.getByLabel(/display.?name/i).fill('New Tester')
    await page.getByLabel(/password/i).fill('NewPass!123')
    await page.getByRole('button', { name: /register|sign up|create account/i }).click()
    await page.waitForURL(/\/(dashboard|onboarding|households)/)
    await expect(page).not.toHaveURL(/\/login/)
  })

  test('login with valid credentials redirects to dashboard', async ({ page }) => {
    const { email, password } = getCredentials()
    await page.goto('/login')
    await page.getByLabel(/email/i).fill(email)
    await page.getByLabel(/password/i).fill(password)
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    await page.waitForURL(/\/(dashboard|accounts|transactions)/)
    await expect(page).not.toHaveURL(/\/login/)
  })

  test('login with wrong password shows error, stays on login', async ({ page }) => {
    const { email } = getCredentials()
    await page.goto('/login')
    await page.getByLabel(/email/i).fill(email)
    await page.getByLabel(/password/i).fill('wrong-password-!!')
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    await expect(page).toHaveURL(/\/login/)
    await expect(
      page.getByRole('alert').or(page.getByText(/invalid|incorrect|wrong/i))
    ).toBeVisible()
  })

  test('unauthenticated access redirects to /login', async ({ page }) => {
    await page.goto('/accounts')
    await page.waitForURL(/\/login/)
    await expect(page).toHaveURL(/\/login/)
  })

  test('logout clears session and redirects to login', async ({ page }) => {
    const { email, password } = getCredentials()
    await page.goto('/login')
    await page.getByLabel(/email/i).fill(email)
    await page.getByLabel(/password/i).fill(password)
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    await page.waitForURL(/\/(dashboard|accounts|transactions)/)

    await page.getByRole('button', { name: /logout|sign out/i }).click()
    await page.waitForURL(/\/login/)
    await expect(page).toHaveURL(/\/login/)
  })
})
