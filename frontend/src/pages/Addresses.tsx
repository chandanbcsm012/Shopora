import { useEffect, useState, type FormEvent } from 'react'
import * as addressesApi from '../api/addresses'
import { ApiError } from '../api/client'
import type { Address, AddressType } from '../api/types'
import { Alert, Badge, Button, Card, ConfirmDialog, EmptyState, Input, Skeleton } from '../components/ui'
import { EMPTY_ADDRESS_FORM, addressToFormValues, formValuesToPayload, type AddressFormValues } from '../lib/addressForm'

const ADDRESS_TYPE_OPTIONS: { value: AddressType; label: string }[] = [
  { value: 'home', label: 'Home' },
  { value: 'office', label: 'Office' },
  { value: 'warehouse', label: 'Warehouse' },
  { value: 'other', label: 'Other' },
]

/**
 * The full Address field set (everything except id/timestamps/user_id) as a
 * controlled form. Shared by the Address Book page (create/edit) and
 * Checkout's inline "add a new address" flow, per CONTRACTS.md's frontend
 * note that Checkout should "reuse the address form from the Address Book
 * page rather than duplicating it" -- duplicating these ~13 fields twice
 * would be the kind of drift this app's shared `ui/*` components already
 * avoid for buttons/inputs/cards.
 */
export function AddressForm({
  values,
  onChange,
  onSubmit,
  onCancel,
  isSaving,
  error,
  submitLabel,
}: {
  values: AddressFormValues
  onChange: (values: AddressFormValues) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onCancel: () => void
  isSaving: boolean
  error: string | null
  submitLabel: string
}) {
  function set<K extends keyof AddressFormValues>(key: K, value: AddressFormValues[K]) {
    onChange({ ...values, [key]: value })
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Input label="Full name" required value={values.full_name} onChange={(e) => set('full_name', e.target.value)} />
        <Input label="Phone" required value={values.phone} onChange={(e) => set('phone', e.target.value)} />
        <Input
          label="Alternate phone (optional)"
          value={values.alternate_phone}
          onChange={(e) => set('alternate_phone', e.target.value)}
        />
        <Input label="Company (optional)" value={values.company} onChange={(e) => set('company', e.target.value)} />
      </div>

      <Input
        label="Address line 1"
        required
        value={values.address_line1}
        onChange={(e) => set('address_line1', e.target.value)}
      />
      <Input
        label="Address line 2 (optional)"
        value={values.address_line2}
        onChange={(e) => set('address_line2', e.target.value)}
      />
      <Input label="Landmark (optional)" value={values.landmark} onChange={(e) => set('landmark', e.target.value)} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Input label="City" required value={values.city} onChange={(e) => set('city', e.target.value)} />
        <Input
          label="District (optional)"
          value={values.district}
          onChange={(e) => set('district', e.target.value)}
        />
        <Input label="State" required value={values.state} onChange={(e) => set('state', e.target.value)} />
        <Input label="Country" required value={values.country} onChange={(e) => set('country', e.target.value)} />
        <Input
          label="Postal code"
          required
          value={values.postal_code}
          onChange={(e) => set('postal_code', e.target.value)}
        />
        <div className="flex flex-col gap-1.5">
          <label htmlFor="address-type" className="text-sm font-medium text-gray-700">
            Address type
          </label>
          <select
            id="address-type"
            value={values.address_type}
            onChange={(e) => set('address_type', e.target.value as AddressType)}
            className="h-10 rounded-md border border-gray-300 px-3 text-sm"
          >
            {ADDRESS_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Input
        label="Delivery instructions (optional)"
        value={values.delivery_instructions}
        onChange={(e) => set('delivery_instructions', e.target.value)}
      />

      <Input
        label="GSTIN (optional)"
        value={values.gstin}
        onChange={(e) => set('gstin', e.target.value.toUpperCase())}
        hint="For B2B invoices. 15 characters, e.g. 27ABCDE1234F1Z5."
        maxLength={15}
      />

      <div className="flex flex-col gap-2 sm:flex-row sm:gap-6">
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <input
            type="checkbox"
            checked={values.is_default_shipping}
            onChange={(e) => set('is_default_shipping', e.target.checked)}
            className="h-4 w-4 rounded border-gray-300"
          />
          Default shipping address
        </label>
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <input
            type="checkbox"
            checked={values.is_default_billing}
            onChange={(e) => set('is_default_billing', e.target.checked)}
            className="h-4 w-4 rounded border-gray-300"
          />
          Default billing address
        </label>
      </div>

      {error && <Alert>{error}</Alert>}

      <div className="flex gap-2">
        <Button type="submit" isLoading={isSaving}>
          {submitLabel}
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel} disabled={isSaving}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

/** Compact read-only rendering of an address, shared by the Address Book
 * cards, Checkout's selectable address cards, and the order detail pages'
 * shipping/billing address blocks. */
export function AddressSummary({ address }: { address: Address }) {
  return (
    <div className="text-sm text-gray-600">
      <p className="font-medium text-gray-900">{address.full_name}</p>
      <p>{address.address_line1}</p>
      {address.address_line2 && <p>{address.address_line2}</p>}
      {address.landmark && <p>{address.landmark}</p>}
      <p>
        {address.city}, {address.state} {address.postal_code}
      </p>
      <p>{address.country}</p>
      <p className="text-gray-500">{address.phone}</p>
      {address.gstin && <p className="text-gray-500">GSTIN: {address.gstin}</p>}
    </div>
  )
}

export default function Addresses() {
  const [addresses, setAddresses] = useState<Address[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formValues, setFormValues] = useState<AddressFormValues>(EMPTY_ADDRESS_FORM)
  const [isSaving, setIsSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [deleteTarget, setDeleteTarget] = useState<Address | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  function loadAddresses() {
    setIsLoading(true)
    setError(null)
    return addressesApi
      .listAddresses()
      .then(setAddresses)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load addresses'))
      .finally(() => setIsLoading(false))
  }

  useEffect(() => {
    void loadAddresses()
  }, [])

  function openCreateForm() {
    setEditingId(null)
    setFormValues(EMPTY_ADDRESS_FORM)
    setFormError(null)
    setIsFormOpen(true)
  }

  function openEditForm(address: Address) {
    setEditingId(address.id)
    setFormValues(addressToFormValues(address))
    setFormError(null)
    setIsFormOpen(true)
  }

  function closeForm() {
    setIsFormOpen(false)
    setFormError(null)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)
    setIsSaving(true)
    const payload = formValuesToPayload(formValues)
    try {
      if (editingId) {
        const updated = await addressesApi.updateAddress(editingId, payload)
        setAddresses((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
      } else {
        const created = await addressesApi.createAddress(payload)
        setAddresses((prev) => [...prev, created])
      }
      closeForm()
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Failed to save address')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return
    setIsDeleting(true)
    setDeleteError(null)
    try {
      await addressesApi.deleteAddress(deleteTarget.id)
      setAddresses((prev) => prev.filter((a) => a.id !== deleteTarget.id))
      setDeleteTarget(null)
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : 'Failed to delete address')
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-gray-900">Address book</h1>
        {!isFormOpen && (
          <Button size="sm" onClick={openCreateForm}>
            Add address
          </Button>
        )}
      </div>

      {isFormOpen && (
        <Card className="mb-6 p-4">
          <h2 className="mb-4 text-sm font-semibold text-gray-900">{editingId ? 'Edit address' : 'New address'}</h2>
          <AddressForm
            values={formValues}
            onChange={setFormValues}
            onSubmit={handleSubmit}
            onCancel={closeForm}
            isSaving={isSaving}
            error={formError}
            submitLabel={editingId ? 'Save changes' : 'Add address'}
          />
        </Card>
      )}

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {isLoading && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      )}

      {!isLoading && addresses.length === 0 && !error && !isFormOpen && (
        <EmptyState
          title="No saved addresses"
          description="Add an address to speed up checkout."
          action={
            <Button size="sm" onClick={openCreateForm}>
              Add address
            </Button>
          }
        />
      )}

      {!isLoading && addresses.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {addresses.map((address) => (
            <Card key={address.id} className="p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Badge>{address.address_type}</Badge>
                {address.is_default_shipping && <Badge tone="info">Default shipping</Badge>}
                {address.is_default_billing && <Badge tone="success">Default billing</Badge>}
              </div>
              <AddressSummary address={address} />
              <div className="mt-4 flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => openEditForm(address)}>
                  Edit
                </Button>
                <Button variant="danger" size="sm" onClick={() => setDeleteTarget(address)}>
                  Delete
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete this address?"
        description={deleteError ?? 'This cannot be undone.'}
        confirmLabel="Delete"
        isDestructive
        isConfirming={isDeleting}
        onConfirm={() => void handleDelete()}
        onCancel={() => {
          setDeleteTarget(null)
          setDeleteError(null)
        }}
      />
    </div>
  )
}
