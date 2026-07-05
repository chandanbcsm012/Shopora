import type { AddressPayload } from '../api/addresses'
import type { Address, AddressType } from '../api/types'

/**
 * Plain (non-JSX) form-state shape for the Address form shared by the
 * Address Book page and Checkout's inline "add new address" flow. Every
 * optional/nullable `Address` field is a plain string here so controlled
 * `<input>`s never fight React over `null`/`undefined` values; conversion
 * to/from the wire payload happens in `formValuesToPayload`/
 * `addressToFormValues` below.
 */
export interface AddressFormValues {
  full_name: string
  phone: string
  alternate_phone: string
  company: string
  address_line1: string
  address_line2: string
  landmark: string
  city: string
  district: string
  state: string
  country: string
  postal_code: string
  delivery_instructions: string
  address_type: AddressType
  is_default_shipping: boolean
  is_default_billing: boolean
  gstin: string
}

export const EMPTY_ADDRESS_FORM: AddressFormValues = {
  full_name: '',
  phone: '',
  alternate_phone: '',
  company: '',
  address_line1: '',
  address_line2: '',
  landmark: '',
  city: '',
  district: '',
  state: '',
  country: '',
  postal_code: '',
  delivery_instructions: '',
  address_type: 'home',
  is_default_shipping: false,
  is_default_billing: false,
  gstin: '',
}

export function addressToFormValues(address: Address): AddressFormValues {
  return {
    full_name: address.full_name,
    phone: address.phone,
    alternate_phone: address.alternate_phone ?? '',
    company: address.company ?? '',
    address_line1: address.address_line1,
    address_line2: address.address_line2 ?? '',
    landmark: address.landmark ?? '',
    city: address.city,
    district: address.district ?? '',
    state: address.state,
    country: address.country,
    postal_code: address.postal_code,
    delivery_instructions: address.delivery_instructions ?? '',
    address_type: address.address_type,
    is_default_shipping: address.is_default_shipping,
    is_default_billing: address.is_default_billing,
    gstin: address.gstin ?? '',
  }
}

export function formValuesToPayload(values: AddressFormValues): AddressPayload {
  return {
    full_name: values.full_name,
    phone: values.phone,
    alternate_phone: values.alternate_phone.trim() || null,
    company: values.company.trim() || null,
    address_line1: values.address_line1,
    address_line2: values.address_line2.trim() || null,
    landmark: values.landmark.trim() || null,
    city: values.city,
    district: values.district.trim() || null,
    state: values.state,
    country: values.country,
    postal_code: values.postal_code,
    delivery_instructions: values.delivery_instructions.trim() || null,
    address_type: values.address_type,
    is_default_shipping: values.is_default_shipping,
    is_default_billing: values.is_default_billing,
    gstin: values.gstin.trim().toUpperCase() || null,
  }
}
