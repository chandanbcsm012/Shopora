import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import * as catalogApi from '../api/catalog'
import type { Product } from '../api/types'
import { Alert, Badge, Button, Skeleton } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'
import { useWishlist } from '../context/WishlistContext'
import { cn } from '../lib/cn'
import { formatMoney } from '../lib/format'

function stockBadge(quantity: number) {
  if (quantity < 1) return <Badge tone="danger">Out of stock</Badge>
  if (quantity <= 5) return <Badge tone="warning">Only {quantity} left</Badge>
  return <Badge tone="success">In stock</Badge>
}

export default function ProductDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const { addItem } = useCart()
  const { isWishlisted, toggleWishlist } = useWishlist()
  const [product, setProduct] = useState<Product | null>(null)
  const [quantity, setQuantity] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [addStatus, setAddStatus] = useState<'idle' | 'adding' | 'added'>('idle')
  const [activeImageIndex, setActiveImageIndex] = useState(0)
  const [isTogglingWishlist, setIsTogglingWishlist] = useState(false)

  useEffect(() => {
    if (!id) return
    setIsLoading(true)
    setError(null)
    catalogApi
      .getProduct(id)
      .then((p) => {
        setProduct(p)
        setActiveImageIndex(0)
        setQuantity(1)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load product'))
      .finally(() => setIsLoading(false))
  }, [id])

  async function handleAddToCart() {
    if (!product) return
    if (!isAuthenticated) {
      navigate('/login', { state: { from: `/products/${product.id}` } })
      return
    }
    setAddStatus('adding')
    try {
      await addItem(product.id, quantity)
      setAddStatus('added')
      setTimeout(() => setAddStatus('idle'), 1500)
    } catch {
      setAddStatus('idle')
    }
  }

  async function handleToggleWishlist() {
    if (!product) return
    if (!isAuthenticated) {
      navigate('/login', { state: { from: `/products/${product.id}` } })
      return
    }
    setIsTogglingWishlist(true)
    try {
      await toggleWishlist(product.id)
    } finally {
      setIsTogglingWishlist(false)
    }
  }

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
        <Skeleton className="aspect-square w-full" />
        <div className="flex flex-col gap-3">
          <Skeleton className="h-8 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-6 w-1/4" />
          <Skeleton className="mt-4 h-10 w-40" />
        </div>
      </div>
    )
  }

  if (error) return <Alert>{error}</Alert>
  if (!product) return <p className="text-gray-600">Product not found.</p>

  const images = [...(product.images ?? [])].sort((a, b) => a.sort_order - b.sort_order)
  const activeImage = images[activeImageIndex] ?? images[0]
  const outOfStock = product.stock_quantity < 1
  const wishlisted = isWishlisted(product.id)

  return (
    <div>
      <Link to="/products" className="mb-6 inline-block text-sm text-gray-500 hover:text-gray-900">
        &larr; Back to products
      </Link>

      <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
        <div>
          {images.length > 0 ? (
            <div>
              <div className="aspect-square w-full overflow-hidden rounded-lg bg-gray-100">
                <img
                  src={activeImage.url}
                  alt={activeImage.alt_text ?? product.name}
                  className="h-full w-full object-cover"
                />
              </div>
              {images.length > 1 && (
                <div className="mt-2 flex gap-2">
                  {images.map((image, index) => (
                    <button
                      key={image.id}
                      type="button"
                      aria-label={`View image ${index + 1} of ${images.length}`}
                      aria-pressed={index === activeImageIndex}
                      onClick={() => setActiveImageIndex(index)}
                      className={cn(
                        'h-16 w-16 overflow-hidden rounded-md border-2',
                        index === activeImageIndex ? 'border-brand-600' : 'border-transparent',
                      )}
                    >
                      <img src={image.url} alt="" className="h-full w-full object-cover" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="flex aspect-square w-full items-center justify-center rounded-lg bg-gray-100 text-sm text-gray-400">
              No image
            </div>
          )}
        </div>

        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-gray-900">{product.name}</h1>
          <p className="mt-2 text-sm text-gray-500">SKU {product.sku}</p>
          <p className="mt-4 text-2xl font-semibold text-gray-900">
            {formatMoney(product.price_cents, product.currency)}
          </p>
          <div className="mt-2">{stockBadge(product.stock_quantity)}</div>

          {product.description && <p className="mt-4 text-sm leading-relaxed text-gray-600">{product.description}</p>}

          <div className="mt-6 flex items-center gap-4">
            <div className="flex items-center rounded-md border border-gray-300">
              <button
                type="button"
                disabled={quantity <= 1}
                onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                aria-label="Decrease quantity"
                className="flex h-10 w-9 items-center justify-center text-gray-600 hover:bg-gray-50 disabled:opacity-40"
              >
                &minus;
              </button>
              <label htmlFor="quantity" className="sr-only">
                Quantity
              </label>
              <input
                id="quantity"
                type="number"
                min={1}
                max={Math.max(1, product.stock_quantity)}
                value={quantity}
                onChange={(e) =>
                  setQuantity(Math.min(Math.max(1, Number(e.target.value)), Math.max(1, product.stock_quantity)))
                }
                className="h-10 w-12 border-x border-gray-300 text-center text-sm [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              />
              <button
                type="button"
                disabled={quantity >= product.stock_quantity}
                onClick={() => setQuantity((q) => Math.min(product.stock_quantity, q + 1))}
                aria-label="Increase quantity"
                className="flex h-10 w-9 items-center justify-center text-gray-600 hover:bg-gray-50 disabled:opacity-40"
              >
                +
              </button>
            </div>
            <Button
              disabled={outOfStock}
              isLoading={addStatus === 'adding'}
              onClick={() => void handleAddToCart()}
              className="flex-1"
            >
              {addStatus === 'added' ? 'Added ✓' : outOfStock ? 'Out of stock' : 'Add to cart'}
            </Button>
          </div>

          <Button
            type="button"
            variant="secondary"
            aria-pressed={wishlisted}
            isLoading={isTogglingWishlist}
            onClick={() => void handleToggleWishlist()}
            className="mt-3 w-full sm:w-auto"
          >
            {wishlisted ? 'Remove from wishlist' : 'Save to wishlist'}
          </Button>
        </div>
      </div>
    </div>
  )
}
