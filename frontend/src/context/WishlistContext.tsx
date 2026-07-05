import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import * as catalogApi from '../api/catalog'
import * as wishlistApi from '../api/wishlist'
import type { WishlistItem } from '../api/wishlist'
import type { Product } from '../api/types'
import { useAuth } from './AuthContext'

interface WishlistContextValue {
  items: WishlistItem[]
  /** product_id -> Product, same client-side enrichment technique as
   * CartContext.productsById (see below) — the wishlist API deliberately
   * doesn't embed product details. */
  productsById: Map<string, Product>
  isLoading: boolean
  error: string | null
  isWishlisted: (productId: string) => boolean
  toggleWishlist: (productId: string) => Promise<void>
  refreshWishlist: () => Promise<void>
}

const WishlistContext = createContext<WishlistContextValue | undefined>(undefined)

export function WishlistProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  const [items, setItems] = useState<WishlistItem[]>([])
  const [productsById, setProductsById] = useState<Map<string, Product>>(new Map())
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshWishlist = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const nextItems = await wishlistApi.listWishlist()
      setItems(nextItems)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load wishlist')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isAuthenticated) {
      void refreshWishlist()
    } else {
      setItems([])
      setProductsById(new Map())
    }
  }, [isAuthenticated, refreshWishlist])

  // Same enrichment technique as CartContext: the wishlist API only returns
  // product_id per item, so resolve (and cache) full Product records for
  // whatever's currently wishlisted. Only re-fetches products we don't
  // already have cached, and tolerates a product having been
  // deleted/deactivated since it was wishlisted (falls back to an "no
  // longer available" render rather than crashing the page).
  useEffect(() => {
    const missingIds = items.map((item) => item.product_id).filter((id) => !productsById.has(id))

    if (missingIds.length === 0) return

    let cancelled = false
    void Promise.all(
      missingIds.map(async (id) => {
        try {
          return await catalogApi.getProduct(id)
        } catch {
          return null
        }
      }),
    ).then((products) => {
      if (cancelled) return
      setProductsById((prev) => {
        const next = new Map(prev)
        for (const product of products) {
          if (product) next.set(product.id, product)
        }
        return next
      })
    })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- productsById is read, not depended on, to avoid refetch loops
  }, [items])

  const isWishlisted = useCallback(
    (productId: string) => items.some((item) => item.product_id === productId),
    [items],
  )

  // Mutation response shapes aren't trusted (same philosophy as CartContext):
  // always refetch the list after add/remove rather than optimistically
  // patching local state from the mutation's own response.
  const toggleWishlist = useCallback(
    async (productId: string) => {
      const alreadyWishlisted = items.some((item) => item.product_id === productId)
      if (alreadyWishlisted) {
        await wishlistApi.removeFromWishlist(productId)
      } else {
        await wishlistApi.addToWishlist(productId)
      }
      await refreshWishlist()
    },
    [items, refreshWishlist],
  )

  const value = useMemo<WishlistContextValue>(
    () => ({ items, productsById, isLoading, error, isWishlisted, toggleWishlist, refreshWishlist }),
    [items, productsById, isLoading, error, isWishlisted, toggleWishlist, refreshWishlist],
  )

  return <WishlistContext.Provider value={value}>{children}</WishlistContext.Provider>
}

export function useWishlist(): WishlistContextValue {
  const ctx = useContext(WishlistContext)
  if (!ctx) {
    throw new Error('useWishlist must be used within a WishlistProvider')
  }
  return ctx
}
