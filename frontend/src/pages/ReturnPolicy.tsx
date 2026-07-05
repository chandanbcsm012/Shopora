import PolicyLayout, { PolicySection } from '../components/PolicyLayout'

export default function ReturnPolicy() {
  return (
    <PolicyLayout title="Return Policy">
      <PolicySection heading="Returns and exchanges are not yet supported">
        <p>
          We want to be upfront: this storefront does not currently have a returns or exchanges feature. There is no
          return-request workflow, no return shipping label generation, and no automated exchange process available
          today.
        </p>
      </PolicySection>

      <PolicySection heading="What we can do today">
        <p>
          If you received a wrong, damaged, or defective item, contact us at [Support Email Address] with your order
          number. Our support team will review it manually and, at our discretion, arrange a resolution such as a
          refund (see our Refund Policy) via the same payment method used at checkout.
        </p>
      </PolicySection>

      <PolicySection heading="What's coming later">
        <p>
          A self-service returns/exchanges workflow is planned for a future update to this platform, but it is not
          part of this release. This page will be updated once that capability ships.
        </p>
      </PolicySection>
    </PolicyLayout>
  )
}
