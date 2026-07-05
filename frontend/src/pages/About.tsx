export default function About() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight text-gray-900">About Shopora</h1>
      <div className="flex flex-col gap-4 text-sm leading-relaxed text-gray-700">
        <p>
          Shopora is a demo e-commerce storefront — built to show what a real, working online store looks
          like end to end: browsing and search, a cart and checkout, order history with invoices, an address book,
          and a straightforward admin panel for managing the catalog.
        </p>
        <p>
          It's intentionally scoped as a foundation rather than a feature-complete marketplace: there are no product
          reviews, no coupons, no real payment gateway, and no shipping-carrier integration. What is here — Cash on
          Delivery, a simulated test-card payment flow, GST-aware pricing for INR orders, and downloadable invoices —
          is built to actually work, not just look like it does.
        </p>
        <p>
          If you're evaluating this project, feel free to poke around: create an account, browse products, add
          something to your cart or wishlist, and walk through a checkout.
        </p>
      </div>
    </div>
  )
}
