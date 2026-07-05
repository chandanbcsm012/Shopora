import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import * as addressesApi from '../api/addresses'
import { ApiError } from '../api/client'
import * as ordersApi from '../api/orders'
import type { Address, PaymentMethod } from '../api/types'
import { USD_FALLBACK } from '../api/types'
import { Alert, Badge, Button, Card, EmptyState, Skeleton } from '../components/ui'
import { useCart } from '../context/CartContext'
import { formatMoney } from '../lib/format'
import { cn } from '../lib/cn'
import { EMPTY_ADDRESS_FORM, formValuesToPayload, type AddressFormValues } from '../lib/addressForm'
import { AddressForm, AddressSummary } from './Addresses'

/**
 * Rewritten per docs/CONTRACTS.md's "Checkout, Addresses, Payments &
 * Invoices" section: a single page with clear sections (address, payment,
 * review) rather than a routed multi-step wizard, matching this app's
 * existing preference for simple, un-nested flows. Address selection reuses
 * `AddressForm`/`AddressSummary` from Addresses.tsx instead of duplicating
 * the ~13 form fields.
 */
export default function Checkout() {
  const { cart, productsById, refreshCart } = useCart()
  const navigate = useNavigate()

  const [addresses, setAddresses] = useState<Address[]>([])
  const [isLoadingAddresses, setIsLoadingAddresses] = useState(true)
  const [addressesError, setAddressesError] = useState<string | null>(null)

  const [shippingId, setShippingId] = useState<string | null>(null)
  const [billingSameAsShipping, setBillingSameAsShipping] = useState(true)
  const [billingId, setBillingId] = useState<string | null>(null)

  const [isAddressFormOpen, setIsAddressFormOpen] = useState(false)
  const [addressFormValues, setAddressFormValues] = useState<AddressFormValues>(EMPTY_ADDRESS_FORM)
  const [isSavingAddress, setIsSavingAddress] = useState(false)
  const [addressFormError, setAddressFormError] = useState<string | null>(null)

  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod | null>(null)
  const [testCardOutcome, setTestCardOutcome] = useState<'succeed' | 'decline'>('succeed')

  const [submitError, setSubmitError] = useState<string | null>(null)
  const [cartWasCleared, setCartWasCleared] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    setIsLoadingAddresses(true)
    setAddressesError(null)
    addressesApi
      .listAddresses()
      .then((result) => {
        if (cancelled) return
        setAddresses(result)
        const defaultShipping = result.find((a) => a.is_default_shipping) ?? result[0]
        if (defaultShipping) setShippingId(defaultShipping.id)
        const defaultBilling = result.find((a) => a.is_default_billing)
        if (defaultBilling) setBillingId(defaultBilling.id)
        if (result.length === 0) setIsAddressFormOpen(true)
      })
      .catch((err) => {
        if (!cancelled) setAddressesError(err instanceof Error ? err.message : 'Failed to load addresses')
      })
      .finally(() => {
        if (!cancelled) setIsLoadingAddresses(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  function openAddAddressForm() {
    setAddressFormValues(EMPTY_ADDRESS_FORM)
    setAddressFormError(null)
    setIsAddressFormOpen(true)
  }

  async function handleAddressSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAddressFormError(null)
    setIsSavingAddress(true)
    try {
      const created = await addressesApi.createAddress(formValuesToPayload(addressFormValues))
      setAddresses((prev) => [...prev, created])
      setShippingId(created.id)
      if (billingSameAsShipping) setBillingId(created.id)
      setIsAddressFormOpen(false)
    } catch (err) {
      setAddressFormError(err instanceof ApiError ? err.message : 'Failed to save address')
    } finally {
      setIsSavingAddress(false)
    }
  }

  async function handlePlaceOrder() {
    if (!shippingId || !paymentMethod) return
    const resolvedBillingId = billingSameAsShipping ? shippingId : billingId
    if (!resolvedBillingId) return

    setSubmitError(null)
    setCartWasCleared(false)
    setIsSubmitting(true)
    try {
      const order = await ordersApi.checkout({
        shipping_address_id: shippingId,
        billing_address_id: resolvedBillingId,
        payment_method: paymentMethod,
        ...(paymentMethod === 'test_card' ? { test_card_outcome: testCardOutcome } : {}),
      })
      await refreshCart()
      navigate(`/orders/${order.id}`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) {
        // Per CONTRACTS.md: checkout empties the cart as part of Order
        // creation regardless of payment outcome, since the (cancelled)
        // Order row is created either way -- so a 402 here means the cart is
        // already gone server-side, not just that this request failed.
        setSubmitError(err.message)
        setCartWasCleared(true)
        await refreshCart()
      } else {
        setSubmitError(err instanceof ApiError ? err.message : 'Checkout failed. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!cart || cart.items.length === 0) {
    return (
      <EmptyState
        title="Your cart is empty"
        description="Add items to your cart before checking out."
        action={
          <Button size="sm" onClick={() => navigate('/products')}>
            Browse products
          </Button>
        }
      />
    )
  }

  const canSubmit =
    Boolean(shippingId) && Boolean(paymentMethod) && (billingSameAsShipping || Boolean(billingId)) && !isSubmitting

  return (
    <div className="max-w-2xl">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight text-gray-900">Checkout</h1>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium text-gray-900">Shipping address</h2>

        {isLoadingAddresses && <Skeleton className="h-24 w-full" />}
        {addressesError && <Alert>{addressesError}</Alert>}

        {!isLoadingAddresses && !addressesError && (
          <>
            {addresses.length > 0 && (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {addresses.map((address) => (
                  <SelectableCard key={address.id} selected={shippingId === address.id} onSelect={() => setShippingId(address.id)}>
                    <AddressSummary address={address} />
                  </SelectableCard>
                ))}
              </div>
            )}

            {!isAddressFormOpen && (
              <Button variant="secondary" size="sm" className="mt-3" onClick={openAddAddressForm}>
                Add new address
              </Button>
            )}

            {isAddressFormOpen && (
              <Card className="mt-4 p-4">
                <h3 className="mb-4 text-sm font-semibold text-gray-900">New address</h3>
                <AddressForm
                  values={addressFormValues}
                  onChange={setAddressFormValues}
                  onSubmit={handleAddressSubmit}
                  onCancel={() => setIsAddressFormOpen(false)}
                  isSaving={isSavingAddress}
                  error={addressFormError}
                  submitLabel="Save address"
                />
              </Card>
            )}
          </>
        )}

        {addresses.length > 0 && (
          <div className="mt-5">
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
              <input
                type="checkbox"
                checked={billingSameAsShipping}
                onChange={(e) => setBillingSameAsShipping(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300"
              />
              Billing address same as shipping
            </label>

            {!billingSameAsShipping && (
              <div className="mt-3">
                <h3 className="mb-3 text-sm font-medium text-gray-700">Billing address</h3>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {addresses.map((address) => (
                    <SelectableCard key={address.id} selected={billingId === address.id} onSelect={() => setBillingId(address.id)}>
                      <AddressSummary address={address} />
                    </SelectableCard>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium text-gray-900">Payment method</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <SelectableCard selected={paymentMethod === 'cod'} onSelect={() => setPaymentMethod('cod')}>
            <p className="font-medium text-gray-900">Cash on Delivery</p>
            <p className="text-gray-500">Pay in cash when your order arrives.</p>
          </SelectableCard>
          <SelectableCard selected={paymentMethod === 'test_card'} onSelect={() => setPaymentMethod('test_card')}>
            <p className="font-medium text-gray-900">Test Card (demo)</p>
            <p className="text-gray-500">Simulated card payment for demo purposes only.</p>
          </SelectableCard>
        </div>

        {paymentMethod === 'test_card' && (
          <div className="mt-4 rounded-md border border-dashed border-gray-300 p-4">
            <p className="mb-3 text-sm font-medium text-gray-700">
              Demo control &mdash; no real card is collected or charged
            </p>
            <div className="flex gap-6">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="radio"
                  name="test-card-outcome"
                  checked={testCardOutcome === 'succeed'}
                  onChange={() => setTestCardOutcome('succeed')}
                  className="h-4 w-4"
                />
                Simulate: Succeed
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="radio"
                  name="test-card-outcome"
                  checked={testCardOutcome === 'decline'}
                  onChange={() => setTestCardOutcome('decline')}
                  className="h-4 w-4"
                />
                Simulate: Decline
              </label>
            </div>
          </div>
        )}
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium text-gray-900">Review order</h2>
        <Card className="divide-y divide-gray-200">
          {cart.items.map((item) => {
            const name = productsById.get(item.product_id)?.name ?? 'Product no longer available'
            return (
              <div key={item.id} className="flex items-center justify-between gap-4 p-4">
                <p className="text-sm text-gray-900">
                  {name} <span className="text-gray-500">&times; {item.quantity}</span>
                </p>
                <p className="text-sm font-medium text-gray-900">
                  {formatMoney(item.line_total_cents, USD_FALLBACK)}
                </p>
              </div>
            )
          })}
        </Card>
        <p className="mt-4 text-lg font-medium text-gray-900">
          Total: {formatMoney(cart.subtotal_cents, USD_FALLBACK)}
        </p>
      </section>

      {submitError && (
        <div className="mb-4">
          <Alert>
            <p>{submitError}</p>
            {cartWasCleared && (
              <p className="mt-1">Your cart has been cleared; please add items again to retry.</p>
            )}
          </Alert>
        </div>
      )}

      <Button isLoading={isSubmitting} disabled={!canSubmit} onClick={() => void handlePlaceOrder()} className="w-full sm:w-auto">
        {isSubmitting ? 'Placing order…' : 'Place order'}
      </Button>
    </div>
  )
}

function SelectableCard({
  selected,
  onSelect,
  children,
}: {
  selected: boolean
  onSelect: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        'flex flex-col gap-1 rounded-lg border p-4 text-left text-sm transition-colors',
        selected ? 'border-brand-600 ring-1 ring-brand-600' : 'border-gray-200 hover:border-gray-300',
      )}
    >
      {selected && (
        <div className="mb-1">
          <Badge tone="info">Selected</Badge>
        </div>
      )}
      {children}
    </button>
  )
}
