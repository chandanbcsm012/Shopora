import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import * as adminOrdersApi from '../../api/admin-orders'
import { ApiError } from '../../api/client'
import * as ordersApi from '../../api/orders'
import type { Order, OrderStatus, OrderStatusHistory } from '../../api/types'
import { Alert, Badge, type BadgeTone, Button, Card, ConfirmDialog, Input, Skeleton } from '../../components/ui'
import { OrderTaxSummary } from '../../components/OrderTaxSummary'
import { formatMoney } from '../../lib/format'
import { AddressSummary } from '../Addresses'

const STATUS_TONE: Record<OrderStatus, BadgeTone> = {
  pending: 'warning',
  paid: 'info',
  shipped: 'info',
  delivered: 'success',
  cancelled: 'danger',
}

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

const STATUSES: OrderStatus[] = ['pending', 'paid', 'shipped', 'delivered', 'cancelled']

/** Admin/super_admin only. Full order info (items, both addresses, payment
 * status), a status-change control, a refund action, the timeline, and
 * invoice download -- the admin counterpart of the customer-facing
 * OrderDetail.tsx, following ProductForm.tsx/Categories.tsx's layout
 * conventions for this admin panel. */
export default function AdminOrderDetail() {
  const { id } = useParams<{ id: string }>()
  const [order, setOrder] = useState<Order | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [timeline, setTimeline] = useState<OrderStatusHistory[]>([])
  const [isTimelineLoading, setIsTimelineLoading] = useState(true)
  const [timelineError, setTimelineError] = useState<string | null>(null)

  const [nextStatus, setNextStatus] = useState<OrderStatus | ''>('')
  const [statusNote, setStatusNote] = useState('')
  const [isStatusConfirmOpen, setIsStatusConfirmOpen] = useState(false)
  const [isChangingStatus, setIsChangingStatus] = useState(false)
  const [statusError, setStatusError] = useState<string | null>(null)

  const [refundAmountDollars, setRefundAmountDollars] = useState('')
  const [isRefundConfirmOpen, setIsRefundConfirmOpen] = useState(false)
  const [isRefunding, setIsRefunding] = useState(false)
  const [refundError, setRefundError] = useState<string | null>(null)

  const [isDownloading, setIsDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  function loadOrder() {
    if (!id) return undefined
    setIsLoading(true)
    setError(null)
    return ordersApi
      .getOrder(id)
      .then((result) => {
        setOrder(result)
        setNextStatus(result.status)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load order'))
      .finally(() => setIsLoading(false))
  }

  function loadTimeline() {
    if (!id) return undefined
    setIsTimelineLoading(true)
    setTimelineError(null)
    return ordersApi
      .getOrderTimeline(id)
      .then(setTimeline)
      .catch((err) => setTimelineError(err instanceof Error ? err.message : 'Failed to load timeline'))
      .finally(() => setIsTimelineLoading(false))
  }

  useEffect(() => {
    void loadOrder()
    void loadTimeline()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadOrder/loadTimeline read `id` directly, not worth memoizing
  }, [id])

  async function handleConfirmStatusChange() {
    if (!id || !nextStatus) return
    setIsChangingStatus(true)
    setStatusError(null)
    try {
      const updated = await adminOrdersApi.updateOrderStatus(id, { status: nextStatus, note: statusNote.trim() || undefined })
      setOrder(updated)
      setStatusNote('')
      setIsStatusConfirmOpen(false)
      await loadTimeline()
    } catch (err) {
      setStatusError(err instanceof ApiError ? err.message : 'Failed to update status')
    } finally {
      setIsChangingStatus(false)
    }
  }

  async function handleConfirmRefund() {
    if (!id) return
    setIsRefunding(true)
    setRefundError(null)
    try {
      const trimmed = refundAmountDollars.trim()
      const payload = trimmed ? { amount_cents: Math.round(Number(trimmed) * 100) } : {}
      const updated = await adminOrdersApi.refundOrder(id, payload)
      setOrder(updated)
      setRefundAmountDollars('')
      setIsRefundConfirmOpen(false)
    } catch (err) {
      setRefundError(err instanceof ApiError ? err.message : 'Failed to process refund')
    } finally {
      setIsRefunding(false)
    }
  }

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
      <div className="max-w-2xl">
        <Skeleton className="mb-2 h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (error) return <Alert>{error}</Alert>
  if (!order) return <p className="text-gray-600">Order not found.</p>

  const isRefundable = order.payment_status === 'captured' || order.payment_status === 'partially_refunded'

  return (
    <div className="max-w-2xl">
      <Link to="/admin/orders" className="mb-4 inline-block text-sm text-gray-500 hover:text-gray-900">
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

      <Card className="mb-6 divide-y divide-gray-200">
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
      <div className="mb-6">
        <OrderTaxSummary order={order} />
      </div>

      {(order.shipping_address || order.billing_address) && (
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
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

      <div className="mb-8 flex flex-wrap items-end gap-3">
        {order.invoice_number && (
          <Button variant="secondary" size="sm" isLoading={isDownloading} onClick={() => void handleDownloadInvoice()}>
            Download Invoice
          </Button>
        )}
        {isRefundable && (
          <>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="refund-amount" className="text-sm font-medium text-gray-700">
                Refund amount (optional)
              </label>
              <input
                id="refund-amount"
                type="number"
                min="0"
                step="0.01"
                placeholder="Full remaining amount"
                value={refundAmountDollars}
                onChange={(e) => setRefundAmountDollars(e.target.value)}
                className="h-10 w-44 rounded-md border border-gray-300 px-3 text-sm"
              />
            </div>
            <Button variant="danger" size="sm" onClick={() => setIsRefundConfirmOpen(true)}>
              Refund payment
            </Button>
          </>
        )}
      </div>
      {downloadError && (
        <div className="mb-6">
          <Alert>{downloadError}</Alert>
        </div>
      )}

      <Card className="mb-8 p-4">
        <h2 className="mb-3 text-sm font-semibold text-gray-900">Change order status</h2>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex flex-col gap-1.5 sm:w-48">
            <label htmlFor="admin-order-status" className="text-sm font-medium text-gray-700">
              Status
            </label>
            <select
              id="admin-order-status"
              value={nextStatus}
              onChange={(e) => setNextStatus(e.target.value as OrderStatus)}
              className="h-10 rounded-md border border-gray-300 px-3 text-sm"
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <Input label="Note (optional)" value={statusNote} onChange={(e) => setStatusNote(e.target.value)} />
          </div>
          <Button size="sm" disabled={nextStatus === order.status} onClick={() => setIsStatusConfirmOpen(true)}>
            Update status
          </Button>
        </div>
      </Card>

      <div>
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

      <ConfirmDialog
        open={isStatusConfirmOpen}
        title={`Change status to "${nextStatus}"?`}
        description={
          statusError ?? `Order ${order.id.slice(0, 8)}'s status will change from "${order.status}" to "${nextStatus}".`
        }
        confirmLabel="Update status"
        isConfirming={isChangingStatus}
        onConfirm={() => void handleConfirmStatusChange()}
        onCancel={() => {
          setIsStatusConfirmOpen(false)
          setStatusError(null)
        }}
      />

      <ConfirmDialog
        open={isRefundConfirmOpen}
        title="Refund this payment?"
        description={
          refundError ??
          (refundAmountDollars.trim()
            ? `Refund ${formatMoney(Math.round(Number(refundAmountDollars) * 100), order.currency)} for this order?`
            : 'Leave the amount blank to fully refund the remaining captured amount.')
        }
        confirmLabel="Refund"
        isDestructive
        isConfirming={isRefunding}
        onConfirm={() => void handleConfirmRefund()}
        onCancel={() => {
          setIsRefundConfirmOpen(false)
          setRefundError(null)
        }}
      />
    </div>
  )
}
