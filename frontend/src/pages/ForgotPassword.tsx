import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import * as authApi from '../api/auth'
import { Alert, Button, Card, Input } from '../components/ui'

const GENERIC_MESSAGE = "If an account exists for that email, we've sent a reset link."

/**
 * POST /auth/forgot-password always returns 202 regardless of whether the
 * email is registered (no user enumeration, per CONTRACTS.md) — so unlike
 * every other form in this app, there is deliberately only ONE outcome UI,
 * shown identically whether the request resolves or rejects. Do not add a
 * distinct "email not found" branch; that would leak exactly what this
 * endpoint is designed to hide.
 */
export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSubmitting(true)
    try {
      await authApi.forgotPassword(email)
    } catch {
      // Intentionally swallowed: show the same generic message either way.
    } finally {
      setIsSubmitting(false)
      setSubmitted(true)
    }
  }

  return (
    <div className="mx-auto mt-8 max-w-sm sm:mt-16">
      <Card className="p-6">
        <h1 className="mb-6 text-xl font-semibold text-gray-900">Forgot password</h1>

        {submitted ? (
          <div className="flex flex-col gap-4">
            <Alert tone="info">{GENERIC_MESSAGE}</Alert>
            <Link to="/login" className="font-medium text-brand-600 hover:text-brand-700">
              Back to login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <p className="text-sm text-gray-600">
              Enter your account email and we&rsquo;ll send you a link to reset your password.
            </p>
            <Input
              label="Email"
              type="email"
              name="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Button type="submit" isLoading={isSubmitting} className="mt-1 w-full">
              {isSubmitting ? 'Sending…' : 'Send reset link'}
            </Button>
          </form>
        )}
      </Card>
    </div>
  )
}
