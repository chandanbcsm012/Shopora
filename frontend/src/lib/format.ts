// Picks the locale whose grouping/symbol conventions match the currency
// itself (e.g. INR uses the Indian digit-grouping system — lakhs/crores,
// ₹1,00,000.00 not ₹100,000.00) rather than always formatting as en-US.
const CURRENCY_LOCALES: Record<string, string> = {
  INR: 'en-IN',
}
const DEFAULT_LOCALE = 'en-US'

/** Formats an integer minor-units amount (see CONTRACTS.md money convention) as a currency string. */
export function formatMoney(amountCents: number, currency: string): string {
  const locale = CURRENCY_LOCALES[currency] ?? DEFAULT_LOCALE
  try {
    return new Intl.NumberFormat(locale, { style: 'currency', currency }).format(amountCents / 100)
  } catch {
    return `${(amountCents / 100).toFixed(2)} ${currency}`
  }
}
