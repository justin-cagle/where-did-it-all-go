import type { AccountOut } from '@/api/generated/model/accountOut'

export const LIABILITY_ACCOUNT_TYPES = ['credit_card', 'loan', 'line_of_credit'] as const
type LiabilityType = (typeof LIABILITY_ACCOUNT_TYPES)[number]

export function isLiabilityType(t: string): boolean {
  return LIABILITY_ACCOUNT_TYPES.includes(t as LiabilityType)
}

export type AccountGroupConfig = {
  label: string
  types: string[]
}

export const ACCOUNT_GROUP_CONFIGS: AccountGroupConfig[] = [
  { label: 'Banks', types: ['checking', 'savings'] },
  { label: 'Credit Cards', types: ['credit_card'] },
  { label: 'Investments', types: ['investment'] },
  { label: 'Debts', types: ['loan', 'line_of_credit'] },
  { label: 'Other', types: ['manual', 'other'] },
]

export function groupAccounts(
  accounts: AccountOut[]
): { config: AccountGroupConfig; accounts: AccountOut[] }[] {
  return ACCOUNT_GROUP_CONFIGS.map((config) => ({
    config,
    accounts: accounts.filter((a) => config.types.includes(a.account_type)),
  })).filter(({ accounts: accs }) => accs.length > 0)
}

export function calcNetWorth(accounts: AccountOut[]): number {
  return accounts.reduce((sum, a) => sum + parseFloat(a.current_balance), 0)
}

export function groupTotal(accounts: AccountOut[]): number {
  return accounts.reduce((sum, a) => sum + parseFloat(a.current_balance), 0)
}

export function accountTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    checking: 'Checking',
    savings: 'Savings',
    credit_card: 'Credit Card',
    investment: 'Investment',
    loan: 'Loan',
    line_of_credit: 'Line of Credit',
    manual: 'Manual',
    other: 'Other',
  }
  return labels[type] ?? type
}
