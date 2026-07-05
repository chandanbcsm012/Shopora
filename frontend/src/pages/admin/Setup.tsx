import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import * as authApi from '../../api/auth'
import { ApiError } from '../../api/client'
import { Alert, Button, Card, Input, Spinner } from '../../components/ui'
import { useAuth } from '../../context/AuthContext'

/**
 * First-run setup wizard: public route (no auth, no RequireAdmin) since by
 * definition no admin exists yet the first time this is useful. Mirrors
 * Register.tsx's layout/behavior exactly — it's a single 4-field form, not
 * a multi-step wizard, per the foundation scope.
 */
export default function Setup() {
  const { bootstrap } = useAuth()
  const navigate = useNavigate()
  const [status, setStatus] = useState<'checking' | 'ready' | 'already-done'>('checking')
  const [statusError, setStatusError] = useState<string | null>(null)

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    authApi
      .getBootstrapStatus()
      .then((result) => {
        if (cancelled) return
        setStatus(result.admin_exists ? 'already-done' : 'ready')
      })
      .catch((err) => {
        if (cancelled) return
        setStatusError(err instanceof Error ? err.message : 'Failed to check setup status')
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)

    if (password !== confirmPassword) {
      setFormError('Passwords do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      await bootstrap(email, password, fullName)
      navigate('/admin', { replace: true })
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Setup failed. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto mt-8 max-w-sm sm:mt-16">
      <Card className="p-6">
        <h1 className="mb-6 text-xl font-semibold text-gray-900">Set up your store</h1>

        {status === 'checking' && (
          <div role="status" className="flex justify-center py-8">
            <Spinner />
            <span className="sr-only">Checking setup status…</span>
          </div>
        )}

        {status === 'checking' && statusError && <Alert>{statusError}</Alert>}

        {status === 'already-done' && (
          <div className="flex flex-col gap-4">
            <Alert tone="info">Setup already completed — an administrator account exists.</Alert>
            <Link to="/login" className="font-medium text-brand-600 hover:text-brand-700">
              Go to login
            </Link>
          </div>
        )}

        {status === 'ready' && (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <Input
              label="Full name"
              type="text"
              name="name"
              autoComplete="name"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
            <Input
              label="Email"
              type="email"
              name="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              label="Password"
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
              label="Confirm password"
              type="password"
              name="confirm-password"
              autoComplete="new-password"
              required
              minLength={8}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
            {formError && <Alert>{formError}</Alert>}
            <Button type="submit" isLoading={isSubmitting} className="mt-1 w-full">
              {isSubmitting ? 'Creating admin account…' : 'Create admin account'}
            </Button>
          </form>
        )}
      </Card>
    </div>
  )
}
