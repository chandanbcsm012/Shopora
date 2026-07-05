import PolicyLayout, { PolicySection } from '../components/PolicyLayout'

export default function TermsAndConditions() {
  return (
    <PolicyLayout title="Terms &amp; Conditions">
      <PolicySection heading="1. Acceptance of terms">
        <p>
          By creating an account or placing an order on this storefront, operated by [Company Legal Name], you agree
          to these Terms &amp; Conditions.
        </p>
      </PolicySection>

      <PolicySection heading="2. Accounts">
        <p>
          You're responsible for keeping your account credentials confidential and for all activity under your
          account. Provide accurate information when registering and when placing orders.
        </p>
      </PolicySection>

      <PolicySection heading="3. Orders and pricing">
        <p>
          Product prices are listed in the currency shown at checkout (USD or INR). We reserve the right to correct
          pricing or listing errors. Placing an order is an offer to purchase; an order is confirmed once payment is
          accepted (including Cash on Delivery orders, where payment is collected on delivery).
        </p>
      </PolicySection>

      <PolicySection heading="4. Payments">
        <p>
          We currently support Cash on Delivery and a simulated "test card" payment method for demonstration
          purposes. No real card numbers, expiry dates, or CVVs are collected or processed anywhere on this site.
        </p>
      </PolicySection>

      <PolicySection heading="5. Returns and refunds">
        <p>
          See our separate Return Policy and Refund Policy pages for what is (and isn't) currently supported.
        </p>
      </PolicySection>

      <PolicySection heading="6. Intellectual property">
        <p>
          All content on this site (text, graphics, logos) is the property of [Company Legal Name] or its licensors
          and may not be reused without permission.
        </p>
      </PolicySection>

      <PolicySection heading="7. Limitation of liability">
        <p>
          To the fullest extent permitted by law, [Company Legal Name] is not liable for indirect or consequential
          damages arising from use of this site. This is a foundation/demo platform and is provided "as is."
        </p>
      </PolicySection>

      <PolicySection heading="8. Governing law">
        <p>These terms are governed by the laws of [Governing Law / Jurisdiction].</p>
      </PolicySection>

      <PolicySection heading="9. Changes to these terms">
        <p>We may update these terms from time to time. Continued use of the site after changes constitutes acceptance.</p>
      </PolicySection>

      <PolicySection heading="10. Contact">
        <p>Questions? Contact us at [Support Email Address].</p>
      </PolicySection>
    </PolicyLayout>
  )
}
