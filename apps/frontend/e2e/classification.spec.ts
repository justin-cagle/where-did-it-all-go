import { test, expect } from './fixtures'

test.describe('Classification', () => {
  test('create category appears in tree', async ({ page }) => {
    await page.goto('/settings/classification')

    await page.getByRole('button', { name: /add category|new category/i }).click()
    const catName = `E2E Category ${Date.now()}`
    await page.getByLabel(/category name|name/i).fill(catName)
    await page.getByRole('button', { name: /save|create/i }).click()

    await expect(page.getByText(catName)).toBeVisible()
  })

  test('create rule appears in rules list', async ({ page }) => {
    await page.goto('/settings/classification')

    const rulesTab = page.getByRole('tab', { name: /rules/i })
    if (await rulesTab.isVisible()) {
      await rulesTab.click()
    }

    await page.getByRole('button', { name: /add rule|new rule/i }).click()
    const ruleName = `E2E Rule ${Date.now()}`
    await page.getByLabel(/rule name|name/i).fill(ruleName)
    await page.getByRole('button', { name: /save|create/i }).click()

    await expect(page.getByText(ruleName)).toBeVisible()
  })

  test('enable/disable rule toggle persists', async ({ page, credentials, apiPost }) => {
    const rule = (await apiPost(`/households/${credentials.householdId}/rules/`, {
      name: `Toggle Rule ${Date.now()}`,
      priority: 100,
      conditions: [{ field: 'description', operator: 'contains', value: 'e2e-test-unique' }],
      actions: [],
      enabled: true,
    })) as { id: string; name: string; enabled: boolean }

    await page.goto('/settings/classification')
    const rulesTab = page.getByRole('tab', { name: /rules/i })
    if (await rulesTab.isVisible()) {
      await rulesTab.click()
    }

    const ruleRow = page.getByText(rule.name).first()
    if (await ruleRow.isVisible()) {
      const toggle = page.getByRole('switch').first()
      const wasChecked = await toggle.isChecked()
      await toggle.click()
      await expect(toggle).toHaveAttribute('aria-checked', wasChecked ? 'false' : 'true')

      await page.reload()
      const toggleAfterReload = page.getByRole('switch').first()
      await expect(toggleAfterReload).toHaveAttribute('aria-checked', wasChecked ? 'false' : 'true')
    }
  })
})
