export function parseVersion(v: string): [number, number, number] {
  const parts = v.replace(/^v/, '').split('.').map(Number)
  return [parts[0] ?? 0, parts[1] ?? 0, parts[2] ?? 0]
}

export function isNewerVersion(current: string, candidate: string): boolean {
  const [cMaj, cMin, cPatch] = parseVersion(current)
  const [lMaj, lMin, lPatch] = parseVersion(candidate)
  if (lMaj !== cMaj) return lMaj > cMaj
  if (lMin !== cMin) return lMin > cMin
  return lPatch > cPatch
}
