import { useState } from 'react'
import { setup } from '@/lib/api'
import { FlaskConical } from 'lucide-react'

interface SetupPageProps {
  onComplete: () => void
}

export function SetupPage({ onComplete }: SetupPageProps) {
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
    <div className="min-h-screen bg-[var(--background)] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <FlaskConical className="w-10 h-10 text-[var(--primary)]" />
          <h1 className="text-2xl font-display font-bold text-[var(--foreground)]">
            LabClaw
          </h1>
        </div>

        <div className="card space-y-5">
          <div>
            <h2 className="text-lg font-display font-semibold text-[var(--foreground)] mb-1">
              Welcome to Lab Manager
            </h2>
            <p className="text-sm text-[var(--muted-foreground)]">
              Create your admin account to get started.
            </p>
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-[var(--destructive)]/10 border border-[var(--destructive)]/30 text-sm text-[var(--destructive)]">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label
                htmlFor="setup-name"
                className="block text-sm font-medium text-[var(--muted-foreground)] mb-1.5"
              >
                Name
              </label>
              <input
                id="setup-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-[var(--popover)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                placeholder="Your name"
                required
                autoFocus
              />
            </div>

            <div>
              <label
                htmlFor="setup-email"
                className="block text-sm font-medium text-[var(--muted-foreground)] mb-1.5"
              >
                Email
              </label>
              <input
                id="setup-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-[var(--popover)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                placeholder="admin@lab.edu"
                required
              />
            </div>

            <div>
              <label
                htmlFor="setup-password"
                className="block text-sm font-medium text-[var(--muted-foreground)] mb-1.5"
              >
                Password
              </label>
              <input
                id="setup-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-[var(--popover)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                placeholder="At least 8 characters"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Creating account...</span>
                </>
              ) : (
                'Create Admin Account'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
