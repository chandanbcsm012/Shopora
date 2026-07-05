import PolicyLayout, { PolicySection } from '../components/PolicyLayout'

export default function ShippingPolicy() {
  return (
    <PolicyLayout title="Shipping Policy">
      <PolicySection heading="1. Order processing">
        <p>
          Once an order is confirmed (payment accepted, including Cash on Delivery orders), we begin preparing it for
          shipment. You can follow your order's progress at any time from "My Orders," which shows a status timeline
          (pending, paid, shipped, delivered, or cancelled).
        </p>
      </PolicySection>

      <PolicySection heading="2. Delivery estimates">
        <p>
          We do not currently commit to a specific delivery window or partner with a named courier/carrier — delivery
          timing depends on the fulfillment process at the time of your order. We'll update your order's status as it
          progresses.
        </p>
      </PolicySection>

      <PolicySection heading="3. Shipping charges">
        <p>
          Shipping charges are not calculated or added at checkout in this version of the store; the total you see at
          checkout is the full amount charged (plus any applicable GST shown separately for INR orders).
        </p>
      </PolicySection>

      <PolicySection heading="4. Tracking">
        <p>
          We don't yet integrate with a third-party shipment-tracking service. The order status timeline on your
          order detail page is the authoritative source for where your order stands.
        </p>
      </PolicySection>

      <PolicySection heading="5. Delivery address">
        <p>
          Orders are shipped to the shipping address you select or add at checkout. Please double-check your address
          book entries for accuracy before placing an order.
        </p>
      </PolicySection>

      <PolicySection heading="6. Questions">
        <p>If your order seems delayed or you have shipping questions, contact us at [Support Email Address].</p>
      </PolicySection>
    </PolicyLayout>
  )
}
