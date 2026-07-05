import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import * as authApi from '../api/auth'
import { configureApiClient } from '../api/client'
import type { User } from '../api/types'

interface AuthContextValue {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName: string) => Promise<void>
  bootstrap: (email: string, password: string, fullName: string) => Promise<void>
  acceptInvitation: (token: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  // Tokens live only in memory (refs, not state) per the foundation-slice
  // spec: no persistence across reloads, and refs avoid re-render churn on
  // every silent refresh.
  const accessTokenRef = useRef<string | null>(null)
  const refreshTokenRef = useRef<string | null>(null)

  const clearAuth = useCallback(() => {
    accessTokenRef.current = null
    refreshTokenRef.current = null
    setUser(null)
  }, [])

  const refreshAccessToken = useCallback(async (): Promise<string | null> => {
    if (!refreshTokenRef.current) return null
    try {
      const tokens = await authApi.refresh(refreshTokenRef.current)
      accessTokenRef.current = tokens.access_token
      refreshTokenRef.current = tokens.refresh_token
      return tokens.access_token
    } catch {
      clearAuth()
      return null
    }
  }, [clearAuth])

  // Wire the shared API client to this context's token storage + refresh
  // hook once, so every apiRequest() call transparently retries a single
  // 401 after refreshing the access token.
  useEffect(() => {
    configureApiClient({
      getAccessToken: () => accessTokenRef.current,
      onUnauthorized: refreshAccessToken,
    })
  }, [refreshAccessToken])

  // Shared by login/bootstrap: both endpoints return the same TokenPair
  // shape and both want to end up with the token pair stored + `user`
  // populated from a follow-up GET /auth/me.
  const applyTokens = useCallback(async (tokens: { access_token: string; refresh_token: string }) => {
    accessTokenRef.current = tokens.access_token
    refreshTokenRef.current = tokens.refresh_token
    const currentUser = await authApi.me()
    setUser(currentUser)
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      setIsLoading(true)
      try {
        const tokens = await authApi.login({ email, password })
        await applyTokens(tokens)
      } finally {
        setIsLoading(false)
      }
    },
    [applyTokens],
  )

  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      setIsLoading(true)
      try {
        // POST /auth/register only returns the created User (no tokens per
        // CONTRACTS.md), so we log in right after to establish a session.
        await authApi.register({ email, password, full_name: fullName })
        await login(email, password)
      } finally {
        setIsLoading(false)
      }
    },
    [login],
  )

  const bootstrap = useCallback(
    async (email: string, password: string, fullName: string) => {
      setIsLoading(true)
      try {
        // POST /auth/bootstrap returns a TokenPair directly (it behaves like
        // login, not register) so we can store tokens right away without a
        // separate login() round-trip.
        const tokens = await authApi.bootstrap({ email, password, full_name: fullName })
        await applyTokens(tokens)
      } finally {
        setIsLoading(false)
      }
    },
    [applyTokens],
  )

  const acceptInvitation = useCallback(
    async (token: string, password: string) => {
      setIsLoading(true)
      try {
        // POST /auth/accept-invitation returns a TokenPair directly (same
        // auto-login pattern as bootstrap), so we can apply tokens without
        // a separate login() round-trip.
        const tokens = await authApi.acceptInvitation({ token, password })
        await applyTokens(tokens)
      } finally {
        setIsLoading(false)
      }
    },
    [applyTokens],
  )

  const logout = useCallback(async () => {
    const token = refreshTokenRef.current
    clearAuth()
    if (token) {
      try {
        await authApi.logout(token)
      } catch {
        // Best-effort: local session is already cleared either way.
      }
    }
  }, [clearAuth])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      login,
      register,
      bootstrap,
      acceptInvitation,
      logout,
    }),
    [user, isLoading, login, register, bootstrap, acceptInvitation, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return ctx
}
