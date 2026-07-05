import PolicyLayout, { PolicySection } from '../components/PolicyLayout'

export default function RefundPolicy() {
  return (
    <PolicyLayout title="Refund Policy">
      <PolicySection heading="How refunds work here">
        <p>
          Refunds on this platform are processed at the payment level, not as part of a self-service return request
          (see our Return Policy — returns/exchanges aren't a supported feature yet). When our support team approves
          a refund, an administrator issues it against the original payment for your order.
        </p>
      </PolicySection>

      <PolicySection heading="Cash on Delivery orders">
        <p>
          For Cash on Delivery orders, no payment is captured until delivery, so there is nothing to refund unless
          cash was actually collected. If cash was collected and a refund is warranted, this is arranged manually by
          our support team outside the automated payment flow.
        </p>
      </PolicySection>

      <PolicySection heading="Test-card orders">
        <p>
          For orders paid via our simulated test-card flow, a captured payment can be refunded (in full or in part)
          by an administrator. Refund status appears on your order's payment details once processed.
        </p>
      </PolicySection>

      <PolicySection heading="Requesting a refund">
        <p>
          Contact us at [Support Email Address] with your order number and the reason for your request. There is no
          automated self-service refund button in this version of the store — every refund is reviewed by a person.
        </p>
      </PolicySection>

      <PolicySection heading="Timing">
        <p>
          We don't currently commit to a fixed refund-processing timeframe, since no real payment gateway is
          connected in this environment (payments are simulated for demonstration purposes).
        </p>
      </PolicySection>
    </PolicyLayout>
  )
}
