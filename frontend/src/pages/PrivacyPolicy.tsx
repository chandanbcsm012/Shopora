import PolicyLayout, { PolicySection } from '../components/PolicyLayout'

export default function PrivacyPolicy() {
  return (
    <PolicyLayout title="Privacy Policy">
      <PolicySection heading="1. Who we are">
        <p>
          [Company Legal Name] ("we", "us") operates this storefront. This policy explains what information we
          collect when you use it, and how we use it. If you have questions, contact us at [Support Email Address] or
          [Support Phone Number].
        </p>
      </PolicySection>

      <PolicySection heading="2. Information we collect">
        <p>We collect only what's needed to run the store:</p>
        <ul className="ml-5 list-disc">
          <li>Account details you provide: email address, full name, and a securely hashed password (we never store your password in plain text).</li>
          <li>Order information: items purchased, shipping and billing addresses, payment method (Cash on Delivery or our simulated test-card flow — we do not collect real card numbers), and order status history.</li>
          <li>Content you submit voluntarily: contact form messages and newsletter subscription email addresses.</li>
          <li>Wishlist and cart contents tied to your account.</li>
        </ul>
      </PolicySection>

      <PolicySection heading="3. How we use your information">
        <p>
          We use your information to create and fulfill orders, maintain your account, respond to support requests,
          generate invoices, and — only if you subscribe — send newsletter updates. We do not sell your personal
          information, and we do not use it for third-party advertising.
        </p>
      </PolicySection>

      <PolicySection heading="4. How long we keep it">
        <p>
          Account and order data is retained for as long as your account is active, plus any period required to keep
          accurate business and tax records. Contact us if you'd like to request deletion of your account data; as a
          demo/foundation platform, this is handled manually by our support team rather than a self-service tool.
        </p>
      </PolicySection>

      <PolicySection heading="5. Security">
        <p>
          Passwords are hashed, not stored in plain text. Access to your account uses short-lived session tokens.
          Administrative actions on your account (role or status changes, refunds) are logged internally for audit
          purposes.
        </p>
      </PolicySection>

      <PolicySection heading="6. Your choices">
        <p>
          You can unsubscribe from newsletter emails at any time by contacting us. You can review and update your
          saved addresses from your account's Address Book at any time.
        </p>
      </PolicySection>

      <PolicySection heading="7. Contact">
        <p>Questions about this policy? Reach us at [Support Email Address], [Registered Address].</p>
      </PolicySection>
    </PolicyLayout>
  )
}
