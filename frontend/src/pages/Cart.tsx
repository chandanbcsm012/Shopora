import { Link, useNavigate } from 'react-router-dom'
import { USD_FALLBACK } from '../api/types'
import { Alert, Button, Card, EmptyState, Skeleton } from '../components/ui'
import { useCart } from '../context/CartContext'
import { formatMoney } from '../lib/format'

export default function Cart() {
  const { cart, productsById, isLoading, error, updateItem, removeItem } = useCart()
  const navigate = useNavigate()

  if (isLoading && !cart) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-semibold tracking-tight text-gray-900">Cart</h1>
        <div className="flex flex-col gap-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      </div>
    )
  }

  if (error) return <Alert>{error}</Alert>

  if (!cart || cart.items.length === 0) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-semibold tracking-tight text-gray-900">Cart</h1>
        <EmptyState
          title="Your cart is empty"
          description="Browse the catalog and add something you like."
          action={
            <Button size="sm" onClick={() => navigate('/products')}>
              Continue shopping
            </Button>
          }
        />
      </div>
    )
  }

  return (
    <div className="max-w-2xl">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight text-gray-900">Cart</h1>
      <Card className="divide-y divide-gray-200">
        {cart.items.map((item) => {
          const product = productsById.get(item.product_id)
          const name = product?.name ?? 'Product no longer available'
          const image = product?.images?.[0]
          return (
            <div key={item.id} className="flex flex-wrap items-center gap-4 p-4">
              <div className="h-16 w-16 shrink-0 overflow-hidden rounded-md bg-gray-100">
                {image ? (
                  <img src={image.url} alt="" className="h-full w-full object-cover" />
                ) : (
                  <Link to={`/products/${item.product_id}`} className="block h-full w-full" aria-hidden="true" />
                )}
              </div>
              <div className="min-w-[8rem] flex-1">
                {product ? (
                  <Link to={`/products/${item.product_id}`} className="font-medium text-gray-900 hover:text-brand-600">
                    {name}
                  </Link>
                ) : (
                  <p className="font-medium text-gray-500">{name}</p>
                )}
                <p className="text-sm text-gray-500">{formatMoney(item.unit_price_cents, USD_FALLBACK)} each</p>
              </div>
              <div className="flex items-center gap-3">
                <label htmlFor={`qty-${item.id}`} className="sr-only">
                  Quantity for {name}
                </label>
                <input
                  id={`qty-${item.id}`}
                  type="number"
                  min={1}
                  value={item.quantity}
                  onChange={(e) => void updateItem(item.id, Math.max(1, Number(e.target.value)))}
                  className="h-9 w-16 rounded-md border border-gray-300 px-2 text-sm"
                />
                <p className="w-24 text-right text-sm font-medium text-gray-900">
                  {formatMoney(item.line_total_cents, USD_FALLBACK)}
                </p>
                <Button variant="danger" size="sm" onClick={() => void removeItem(item.id)}>
                  Remove
                </Button>
              </div>
            </div>
          )
        })}
      </Card>
      <div className="mt-4 flex items-center justify-between">
        <p className="text-lg font-medium text-gray-900">
          Total: {formatMoney(cart.subtotal_cents, USD_FALLBACK)}
        </p>
        <Button onClick={() => navigate('/checkout')}>Checkout</Button>
      </div>
    </div>
  )
}
