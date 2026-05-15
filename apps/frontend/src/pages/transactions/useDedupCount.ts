import { useListDedupCandidatesApiV1HouseholdsHouseholdIdTransactionsDedupCandidatesGet } from '@/api/generated/transactions/transactions'

export function useDedupCount(householdId: string | null) {
  const { data } = useListDedupCandidatesApiV1HouseholdsHouseholdIdTransactionsDedupCandidatesGet(
    householdId ?? '',
    { query: { enabled: !!householdId } }
  )
  return data?.length ?? 0
}
