/** Minimal TypeScript fixture for integration quickstart validation. */

export function computeBackoffMs(attempt: number): number {
  const baseMs = 250;
  return baseMs * 2 ** attempt;
}
