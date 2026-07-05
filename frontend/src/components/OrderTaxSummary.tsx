import type { Order } from '../api/types'
import { orderDisplayTotalCents } from '../api/types'
import { formatMoney } from '../lib/format'

/**
 * Subtotal + GST breakdown + grand total, shared by the customer and admin
 * order detail pages (see docs/CONTRACTS.md "INR Currency & GST"). Renders
 * a plain "Total" row when the order carries no tax fields (every non-INR
 * order, or INR orders when GST is disabled) -- same "only render extra
 * rows if present" pattern already used for payment_status/invoice_number
 * elsewhere in these pages.
 */
export function OrderTaxSummary({ order }: { order: Order }) {
  const hasTax = order.tax_total_cents !== null

  if (!hasTax) {
    return (
      <p className="mt-4 text-lg font-medium text-gray-900">
        Total: {formatMoney(orderDisplayTotalCents(order), order.currency)}
      </p>
    )
  }

  const row = (label: string, cents: number | null) => (
    <div className="flex items-center justify-between text-sm text-gray-600">
      <span>{label}</span>
      <span>{formatMoney(cents ?? 0, order.currency)}</span>
    </div>
  )

  return (
    <div className="mt-4 flex flex-col gap-1 border-t border-gray-200 pt-4">
      {row('Taxable amount', order.taxable_amount_cents)}
      {order.cgst_cents ? row('CGST', order.cgst_cents) : null}
      {order.sgst_cents ? row('SGST', order.sgst_cents) : null}
      {order.igst_cents ? row('IGST', order.igst_cents) : null}
      <div className="mt-1 flex items-center justify-between text-lg font-medium text-gray-900">
        <span>Grand total</span>
        <span>{formatMoney(orderDisplayTotalCents(order), order.currency)}</span>
      </div>
    </div>
  )
}
