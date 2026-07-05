import { useState, type FormEvent } from 'react'
import * as siteApi from '../api/site'
import { ApiError } from '../api/client'
import { Alert, Button, Card, Input } from '../components/ui'

export default function Contact() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await siteApi.submitContactMessage({ name, email, subject, message })
      setSuccess(true)
      setName('')
      setEmail('')
      setSubject('')
      setMessage('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send your message. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight text-gray-900">Contact us</h1>
      <p className="mb-6 text-sm text-gray-600">
        Questions about an order, a product, or anything else? Send us a message and we'll get back to you.
      </p>
      <Card className="p-6">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
          <Input
            label="Email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input label="Subject" required value={subject} onChange={(e) => setSubject(e.target.value)} />
          <div className="flex flex-col gap-1.5">
            <label htmlFor="contact-message" className="text-sm font-medium text-gray-700">
              Message
            </label>
            <textarea
              id="contact-message"
              rows={5}
              required
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400"
            />
          </div>

          {success && <Alert tone="success">Thanks — your message has been sent. We'll be in touch soon.</Alert>}
          {error && <Alert>{error}</Alert>}

          <Button type="submit" isLoading={isSubmitting} className="mt-1 w-full sm:w-auto">
            Send message
          </Button>
        </form>
      </Card>
    </div>
  )
}
