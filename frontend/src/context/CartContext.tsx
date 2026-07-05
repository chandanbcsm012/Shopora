import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import * as catalogApi from '../api/catalog'
import * as ordersApi from '../api/orders'
import type { Cart, Product } from '../api/types'
import { useAuth } from './AuthContext'

interface CartContextValue {
  cart: Cart | null
  /** product_id -> Product, for rendering cart/checkout line items with a
   * real name/image instead of a raw product_id (see productsById note
   * below). Absent entries just mean "still loading" or "product was
   * deleted since"; callers should fall back gracefully either way. */
  productsById: Map<string, Product>
  itemCount: number
  isLoading: boolean
  error: string | null
  addItem: (productId: string, quantity: number) => Promise<void>
  updateItem: (itemId: string, quantity: number) => Promise<void>
  removeItem: (itemId: string) => Promise<void>
  refreshCart: () => Promise<void>
}

const CartContext = createContext<CartContextValue | undefined>(undefined)

export function CartProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  const [cart, setCart] = useState<Cart | null>(null)
  const [productsById, setProductsById] = useState<Map<string, Product>>(new Map())
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshCart = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const nextCart = await ordersApi.getCart()
      setCart(nextCart)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cart')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isAuthenticated) {
      void refreshCart()
    } else {
      setCart(null)
      setProductsById(new Map())
    }
  }, [isAuthenticated, refreshCart])

  // The cart API (see docs/CONTRACTS.md / app/modules/orders/schemas.py)
  // deliberately returns only `product_id` per line item, not a name or
  // image — orders snapshot a name at checkout time, but a live cart
  // shouldn't snapshot anything since price/availability can still change.
  // So the UI resolves display data itself: fetch (and cache) full Product
  // records for whatever's currently in the cart. This only re-fetches
  // products we don't already have cached, and tolerates a product having
  // been deleted/deactivated since it was added (falls back to showing the
  // bare id rather than crashing the page).
  useEffect(() => {
    const missingIds = (cart?.items ?? [])
      .map((item) => item.product_id)
      .filter((id) => !productsById.has(id))

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
  }, [cart])

  const addItem = useCallback(
    async (productId: string, quantity: number) => {
      await ordersApi.addCartItem({ product_id: productId, quantity })
      await refreshCart()
    },
    [refreshCart],
  )

  const updateItem = useCallback(
    async (itemId: string, quantity: number) => {
      await ordersApi.updateCartItem(itemId, { quantity })
      await refreshCart()
    },
    [refreshCart],
  )

  const removeItem = useCallback(
    async (itemId: string) => {
      await ordersApi.removeCartItem(itemId)
      await refreshCart()
    },
    [refreshCart],
  )

  const itemCount = useMemo(() => cart?.items.reduce((sum, item) => sum + item.quantity, 0) ?? 0, [cart])

  const value = useMemo<CartContextValue>(
    () => ({ cart, productsById, itemCount, isLoading, error, addItem, updateItem, removeItem, refreshCart }),
    [cart, productsById, itemCount, isLoading, error, addItem, updateItem, removeItem, refreshCart],
  )

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext)
  if (!ctx) {
    throw new Error('useCart must be used within a CartProvider')
  }
  return ctx
}
