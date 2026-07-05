import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import * as ordersApi from '../api/orders'
import type { Order, OrderStatus } from '../api/types'
import { orderDisplayTotalCents } from '../api/types'
import { Alert, Badge, type BadgeTone, Button, Card, EmptyState, Skeleton } from '../components/ui'
import { formatMoney } from '../lib/format'

const PAGE_SIZE = 10

const STATUS_TONE: Record<OrderStatus, BadgeTone> = {
  pending: 'warning',
  paid: 'info',
  shipped: 'info',
  delivered: 'success',
  cancelled: 'danger',
}

export default function Orders() {
  const [orders, setOrders] = useState<Order[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    ordersApi
      .listOrders({ page, page_size: PAGE_SIZE })
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
  }, [page])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight text-gray-900">Order history</h1>

      {error && <Alert>{error}</Alert>}

      {isLoading && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      )}

      {!isLoading && orders.length === 0 && !error && (
        <EmptyState title="No orders yet" description="Orders you place will show up here." />
      )}

      {!isLoading && orders.length > 0 && (
        <Card className="divide-y divide-gray-200">
          {orders.map((order) => (
            <Link
              key={order.id}
              to={`/orders/${order.id}`}
              className="flex items-center justify-between gap-4 p-4 hover:bg-gray-50"
            >
              <div>
                <p className="font-medium text-gray-900">Order {order.id.slice(0, 8)}</p>
                <p className="text-sm text-gray-500">{new Date(order.created_at).toLocaleString()}</p>
              </div>
              <div className="flex flex-col items-end gap-1">
                <Badge tone={STATUS_TONE[order.status]}>{order.status}</Badge>
                <p className="text-sm text-gray-500">{formatMoney(orderDisplayTotalCents(order), order.currency)}</p>
              </div>
            </Link>
          ))}
        </Card>
      )}

      {!isLoading && orders.length > 0 && totalPages > 1 && (
        <nav aria-label="Orders pagination" className="mt-6 flex items-center justify-center gap-3">
          <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </Button>
          <span className="text-sm text-gray-600" aria-live="polite">
            Page {page} of {totalPages}
          </span>
          <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </nav>
      )}
    </div>
  )
}
