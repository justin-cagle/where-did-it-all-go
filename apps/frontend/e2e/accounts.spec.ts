import { test, expect } from './fixtures'

test.describe('Accounts', () => {
  test('create manual account appears in list', async ({ page, credentials, apiPost }) => {
    const name = `E2E Account ${Date.now()}`
    await page.goto('/accounts')

    await page.getByRole('button', { name: /add account|new account|create account/i }).click()
    await page.getByLabel(/account name|name/i).fill(name)
    await page.getByRole('button', { name: /save|create|add/i }).click()

    await expect(page.getByText(name)).toBeVisible()
  })

  test('account detail page loads with correct name', async ({ page, credentials, apiPost }) => {
    const name = `Detail E2E ${Date.now()}`
    const account = (await apiPost(`/households/${credentials.householdId}/accounts/`, {
      name,
      account_type: 'manual',
      currency: 'USD',
    })) as { id: string; name: string }

    await page.goto('/accounts')
    await page.getByText(account.name).click()
    await expect(page.getByRole('heading', { name: account.name })).toBeVisible()
  })

  test('archive account removes it from list', async ({ page, credentials, apiPost }) => {
    const name = `Archive E2E ${Date.now()}`
    const account = (await apiPost(`/households/${credentials.householdId}/accounts/`, {
      name,
      account_type: 'manual',
      currency: 'USD',
    })) as { id: string; name: string }

    await page.goto('/accounts')
    await expect(page.getByText(account.name)).toBeVisible()

    await page.getByText(account.name).click()
    await page.getByRole('button', { name: /archive|delete/i }).click()
    await page.getByRole('button', { name: /confirm|yes/i }).click()

    await page.goto('/accounts')
    await expect(page.getByText(account.name)).not.toBeVisible()
  })
})
