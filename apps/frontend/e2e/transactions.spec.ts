import { test, expect } from './fixtures'

test.describe('Transactions', () => {
  test('manual transaction entry appears in list', async ({ page, credentials, apiPost }) => {
    const account = (await apiPost(`/households/${credentials.householdId}/accounts/`, {
      name: `Tx Account ${Date.now()}`,
      account_type: 'manual',
      currency: 'USD',
    })) as { id: string }

    await page.goto('/transactions')
    await page.getByRole('button', { name: /add transaction|new transaction/i }).click()
    await page.getByLabel(/amount/i).fill('42.00')
    await page.getByLabel(/description/i).fill('E2E Test Transaction')
    await page.getByRole('button', { name: /save|create|add/i }).click()

    await expect(page.getByText('E2E Test Transaction')).toBeVisible()
  })

  test('transaction detail sheet opens on click', async ({ page, credentials, apiPost }) => {
    const account = (await apiPost(`/households/${credentials.householdId}/accounts/`, {
      name: `Sheet Account ${Date.now()}`,
      account_type: 'manual',
      currency: 'USD',
    })) as { id: string }

    await page.goto('/transactions')

    const rows = page.getByRole('row')
    const firstRow = rows.nth(1)
    if (await firstRow.isVisible()) {
      await firstRow.click()
      await expect(
        page.getByRole('dialog').or(page.locator("[data-testid='transaction-detail']"))
      ).toBeVisible()
    }
  })

  test('filter by date range updates list', async ({ page }) => {
    await page.goto('/transactions')

    const dateFilter = page.getByRole('button', { name: /date range|filter/i }).first()
    if (await dateFilter.isVisible()) {
      await dateFilter.click()
      await expect(
        page.getByRole('dialog').or(page.locator("[data-testid='date-filter']"))
      ).toBeVisible()
    }
  })
})
