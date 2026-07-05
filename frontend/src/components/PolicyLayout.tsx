import type { ReactNode } from 'react'

/**
 * Shared heading/spacing chrome for the policy pages (Privacy, Terms,
 * Shipping, Return, Refund, Cookie) so the six of them don't each hand-roll
 * the same `<h1>`/section markup. Plain semantic HTML — no markdown-renderer
 * dependency needed for static legal copy.
 */
export default function PolicyLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight text-gray-900">{title}</h1>
      <p className="mb-8 text-sm text-gray-500">
        This is a demo storefront. Replace bracketed placeholders with your real business details before using this
        policy in production.
      </p>
      <div className="flex flex-col gap-6 text-sm leading-relaxed text-gray-700">{children}</div>
    </div>
  )
}

export function PolicySection({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="mb-2 text-base font-semibold text-gray-900">{heading}</h2>
      <div className="flex flex-col gap-2">{children}</div>
    </section>
  )
}
