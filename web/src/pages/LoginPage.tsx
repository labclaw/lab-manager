import { useState } from 'react'
import { auth } from '@/lib/api'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await auth.login(email, password)
      window.location.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--background)] flex items-center justify-center p-4 relative">
      {/* Background gradient blobs */}
      <div className="fixed inset-0 -z-10 opacity-20 pointer-events-none overflow-hidden">
        <div className="absolute -top-[10%] -left-[10%] w-[40%] h-[40%] bg-[var(--primary)] rounded-full blur-[120px]" />
        <div className="absolute -bottom-[10%] -right-[10%] w-[40%] h-[40%] bg-[var(--primary)]/30 rounded-full blur-[120px]" />
      </div>

      {/* Login Card */}
      <div className="w-full max-w-96 bg-[var(--card)] border border-[var(--border)] rounded-xl p-8 shadow-2xl">
        {/* Header / Logo */}
        <div className="flex flex-col items-center gap-2 mb-8">
          <div className="flex items-center gap-2">
            <div className="bg-[var(--primary)]/20 p-2 rounded-lg flex items-center justify-center">
              <span className="material-symbols-outlined text-[var(--primary)] text-3xl">science</span>
            </div>
            <h1 className="text-[var(--foreground)] text-2xl font-bold tracking-tight">LabClaw</h1>
          </div>
          <p className="text-[var(--muted-foreground)] text-sm font-medium">Lab Manager</p>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-5 p-3 rounded-lg bg-[var(--destructive)]/10 border border-[var(--destructive)]/30 text-sm text-[var(--destructive)]">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {/* Email */}
          <div className="flex flex-col gap-2">
            <label htmlFor="email" className="text-[var(--foreground)] text-sm font-medium ml-1">
              Email
            </label>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] text-xl">
                mail
              </span>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-11 pr-4 py-3 bg-[var(--background)] border border-[var(--border)] rounded-lg text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:ring-2 focus:ring-[var(--ring)]/50 focus:border-[var(--primary)] transition-all outline-none"
                placeholder="Enter your email"
                required
                autoFocus
              />
            </div>
          </div>

          {/* Password */}
          <div className="flex flex-col gap-2">
            <div className="flex justify-between items-center px-1">
              <label htmlFor="password" className="text-[var(--foreground)] text-sm font-medium">
                Password
              </label>
              <a href="#" className="text-[var(--primary)] text-xs font-semibold hover:underline">
                Forgot password?
              </a>
            </div>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] text-xl">
                lock
              </span>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-11 pr-4 py-3 bg-[var(--background)] border border-[var(--border)] rounded-lg text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:ring-2 focus:ring-[var(--ring)]/50 focus:border-[var(--primary)] transition-all outline-none"
                placeholder="Enter your password"
                required
              />
            </div>
          </div>

          {/* Sign In Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[var(--primary)] hover:bg-[var(--primary)]/90 text-white font-bold py-3 px-4 rounded-lg mt-2 shadow-lg shadow-[var(--primary)]/20 flex items-center justify-center gap-2 transition-colors disabled:opacity-60"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Signing in...</span>
              </>
            ) : (
              <>
                <span>Sign In</span>
                <span className="material-symbols-outlined text-xl">login</span>
              </>
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="mt-8 text-center">
          <p className="text-[var(--muted-foreground)] text-sm">
            Don't have an account?{' '}
            <a href="#" className="text-[var(--primary)] font-semibold hover:underline">
              Request access
            </a>
          </p>
        </div>
      </div>

      {/* Security Badge */}
      <div className="fixed bottom-6 flex items-center gap-2 text-[var(--muted-foreground)]/50">
        <span className="material-symbols-outlined text-sm">verified_user</span>
        <span className="text-[10px] uppercase tracking-widest font-bold">Secure Environment</span>
      </div>
    </div>
  )
}
