import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Alert, Badge, Button, Card, EmptyState, Skeleton } from '../components/ui'
import { useCart } from '../context/CartContext'
import { useWishlist } from '../context/WishlistContext'
import { formatMoney } from '../lib/format'

function stockBadge(quantity: number) {
  if (quantity < 1) return <Badge tone="danger">Out of stock</Badge>
  if (quantity <= 5) return <Badge tone="warning">Only {quantity} left</Badge>
  return <Badge tone="success">In stock</Badge>
}

export default function Wishlist() {
  const { items, productsById, isLoading, error, toggleWishlist } = useWishlist()
  const { addItem } = useCart()
  const [removingProductId, setRemovingProductId] = useState<string | null>(null)
  const [addStatusByProduct, setAddStatusByProduct] = useState<Record<string, 'adding' | 'added'>>({})

  async function handleRemove(productId: string) {
    setRemovingProductId(productId)
    try {
      await toggleWishlist(productId)
    } finally {
      setRemovingProductId(null)
    }
  }

  async function handleAddToCart(productId: string) {
    setAddStatusByProduct((prev) => ({ ...prev, [productId]: 'adding' }))
    try {
      await addItem(productId, 1)
      setAddStatusByProduct((prev) => ({ ...prev, [productId]: 'added' }))
      setTimeout(() => {
        setAddStatusByProduct((prev) => {
          const { [productId]: _removed, ...rest } = prev
          return rest
        })
      }, 1500)
    } catch {
      setAddStatusByProduct((prev) => {
        const { [productId]: _removed, ...rest } = prev
        return rest
      })
    }
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight text-gray-900">Your wishlist</h1>

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {isLoading && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      )}

      {!isLoading && items.length === 0 && !error && (
        <EmptyState
          title="Your wishlist is empty"
          description="Save products you love to find them here later."
          action={
            <Link to="/products">
              <Button size="sm">Browse products</Button>
            </Link>
          }
        />
      )}

      {!isLoading && items.length > 0 && (
        <Card className="divide-y divide-gray-200">
          {items.map((item) => {
            const product = productsById.get(item.product_id)
            const image =
              product?.images && product.images.length > 0
                ? [...product.images].sort((a, b) => a.sort_order - b.sort_order)[0]
                : undefined
            const addStatus = addStatusByProduct[item.product_id]
            const outOfStock = (product?.stock_quantity ?? 0) < 1

            return (
              <div key={item.id} className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center">
                <Link
                  to={product ? `/products/${product.id}` : '#'}
                  className="h-20 w-20 shrink-0 overflow-hidden rounded-md bg-gray-100"
                >
                  {image ? (
                    <img
                      src={image.url}
                      alt={image.alt_text ?? product?.name ?? ''}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-xs text-gray-400">
                      No image
                    </div>
                  )}
                </Link>
                <div className="min-w-0 flex-1">
                  {product ? (
                    <>
                      <Link to={`/products/${product.id}`} className="font-medium text-gray-900 hover:text-brand-600">
                        {product.name}
                      </Link>
                      <p className="mt-1 text-sm font-medium text-gray-900">
                        {formatMoney(product.price_cents, product.currency)}
                      </p>
                      <div className="mt-1.5">{stockBadge(product.stock_quantity)}</div>
                    </>
                  ) : (
                    <p className="text-sm text-gray-500">This product is no longer available.</p>
                  )}
                </div>
                <div className="flex shrink-0 gap-2">
                  {product && (
                    <Button
                      size="sm"
                      variant={addStatus === 'added' ? 'secondary' : 'primary'}
                      disabled={outOfStock}
                      isLoading={addStatus === 'adding'}
                      onClick={() => void handleAddToCart(product.id)}
                    >
                      {addStatus === 'added' ? 'Added ✓' : outOfStock ? 'Out of stock' : 'Add to cart'}
                    </Button>
                  )}
                  <Button
                    variant="danger"
                    size="sm"
                    isLoading={removingProductId === item.product_id}
                    onClick={() => void handleRemove(item.product_id)}
                  >
                    Remove
                  </Button>
                </div>
              </div>
            )
          })}
        </Card>
      )}
    </div>
  )
}
