import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import * as ordersApi from '../api/orders'
import type { Order, OrderStatus, OrderStatusHistory } from '../api/types'
import { Alert, Badge, type BadgeTone, Button, Card, Skeleton } from '../components/ui'
import { OrderTaxSummary } from '../components/OrderTaxSummary'
import { formatMoney } from '../lib/format'
import { AddressSummary } from './Addresses'

const STATUS_TONE: Record<OrderStatus, BadgeTone> = {
  pending: 'warning',
  paid: 'info',
  shipped: 'info',
  delivered: 'success',
  cancelled: 'danger',
}

/** `Payment.status` values (see docs/CONTRACTS.md's `payments` module).
 * Kept separate from STATUS_TONE (which maps `Order.status`) since the two
 * are independent fields that can disagree -- e.g. a "paid" order with a
 * "pending" (COD, cash not yet collected) payment status. */
const PAYMENT_STATUS_TONE: Record<string, BadgeTone> = {
  pending: 'warning',
  authorized: 'info',
  captured: 'success',
  failed: 'danger',
  cancelled: 'neutral',
  refunded: 'neutral',
  partially_refunded: 'warning',
  expired: 'danger',
}

export default function OrderDetail() {
  const { id } = useParams<{ id: string }>()
  const [order, setOrder] = useState<Order | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [timeline, setTimeline] = useState<OrderStatusHistory[]>([])
  const [isTimelineLoading, setIsTimelineLoading] = useState(true)
  const [timelineError, setTimelineError] = useState<string | null>(null)

  const [isDownloading, setIsDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setIsLoading(true)
    ordersApi
      .getOrder(id)
      .then(setOrder)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load order'))
      .finally(() => setIsLoading(false))
  }, [id])

  useEffect(() => {
    if (!id) return
    setIsTimelineLoading(true)
    ordersApi
      .getOrderTimeline(id)
      .then(setTimeline)
      .catch((err) => setTimelineError(err instanceof Error ? err.message : 'Failed to load timeline'))
      .finally(() => setIsTimelineLoading(false))
  }, [id])

  async function handleDownloadInvoice() {
    if (!order?.invoice_number) return
    setDownloadError(null)
    setIsDownloading(true)
    try {
      await ordersApi.downloadInvoice(order.id, `${order.invoice_number}.pdf`)
    } catch (err) {
      setDownloadError(err instanceof ApiError ? err.message : 'Failed to download invoice')
    } finally {
      setIsDownloading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="max-w-xl">
        <Skeleton className="mb-2 h-8 w-48" />
        <Skeleton className="mb-6 h-4 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (error) return <Alert>{error}</Alert>
  if (!order) return <p className="text-gray-600">Order not found.</p>

  return (
    <div className="max-w-xl">
      <Link to="/orders" className="mb-4 inline-block text-sm text-gray-500 hover:text-gray-900">
        &larr; Back to orders
      </Link>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-gray-900">Order {order.id.slice(0, 8)}</h1>
          <p className="mt-1 text-sm text-gray-500">Placed {new Date(order.created_at).toLocaleString()}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <Badge tone={STATUS_TONE[order.status]}>{order.status}</Badge>
          {order.payment_status && (
            <Badge tone={PAYMENT_STATUS_TONE[order.payment_status] ?? 'neutral'}>
              {order.payment_status.replace(/_/g, ' ')}
            </Badge>
          )}
        </div>
      </div>
      <Card className="divide-y divide-gray-200">
        {order.items.map((item) => (
          <div key={item.id} className="flex items-center justify-between gap-4 p-4">
            <p className="text-sm text-gray-900">
              {item.product_name_snapshot} <span className="text-gray-500">&times; {item.quantity}</span>
            </p>
            <p className="text-sm font-medium text-gray-900">
              {formatMoney(item.line_total_cents, order.currency)}
            </p>
          </div>
        ))}
      </Card>
      <OrderTaxSummary order={order} />

      {(order.shipping_address || order.billing_address) && (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {order.shipping_address && (
            <div>
              <h2 className="mb-2 text-sm font-semibold text-gray-900">Shipping address</h2>
              <AddressSummary address={order.shipping_address} />
            </div>
          )}
          {order.billing_address && (
            <div>
              <h2 className="mb-2 text-sm font-semibold text-gray-900">Billing address</h2>
              <AddressSummary address={order.billing_address} />
            </div>
          )}
        </div>
      )}

      {order.invoice_number && (
        <div className="mt-6">
          <Button variant="secondary" size="sm" isLoading={isDownloading} onClick={() => void handleDownloadInvoice()}>
            Download Invoice
          </Button>
          {downloadError && (
            <div className="mt-2">
              <Alert>{downloadError}</Alert>
            </div>
          )}
        </div>
      )}

      <div className="mt-8">
        <h2 className="mb-3 text-lg font-medium text-gray-900">Timeline</h2>
        {isTimelineLoading && <Skeleton className="h-24 w-full" />}
        {timelineError && <Alert>{timelineError}</Alert>}
        {!isTimelineLoading && !timelineError && timeline.length === 0 && (
          <p className="text-sm text-gray-500">No history yet.</p>
        )}
        {!isTimelineLoading && timeline.length > 0 && (
          <Card className="divide-y divide-gray-200">
            {timeline.map((entry) => (
              <div key={entry.id} className="flex flex-col gap-1 p-4 text-sm">
                <div className="flex items-center justify-between gap-4">
                  <p className="font-medium text-gray-900">
                    {entry.from_status ? `${entry.from_status} → ${entry.to_status}` : `Order created (${entry.to_status})`}
                  </p>
                  <p className="text-gray-500">{new Date(entry.created_at).toLocaleString()}</p>
                </div>
                {entry.note && <p className="text-gray-600">{entry.note}</p>}
              </div>
            ))}
          </Card>
        )}
      </div>
    </div>
  )
}
