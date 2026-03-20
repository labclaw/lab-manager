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
    <div className="bg-[var(--background)] font-[Inter,sans-serif] text-[var(--foreground)] flex items-center justify-center min-h-screen p-4">
      {/* Login Card Container */}
      <div className="w-full max-w-96 bg-[var(--card)] border border-[var(--border)] rounded-xl p-8 shadow-2xl">
        {/* Header / Logo Section */}
        <div className="flex flex-col items-center gap-2 mb-8">
          <div className="flex items-center gap-2">
            <div className="bg-primary/20 p-2 rounded-lg flex items-center justify-center">
              <span className="material-symbols-outlined text-primary text-3xl">science</span>
            </div>
            <h1 className="text-[var(--foreground)] text-2xl font-bold tracking-tight">LabClaw</h1>
          </div>
          <p className="text-[var(--muted-foreground)] text-sm font-medium">Lab Manager</p>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-5 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-500">
            {error}
          </div>
        )}

        {/* Form Section */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {/* Email Input */}
          <div className="flex flex-col gap-2">
            <label htmlFor="email" className="text-[var(--foreground)] text-sm font-medium ml-1">Email</label>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] text-xl">mail</span>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-11 pr-4 py-3 bg-[var(--background)] border border-[var(--border)] rounded-lg text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all outline-none"
                placeholder="Enter your email"
                required
                autoFocus
              />
            </div>
          </div>

          {/* Password Input */}
          <div className="flex flex-col gap-2">
            <div className="flex justify-between items-center px-1">
              <label htmlFor="password" className="text-[var(--foreground)] text-sm font-medium">Password</label>
              <a href="#" className="text-primary text-xs font-semibold hover:underline">Forgot password?</a>
            </div>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] text-xl">lock</span>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-11 pr-4 py-3 bg-[var(--background)] border border-[var(--border)] rounded-lg text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all outline-none"
                placeholder="Enter your password"
                required
              />
            </div>
          </div>

          {/* Remember Me */}
          <div className="flex items-center gap-2 px-1">
            <input
              id="remember"
              type="checkbox"
              className="w-4 h-4 rounded border-[var(--border)] bg-[var(--background)] text-primary focus:ring-offset-[var(--background)]"
            />
            <label htmlFor="remember" className="text-[var(--muted-foreground)] text-sm">Remember this device</label>
          </div>

          {/* Sign In Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary hover:bg-primary/90 text-white font-bold py-3 px-4 rounded-lg mt-2 shadow-lg shadow-primary/20 flex items-center justify-center gap-2 transition-colors disabled:opacity-60"
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

        {/* Footer Info */}
        <div className="mt-8 text-center">
          <p className="text-[var(--muted-foreground)] text-sm">
            Don&apos;t have an account?{' '}
            <a href="#" className="text-primary font-semibold hover:underline">Request access</a>
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
