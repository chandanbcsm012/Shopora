import PolicyLayout, { PolicySection } from '../components/PolicyLayout'

export default function CookiePolicy() {
  return (
    <PolicyLayout title="Cookie Policy">
      <PolicySection heading="Short version">
        <p>
          This site does not use tracking or advertising cookies. We don't run any third-party analytics or ad
          scripts.
        </p>
      </PolicySection>

      <PolicySection heading="How sign-in works">
        <p>
          When you log in, your session is kept in your browser's memory for the current tab only — it is not stored
          in a cookie or in persistent local storage. Refreshing or closing the page ends your session and you'll
          need to log in again. This is a deliberate, simple approach for this foundation platform rather than a
          persistent "remember me" cookie.
        </p>
      </PolicySection>

      <PolicySection heading="Essential storage">
        <p>
          Beyond your active session, the site doesn't set cookies to remember preferences, track your browsing
          across visits, or build an advertising profile.
        </p>
      </PolicySection>

      <PolicySection heading="Changes">
        <p>
          If this changes in a future update (for example, adding a persistent "stay signed in" option), this page
          will be updated to describe exactly what's stored and why.
        </p>
      </PolicySection>
    </PolicyLayout>
  )
}
