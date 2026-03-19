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
    <div className="bg-background-light dark:bg-background-dark font-[Inter,sans-serif] antialiased flex items-center justify-center min-h-screen p-4">
      {/* Setup Wizard Card */}
      <div className="w-full max-w-[440px] bg-white dark:bg-card-dark border border-slate-200 dark:border-[#2d2d44] rounded-xl shadow-2xl p-8 md:p-10">
        {/* Icon Header */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 bg-primary/20 rounded-full flex items-center justify-center mb-6">
            <span className="material-symbols-outlined text-primary text-4xl">science</span>
          </div>
          <h1 className="text-slate-900 dark:text-slate-100 text-3xl font-bold tracking-tight text-center mb-2">
            Welcome to LabClaw
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm font-medium text-center">
            Set up your lab in 30 seconds
          </p>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-5 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-500">
            {error}
          </div>
        )}

        {/* Setup Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Name Input */}
          <div className="space-y-2">
            <label htmlFor="setup-name" className="text-slate-700 dark:text-slate-300 text-sm font-semibold ml-1">Your Name</label>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xl">person</span>
              <input
                id="setup-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full pl-11 pr-4 py-3.5 bg-slate-50 dark:bg-background-dark/50 border border-slate-200 dark:border-[#2d2d44] rounded-lg text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
                placeholder="John Doe"
                required
                autoFocus
              />
            </div>
          </div>

          {/* Email Input */}
          <div className="space-y-2">
            <label htmlFor="setup-email" className="text-slate-700 dark:text-slate-300 text-sm font-semibold ml-1">Email</label>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xl">mail</span>
              <input
                id="setup-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-11 pr-4 py-3.5 bg-slate-50 dark:bg-background-dark/50 border border-slate-200 dark:border-[#2d2d44] rounded-lg text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
                placeholder="name@lab.com"
                required
              />
            </div>
          </div>

          {/* Password Input */}
          <div className="space-y-2">
            <label htmlFor="setup-password" className="text-slate-700 dark:text-slate-300 text-sm font-semibold ml-1">Password</label>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xl">lock</span>
              <input
                id="setup-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-11 pr-4 py-3.5 bg-slate-50 dark:bg-background-dark/50 border border-slate-200 dark:border-[#2d2d44] rounded-lg text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
                placeholder="........"
                required
              />
            </div>
          </div>

          {/* CTA Button */}
          <div className="pt-4">
            <button
              type="submit"
              disabled={loading}
              className="w-full py-4 bg-accent-green hover:bg-[#05c491] text-background-dark font-bold rounded-lg shadow-lg shadow-accent-green/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 disabled:opacity-60"
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

        {/* Footer Info */}
        <div className="mt-8 pt-6 border-t border-slate-200 dark:border-[#2d2d44] flex items-center justify-center gap-2">
          <span className="material-symbols-outlined text-slate-400 text-lg">info</span>
          <p className="text-slate-500 dark:text-slate-400 text-[11px] uppercase tracking-wider font-semibold">
            You can add more team members after setup
          </p>
        </div>
      </div>

      {/* Background Pattern */}
      <div className="fixed inset-0 -z-10 opacity-20 pointer-events-none overflow-hidden">
        <div className="absolute -top-[10%] -left-[10%] w-[40%] h-[40%] bg-primary rounded-full blur-[120px]" />
        <div className="absolute -bottom-[10%] -right-[10%] w-[40%] h-[40%] bg-accent-green/30 rounded-full blur-[120px]" />
      </div>
    </div>
  )
}
