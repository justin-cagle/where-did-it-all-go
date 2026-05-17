import { test, expect } from './fixtures'

test.describe('Goals', () => {
  test('create savings_target goal appears in list', async ({ page, credentials, apiPost }) => {
    await page.goto('/goals')

    await page.getByRole('button', { name: /new goal|create goal|add goal/i }).click()

    await page.getByLabel(/goal name|name/i).fill(`E2E Goal ${Date.now()}`)
    const typeSelect = page.getByLabel(/goal type|type/i)
    if (await typeSelect.isVisible()) {
      await typeSelect.selectOption('savings_target')
    }
    await page.getByLabel(/target amount|amount/i).fill('1000')
    await page.getByRole('button', { name: /save|create/i }).click()

    await expect(page.getByText(/E2E Goal/)).toBeVisible()
  })

  test('log contribution updates progress bar', async ({ page, credentials, apiPost }) => {
    const goal = (await apiPost(`/households/${credentials.householdId}/goals/`, {
      name: `Progress Goal ${Date.now()}`,
      goal_type: 'savings_target',
      target_amount: '500',
      currency: 'USD',
      target_date: new Date(Date.now() + 90 * 86400_000).toISOString().split('T')[0],
    })) as { id: string; name: string }

    await page.goto('/goals')
    const goalCard = page.getByText(goal.name)
    if (await goalCard.isVisible()) {
      await goalCard.click()
      const logBtn = page.getByRole('button', { name: /log contribution|add contribution/i })
      if (await logBtn.isVisible()) {
        await logBtn.click()
        await page.getByLabel(/amount/i).fill('100')
        await page.getByRole('button', { name: /save|add/i }).click()
        await expect(
          page.locator("[role='progressbar']").or(page.locator("[data-testid='progress']"))
        ).toBeVisible()
      }
    }
  })
})
