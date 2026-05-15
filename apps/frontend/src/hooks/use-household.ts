import { useListHouseholdsApiV1HouseholdsGet } from '@/api/generated/households/households'

export function useHousehold() {
  const { data, isLoading, isError } = useListHouseholdsApiV1HouseholdsGet()
  const household = data?.[0] ?? null
  return { household, householdId: household?.id ?? null, isLoading, isError }
}
