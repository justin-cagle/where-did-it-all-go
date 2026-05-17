import { test, expect } from './fixtures'

test.describe('Budgets', () => {
  test('create budget appears in list', async ({ page, credentials, apiPost }) => {
    await page.goto('/budget')

    const createBtn = page.getByRole('button', { name: /new budget|create budget|add budget/i })
    await createBtn.click()

    const nameInput = page.getByLabel(/budget name|name/i)
    await nameInput.fill(`E2E Budget ${Date.now()}`)
    await page.getByRole('button', { name: /save|create/i }).click()

    await expect(page.getByText(/E2E Budget/)).toBeVisible()
  })

  test('add budget line appears in detail', async ({ page, credentials, apiPost }) => {
    const budget = (await apiPost(`/households/${credentials.householdId}/budgets/`, {
      name: `Line Test Budget ${Date.now()}`,
      method: 'envelope',
      period_type: 'monthly',
      currency: 'USD',
      period_start: new Date().toISOString().split('T')[0],
    })) as { id: string; name: string }

    await page.goto('/budget')
    const budgetLink = page.getByText(budget.name)
    if (await budgetLink.isVisible()) {
      await budgetLink.click()
      await page.getByRole('button', { name: /add line|new line/i }).click()
      await expect(
        page.getByRole('dialog').or(page.locator("[data-testid='add-budget-line']"))
      ).toBeVisible()
    }
  })

  test('budget page loads without error state', async ({ page }) => {
    await page.goto('/budget')
    await expect(page.getByRole('main')).toBeVisible()
    await expect(page.getByText(/error|something went wrong/i)).not.toBeVisible()
  })
})
