import { Link } from 'react-router-dom'

interface FaqEntry {
  question: string
  answer: string
}

interface FaqGroup {
  topic: string
  entries: FaqEntry[]
}

// Grounded in what this store actually does (see docs/CONTRACTS.md) — no
// generic "lorem ipsum" filler questions.
const FAQ_GROUPS: FaqGroup[] = [
  {
    topic: 'Orders',
    entries: [
      {
        question: 'How do I track my order?',
        answer:
          'Open "My Orders" and select the order to see its full status timeline — pending, paid, shipped, delivered, or cancelled — updated as your order progresses.',
      },
      {
        question: 'Can I download an invoice?',
        answer:
          'Yes. Once your payment succeeds, a "Download Invoice" button appears on the order detail page. Invoices are generated fresh each time you download them, so they always reflect the current order status.',
      },
      {
        question: 'Why does my order show as "paid" for a Cash on Delivery purchase?',
        answer:
          'For Cash on Delivery orders, "paid" means the order is confirmed and accepted, not that cash has been collected yet. The separate payment status field on your order shows "pending" until cash is actually collected on delivery.',
      },
    ],
  },
  {
    topic: 'Shipping',
    entries: [
      {
        question: 'Which courier delivers my order?',
        answer:
          "We don't commit to a specific named carrier in this version of the store. Delivery progress is tracked through the order status timeline rather than a third-party tracking number.",
      },
      {
        question: 'How much does shipping cost?',
        answer:
          'Shipping charges are not calculated or added separately at checkout right now — the total shown at checkout (including any GST for INR orders) is the full amount charged.',
      },
    ],
  },
  {
    topic: 'Payments',
    entries: [
      {
        question: 'What payment methods are accepted?',
        answer:
          'Cash on Delivery, or our "Test Card" flow for demonstration purposes. The test-card option never asks for a real card number, expiry, or CVV — you simply choose a simulated "succeed" or "decline" outcome.',
      },
      {
        question: 'Is GST charged on my order?',
        answer:
          'For orders in INR, GST may be calculated and shown as a breakdown (CGST/SGST for in-state orders, IGST for out-of-state orders) on top of the item subtotal, based on the seller and shipping addresses.',
      },
      {
        question: 'Do you store my card details?',
        answer:
          'No. There is no real payment gateway connected in this environment, and no card-data field exists anywhere in the checkout flow.',
      },
    ],
  },
  {
    topic: 'Returns',
    entries: [
      {
        question: 'Can I return or exchange an item?',
        answer:
          "Not yet — self-service returns and exchanges aren't a supported feature in this version of the store. Contact support if you received a wrong, damaged, or defective item, and we'll help manually.",
      },
      {
        question: 'How do refunds work?',
        answer:
          'Refunds are issued by an administrator against the original payment method after a support review — see our Refund Policy for details. There is no automated self-service refund button yet.',
      },
    ],
  },
]

export default function FAQ() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight text-gray-900">Help Center / FAQ</h1>
      <p className="mb-8 text-sm text-gray-600">
        Answers to common questions. Can't find what you're looking for?{' '}
        <Link to="/contact" className="font-medium text-brand-600 hover:text-brand-700">
          Contact us
        </Link>
        .
      </p>

      <div className="flex flex-col gap-8">
        {FAQ_GROUPS.map((group) => (
          <section key={group.topic} aria-labelledby={`faq-${group.topic.toLowerCase()}`}>
            <h2 id={`faq-${group.topic.toLowerCase()}`} className="mb-3 text-lg font-semibold text-gray-900">
              {group.topic}
            </h2>
            <div className="flex flex-col divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
              {group.entries.map((entry) => (
                <details key={entry.question} className="group px-4 py-3">
                  <summary className="cursor-pointer list-none text-sm font-medium text-gray-900 marker:content-none">
                    <span className="flex items-center justify-between gap-4">
                      {entry.question}
                      <span aria-hidden="true" className="text-gray-400 group-open:rotate-180">
                        &darr;
                      </span>
                    </span>
                  </summary>
                  <p className="mt-2 text-sm leading-relaxed text-gray-600">{entry.answer}</p>
                </details>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
