import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import * as siteApi from '../api/site'
import { Alert, Button, Input } from './ui'

const FOOTER_LINK_GROUPS: { heading: string; links: { label: string; to: string }[] }[] = [
  {
    heading: 'Shop',
    links: [
      { label: 'All products', to: '/products' },
      { label: 'Your wishlist', to: '/wishlist' },
      { label: 'Your orders', to: '/orders' },
    ],
  },
  {
    heading: 'Company',
    links: [
      { label: 'About', to: '/about' },
      { label: 'Contact us', to: '/contact' },
      { label: 'Help / FAQ', to: '/faq' },
    ],
  },
  {
    heading: 'Policies',
    links: [
      { label: 'Privacy Policy', to: '/privacy-policy' },
      { label: 'Terms & Conditions', to: '/terms-and-conditions' },
      { label: 'Shipping Policy', to: '/shipping-policy' },
      { label: 'Return Policy', to: '/return-policy' },
      { label: 'Refund Policy', to: '/refund-policy' },
      { label: 'Cookie Policy', to: '/cookie-policy' },
    ],
  },
]

// Same no-enumeration spirit as forgot-password: show one generic message
// regardless of whether the email was already subscribed, or the request
// even succeeded.
const GENERIC_SUBSCRIBE_MESSAGE = "Thanks! If that address isn't already subscribed, you're on the list now."

export default function Footer() {
  const [email, setEmail] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [subscribed, setSubscribed] = useState(false)

  async function handleSubscribe(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSubmitting(true)
    try {
      await siteApi.subscribeToNewsletter(email)
    } catch {
      // Intentionally swallowed — see GENERIC_SUBSCRIBE_MESSAGE above.
    } finally {
      setIsSubmitting(false)
      setSubscribed(true)
      setEmail('')
    }
  }

  return (
    <footer className="border-t border-gray-200 bg-white">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-4">
        <div>
          <p className="text-lg font-semibold tracking-tight text-gray-900">Shopora</p>
          <p className="mt-2 text-sm text-gray-500">A demo storefront built on a simple, honest foundation.</p>
        </div>

        {FOOTER_LINK_GROUPS.map((group) => (
          <div key={group.heading}>
            <p className="text-sm font-semibold text-gray-900">{group.heading}</p>
            <ul className="mt-3 flex flex-col gap-2">
              {group.links.map((link) => (
                <li key={link.to}>
                  <Link to={link.to} className="text-sm text-gray-500 hover:text-gray-900">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}

        <div>
          <p className="text-sm font-semibold text-gray-900">Stay in the loop</p>
          {subscribed ? (
            <div className="mt-3">
              <Alert tone="success">{GENERIC_SUBSCRIBE_MESSAGE}</Alert>
            </div>
          ) : (
            <form onSubmit={handleSubscribe} className="mt-3 flex flex-col gap-2">
              <Input
                label="Email address"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
              <Button type="submit" size="sm" isLoading={isSubmitting}>
                Subscribe
              </Button>
            </form>
          )}
        </div>
      </div>

      <div className="border-t border-gray-200">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-4 text-xs text-gray-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>&copy; {new Date().getFullYear()} Shopora. All rights reserved.</p>
          <p>We accept: Cash on Delivery &middot; Card (test mode)</p>
        </div>
      </div>
    </footer>
  )
}
