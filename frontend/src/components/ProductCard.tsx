import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { Product } from '../api/types'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'
import { useWishlist } from '../context/WishlistContext'
import { cn } from '../lib/cn'
import { formatMoney } from '../lib/format'
import { Badge, Button, Card, Skeleton } from './ui'

function primaryImage(product: Product) {
  if (!product.images || product.images.length === 0) return undefined
  return [...product.images].sort((a, b) => a.sort_order - b.sort_order)[0]
}

function stockBadge(quantity: number) {
  if (quantity < 1) return <Badge tone="danger">Out of stock</Badge>
  if (quantity <= 5) return <Badge tone="warning">Only {quantity} left</Badge>
  return <Badge tone="success">In stock</Badge>
}

/** Loading placeholder matching ProductCard's layout, for grid loading states. */
export function ProductCardSkeleton() {
  return (
    <Card className="flex flex-col p-4">
      <Skeleton className="mb-3 aspect-square w-full" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="mt-2 h-4 w-1/3" />
      <Skeleton className="mt-3 h-9 w-full" />
    </Card>
  )
}

/**
 * The single product-card visual treatment for the storefront — shared by
 * ProductList.tsx's grid and Home.tsx's "New Arrivals" rail so the two never
 * drift apart. Consumes CartContext/WishlistContext directly rather than
 * taking handlers as props: every caller wants the exact same add-to-cart /
 * wishlist-toggle behavior, so prop-drilling would just be boilerplate
 * repeated at each call site.
 */
export function ProductCard({ product }: { product: Product }) {
  const { isAuthenticated } = useAuth()
  const { addItem } = useCart()
  const { isWishlisted, toggleWishlist } = useWishlist()
  const [addStatus, setAddStatus] = useState<'idle' | 'adding' | 'added'>('idle')
  const [isTogglingWishlist, setIsTogglingWishlist] = useState(false)

  const image = primaryImage(product)
  const outOfStock = product.stock_quantity < 1
  const wishlisted = isWishlisted(product.id)

  async function handleAddToCart() {
    setAddStatus('adding')
    try {
      await addItem(product.id, 1)
      setAddStatus('added')
      setTimeout(() => setAddStatus('idle'), 1500)
    } catch {
      setAddStatus('idle')
    }
  }

  async function handleToggleWishlist() {
    setIsTogglingWishlist(true)
    try {
      await toggleWishlist(product.id)
    } finally {
      setIsTogglingWishlist(false)
    }
  }

  return (
    <Card className="relative flex h-full flex-col p-4">
      <button
        type="button"
        aria-label={wishlisted ? `Remove ${product.name} from wishlist` : `Add ${product.name} to wishlist`}
        aria-pressed={wishlisted}
        disabled={!isAuthenticated || isTogglingWishlist}
        onClick={() => void handleToggleWishlist()}
        className="absolute right-6 top-6 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-white text-gray-400 shadow-card hover:text-danger-600 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <HeartIcon filled={wishlisted} />
      </button>
      <Link
        to={`/products/${product.id}`}
        className="mb-3 block aspect-square overflow-hidden rounded-md bg-gray-100"
      >
        {image ? (
          <img
            src={image.url}
            alt={image.alt_text ?? product.name}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-gray-400">No image</div>
        )}
      </Link>
      <Link
        to={`/products/${product.id}`}
        className="line-clamp-2 pr-6 font-medium text-gray-900 hover:text-brand-600"
      >
        {product.name}
      </Link>
      <p className="mt-1 text-sm font-medium text-gray-900">{formatMoney(product.price_cents, product.currency)}</p>
      <div className="mt-1.5">{stockBadge(product.stock_quantity)}</div>
      <Button
        size="sm"
        variant={addStatus === 'added' ? 'secondary' : 'primary'}
        disabled={!isAuthenticated || outOfStock}
        isLoading={addStatus === 'adding'}
        onClick={() => void handleAddToCart()}
        className="mt-3 w-full"
      >
        {addStatus === 'added' ? 'Added ✓' : outOfStock ? 'Out of stock' : 'Add to cart'}
      </Button>
    </Card>
  )
}

function HeartIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill={filled ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth={1.75}
      className={cn('h-4 w-4', filled && 'text-danger-600')}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 20.25c-.318 0-.636-.083-.919-.248C6.783 17.503 3 14.09 3 9.94 3 7.203 5.172 5 7.875 5c1.564 0 2.958.752 3.858 1.92a.32.32 0 0 0 .534 0C13.167 5.752 14.561 5 16.125 5 18.828 5 21 7.203 21 9.94c0 4.15-3.783 7.563-8.081 10.062-.283.165-.601.248-.919.248Z"
      />
    </svg>
  )
}
