import { useState } from 'react'
import { setup } from '@/lib/api'

interface Readonly_SetupPageProps {
  readonly onComplete: () => void
}

export function SetupPage({ onComplete }: Readonly_SetupPageProps) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await setup.complete({ admin_name: name, admin_email: email, admin_password: password })
      onComplete()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Setup failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--background)] flex items-center justify-center p-4 relative">
      {/* Background gradient blobs */}
      <div className="fixed inset-0 -z-10 opacity-20 pointer-events-none overflow-hidden">
        <div className="absolute -top-[10%] -left-[10%] w-[40%] h-[40%] bg-[var(--primary)] rounded-full blur-[120px]" />
        <div className="absolute -bottom-[10%] -right-[10%] w-[40%] h-[40%] bg-[var(--accent)]/30 rounded-full blur-[120px]" />
      </div>

      {/* Setup Card */}
      <div className="w-full max-w-[440px] bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-2xl p-8 md:p-10">
        {/* Icon Header */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 bg-[var(--primary)]/20 rounded-full flex items-center justify-center mb-6">
            <span className="material-symbols-outlined text-[var(--primary)] text-4xl">science</span>
          </div>
          <h1 className="text-[var(--foreground)] text-3xl font-bold tracking-tight text-center mb-2">
            Welcome to LabClaw
          </h1>
          <p className="text-[var(--muted-foreground)] text-sm font-medium text-center">
            Set up your lab in 30 seconds
          </p>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-5 p-3 rounded-lg bg-[var(--destructive)]/10 border border-[var(--destructive)]/30 text-sm text-[var(--destructive)]">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Name */}
          <div className="space-y-2">
            <label htmlFor="setup-name" className="text-[var(--foreground)] text-sm font-semibold ml-1">
              Your Name
            </label>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] text-xl">
                person
              </span>
              <input
                id="setup-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full pl-11 pr-4 py-3.5 bg-[var(--background)]/50 border border-[var(--border)] rounded-lg text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:ring-2 focus:ring-[var(--ring)]/50 focus:border-[var(--primary)] outline-none transition-all"
                placeholder="John Doe"
                required
                autoFocus
              />
            </div>
          </div>

          {/* Email */}
          <div className="space-y-2">
            <label htmlFor="setup-email" className="text-[var(--foreground)] text-sm font-semibold ml-1">
              Email
            </label>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] text-xl">
                mail
              </span>
              <input
                id="setup-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-11 pr-4 py-3.5 bg-[var(--background)]/50 border border-[var(--border)] rounded-lg text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:ring-2 focus:ring-[var(--ring)]/50 focus:border-[var(--primary)] outline-none transition-all"
                placeholder="name@lab.com"
                required
              />
            </div>
          </div>

          {/* Password */}
          <div className="space-y-2">
            <label htmlFor="setup-password" className="text-[var(--foreground)] text-sm font-semibold ml-1">
              Password
            </label>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] text-xl">
                lock
              </span>
              <input
                id="setup-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-11 pr-4 py-3.5 bg-[var(--background)]/50 border border-[var(--border)] rounded-lg text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:ring-2 focus:ring-[var(--ring)]/50 focus:border-[var(--primary)] outline-none transition-all"
                placeholder="At least 8 characters"
                required
              />
            </div>
          </div>

          {/* CTA Button */}
          <div className="pt-4">
            <button
              type="submit"
              disabled={loading}
              className="w-full py-4 bg-[var(--accent)] hover:brightness-110 text-white font-bold rounded-lg shadow-lg shadow-[var(--accent)]/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Creating account...</span>
                </>
              ) : (
                <>
                  <span>Create Admin Account</span>
                  <span className="material-symbols-outlined text-xl">arrow_forward</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Footer */}
        <div className="mt-8 pt-6 border-t border-[var(--border)] flex items-center justify-center gap-2">
          <span className="material-symbols-outlined text-[var(--muted-foreground)] text-lg">info</span>
          <p className="text-[var(--muted-foreground)] text-[11px] uppercase tracking-wider font-semibold">
            You can add more team members after setup
          </p>
        </div>
      </div>
    </div>
  )
}
