import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import * as authApi from '../api/auth'
import { ApiError } from '../api/client'
import { Alert, Button, Card, Input } from '../components/ui'

/**
 * Public route reached via the emailed reset link (?token=). Unlike
 * AcceptInvitation, this does NOT auto-login on success — per CONTRACTS.md
 * a completed reset revokes all of the user's existing refresh tokens, so
 * the intentional UX here is a fresh login, not a session carried over
 * from the reset form.
 */
export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [succeeded, setSucceeded] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)

    if (!token) {
      setError('This reset link is missing a token.')
      return
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      await authApi.resetPassword({ token, new_password: password })
      setSucceeded(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to reset password. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto mt-8 max-w-sm sm:mt-16">
      <Card className="p-6">
        <h1 className="mb-6 text-xl font-semibold text-gray-900">Reset password</h1>

        {succeeded ? (
          <div className="flex flex-col gap-4">
            <Alert tone="success">Your password has been reset. Please log in with your new password.</Alert>
            <Link to="/login" className="font-medium text-brand-600 hover:text-brand-700">
              Go to login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <Input
              label="New password"
              type="password"
              name="password"
              autoComplete="new-password"
              required
              minLength={8}
              hint="At least 8 characters."
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Input
              label="Confirm new password"
              type="password"
              name="confirm-password"
              autoComplete="new-password"
              required
              minLength={8}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
            {error && <Alert>{error}</Alert>}
            <Button type="submit" isLoading={isSubmitting} className="mt-1 w-full">
              {isSubmitting ? 'Resetting…' : 'Reset password'}
            </Button>
          </form>
        )}
      </Card>
    </div>
  )
}
