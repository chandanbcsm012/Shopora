import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import * as adminOrdersApi from '../../api/admin-orders'
import type { Order, OrderStatus } from '../../api/types'
import { orderDisplayTotalCents } from '../../api/types'
import { Alert, Badge, type BadgeTone, Card, EmptyState, Skeleton } from '../../components/ui'
import { usePagination } from '../../hooks/usePagination'
import { formatMoney } from '../../lib/format'

const PAGE_SIZE = 20

const STATUS_TONE: Record<OrderStatus, BadgeTone> = {
  pending: 'warning',
  paid: 'info',
  shipped: 'info',
  delivered: 'success',
  cancelled: 'danger',
}

const STATUSES: OrderStatus[] = ['pending', 'paid', 'shipped', 'delivered', 'cancelled']

/** Admin/super_admin only (route-gated in App.tsx, same tier as Users/Audit Logs). */
export default function AdminOrders() {
  const [orders, setOrders] = useState<Order[]>([])
  const [total, setTotal] = useState(0)
  const { page, setPage, totalPages, goToPrevious, goToNext } = usePagination(total, PAGE_SIZE)
  const [status, setStatus] = useState<OrderStatus | ''>('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setError(null)
    adminOrdersApi
      .listAllOrders({ page, page_size: PAGE_SIZE, status: status || undefined })
      .then((result) => {
        if (cancelled) return
        setOrders(result.items)
        setTotal(result.total)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load orders')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [page, status])

  return (
    <div>
      <div className="mb-4 flex items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5 sm:w-56">
          <label htmlFor="admin-order-status-filter" className="text-sm font-medium text-gray-700">
            Status
          </label>
          <select
            id="admin-order-status-filter"
            value={status}
            onChange={(e) => {
              setPage(1)
              setStatus(e.target.value as OrderStatus | '')
            }}
            className="h-10 rounded-md border border-gray-300 px-3 text-sm"
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {isLoading && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      )}

      {!isLoading && orders.length === 0 && !error && (
        <EmptyState title="No orders found" description="Try a different status filter." />
      )}

      {!isLoading && orders.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-3 font-medium">Order</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Payment</th>
                <th className="px-4 py-3 font-medium">Total</th>
                <th className="px-4 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {orders.map((order) => (
                <tr key={order.id}>
                  <td className="px-4 py-3">
                    <Link to={`/admin/orders/${order.id}`} className="font-medium text-brand-600 hover:underline">
                      {order.id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={STATUS_TONE[order.status]}>{order.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    {order.payment_status ? order.payment_status.replace(/_/g, ' ') : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-900">{formatMoney(orderDisplayTotalCents(order), order.currency)}</td>
                  <td className="px-4 py-3 text-gray-500">{new Date(order.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {!isLoading && orders.length > 0 && totalPages > 1 && (
        <nav aria-label="Orders pagination" className="mt-6 flex items-center justify-center gap-3">
          <button
            type="button"
            disabled={page <= 1}
            onClick={goToPrevious}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray-600" aria-live="polite">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={goToNext}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Next
          </button>
        </nav>
      )}
    </div>
  )
}
